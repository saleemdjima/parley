import logging

from parley.config import settings

logger = logging.getLogger(__name__)


class ClickHouseEngine:
    name = "clickhouse"

    def connection(self):
        import clickhouse_connect.dbapi

        return clickhouse_connect.dbapi.connect(
            host=settings.clickhouse_host,
            port=settings.clickhouse_port,
            username=settings.clickhouse_user,
            password=settings.clickhouse_password,
            database=settings.clickhouse_database,
        )

    def source_expr(self) -> str:
        return settings.clickhouse_table

    def placeholder(self, index: int) -> str:
        # clickhouse-connect's DB-API escapes params client-side with %s, like
        # psycopg. VERIFY the paramstyle on your installed version if binding fails.
        return "%s"

    def catalog(self) -> dict[str, str]:
        connection = self.connection()
        cursor = connection.cursor()
        cursor.execute(f"DESCRIBE TABLE {settings.clickhouse_table}")
        catalog = {row[0]: row[1] for row in cursor.fetchall()}
        cursor.close()
        connection.close()
        logger.debug("clickhouse catalog columns=%d", len(catalog))
        return catalog

    def execute(self, sql: str, params: list) -> list[dict]:
        connection = self.connection()
        cursor = connection.cursor()
        logger.debug("clickhouse execute sql=%s params=%s", sql, params)
        cursor.execute(sql, params)
        columns = [desc[0] for desc in cursor.description]
        # Hard result cap (defense in depth), matching the DuckDB engine.
        rows = [
            dict(zip(columns, row, strict=False))
            for row in cursor.fetchmany(settings.max_limit)
        ]
        cursor.close()
        connection.close()
        logger.debug("clickhouse returned rows=%d", len(rows))
        return rows
