import logging
import os
import tempfile

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from parley.config import settings
from parley.rag.documents import load_docs
from parley.rag.retriever import load_store

logger = logging.getLogger(__name__)


def ingest_documents(docs: list[Document]) -> int:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    chunks = splitter.split_documents(docs)
    load_store().add_documents(chunks)
    logger.debug("ingest_documents added %d chunks", len(chunks))
    return len(chunks)


def build_index(docs_dir: str | None = None) -> int:
    # Full (re)build from the docs directory.
    return ingest_documents(load_docs(docs_dir))


def documents_from_upload(name: str, data: bytes) -> list[Document]:
    # Turn an uploaded file's bytes into Documents. PDFs go through PyPDFLoader
    # (via a temp file, since it takes a path); everything else is treated as text.
    if name.lower().endswith(".pdf"):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(data)
            path = tmp.name
        try:
            pages = PyPDFLoader(path).load()
        finally:
            os.unlink(path)
        for page in pages:
            page.metadata.setdefault("source", name)
        return pages

    text = data.decode("utf-8", errors="replace")
    return [Document(page_content=text, metadata={"source": name})]
