import logging

from parley.config import settings
from parley.engines.base import Engine

logger = logging.getLogger(__name__)


def get_engine() -> Engine:
    name = settings.engine.lower()
    logger.debug("get_engine engine=%s", name)
    if name == "clickhouse":
        from parley.engines.clickhouse_engine import ClickHouseEngine

        return ClickHouseEngine()
    from parley.engines.duckdb_engine import DuckDBEngine

    return DuckDBEngine()


__all__ = ["Engine", "get_engine"]
