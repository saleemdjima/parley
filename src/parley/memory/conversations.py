import logging
from datetime import UTC, datetime

from langgraph.store.base import BaseStore

logger = logging.getLogger(__name__)

CONVERSATIONS = "conversations"
TITLE_LIMIT = 60


def namespace(user_id: str) -> tuple[str, str]:
    return (user_id, CONVERSATIONS)


def title_from(question: str) -> str:
    first_line = question.strip().splitlines()[0] if question.strip() else ""
    return (first_line[:TITLE_LIMIT] or "New conversation").strip()


async def record_turn(
    store: BaseStore, user_id: str, thread_id: str, question: str
) -> None:
    now = datetime.now(UTC).isoformat()
    existing = await store.aget(namespace(user_id), thread_id)
    if existing is None:
        value = {"title": title_from(question), "created_at": now}
    else:
        value = dict(existing.value)
    value["updated_at"] = now
    value["last_question"] = question
    await store.aput(namespace(user_id), thread_id, value)
    logger.debug("record_turn user=%s thread=%s", user_id, thread_id)


async def list_conversations(store: BaseStore, user_id: str) -> list[dict]:
    items = await store.asearch(namespace(user_id))
    convos = [{"thread_id": item.key, **item.value} for item in items]
    convos.sort(key=lambda c: c.get("updated_at", ""), reverse=True)
    logger.debug("list_conversations user=%s count=%d", user_id, len(convos))
    return convos
