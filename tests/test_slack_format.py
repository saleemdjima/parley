from parley.slack.format import format_blocks, format_footer, format_message


def test_footer_sums_tokens_and_shows_route() -> None:
    footer = format_footer(
        "sql",
        {"input_tokens": 150, "output_tokens": 30, "latency_s": 7.1, "cost_usd": 0.0001},
    )
    assert "route `sql`" in footer
    assert "180 tokens" in footer
    assert "7.1s" in footer
    assert "$0.000100" in footer


def test_message_includes_sql_on_its_own_lines() -> None:
    result = {
        "route": "sql",
        "sql": "SELECT 1",
        "params": [1],
        "answer": "one",
        "metrics": {
            "input_tokens": 1,
            "output_tokens": 1,
            "latency_s": 1.0,
            "cost_usd": 0.0,
        },
    }
    text = format_message(result)
    assert text.startswith("one")
    assert "*SQL*\n```SELECT 1\nparams: [1]```" in text
    assert "route `sql`" in text


def test_message_omits_sql_on_rag() -> None:
    result = {"route": "rag", "answer": "negotiated fare", "metrics": {}}
    text = format_message(result)
    assert "negotiated fare" in text
    assert "SQL" not in text


def test_show_sql_false_hides_sql() -> None:
    result = {"route": "sql", "sql": "SELECT 1", "answer": "one", "metrics": {}}
    assert "SQL" not in format_message(result, show_sql=False)


def test_blocks_is_single_section() -> None:
    result = {"route": "rag", "answer": "hi", "metrics": {}}
    blocks = format_blocks(result)
    assert len(blocks) == 1
    assert blocks[0]["type"] == "section"
