import logging

from parley.graph import run

logger = logging.getLogger(__name__)


def ask(question: str) -> dict:
    # Thin entry point; orchestration lives in the LangGraph graph (graph.py).
    return run(question)
