import logging
from enum import StrEnum

from parley import llm

logger = logging.getLogger(__name__)


class Route(StrEnum):
    sql = "sql"
    rag = "rag"
    hybrid = "hybrid"


ROUTER_PROMPT = """Classify the question into exactly one word: "sql", "rag" or
"hybrid".
- "sql": aggregate/statistical questions answerable from trip columns (counts,
  averages, totals, group-bys over fares, tips, distances, locations).
- "rag": definitional/documentation questions (what a field or code means, how a
  surcharge is defined).
- "hybrid": needs BOTH a computed statistic AND a definition.

Examples:
- "how many trips in January?" -> sql
- "average tip by payment type" -> sql
- "what does RatecodeID 5 mean?" -> rag
- "how is the congestion surcharge defined?" -> rag
- "what is the average fare, and what does fare_amount include?" -> hybrid

Question: {question}
Answer:"""


def route(question: str) -> Route:
    text = llm.classify(ROUTER_PROMPT.format(question=question)).lower()
    if "hybrid" in text:
        decision = Route.hybrid
    elif "rag" in text:
        decision = Route.rag
    else:
        decision = Route.sql
    logger.debug("route question=%r raw=%r -> %s", question, text, decision)
    return decision
