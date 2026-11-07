import logging
import os

from langchain_core.embeddings import Embeddings

from parley.config import settings

logger = logging.getLogger(__name__)


def build_embeddings() -> Embeddings:
    provider = settings.embeddings_provider.lower()
    logger.debug("build_embeddings provider=%s", provider)

    if provider == "google":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        # The SDK reads GOOGLE_API_KEY from os.environ; bridge it from settings.
        if settings.google_api_key:
            os.environ.setdefault("GOOGLE_API_KEY", settings.google_api_key)
        return GoogleGenerativeAIEmbeddings(model=settings.embeddings_model_google)

    if provider == "huggingface":
        from langchain_huggingface import HuggingFaceEmbeddings

        return HuggingFaceEmbeddings(model_name=settings.embeddings_model_hf)

    raise ValueError(f"Unknown embeddings provider: {provider}")
