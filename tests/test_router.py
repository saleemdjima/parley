from unittest.mock import patch

from parley.sql.router import Route, route


def classify_returns(value: str):
    return patch("parley.sql.router.llm.classify", return_value=value)


def test_route_sql() -> None:
    with classify_returns("sql"):
        assert route("how many trips in January?") == Route.sql


def test_route_rag() -> None:
    with classify_returns("rag"):
        assert route("what does RatecodeID 5 mean?") == Route.rag


def test_route_hybrid() -> None:
    with classify_returns("hybrid"):
        assert route("average fare and what fare_amount includes?") == Route.hybrid


def test_route_clarify() -> None:
    with classify_returns("clarify"):
        assert route("hi, what can you do?") == Route.clarify


def test_route_defaults_to_sql_on_garbage() -> None:
    # The model returning something unexpected must not crash; sql is the safe default.
    with classify_returns("¯\\_(ツ)_/¯"):
        assert route("???") == Route.sql
