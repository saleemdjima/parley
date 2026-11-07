import logging

from parley.config import settings
from parley.errors import InvalidQuestion

logger = logging.getLogger(__name__)


def validate_question(question: str) -> str:
    cleaned = question.strip()
    if not cleaned:
        raise InvalidQuestion("Question must not be empty.")
    if len(cleaned) > settings.max_question_length:
        raise InvalidQuestion(
            f"Question too long (max {settings.max_question_length} characters)."
        )
    logger.debug("validate_question ok length=%d", len(cleaned))
    return cleaned
