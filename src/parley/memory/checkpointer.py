import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, cast

from langgraph.checkpoint.base import BaseCheckpointSaver

from parley.config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def open_checkpointer() -> AsyncGenerator[BaseCheckpointSaver]:
    if settings.database_url:
        async with open_postgres() as saver:
            yield saver
    else:
        async with open_sqlite() as saver:
            yield saver


@asynccontextmanager
async def open_postgres() -> AsyncGenerator[BaseCheckpointSaver]:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from psycopg import AsyncConnection
    from psycopg.rows import dict_row
    from psycopg_pool import AsyncConnectionPool

    # prepare_threshold=None disables server-side prepared statements, which the Neon
    # pooled endpoint (PgBouncer, transaction mode) cannot keep across pooled sessions.
    kwargs = {"autocommit": True, "prepare_threshold": None, "row_factory": dict_row}
    async with AsyncConnectionPool(
        conninfo=settings.database_url, kwargs=kwargs, open=False
    ) as pool:
        await pool.open()
        saver = AsyncPostgresSaver(
            cast(AsyncConnectionPool[AsyncConnection[dict[str, Any]]], pool)
        )
        await saver.setup()
        logger.debug("checkpointer=postgres")
        yield saver


@asynccontextmanager
async def open_sqlite() -> AsyncGenerator[BaseCheckpointSaver]:
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    Path(settings.sqlite_path).parent.mkdir(parents=True, exist_ok=True)
    async with AsyncSqliteSaver.from_conn_string(settings.sqlite_path) as saver:
        logger.debug("checkpointer=sqlite path=%s", settings.sqlite_path)
        yield saver
