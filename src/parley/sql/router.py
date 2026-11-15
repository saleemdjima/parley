import logging
from enum import StrEnum

from pydantic import BaseModel, Field

from parley import llm

logger = logging.getLogger(__name__)


class Route(StrEnum):
    sql = "sql"
    rag = "rag"
    hybrid = "hybrid"
    clarify = "clarify"


class RouteDecision(BaseModel):
    reasoning: str = Field(
        description="One short, plain-language sentence explaining the choice."
    )
    route: Route


ROUTER_PROMPT = """Decide how to answer a question about NYC yellow-taxi trips. Classify
it as exactly one of "sql", "rag", "hybrid" or "clarify".
- "sql": aggregate/statistical questions answerable from trip columns (counts,
  averages, totals, min/max, group-bys over fares, tips, distances, locations).
- "rag": definitional/documentation questions (what a field or code means, how a
  surcharge is defined).
- "hybrid": needs BOTH a computed statistic AND a definition.
- "clarify": the question is ambiguous, incomplete, a greeting, or not about NYC
  taxi trips at all — too vague or off-topic to answer.

Examples:
- "how many trips in January?" -> sql
- "average tip by payment type" -> sql
- "what does RatecodeID 5 mean?" -> rag
- "how is the congestion surcharge defined?" -> rag
- "what is the average fare, and what does fare_amount include?" -> hybrid
- "hi, what can you do?" -> clarify
- "what's the weather tomorrow?" -> clarify

Reply with one short sentence explaining your choice, then a final line exactly:
ROUTE: <sql|rag|hybrid|clarify>

Question: {question}"""


def parse_route(token: str) -> Route:
    token = token.lower()
    if "hybrid" in token:
        return Route.hybrid
    if "clarify" in token:
        return Route.clarify
    if "rag" in token:
        return Route.rag
    return Route.sql


def route(question: str) -> RouteDecision:
    text = llm.classify(ROUTER_PROMPT.format(question=question)).strip()
    route_value = Route.sql
    reasoning_lines: list[str] = []
    for line in text.splitlines():
        if line.strip().lower().startswith("route:"):
            route_value = parse_route(line.split(":", 1)[1])
        elif line.strip():
            reasoning_lines.append(line.strip())
    reasoning = " ".join(reasoning_lines) or f"Treating this as a {route_value} question."
    logger.debug("route question=%r -> %s (%s)", question, route_value, reasoning)
    return RouteDecision(reasoning=reasoning, route=route_value)
