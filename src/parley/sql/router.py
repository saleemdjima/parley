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
it as exactly one of "sql", "rag", "hybrid" or "clarify". The question may be in any
language; classify it the same way regardless of language.
- "sql": any analytical/statistical question answerable from trip columns (counts,
  averages, totals, min/max, group-bys, "most/least", "most popular/frequent/common/
  busiest") over fares, tips, distances, times, or pickup/dropoff locations. Prefer sql
  whenever the question has analytical intent, even if a detail is underspecified: a
  vague metric like "popular" or "busiest" has a natural default (number of trips), so
  answer it rather than asking what it means.
- "rag": definitional/documentation questions (what a field or code means, how a
  surcharge is defined).
- "hybrid": needs BOTH a computed statistic AND a definition.
- "clarify": ONLY for greetings, chit-chat, or input that is not about the taxi data at
  all. Do NOT clarify a real analytical question merely because a detail (pickup vs
  dropoff, a time window, a ranking size, or what a word like "popular" means) is
  missing — pick the natural default and choose sql instead.

Examples:
- "how many trips in January?" -> sql
- "average tip by payment type" -> sql
- "what are the most popular trips?" -> sql
- "which neighborhoods are the busiest?" -> sql
- "quels sont les quartiers les plus frequentes ?" -> sql
- "quel est le pourboire moyen ?" -> sql
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
