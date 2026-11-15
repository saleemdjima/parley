import logging
import time
from collections.abc import AsyncIterator
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from parley import llm
from parley.domains.taxi import TAXI_METRICS
from parley.engines import get_engine
from parley.metrics import QueryMetrics, track
from parley.prompts import render_system_prompt
from parley.sql.builder import build_query
from parley.sql.catalog import get_catalog
from parley.sql.intent import extract_intent
from parley.sql.router import Route, route
from parley.verify import judge

logger = logging.getLogger(__name__)

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
Answer the question in one natural sentence using those numbers. Round sensibly (money
to cents). If there are several rows, summarize the key finding."""


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


class AgentState(TypedDict, total=False):
    question: str
    route: str
    sql: str
    params: list
    rows: list
    context: str
    answer: str
    verified: bool


def classify_node(state: AgentState) -> AgentState:
    decision = route(state["question"])
    logger.debug("classify_node -> %s", decision)
    return {"route": decision.value}


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
            current_system_prompt()
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
        current_system_prompt()
        + "\n\n"
        + RAG_PROMPT.format(context=context, question=state["question"])
    )
    logger.debug("rag_node chunks=%d", len(docs))
    return {"context": context, "answer": answer}


def merge_node(state: AgentState) -> AgentState:
    answer = llm.answer(
        current_system_prompt()
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
    prompt = (
        current_system_prompt()
        + "\n\n"
        + CLARIFY_PROMPT.format(question=state["question"])
    )
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


def build_graph() -> CompiledStateGraph:
    graph = StateGraph(AgentState)
    graph.add_node("classify", classify_node)
    graph.add_node("sql", sql_node)
    graph.add_node("rag", rag_node)
    graph.add_node("merge", merge_node)
    graph.add_node("clarify", clarify_node)
    graph.add_node("verify", verify_node)

    graph.add_edge(START, "classify")
    graph.add_conditional_edges(
        "classify", route_from_classify, ["sql", "rag", "clarify"]
    )
    graph.add_conditional_edges("sql", after_data, {"merge": "merge", "verify": "verify"})
    graph.add_conditional_edges("rag", after_data, {"merge": "merge", "verify": "verify"})
    graph.add_edge("merge", "verify")
    graph.add_edge("clarify", "verify")
    graph.add_edge("verify", END)
    return graph.compile()


agent_graph = build_graph()


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
        "sql": None,
        "params": None,
        "rows": None,
        "context": None,
        "answer": SAFE_ERROR_ANSWER,
        "verified": False,
        "metrics": usage,
    }


def run(question: str) -> dict:
    # Sync entry point (CLI).
    with track() as metrics:
        try:
            state = agent_graph.invoke({"question": question})
        except Exception:
            logger.exception("run failed question=%r", question)
            return error_result(metrics_dict(metrics))
    usage = metrics_dict(metrics)
    logger.debug(
        "run question=%r route=%s metrics=%s", question, state.get("route"), usage
    )
    return build_result(state, usage)


async def astream_run(question: str) -> AsyncIterator[dict]:
    # Yields a "step" event per node as it finishes, then one "result" event.
    merged: dict = {}
    failed = False
    with track() as metrics:
        start = time.monotonic()
        try:
            async for update in agent_graph.astream(
                {"question": question}, stream_mode="updates"
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
