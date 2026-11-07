import logging

import duckdb

from parley.config import settings

logger = logging.getLogger(__name__)


def execute(sql: str, params: list) -> list[dict]:
    con = duckdb.connect()
    logger.debug("execute sql=%s params=%s", sql, params)
    cursor = con.execute(sql, params)
    columns = [d[0] for d in cursor.description]

    rows = [
        dict(zip(columns, row, strict=False))
        for row in cursor.fetchmany(settings.max_limit)
    ]
    con.close()
    logger.debug("execute returned rows=%d", len(rows))
    return rows
