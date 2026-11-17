import asyncio

import pytest
from langgraph.store.memory import InMemoryStore

from parley.memory.users import create_user, get_user, normalize


def test_normalize_lowercases_and_dashes_spaces() -> None:
    assert normalize("  John Doe  ") == "john-doe"


def test_create_user_is_idempotent() -> None:
    async def scenario() -> tuple[dict, dict]:
        store = InMemoryStore()
        first = await create_user(store, "John Doe")
        second = await create_user(store, "john doe")
        return first, second

    first, second = asyncio.run(scenario())
    assert first["user_id"] == "john-doe"
    assert first["pseudo"] == "John Doe"
    assert second["created_at"] == first["created_at"]


def test_create_user_rejects_invalid_pseudo() -> None:
    async def scenario() -> None:
        store = InMemoryStore()
        await create_user(store, "a@b!")

    with pytest.raises(ValueError):
        asyncio.run(scenario())


def test_get_user_roundtrip_and_missing() -> None:
    async def scenario() -> tuple[dict | None, dict | None]:
        store = InMemoryStore()
        await create_user(store, "alice")
        return await get_user(store, "alice"), await get_user(store, "ghost")

    found, missing = asyncio.run(scenario())
    assert found is not None and found["user_id"] == "alice"
    assert missing is None
