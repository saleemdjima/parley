def format_footer(route: str, metrics: dict) -> str:
    total_tokens = (metrics.get("input_tokens") or 0) + (
        metrics.get("output_tokens") or 0
    )
    parts: list[str] = []
    if route:
        parts.append(f"route `{route}`")
    first = metrics.get("first_response_s")
    if first is not None:
        parts.append(f"first {first:.1f}s")
    latency = metrics.get("latency_s")
    if latency is not None:
        parts.append(f"{latency:.1f}s total")
    parts.append(f"{total_tokens:,} tokens")
    cost = metrics.get("cost_usd")
    if cost is not None:
        parts.append(f"${cost:.6f}")
    return " · ".join(parts)


def format_message(result: dict, show_sql: bool = True) -> str:
    lines: list[str] = [result.get("answer") or "..."]

    sql = result.get("sql")
    if sql and show_sql:
        params = result.get("params")
        sql_text = sql if not params else f"{sql}\nparams: {params}"
        lines.append(f"*SQL*\n```{sql_text}```")

    footer = format_footer(result.get("route", ""), result.get("metrics", {}))
    lines.append(f"_{footer}_")
    return "\n\n".join(lines)


def format_blocks(result: dict, show_sql: bool = True) -> list[dict]:
    # One section block so the whole reply renders as a single message with line
    # breaks, not several stacked blocks.
    text = format_message(result, show_sql=show_sql)
    return [{"type": "section", "text": {"type": "mrkdwn", "text": text}}]
