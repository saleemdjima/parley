import asyncio
import logging
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from parley import llm
from parley.domains.taxi import TAXI_METRICS
from parley.engines import get_engine
from parley.metrics import QueryMetrics, track
from parley.sql.builder import build_query
from parley.sql.intent import extract_intent
from parley.sql.router import Route, route

logger = logging.getLogger(__name__)

RAG_PROMPT = """Answer the question using ONLY the NYC TLC documentation context
below. If the answer is not in the context, say you don't know. Name the field or
code you are explaining.

Context:
{context}

Question: {question}
Answer:"""

MERGE_PROMPT = """Answer the question using BOTH sources below: the computed query
result and the documentation context.

Query result rows: {rows}

Documentation context:
{context}

Question: {question}
Answer:"""


class AgentState(TypedDict, total=False):
    question: str
    route: str
    sql: str
    params: list
    rows: list
    context: str
    answer: str


def classify_node(state: AgentState) -> AgentState:
    decision = route(state["question"])
    logger.debug("classify_node -> %s", decision)
    return {"route": decision.value}


def sql_node(state: AgentState) -> AgentState:
    engine = get_engine()
    catalog = engine.catalog()
    intent = extract_intent(state["question"], list(catalog.keys()))
    sql, params = build_query(intent, catalog, engine, TAXI_METRICS)
    rows = engine.execute(sql, params)
    logger.debug("sql_node engine=%s rows=%d", engine.name, len(rows))
    return {"sql": sql, "params": params, "rows": rows}


def rag_node(state: AgentState) -> AgentState:
    # Imported lazily so the SQL path runs without the rag module / Chroma index.
    from parley.rag.retriever import format_context, retrieve

    docs = retrieve(state["question"])
    context = format_context(docs)
    answer = llm.answer(RAG_PROMPT.format(context=context, question=state["question"]))
    logger.debug("rag_node chunks=%d", len(docs))
    return {"context": context, "answer": answer}


def merge_node(state: AgentState) -> AgentState:
    answer = llm.answer(
        MERGE_PROMPT.format(
            question=state["question"],
            rows=state.get("rows"),
            context=state.get("context"),
        )
    )
    logger.debug("merge_node")
    return {"answer": answer}


def from_classify(state: AgentState) -> str:
    return state["route"]


def after_sql(state: AgentState) -> str:
    return "rag" if state["route"] == Route.hybrid.value else "end"


def after_rag(state: AgentState) -> str:
    return "merge" if state["route"] == Route.hybrid.value else "end"


def build_graph() -> CompiledStateGraph:
    graph = StateGraph(AgentState)
    graph.add_node("classify", classify_node)
    graph.add_node("sql", sql_node)
    graph.add_node("rag", rag_node)
    graph.add_node("merge", merge_node)

    graph.add_edge(START, "classify")
    graph.add_conditional_edges(
        "classify", from_classify, {"sql": "sql", "rag": "rag", "hybrid": "sql"}
    )
    graph.add_conditional_edges("sql", after_sql, {"rag": "rag", "end": END})
    graph.add_conditional_edges("rag", after_rag, {"merge": "merge", "end": END})
    graph.add_edge("merge", END)
    return graph.compile()


agent_graph = build_graph()


SAFE_ERROR_ANSWER = "Sorry, I could not answer that right now. Please try rephrasing."


def metrics_dict(metrics: QueryMetrics) -> dict:
    return {
        "input_tokens": metrics.input_tokens,
        "output_tokens": metrics.output_tokens,
        "cost_usd": round(metrics.cost_usd, 6),
        "latency_s": round(metrics.latency_s, 3),
    }


async def arun(question: str) -> dict:
    with track() as metrics:
        try:
            state: AgentState = {"question": question}
            decision = await asyncio.to_thread(route, question)
            state["route"] = decision.value

            if decision == Route.hybrid:
                sql_part, rag_part = await asyncio.gather(
                    asyncio.to_thread(sql_node, state),
                    asyncio.to_thread(rag_node, state),
                )
                state.update(sql_part)
                state.update(rag_part)
                state.update(await asyncio.to_thread(merge_node, state))
            elif decision == Route.sql:
                state.update(await asyncio.to_thread(sql_node, state))
            else:
                state.update(await asyncio.to_thread(rag_node, state))
        except Exception:
            logger.exception("arun failed question=%r", question)
            return {
                "route": "error",
                "sql": None,
                "params": None,
                "rows": None,
                "context": None,
                "answer": SAFE_ERROR_ANSWER,
                "metrics": metrics_dict(metrics),
            }

    usage = metrics_dict(metrics)
    logger.debug("arun question=%r route=%s metrics=%s", question, state["route"], usage)
    return {
        "route": state.get("route", ""),
        "sql": state.get("sql"),
        "params": state.get("params"),
        "rows": state.get("rows"),
        "context": state.get("context"),
        "answer": state.get("answer"),
        "metrics": usage,
    }


def run(question: str) -> dict:
    failed = False
    state: dict = {}
    with track() as metrics:
        try:
            state = agent_graph.invoke({"question": question})
        except Exception:
            logger.exception("run failed question=%r", question)
            failed = True

    usage = metrics_dict(metrics)
    if failed:
        return {
            "route": "error",
            "sql": None,
            "params": None,
            "rows": None,
            "context": None,
            "answer": SAFE_ERROR_ANSWER,
            "metrics": usage,
        }
    logger.debug(
        "run question=%r route=%s metrics=%s", question, state.get("route"), usage
    )
    return {
        "route": state.get("route", ""),
        "sql": state.get("sql"),
        "params": state.get("params"),
        "rows": state.get("rows"),
        "context": state.get("context"),
        "answer": state.get("answer"),
        "metrics": usage,
    }
