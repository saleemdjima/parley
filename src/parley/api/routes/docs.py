import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from parley.api.deps import require_api_key
from parley.rag.ingest import documents_from_upload, ingest_documents

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_SUFFIXES = {".pdf", ".txt", ".md"}


@router.post("/documents", dependencies=[Depends(require_api_key)])
async def add_document(file: UploadFile) -> dict:
    name = file.filename or "upload"
    suffix = Path(name).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported type {suffix!r}; allowed: {sorted(ALLOWED_SUFFIXES)}",
        )
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file.")
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 10 MB).")

    # Chunking + embedding + Chroma write are blocking; keep the event loop free.
    added = await asyncio.to_thread(
        lambda: ingest_documents(documents_from_upload(name, data))
    )
    logger.debug("add_document name=%r added_chunks=%d", name, added)
    return {"source": name, "added_chunks": added}
