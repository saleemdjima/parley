from unittest.mock import MagicMock, patch

from parley.graph import clarify_node, sql_node


def test_clarify_node_uses_grounded_system_prompt() -> None:
    catalog = MagicMock()
    catalog.coverage.return_value = "2024"
    catalog.total_rows = 1000
    with (
        patch("parley.graph.get_catalog", return_value=catalog),
        patch("parley.graph.llm.answer", return_value="Hi! Happy to help.") as mock_answer,
    ):
        out = clarify_node({"question": "hi"})

    assert out["answer"] == "Hi! Happy to help."
    prompt = mock_answer.call_args[0][0]
    assert "2024" in prompt
    assert "NYC yellow-taxi trips" in prompt


def test_sql_node_builds_executes_and_phrases() -> None:
    catalog = MagicMock()
    catalog.column_names.return_value = ["fare_amount"]
    catalog.coverage.return_value = "2024"
    catalog.total_rows = 1000
    catalog.columns = {"fare_amount": "DOUBLE"}

    engine = MagicMock()
    engine.name = "duckdb"
    engine.execute.return_value = [{"value": 18.1}]

    with (
        patch("parley.graph.get_catalog", return_value=catalog),
        patch("parley.graph.get_engine", return_value=engine),
        patch("parley.graph.extract_intent", return_value="intent"),
        patch("parley.graph.build_query", return_value=("SELECT 1", [])),
        patch("parley.graph.llm.answer", return_value="The average fare was $18.10."),
    ):
        out = sql_node({"question": "average fare"})

    assert out["sql"] == "SELECT 1"
    assert out["params"] == []
    assert out["rows"] == [{"value": 18.1}]
    # The pure-sql route now phrases the rows into a sentence.
    assert out["answer"] == "The average fare was $18.10."
    engine.execute.assert_called_once_with("SELECT 1", [])
