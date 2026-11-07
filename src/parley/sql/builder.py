import logging
from dataclasses import dataclass

from parley.config import settings
from parley.engines.base import Engine
from parley.sql.schema import QueryIntent

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MetricRegistry:
    expressions: dict[str, str]
    descriptions: dict[str, str]


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

    if intent.metric not in metrics.expressions:
        raise ValueError(f"Unknown metric: {intent.metric}")

    select = f"{metrics.expressions[intent.metric]} AS value"

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

    if intent.group_by:
        clauses.append(f"GROUP BY {intent.group_by}")

    clauses.append(f"ORDER BY value {'DESC' if intent.order_desc else 'ASC'}")
    clauses.append(f"LIMIT {max(1, min(intent.limit, settings.max_limit))}")

    sql = " ".join(clauses)
    logger.debug("build_query sql=%s params=%s", sql, params)
    return sql, params
