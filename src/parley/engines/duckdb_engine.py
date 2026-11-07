import logging

from parley.sql import catalog as duckdb_catalog
from parley.sql.engine import execute as duckdb_execute

logger = logging.getLogger(__name__)


class DuckDBEngine:
    name = "duckdb"

    def source_expr(self) -> str:
        return duckdb_catalog.source_expr()

    def placeholder(self, index: int) -> str:
        return "?"

    def catalog(self) -> dict[str, str]:
        return duckdb_catalog.build_catalog()

    def execute(self, sql: str, params: list) -> list[dict]:
        return duckdb_execute(sql, params)
