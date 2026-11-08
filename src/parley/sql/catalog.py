import logging
import re
import threading
from dataclasses import dataclass

import duckdb

from parley.config import settings
from parley.sql.engine import get_connection

logger = logging.getLogger(__name__)

PERIOD_RE = re.compile(r"(\d{4})-(\d{2})")
YEAR_RE = re.compile(r"(\d{4})")


def parquet_paths() -> list[str]:
    return [p.strip() for p in settings.parquet_path.split(",") if p.strip()]


def source_expr() -> str:
    paths = parquet_paths()
    if len(paths) == 1:
        return f"read_parquet('{paths[0]}')"
    listed = ", ".join(f"'{p}'" for p in paths)
    return f"read_parquet([{listed}], union_by_name=true)"


@dataclass(frozen=True)
class SourceInfo:
    path: str
    label: str
    year: int | None
    columns: dict[str, str]
    row_count: int


@dataclass(frozen=True)
class Catalog:
    sources: list[SourceInfo]
    columns: dict[str, str]
    all_columns: dict[str, str]
    total_rows: int
    year_min: int | None
    year_max: int | None

    def column_names(self) -> list[str]:
        return list(self.columns.keys())

    def coverage(self) -> str:
        if self.year_min is None or self.year_max is None:
            return "unknown"
        if self.year_min == self.year_max:
            return str(self.year_min)
        return f"{self.year_min}-{self.year_max}"


catalog_lock = threading.Lock()
cached_catalog: Catalog | None = None


def parse_period(path: str) -> tuple[str, int | None]:
    period = PERIOD_RE.search(path)
    if period:
        return period.group(0), int(period.group(1))
    year = YEAR_RE.search(path)
    if year:
        return year.group(0), int(year.group(0))
    return path.rsplit("/", 1)[-1], None


def describe_source(con: duckdb.DuckDBPyConnection, path: str) -> dict[str, str]:
    rows = (
        con.cursor().execute(f"DESCRIBE SELECT * FROM read_parquet('{path}')").fetchall()
    )
    return {row[0]: row[1] for row in rows}


def count_rows(con: duckdb.DuckDBPyConnection, path: str) -> int:
    row = (
        con.cursor()
        .execute(f"SELECT SUM(num_rows) FROM parquet_file_metadata('{path}')")
        .fetchone()
    )
    return int(row[0]) if row and row[0] is not None else 0


def build_catalog_layer() -> Catalog:
    con = get_connection()
    sources: list[SourceInfo] = []
    for path in parquet_paths():
        label, year = parse_period(path)
        sources.append(
            SourceInfo(
                path=path,
                label=label,
                year=year,
                columns=describe_source(con, path),
                row_count=count_rows(con, path),
            )
        )

    all_columns: dict[str, str] = {}
    for source in sources:
        all_columns.update(source.columns)

    common: dict[str, str] = {}
    if sources:
        shared = set(sources[0].columns)
        for source in sources[1:]:
            shared &= set(source.columns)
        common = {name: typ for name, typ in sources[0].columns.items() if name in shared}

    years = [source.year for source in sources if source.year is not None]
    catalog = Catalog(
        sources=sources,
        columns=common or all_columns,
        all_columns=all_columns,
        total_rows=sum(source.row_count for source in sources),
        year_min=min(years) if years else None,
        year_max=max(years) if years else None,
    )
    logger.debug(
        "catalog built sources=%d columns=%d total_rows=%d coverage=%s",
        len(sources),
        len(catalog.columns),
        catalog.total_rows,
        catalog.coverage(),
    )
    return catalog


def get_catalog(refresh: bool = False) -> Catalog:
    global cached_catalog
    if cached_catalog is not None and not refresh:
        return cached_catalog
    with catalog_lock:
        if cached_catalog is None or refresh:
            cached_catalog = build_catalog_layer()
        return cached_catalog


def build_catalog(con: duckdb.DuckDBPyConnection | None = None) -> dict[str, str]:
    return get_catalog().columns
