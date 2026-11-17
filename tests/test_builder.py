import pytest

from parley.domains.taxi import TAXI_METRICS
from parley.sql.builder import build_query
from parley.sql.schema import Aggregation, Comparator, Filter, QueryIntent

# A representative taxi catalog. Tests need no Parquet file and no network.
CATALOG = {
    "VendorID": "BIGINT",
    "tpep_pickup_datetime": "TIMESTAMP",
    "passenger_count": "DOUBLE",
    "trip_distance": "DOUBLE",
    "PULocationID": "BIGINT",
    "payment_type": "BIGINT",
    "store_and_fwd_flag": "VARCHAR",
    "fare_amount": "DOUBLE",
    "tip_amount": "DOUBLE",
    "total_amount": "DOUBLE",
}


class FakeEngine:
    # Stand-in engine so builder tests run with no DuckDB/ClickHouse connection.
    name = "fake"

    def source_expr(self) -> str:
        return "read_parquet('trips.parquet')"

    def placeholder(self, index: int) -> str:
        return "?"

    def catalog(self) -> dict[str, str]:
        return CATALOG

    def execute(self, sql, params):
        raise NotImplementedError


ENGINE = FakeEngine()


def test_count_no_filters():
    sql, params = build_query(
        QueryIntent(aggregation=Aggregation.COUNT), CATALOG, ENGINE, TAXI_METRICS
    )
    assert "COUNT(*)" in sql
    assert "read_parquet" in sql
    assert params == []


def test_aggregation_over_column():
    sql, _ = build_query(
        QueryIntent(aggregation=Aggregation.AVG, measure="fare_amount"),
        CATALOG,
        ENGINE,
        TAXI_METRICS,
    )
    assert "AVG(fare_amount) AS value" in sql


def test_max_builds_max_expression():
    sql, _ = build_query(
        QueryIntent(aggregation=Aggregation.MAX, measure="trip_distance"),
        CATALOG,
        ENGINE,
        TAXI_METRICS,
    )
    assert "MAX(trip_distance) AS value" in sql


def test_metric_expression_comes_from_the_registry():
    sql, _ = build_query(QueryIntent(metric="avg_tip_pct"), CATALOG, ENGINE, TAXI_METRICS)
    assert TAXI_METRICS.expressions["avg_tip_pct"] in sql


def test_numeric_value_is_parameterized_not_inlined():
    intent = QueryIntent(
        aggregation=Aggregation.AVG,
        measure="fare_amount",
        filters=[Filter(column="trip_distance", op=Comparator.gt, value=7.5)],
    )
    sql, params = build_query(intent, CATALOG, ENGINE, TAXI_METRICS)
    assert "trip_distance > ?" in sql
    assert params == [7.5]
    assert "7.5" not in sql  # the value must live in params, never in the SQL text


def test_string_value_never_reaches_sql():
    # The core "safe by design" guarantee: a malicious value cannot alter the SQL.
    malicious = "x'; DROP TABLE trips; --"
    intent = QueryIntent(
        aggregation=Aggregation.COUNT,
        filters=[Filter(column="payment_type", op=Comparator.eq, value=malicious)],
    )
    sql, params = build_query(intent, CATALOG, ENGINE, TAXI_METRICS)
    assert malicious in params
    assert "DROP TABLE" not in sql


def test_placeholder_count_matches_params():
    intent = QueryIntent(
        aggregation=Aggregation.AVG,
        measure="total_amount",
        filters=[
            Filter(column="passenger_count", op=Comparator.gte, value=2),
            Filter(column="payment_type", op=Comparator.eq, value=1),
        ],
    )
    sql, params = build_query(intent, CATALOG, ENGINE, TAXI_METRICS)
    assert sql.count("?") == len(params) == 2


def test_group_by_valid_column():
    intent = QueryIntent(
        aggregation=Aggregation.AVG, measure="tip_amount", group_by="payment_type"
    )
    sql, _ = build_query(intent, CATALOG, ENGINE, TAXI_METRICS)
    assert "GROUP BY" in sql.upper()
    assert "payment_type" in sql


def test_scalar_aggregate_has_no_order_or_limit():
    intent = QueryIntent(
        aggregation=Aggregation.AVG, measure="fare_amount", order_desc=False, top_n=5
    )
    sql, _ = build_query(intent, CATALOG, ENGINE, TAXI_METRICS)
    assert "ORDER BY" not in sql.upper()
    assert "LIMIT" not in sql.upper()


def test_grouped_ranking_uses_default_limit():
    intent = QueryIntent(
        aggregation=Aggregation.AVG, measure="tip_amount", group_by="payment_type"
    )
    sql, _ = build_query(intent, CATALOG, ENGINE, TAXI_METRICS)
    assert "ORDER BY value DESC" in sql
    assert "LIMIT 20" in sql


def test_top_n_overrides_default_limit():
    intent = QueryIntent(
        aggregation=Aggregation.AVG,
        measure="tip_amount",
        group_by="payment_type",
        top_n=5,
    )
    sql, _ = build_query(intent, CATALOG, ENGINE, TAXI_METRICS)
    assert "LIMIT 5" in sql


def test_breakdown_ignores_arbitrary_order_desc():
    # No top_n: a plain breakdown is always highest-first, regardless of order_desc,
    # so the arbitrary LLM flag can't make the SQL flake run to run.
    intent = QueryIntent(
        aggregation=Aggregation.AVG,
        measure="tip_amount",
        group_by="payment_type",
        order_desc=False,
    )
    sql, _ = build_query(intent, CATALOG, ENGINE, TAXI_METRICS)
    assert "ORDER BY value DESC" in sql


def test_explicit_bottom_ranking_orders_ascending():
    intent = QueryIntent(
        aggregation=Aggregation.AVG,
        measure="tip_amount",
        group_by="payment_type",
        order_desc=False,
        top_n=5,
    )
    sql, _ = build_query(intent, CATALOG, ENGINE, TAXI_METRICS)
    assert "ORDER BY value ASC" in sql


def test_avg_on_non_numeric_column_raises():
    intent = QueryIntent(aggregation=Aggregation.AVG, measure="store_and_fwd_flag")
    with pytest.raises(ValueError):
        build_query(intent, CATALOG, ENGINE, TAXI_METRICS)


def test_requires_metric_or_aggregation():
    with pytest.raises(ValueError):
        build_query(QueryIntent(), CATALOG, ENGINE, TAXI_METRICS)


def test_rejects_unwhitelisted_measure():
    intent = QueryIntent(aggregation=Aggregation.MAX, measure="not_a_column")
    with pytest.raises(ValueError):
        build_query(intent, CATALOG, ENGINE, TAXI_METRICS)


def test_rejects_unwhitelisted_filter_column():
    intent = QueryIntent(
        aggregation=Aggregation.COUNT,
        filters=[Filter(column="hacked; DROP TABLE t", op=Comparator.eq, value=1)],
    )
    with pytest.raises(ValueError):
        build_query(intent, CATALOG, ENGINE, TAXI_METRICS)


def test_rejects_unwhitelisted_group_by():
    intent = QueryIntent(aggregation=Aggregation.COUNT, group_by="not_a_column")
    with pytest.raises(ValueError):
        build_query(intent, CATALOG, ENGINE, TAXI_METRICS)


def test_rejects_unknown_metric():
    intent = QueryIntent(metric="avg_nonexistent")
    with pytest.raises(ValueError):
        build_query(intent, CATALOG, ENGINE, TAXI_METRICS)
