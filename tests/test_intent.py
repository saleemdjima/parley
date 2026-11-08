from unittest.mock import patch

from parley.domains.taxi import TAXI_METRICS
from parley.sql.intent import extract_intent


def test_prompt_grounds_coverage_and_renders_metrics_from_registry() -> None:
    with patch("parley.sql.intent.llm.extract", return_value="intent") as mock_extract:
        result = extract_intent("avg fare", ["fare_amount"], "2024", TAXI_METRICS)

    prompt = mock_extract.call_args[0][0]
    assert "2024" in prompt
    assert "fare_amount" in prompt
    assert "avg_fare" in prompt
    assert result == "intent"
