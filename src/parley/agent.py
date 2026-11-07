import logging

from parley.graph import arun, run

logger = logging.getLogger(__name__)


def ask(question: str) -> dict:
    # Thin sync entry point (CLI); orchestration lives in graph.py.
    return run(question)


async def aask(question: str) -> dict:
    # Async entry point (API); the hybrid route runs its branches concurrently.
    return await arun(question)
