import logging

from parley import llm
from parley.sql.schema import QueryIntent

logger = logging.getLogger(__name__)

INTENT_PROMPT = """You convert a question about NYC yellow-taxi trips into a typed
QueryIntent. Pick exactly one metric. Only use these columns in group_by and
filters, matching the names exactly: {columns}. Never invent a column. If the
question implies no filter, return an empty filters list.

Metrics:
- count_trips: number of trips
- avg_fare: average fare_amount
- avg_tip: average tip_amount
- avg_trip_distance: average trip_distance
- avg_total: average total_amount
- sum_total: total of total_amount
- avg_tip_pct: average tip as a fraction of fare

Question: {question}"""


def extract_intent(question: str, columns: list[str]) -> QueryIntent:
    prompt = INTENT_PROMPT.format(columns=", ".join(columns), question=question)
    intent = llm.extract(prompt, QueryIntent)
    logger.debug("extract_intent question=%r intent=%s", question, intent)
    return intent
