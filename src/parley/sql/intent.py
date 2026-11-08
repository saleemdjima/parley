import logging

from parley import llm
from parley.config import settings
from parley.sql.builder import MetricRegistry
from parley.sql.schema import QueryIntent

logger = logging.getLogger(__name__)

INTENT_PROMPT = """You convert a question about {domain} into a typed QueryIntent.
Pick exactly one metric. Only use these columns in group_by and filters, matching the
names exactly: {columns}. Never invent a column. If the question implies no filter,
return an empty filters list.

The dataset covers these years: {coverage}. When the question names a month or season
without a year, assume the most recent year within that coverage. Never filter to a
year outside the coverage.

Metrics (pick one):
{metrics}

Question: {question}"""


def extract_intent(
    question: str,
    columns: list[str],
    coverage: str,
    metrics: MetricRegistry,
    domain: str | None = None,
) -> QueryIntent:
    # The metric list is rendered from the registry, not hardcoded, so the prompt and
    # the SQL builder always agree on what metrics exist.
    metric_lines = "\n".join(
        f"- {name}: {desc}" for name, desc in metrics.descriptions.items()
    )
    prompt = INTENT_PROMPT.format(
        domain=domain or settings.dataset_description,
        columns=", ".join(columns),
        coverage=coverage,
        metrics=metric_lines,
        question=question,
    )
    intent = llm.extract(prompt, QueryIntent)
    logger.debug("extract_intent question=%r intent=%s", question, intent)
    return intent
