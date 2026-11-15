import asyncio
import logging
import re
import textwrap

from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp

from parley.config import settings, setup_logging
from parley.graph import astream_run
from parley.slack.format import format_blocks
from parley.sql.catalog import get_catalog

logger = logging.getLogger(__name__)

MENTION = re.compile(r"<@[A-Z0-9]+>")


def strip_mention(text: str) -> str:
    return MENTION.sub("", text).strip()


def step_line(node: str, state: dict) -> str | None:
    if node == "classify":
        return f"routed to *{state.get('route')}*"
    if node == "sql":
        return f"ran `{textwrap.shorten(state.get('sql') or '', 80)}`"
    if node == "rag":
        return "searched the docs"
    if node == "merge":
        return "combined data and docs"
    if node == "verify":
        return "answer verified" if state.get("verified") else "revised the answer"
    return None


def progress_text(lines: list[str]) -> str:
    header = f"{settings.slack_spinner} _working..._"
    if not lines:
        return header
    body = "\n".join(f"› {line}" for line in lines)
    return f"{header}\n{body}"


async def respond(text: str, event: dict, say, client) -> None:
    question = strip_mention(text)
    if not question:
        return
    channel = event["channel"]
    logger.debug("slack question=%r channel=%s", question, channel)
    placeholder = await say(text=progress_text([]))
    ts = placeholder["ts"]
    lines: list[str] = []
    result: dict = {}
    async for event_dict in astream_run(question):
        if event_dict["kind"] == "step":
            line = step_line(event_dict["node"], event_dict["state"])
            if line:
                lines.append(line)
                await client.chat_update(
                    channel=channel, ts=ts, text=progress_text(lines)
                )
        else:
            result = event_dict["result"]
    await client.chat_update(
        channel=channel,
        ts=ts,
        text=result.get("answer") or "...",
        blocks=format_blocks(result, show_sql=settings.slack_show_sql),
    )


def build_app() -> AsyncApp:
    app = AsyncApp(token=settings.slack_bot_token)

    @app.event("app_mention")
    async def handle_mention(event: dict, say, client) -> None:
        await respond(event.get("text", ""), event, say, client)

    @app.event("message")
    async def handle_message(event: dict, say, client) -> None:
        # Channel mentions are handled by app_mention; here we only take DMs. Skip bot
        # echoes and edited/joined system messages so we never reply to ourselves.
        if event.get("bot_id") or event.get("subtype"):
            return
        if event.get("channel_type") != "im":
            return
        await respond(event.get("text", ""), event, say, client)

    return app


async def main() -> None:
    setup_logging()
    if not settings.slack_bot_token or not settings.slack_app_token:
        raise SystemExit(
            "set SLACK_BOT_TOKEN (xoxb-...) and SLACK_APP_TOKEN (xapp-...) in .env"
        )

    # Warm the catalog so the first reply isn't slow.
    try:
        await asyncio.to_thread(get_catalog)
    except Exception:
        logger.warning("catalog warm-up failed; first query will build it", exc_info=True)

    app = build_app()
    handler = AsyncSocketModeHandler(app, settings.slack_app_token)
    logger.info("parley slack bot starting (socket mode)")
    await handler.start_async()


if __name__ == "__main__":
    asyncio.run(main())
