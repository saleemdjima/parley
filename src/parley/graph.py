import asyncio
import logging
import time
import uuid
from collections.abc import AsyncIterator
from typing import Annotated, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.store.base import BaseStore

from parley import llm
from parley.domains.taxi import TAXI_METRICS
from parley.engines import get_engine
from parley.memory.conversations import record_turn
from parley.metrics import QueryMetrics, track
from parley.prompts import render_system_prompt
from parley.sql.builder import build_query
from parley.sql.catalog import get_catalog
from parley.sql.intent import extract_intent
from parley.sql.router import Route, route
from parley.verify import judge

logger = logging.getLogger(__name__)

PERSONA = """You are a friendly, sharp data analyst. Don't just state the number: say what
it means in plain language, add a short bit of context or a natural next step, and keep a
warm, conversational tone. Be concise but never clipped. Always reply in the same language
as the user's question."""

RAG_PROMPT = """Answer the question using ONLY the documentation context below. If the
answer is not in the context, say you don't know.

Context:
{context}

Question: {question}
Answer:"""

MERGE_PROMPT = """Answer the question using BOTH sources below: the computed result and
the documentation context.

Result rows: {rows}

Documentation context:
{context}

Question: {question}
Answer:"""

CLARIFY_PROMPT = """The user said: "{question}"
This isn't a clear data question - it may be a greeting, too vague, or off-topic. Reply
briefly and warmly, and gently point them toward something you can actually help with."""

SQL_ANSWER_PROMPT = """The user asked: "{question}"
The query returned these rows: {rows}
Explain the finding in natural, friendly language using those numbers. Round sensibly
(money to cents). State only what the rows support: do not assert a time period, location,
or any other filter that is not reflected in the query. If there are several rows,
summarize the key finding."""

CONTEXTUALIZE_PROMPT = """Rewrite the user's latest message into a single standalone
question understandable without the conversation. Stay faithful; do not answer it. If it
is already standalone, return it unchanged. Return only the question.

Summary of earlier conversation:
{summary}

Recent turns:
{history}

Latest message: {question}
Standalone question:"""

MEMORY_EXTRACT_PROMPT = """From the exchange below, extract ONE durable fact worth
remembering about this user for future conversations (a stable preference, context, or
goal - not a one-off data value). If there is nothing worth remembering, reply exactly
NONE.

User: {question}
Assistant: {answer}
Fact:"""

SUMMARY_PROMPT = """Update the running summary of a conversation with the new turns below.
Keep it concise (a few sentences), capturing facts, entities and the user's intent that
later turns may refer back to.

Existing summary:
{summary}

New turns:
{turns}

Updated summary:"""

RECENT_TURNS = 4
COMPACT_AFTER = 8
RECALL_LIMIT = 10


def current_system_prompt() -> str:
    # Rendered from the catalog so the agent describes whatever dataset it's pointed at.
    try:
        catalog = get_catalog()
        coverage, total_rows = catalog.coverage(), catalog.total_rows
    except Exception:
        logger.warning("system prompt: catalog unavailable", exc_info=True)
        coverage, total_rows = "unknown", 0
    examples = list(TAXI_METRICS.descriptions.values())
    return render_system_prompt(coverage, total_rows, examples)


def reduce_history(existing: list | None, update: object) -> list:
    # Turns normally append; {"replace": [...]} overwrites, which is how compact_node
    # trims old turns (a plain append-only reducer could never shrink the list).
    if isinstance(update, dict) and "replace" in update:
        return list(update["replace"])
    rhs = update if isinstance(update, list) else []
    return (existing or []) + rhs


class AgentState(TypedDict, total=False):
    question: str
    original_question: str
    route: str
    reasoning: str
    sql: str
    params: list
    rows: list
    context: str
    answer: str
    verified: bool
    memories: str
    summary: str
    history: Annotated[list, reduce_history]


def config_value(config: RunnableConfig | None, key: str) -> str:
    if not config:
        return ""
    return (config.get("configurable") or {}).get(key) or ""


def format_history(history: list, limit: int = RECENT_TURNS) -> str:
    lines: list[str] = []
    for turn in history[-limit:]:
        lines.append(f"User: {turn.get('question', '')}")
        lines.append(f"Assistant: {turn.get('answer', '')}")
    return "\n".join(lines)


def preamble(state: AgentState) -> str:
    parts = [PERSONA, current_system_prompt()]
    memories = state.get("memories")
    if memories:
        parts.append(f"What you remember about this user:\n{memories}")
    return "\n\n".join(parts)


def contextualize_node(state: AgentState) -> AgentState:
    original = state["question"]
    history = state.get("history") or []
    summary = state.get("summary") or ""
    if not history and not summary:
        return {"original_question": original}
    standalone = llm.classify(
        CONTEXTUALIZE_PROMPT.format(
            summary=summary or "(none)",
            history=format_history(history),
            question=original,
        )
    ).strip()
    logger.debug("contextualize_node %r -> %r", original, standalone)
    return {"original_question": original, "question": standalone or original}


async def recall_node(
    state: AgentState, config: RunnableConfig, *, store: BaseStore | None = None
) -> AgentState:
    user_id = config_value(config, "user_id")
    if store is None or not user_id:
        return {}
    items = await store.asearch((user_id, "memories"), limit=RECALL_LIMIT)
    if not items:
        return {}
    memories = "\n".join(f"- {item.value.get('text', '')}" for item in items)
    logger.debug("recall_node user=%s memories=%d", user_id, len(items))
    return {"memories": memories}


def classify_node(state: AgentState) -> AgentState:
    decision = route(state["question"])
    logger.debug("classify_node -> %s", decision.route)
    return {"route": decision.route.value, "reasoning": decision.reasoning}


def sql_node(state: AgentState) -> AgentState:
    engine = get_engine()
    catalog = get_catalog()
    intent = extract_intent(
        state["question"], catalog.column_names(), catalog.coverage(), TAXI_METRICS
    )
    sql, params = build_query(intent, catalog.columns, engine, TAXI_METRICS)
    rows = engine.execute(sql, params)
    logger.debug("sql_node engine=%s rows=%d", engine.name, len(rows))
    result: AgentState = {"sql": sql, "params": params, "rows": rows}
    # Turn the rows into a sentence for the pure-sql route.
    if state.get("route") != Route.hybrid.value:
        result["answer"] = llm.answer(
            preamble(state)
            + "\n\n"
            + SQL_ANSWER_PROMPT.format(question=state["question"], rows=rows)
        )
    return result


def rag_node(state: AgentState) -> AgentState:
    # Imported lazily so the SQL path runs without the rag module / Chroma index.
    from parley.rag.retriever import format_context, retrieve

    docs = retrieve(state["question"])
    context = format_context(docs)
    answer = llm.answer(
        preamble(state)
        + "\n\n"
        + RAG_PROMPT.format(context=context, question=state["question"])
    )
    logger.debug("rag_node chunks=%d", len(docs))
    return {"context": context, "answer": answer}


def merge_node(state: AgentState) -> AgentState:
    answer = llm.answer(
        preamble(state)
        + "\n\n"
        + MERGE_PROMPT.format(
            question=state["question"],
            rows=state.get("rows"),
            context=state.get("context"),
        )
    )
    logger.debug("merge_node")
    return {"answer": answer}


def clarify_node(state: AgentState) -> AgentState:
    prompt = preamble(state) + "\n\n" + CLARIFY_PROMPT.format(question=state["question"])
    answer = llm.answer(prompt)
    logger.debug("clarify_node")
    return {"answer": answer}


def evidence_for(state: AgentState) -> str:
    # The ground truth the judge checks against.
    parts: list[str] = []
    sql = state.get("sql")
    if sql:
        parts.append(f"SQL query: {sql}")
    rows = state.get("rows")
    if rows:
        parts.append(f"Result rows: {rows}")
    context = state.get("context")
    if context:
        parts.append(f"Documentation:\n{context}")
    return "\n\n".join(parts)


def verify_node(state: AgentState) -> AgentState:
    # Every route terminates here, so no answer reaches the user unchecked.
    answer = state.get("answer") or ""
    if state.get("route") == Route.clarify.value:
        return {"verified": True}
    if not answer.strip():
        logger.warning("verify_node empty answer route=%s", state.get("route"))
        return {"answer": SAFE_ERROR_ANSWER, "verified": False}
    evidence = evidence_for(state)
    if not evidence:
        return {"verified": True}
    verdict = judge(state["question"], answer, evidence)
    return {"answer": verdict.answer, "verified": verdict.supported}


async def remember_node(
    state: AgentState, config: RunnableConfig, *, store: BaseStore | None = None
) -> AgentState:
    question = state.get("original_question") or state.get("question", "")
    answer = state.get("answer", "")
    turn = {"question": question, "answer": answer}
    user_id = config_value(config, "user_id")
    thread_id = config_value(config, "thread_id")
    if store is not None and user_id:
        if thread_id:
            await record_turn(store, user_id, thread_id, question)
        fact = llm.answer(
            MEMORY_EXTRACT_PROMPT.format(question=question, answer=answer)
        ).strip()
        if fact and fact.upper() != "NONE":
            await store.aput((user_id, "memories"), str(uuid.uuid4()), {"text": fact})
            logger.debug("remember_node stored fact user=%s", user_id)
    return {"history": [turn]}


def compact_node(state: AgentState) -> AgentState:
    history = state.get("history") or []
    if len(history) <= COMPACT_AFTER:
        return {}
    kept = history[-RECENT_TURNS:]
    older = history[:-RECENT_TURNS]
    summary = llm.answer(
        SUMMARY_PROMPT.format(
            summary=state.get("summary") or "(none)",
            turns=format_history(older, limit=len(older)),
        )
    ).strip()
    logger.debug("compact_node summarized=%d kept=%d", len(older), len(kept))
    return {"summary": summary, "history": {"replace": kept}}


def route_from_classify(state: AgentState) -> list[str] | str:
    # Hybrid fans out to sql and rag in parallel (one LangGraph superstep)
    decision = state["route"]
    if decision == Route.hybrid.value:
        return ["sql", "rag"]
    if decision == Route.rag.value:
        return "rag"
    if decision == Route.clarify.value:
        return "clarify"
    return "sql"


def after_data(state: AgentState) -> str:
    return "merge" if state["route"] == Route.hybrid.value else "verify"


def build_graph(
    checkpointer: BaseCheckpointSaver | None = None,
    store: BaseStore | None = None,
) -> CompiledStateGraph:
    graph = StateGraph(AgentState)
    graph.add_node("contextualize", contextualize_node)
    graph.add_node("recall", recall_node)
    graph.add_node("classify", classify_node)
    graph.add_node("sql", sql_node)
    graph.add_node("rag", rag_node)
    graph.add_node("merge", merge_node)
    graph.add_node("clarify", clarify_node)
    graph.add_node("verify", verify_node)
    graph.add_node("remember", remember_node)
    graph.add_node("compact", compact_node)

    graph.add_edge(START, "contextualize")
    graph.add_edge("contextualize", "recall")
    graph.add_edge("recall", "classify")
    graph.add_conditional_edges(
        "classify", route_from_classify, ["sql", "rag", "clarify"]
    )
    graph.add_conditional_edges("sql", after_data, {"merge": "merge", "verify": "verify"})
    graph.add_conditional_edges("rag", after_data, {"merge": "merge", "verify": "verify"})
    graph.add_edge("merge", "verify")
    graph.add_edge("clarify", "verify")
    graph.add_edge("verify", "remember")
    graph.add_edge("remember", "compact")
    graph.add_edge("compact", END)
    return graph.compile(checkpointer=checkpointer, store=store)


# The default graph is stateless (CLI/tests). The API lifespan recompiles a second graph
# with a live checkpointer + store and registers it here, so threaded calls persist.
agent_graph = build_graph()
stateful_graph: CompiledStateGraph | None = None


def set_stateful_graph(checkpointer: BaseCheckpointSaver, store: BaseStore) -> None:
    global stateful_graph
    stateful_graph = build_graph(checkpointer, store)


def graph_for(thread_id: str | None) -> CompiledStateGraph:
    if thread_id and stateful_graph is not None:
        return stateful_graph
    return agent_graph


async def get_history(thread_id: str, user_id: str | None = None) -> list:
    if stateful_graph is None:
        return []
    config: RunnableConfig = {
        "configurable": {"thread_id": thread_id, "user_id": user_id or ""}
    }
    snapshot = await stateful_graph.aget_state(config)
    return snapshot.values.get("history", []) if snapshot else []


SAFE_ERROR_ANSWER = "Sorry, I could not answer that right now. Please try rephrasing."


def metrics_dict(metrics: QueryMetrics) -> dict:
    data = {
        "input_tokens": metrics.input_tokens,
        "output_tokens": metrics.output_tokens,
        "cost_usd": round(metrics.cost_usd, 6),
        "latency_s": round(metrics.latency_s, 3),
    }
    if metrics.first_response_s is not None:
        data["first_response_s"] = round(metrics.first_response_s, 3)
    return data


def build_result(state: dict, usage: dict) -> dict:
    return {
        "route": state.get("route", ""),
        "reasoning": state.get("reasoning"),
        "sql": state.get("sql"),
        "params": state.get("params"),
        "rows": state.get("rows"),
        "context": state.get("context"),
        "answer": state.get("answer"),
        "verified": state.get("verified"),
        "metrics": usage,
    }


def error_result(usage: dict) -> dict:
    return {
        "route": "error",
        "reasoning": None,
        "sql": None,
        "params": None,
        "rows": None,
        "context": None,
        "answer": SAFE_ERROR_ANSWER,
        "verified": False,
        "metrics": usage,
    }


def run(question: str) -> dict:
    # Sync entry point (CLI). Drives the async path so the async memory nodes work.
    async def collect() -> dict:
        result: dict = {}
        async for event in astream_run(question):
            if event["kind"] == "result":
                result = event["result"]
        return result

    return asyncio.run(collect())


async def astream_run(
    question: str, thread_id: str | None = None, user_id: str | None = None
) -> AsyncIterator[dict]:
    # Yields a "step" event per node as it finishes, then one "result" event.
    # thread_id (with a checkpointer registered) persists state across turns;
    # user_id scopes long-term memory in the store.
    merged: dict = {}
    failed = False
    graph = graph_for(thread_id)
    config: RunnableConfig | None = None
    if thread_id and graph is stateful_graph:
        config = {"configurable": {"thread_id": thread_id, "user_id": user_id or ""}}
    with track() as metrics:
        start = time.monotonic()
        try:
            async for update in graph.astream(
                {"question": question}, config=config, stream_mode="updates"
            ):
                for node, delta in update.items():
                    if metrics.first_response_s is None:
                        metrics.first_response_s = time.monotonic() - start
                    if delta:
                        merged.update(delta)
                    yield {"kind": "step", "node": node, "state": dict(merged)}
        except Exception:
            logger.exception("astream_run failed question=%r", question)
            failed = True
    usage = metrics_dict(metrics)
    logger.debug(
        "astream_run question=%r route=%s metrics=%s",
        question,
        merged.get("route"),
        usage,
    )
    result = error_result(usage) if failed else build_result(merged, usage)
    yield {"kind": "result", "result": result}
