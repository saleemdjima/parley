from unittest.mock import patch

from parley.sql.router import Route, route


def classify_returns(text: str):
    return patch("parley.sql.router.llm.classify", return_value=text)


def test_route_sql() -> None:
    with classify_returns("It's a count over trips.\nROUTE: sql"):
        decision = route("how many trips in January?")
        assert decision.route == Route.sql
        assert "count" in decision.reasoning.lower()


def test_route_rag() -> None:
    with classify_returns("Asks for a definition.\nROUTE: rag"):
        assert route("what does RatecodeID 5 mean?").route == Route.rag


def test_route_hybrid() -> None:
    with classify_returns("Needs a stat and a definition.\nROUTE: hybrid"):
        assert route("average fare and what fare_amount includes?").route == Route.hybrid


def test_route_clarify() -> None:
    with classify_returns("Just a greeting.\nROUTE: clarify"):
        assert route("hi, what can you do?").route == Route.clarify


def test_route_defaults_to_sql_without_a_route_line() -> None:
    with classify_returns("¯\\_(ツ)_/¯"):
        assert route("???").route == Route.sql


def test_route_falls_back_to_a_default_reasoning() -> None:
    with classify_returns("ROUTE: sql"):
        assert route("how many trips?").reasoning
