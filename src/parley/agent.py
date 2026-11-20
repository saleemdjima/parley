import logging

from parley.graph import astream_run, run

logger = logging.getLogger(__name__)


def ask(question: str) -> dict:
    return run(question)


async def aask(
    question: str,
    thread_id: str | None = None,
    user_id: str | None = None,
    language: str | None = None,
) -> dict:
    result: dict = {}
    async for event in astream_run(question, thread_id, user_id, language):
        if event["kind"] == "result":
            result = event["result"]
    return result
