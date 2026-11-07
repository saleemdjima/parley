import logging
import os
from typing import TypeVar, cast

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from tenacity import retry, stop_after_attempt, wait_exponential

from parley.config import settings
from parley.metrics import record_tokens

T = TypeVar("T")

logger = logging.getLogger(__name__)


# Bridge the key loaded from .env so Gemini auth works.
if settings.google_api_key:
    os.environ.setdefault("GOOGLE_API_KEY", settings.google_api_key)


# Retry transient LLM failures
retry_llm = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, max=8),
    reraise=True,
)


def chat_model() -> BaseChatModel:
    # Swap provider/model via settings (LLM_PROVIDER / LLM_MODEL). Same code path.
    return init_chat_model(settings.llm_model, model_provider=settings.llm_provider)


def text_of(message: BaseMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    parts = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict):
            parts.append(block.get("text", ""))
    return "".join(parts)


def record_usage(message: BaseMessage) -> None:
    # LangChain normalizes token counts across providers onto usage_metadata, so
    # the eval harness tracks cost the same way whatever the backend.
    usage = getattr(message, "usage_metadata", None)
    if not usage:
        return
    record_tokens(
        settings.llm_model,
        usage.get("input_tokens", 0) or 0,
        usage.get("output_tokens", 0) or 0,
    )


@retry_llm
def classify(prompt: str) -> str:
    message = chat_model().invoke(prompt)
    record_usage(message)
    text = text_of(message).strip()
    logger.debug("classify -> %r", text)
    return text


@retry_llm
def extract(prompt: str, schema: type[T]) -> T:
    model = chat_model().with_structured_output(schema, include_raw=True)
    # include_raw=True always yields a dict with "raw"/"parsed"; the stub widens it.
    result = cast(dict, model.invoke(prompt))
    record_usage(result["raw"])
    logger.debug("extract parsed=%s", result["parsed"])
    return result["parsed"]


@retry_llm
def answer(prompt: str) -> str:
    message = chat_model().invoke(prompt)
    record_usage(message)
    return text_of(message).strip()
