import pytest

from parley.domains.taxi import TAXI_METRICS
from parley.sql.builder import build_query
from parley.sql.schema import Comparator, Filter, QueryIntent

# A representative taxi catalog. Tests need no Parquet file and no network.
CATALOG = {
    "VendorID": "BIGINT",
    "tpep_pickup_datetime": "TIMESTAMP",
    "passenger_count": "DOUBLE",
    "trip_distance": "DOUBLE",
    "PULocationID": "BIGINT",
    "payment_type": "BIGINT",
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
        QueryIntent(metric="count_trips"), CATALOG, ENGINE, TAXI_METRICS
    )
    assert TAXI_METRICS.expressions["count_trips"] in sql
    assert "read_parquet" in sql
    assert params == []


def test_metric_expression_comes_from_the_registry():
    sql, _ = build_query(QueryIntent(metric="avg_tip_pct"), CATALOG, ENGINE, TAXI_METRICS)
    assert TAXI_METRICS.expressions["avg_tip_pct"] in sql


def test_numeric_value_is_parameterized_not_inlined():
    intent = QueryIntent(
        metric="avg_fare",
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
        metric="count_trips",
        filters=[Filter(column="payment_type", op=Comparator.eq, value=malicious)],
    )
    sql, params = build_query(intent, CATALOG, ENGINE, TAXI_METRICS)
    assert malicious in params
    assert "DROP TABLE" not in sql


def test_placeholder_count_matches_params():
    intent = QueryIntent(
        metric="avg_total",
        filters=[
            Filter(column="passenger_count", op=Comparator.gte, value=2),
            Filter(column="payment_type", op=Comparator.eq, value=1),
        ],
    )
    sql, params = build_query(intent, CATALOG, ENGINE, TAXI_METRICS)
    assert sql.count("?") == len(params) == 2


def test_group_by_valid_column():
    intent = QueryIntent(metric="avg_tip", group_by="payment_type")
    sql, _ = build_query(intent, CATALOG, ENGINE, TAXI_METRICS)
    assert "GROUP BY" in sql.upper()
    assert "payment_type" in sql


def test_rejects_unwhitelisted_filter_column():
    intent = QueryIntent(
        metric="count_trips",
        filters=[Filter(column="hacked; DROP TABLE t", op=Comparator.eq, value=1)],
    )
    with pytest.raises(ValueError):
        build_query(intent, CATALOG, ENGINE, TAXI_METRICS)


def test_rejects_unwhitelisted_group_by():
    intent = QueryIntent(metric="count_trips", group_by="not_a_column")
    with pytest.raises(ValueError):
        build_query(intent, CATALOG, ENGINE, TAXI_METRICS)


def test_rejects_unknown_metric():
    # A metric not in the registry must raise the same catchable ValueError as an
    # unwhitelisted column, never a raw KeyError.
    intent = QueryIntent(metric="avg_nonexistent")
    with pytest.raises(ValueError):
        build_query(intent, CATALOG, ENGINE, TAXI_METRICS)
