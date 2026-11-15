import logging
from dataclasses import dataclass

from parley.config import settings
from parley.engines.base import Engine
from parley.sql.schema import Aggregation, QueryIntent

logger = logging.getLogger(__name__)

# Default cap on a grouped ranking when the user didn't ask for a specific count.
DEFAULT_GROUP_LIMIT = 20

AGG_SQL = {
    Aggregation.COUNT: "COUNT",
    Aggregation.SUM: "SUM",
    Aggregation.AVG: "AVG",
    Aggregation.MIN: "MIN",
    Aggregation.MAX: "MAX",
}
NUMERIC_TYPES = ("INT", "DOUBLE", "FLOAT", "REAL", "DECIMAL", "NUMERIC", "HUGEINT")
TEMPORAL_TYPES = ("TIMESTAMP", "DATE", "TIME")


@dataclass(frozen=True)
class MetricRegistry:
    expressions: dict[str, str]
    descriptions: dict[str, str]


def is_numeric(sql_type: str) -> bool:
    return any(t in sql_type.upper() for t in NUMERIC_TYPES)


def is_orderable(sql_type: str) -> bool:
    return is_numeric(sql_type) or any(t in sql_type.upper() for t in TEMPORAL_TYPES)


def measure_expression(
    intent: QueryIntent, catalog: dict[str, str], metrics: MetricRegistry
) -> str:
    if intent.metric is not None:
        if intent.metric not in metrics.expressions:
            raise ValueError(f"Unknown metric: {intent.metric}")
        return metrics.expressions[intent.metric]

    if intent.aggregation is None:
        raise ValueError("intent needs a metric or an aggregation")

    if intent.aggregation is Aggregation.COUNT and intent.measure is None:
        return "COUNT(*)"

    column = intent.measure
    if column is None:
        raise ValueError(f"{intent.aggregation} needs a measure column")
    if column not in catalog:
        raise ValueError(f"Unknown measure column: {column}")

    sql_type = catalog[column]
    if intent.aggregation in (Aggregation.SUM, Aggregation.AVG) and not is_numeric(
        sql_type
    ):
        raise ValueError(
            f"{intent.aggregation} needs a numeric column, got {column} ({sql_type})"
        )
    if intent.aggregation in (Aggregation.MIN, Aggregation.MAX) and not is_orderable(
        sql_type
    ):
        raise ValueError(
            f"{intent.aggregation} needs an orderable column, got {column} ({sql_type})"
        )

    return f"{AGG_SQL[intent.aggregation]}({column})"


def build_query(
    intent: QueryIntent, catalog: dict[str, str], engine: Engine, metrics: MetricRegistry
) -> tuple[str, list]:
    """Turn a typed QueryIntent into a parameterized query for the given engine.

    The `engine` owns what differs between backends: the FROM target
    (engine.source_expr()) and the placeholder style (engine.placeholder(i) ->
    DuckDB '?', ClickHouse '%s'). Everything else is identical, which is the whole
    point of the engine seam.

    Security invariants: group_by/filter columns are whitelisted against `catalog`;
    every value is a bound parameter (never concatenated); the metric expression
    comes from a MetricRegistry only; the source comes from the engine only.
    """
    if intent.group_by and intent.group_by not in catalog:
        raise ValueError(f"Unknown group_by column: {intent.group_by}")
    for predicate in intent.filters:
        if predicate.column not in catalog:
            raise ValueError(f"Unknown filter column: {predicate.column}")

    select = f"{measure_expression(intent, catalog, metrics)} AS value"

    if intent.group_by:
        select = f"{intent.group_by}, {select}"

    clauses = [f"SELECT {select}", f"FROM {engine.source_expr()}"]
    params: list = []

    if intent.filters:
        conditions = []
        for index, predicate in enumerate(intent.filters):
            placeholder = engine.placeholder(index)
            conditions.append(f"{predicate.column} {predicate.op.value} {placeholder}")
            params.append(predicate.value)
        clauses.append("WHERE " + " AND ".join(conditions))

    # ORDER BY
    if intent.group_by:
        clauses.append(f"GROUP BY {intent.group_by}")
        clauses.append(f"ORDER BY value {'DESC' if intent.order_desc else 'ASC'}")
        limit = intent.top_n if intent.top_n is not None else DEFAULT_GROUP_LIMIT
        clauses.append(f"LIMIT {max(1, min(limit, settings.max_limit))}")

    sql = " ".join(clauses)
    logger.debug("build_query sql=%s params=%s", sql, params)
    return sql, params
