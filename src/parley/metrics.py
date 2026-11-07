import logging
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

logger = logging.getLogger(__name__)


PRICING: dict[str, tuple[float, float]] = {
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-flash": (0.10, 0.40),
}
DEFAULT_PRICING = (0.10, 0.40)


@dataclass
class QueryMetrics:
    input_tokens: int = 0
    output_tokens: int = 0
    latency_s: float = 0.0
    cost_usd: float = 0.0


current: ContextVar[QueryMetrics | None] = ContextVar("current_metrics", default=None)


def price_for(model: str) -> tuple[float, float]:
    for key, price in PRICING.items():
        if key in model:
            return price
    return DEFAULT_PRICING


def record_tokens(model: str, input_tokens: int, output_tokens: int) -> None:
    metrics = current.get()
    if metrics is None:
        return
    metrics.input_tokens += input_tokens
    metrics.output_tokens += output_tokens
    in_price, out_price = price_for(model)
    metrics.cost_usd += (input_tokens * in_price + output_tokens * out_price) / 1_000_000
    logger.debug(
        "record_tokens model=%s in=%d out=%d", model, input_tokens, output_tokens
    )


def record_gemini_usage(model: str, response) -> None:
    usage = getattr(response, "usage_metadata", None)
    if usage is None:
        return
    record_tokens(
        model,
        getattr(usage, "prompt_token_count", 0) or 0,
        getattr(usage, "candidates_token_count", 0) or 0,
    )


@contextmanager
def track():
    metrics = QueryMetrics()
    token = current.set(metrics)
    start = time.time()
    try:
        yield metrics
    finally:
        metrics.latency_s = time.time() - start
        current.reset(token)

