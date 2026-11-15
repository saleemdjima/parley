from unittest.mock import patch

from parley.graph import evidence_for, verify_node
from parley.verify import Verdict


def test_clarify_passes_through_without_judging():
    with patch("parley.graph.judge") as mock_judge:
        out = verify_node({"route": "clarify", "answer": "Hi! How can I help?"})
    assert out == {"verified": True}
    mock_judge.assert_not_called()


def test_empty_answer_returns_safe_message():
    out = verify_node({"route": "sql", "answer": "", "rows": [{"value": 1}]})
    assert out["verified"] is False
    assert out["answer"]


def test_data_route_uses_judge_correction():
    verdict = Verdict(supported=False, answer="The average fare was $5.00.")
    with patch("parley.graph.judge", return_value=verdict) as mock_judge:
        out = verify_node(
            {
                "route": "sql",
                "question": "average fare?",
                "answer": "The average fare was $999.",
                "rows": [{"value": 5.0}],
            }
        )
    mock_judge.assert_called_once()
    assert out == {"answer": "The average fare was $5.00.", "verified": False}


def test_supported_answer_is_kept():
    verdict = Verdict(supported=True, answer="good")
    with patch("parley.graph.judge", return_value=verdict):
        out = verify_node(
            {"route": "sql", "question": "q", "answer": "good", "rows": [{"value": 5}]}
        )
    assert out == {"answer": "good", "verified": True}


def test_evidence_combines_rows_and_context():
    evidence = evidence_for({"rows": [{"value": 5}], "context": "surcharge is $2.50"})
    assert "Result rows" in evidence
    assert "surcharge is $2.50" in evidence
