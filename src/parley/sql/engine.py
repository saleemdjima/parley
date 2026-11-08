import logging
import threading

import duckdb

from parley.config import settings

logger = logging.getLogger(__name__)

connection_lock = threading.Lock()
connection: duckdb.DuckDBPyConnection | None = None


def get_connection() -> duckdb.DuckDBPyConnection:
    global connection
    if connection is not None:
        return connection
    with connection_lock:
        if connection is not None:
            return connection
        con = duckdb.connect()
        try:
            con.execute("INSTALL httpfs; LOAD httpfs;")
            con.execute("SET enable_object_cache=true;")
        except duckdb.Error as exc:
            logger.warning("duckdb httpfs setup failed: %s", exc)
        connection = con
        logger.debug("duckdb connection initialized (httpfs + object cache)")
        return connection


def execute(sql: str, params: list) -> list[dict]:
    logger.debug("execute sql=%s params=%s", sql, params)
    cursor = get_connection().cursor()
    cursor.execute(sql, params)
    columns = [d[0] for d in cursor.description]
    rows = [
        dict(zip(columns, row, strict=False))
        for row in cursor.fetchmany(settings.max_limit)
    ]
    logger.debug("execute returned rows=%d", len(rows))
    return rows
