import asyncio
from unittest.mock import patch

from langgraph.store.memory import InMemoryStore

from parley.graph import (
    ReplaceHistory,
    contextualize_node,
    recall_node,
    reduce_history,
)
from parley.memory.conversations import list_conversations, record_turn, title_from


def test_reduce_history_appends() -> None:
    assert reduce_history([{"q": 1}], [{"q": 2}]) == [{"q": 1}, {"q": 2}]


def test_reduce_history_replace_trims() -> None:
    out = reduce_history([{"q": 1}, {"q": 2}, {"q": 3}], ReplaceHistory([{"q": 3}]))
    assert out == [{"q": 3}]


def test_title_from_truncates_and_defaults() -> None:
    assert title_from("  How many trips in 2024?  ") == "How many trips in 2024?"
    assert title_from("") == "New conversation"


def test_contextualize_passthrough_without_history() -> None:
    out = contextualize_node({"question": "how many trips?"})
    assert out == {"original_question": "how many trips?"}


def test_contextualize_rewrites_followup() -> None:
    state = {
        "question": "what about February?",
        "history": [{"question": "trips in January?", "answer": "100k"}],
    }
    with patch("parley.graph.llm.classify", return_value="How many trips in February?"):
        out = contextualize_node(state)
    assert out["original_question"] == "what about February?"
    assert out["question"] == "How many trips in February?"


def test_conversations_roundtrip() -> None:
    async def scenario() -> list[dict]:
        store = InMemoryStore()
        await record_turn(store, "u1", "t1", "trips in January?")
        await record_turn(store, "u1", "t2", "average fare?")
        return await list_conversations(store, "u1")

    convos = asyncio.run(scenario())
    assert {c["thread_id"] for c in convos} == {"t1", "t2"}
    assert all("title" in c for c in convos)


def test_recall_reads_user_memories() -> None:
    async def scenario() -> dict:
        store = InMemoryStore()
        await store.aput(("u1", "memories"), "m1", {"text": "prefers euros"})
        config = {"configurable": {"user_id": "u1"}}
        return await recall_node({"question": "q"}, config, store=store)

    out = asyncio.run(scenario())
    assert "prefers euros" in out["memories"]


def test_recall_noop_without_store() -> None:
    config = {"configurable": {"user_id": "u1"}}
    out = asyncio.run(recall_node({"question": "q"}, config, store=None))
    assert out == {}
