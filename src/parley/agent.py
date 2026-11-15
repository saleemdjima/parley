import logging

from parley.graph import astream_run, run

logger = logging.getLogger(__name__)


def ask(question: str) -> dict:
    return run(question)


async def aask(question: str) -> dict:
    result: dict = {}
    async for event in astream_run(question):
        if event["kind"] == "result":
            result = event["result"]
    return result
