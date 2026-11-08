import asyncio
import logging
import re

from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp

from parley.agent import aask
from parley.config import settings, setup_logging
from parley.slack.format import format_blocks
from parley.sql.catalog import get_catalog

logger = logging.getLogger(__name__)

MENTION = re.compile(r"<@[A-Z0-9]+>")


def strip_mention(text: str) -> str:
    return MENTION.sub("", text).strip()


THINKING = ":hourglass_flowing_sand: Thinking..."


async def respond(text: str, event: dict, say, client) -> None:
    question = strip_mention(text)
    if not question:
        return
    channel = event["channel"]
    logger.debug("slack question=%r channel=%s", question, channel)
    # Post a placeholder inline (no thread_ts, so it isn't hidden behind a collapsed
    # thread toggle), then edit it in place with the answer (DVF pattern).
    placeholder = await say(text=THINKING)
    result = await aask(question)
    await client.chat_update(
        channel=channel,
        ts=placeholder["ts"],
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
