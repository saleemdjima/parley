import logging

import duckdb

from parley.config import settings

logger = logging.getLogger(__name__)


def parquet_paths() -> list[str]:
    return [p.strip() for p in settings.parquet_path.split(",") if p.strip()]


def source_expr() -> str:
    paths = parquet_paths()
    if len(paths) == 1:
        return f"read_parquet('{paths[0]}')"
    listed = ", ".join(f"'{p}'" for p in paths)
    return f"read_parquet([{listed}])"


def build_catalog(con: duckdb.DuckDBPyConnection | None = None) -> dict[str, str]:
    owns = con is None
    con = con or duckdb.connect()
    rows = con.execute(f"DESCRIBE SELECT * FROM {source_expr()}").fetchall()
    catalog = {row[0]: row[1] for row in rows}
    logger.debug("build_catalog columns=%d", len(catalog))
    if owns:
        con.close()
    return catalog
