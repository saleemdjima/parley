import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from langgraph.store.base import BaseStore

from parley.config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def open_store() -> AsyncGenerator[BaseStore]:
    if settings.database_url:
        async with open_postgres_store() as store:
            yield store
    else:
        from langgraph.store.memory import InMemoryStore

        logger.debug("store=memory")
        yield InMemoryStore()


@asynccontextmanager
async def open_postgres_store() -> AsyncGenerator[BaseStore]:
    from langgraph.store.postgres.aio import AsyncPostgresStore
    from psycopg.rows import dict_row
    from psycopg_pool import AsyncConnectionPool

    kwargs = {"autocommit": True, "prepare_threshold": None, "row_factory": dict_row}
    async with AsyncConnectionPool(
        conninfo=settings.database_url, kwargs=kwargs, open=False
    ) as pool:
        await pool.open()
        store = AsyncPostgresStore(pool)
        await store.setup()
        logger.debug("store=postgres")
        yield store
