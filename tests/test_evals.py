import pytest

from parley.config import settings
from parley.evaluation import load_reference, run_case

HAS_KEY = bool(settings.google_api_key)

reference_cases = load_reference() if HAS_KEY else []


@pytest.mark.skipif(not HAS_KEY, reason="live regression needs GOOGLE_API_KEY")
@pytest.mark.parametrize("case", reference_cases, ids=lambda c: c["question"])
def test_reference_question(case: dict) -> None:
    result = run_case(case)
    assert result.actual_route == result.expected_route, result.question
    if result.expected_sql is not None:
        assert result.actual_sql == result.expected_sql
        assert result.actual_params == result.expected_params
