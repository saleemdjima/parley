import logging
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document

from parley.config import settings
from parley.rag.embeddings import build_embeddings

logger = logging.getLogger(__name__)


def load_store() -> Chroma:
    # The one place the vector store is constructed, so the local/server choice is
    # a single seam. Local persists to disk (ephemeral on Cloud Run); server talks
    # to an external Chroma so the app stays stateless and scales horizontally.
    embeddings = build_embeddings()
    if settings.chroma_mode == "server":
        import chromadb

        client = chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)
        return Chroma(
            collection_name=settings.chroma_collection,
            embedding_function=embeddings,
            client=client,
        )
    return Chroma(
        collection_name=settings.chroma_collection,
        embedding_function=embeddings,
        persist_directory=settings.chroma_dir,
    )


def retrieve(question: str, k: int | None = None) -> list[Document]:
    top_k = k or settings.retrieval_k
    hits = load_store().similarity_search(question, k=top_k)
    logger.debug("retrieve question=%r k=%d hits=%d", question, top_k, len(hits))
    return hits


def format_context(docs: list[Document]) -> str:
    blocks = []
    for doc in docs:
        source = Path(doc.metadata.get("source", "unknown")).name
        page = doc.metadata.get("page", "?")
        blocks.append(f"[{source} p.{page}]\n{doc.page_content.strip()}")
    return "\n\n".join(blocks)
