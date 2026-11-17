import logging
import re
from datetime import UTC, datetime

from langgraph.store.base import BaseStore

logger = logging.getLogger(__name__)

USERS = "users"
HANDLE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{1,31}$")


def namespace() -> tuple[str, ...]:
    return (USERS,)


def normalize(pseudo: str) -> str:
    return "-".join(pseudo.strip().lower().split())


async def create_user(store: BaseStore, pseudo: str) -> dict:
    user_id = normalize(pseudo)
    if not HANDLE_PATTERN.match(user_id):
        raise ValueError(
            "Pseudo must be 2-32 chars: letters, digits, spaces, '-' or '_'."
        )
    existing = await store.aget(namespace(), user_id)
    if existing is not None:
        logger.debug("create_user existing user=%s", user_id)
        return dict(existing.value)
    profile = {
        "user_id": user_id,
        "pseudo": pseudo.strip(),
        "created_at": datetime.now(UTC).isoformat(),
    }
    await store.aput(namespace(), user_id, profile)
    logger.debug("create_user new user=%s", user_id)
    return profile


async def get_user(store: BaseStore, user_id: str) -> dict | None:
    item = await store.aget(namespace(), user_id)
    return dict(item.value) if item is not None else None
