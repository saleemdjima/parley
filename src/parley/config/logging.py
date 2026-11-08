import logging
import os
import sys
from logging.config import dictConfig

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s %(levelname)-8s [%(name)s] %(filename)s:%(lineno)d %(message)s",  # noqa: E501
        },
    },
    "handlers": {
        "stdout": {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
            "formatter": "standard",
            "stream": sys.stdout,
        },
    },
    "loggers": {
        "parley": {"level": LOG_LEVEL, "handlers": ["stdout"], "propagate": False},
        "httpx": {"level": "WARNING"},
        "httpcore": {"level": "WARNING"},
        "urllib3": {"level": "WARNING"},
        "google_genai": {"level": "WARNING"},
        "opentelemetry": {"level": "CRITICAL", "propagate": False},
    },
    "root": {"level": "WARNING", "handlers": ["stdout"]},
}


def setup_logging() -> None:
    dictConfig(LOGGING_CONFIG)


setup_logging()

logger = logging.getLogger("parley")
