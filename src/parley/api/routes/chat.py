import asyncio
import logging

from fastapi import APIRouter, HTTPException

from parley.agent import aask
from parley.api.models import ChatRequest, ChatResponse
from parley.errors import InvalidQuestion
from parley.guards import validate_question
from parley.sql.catalog import get_catalog

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/stats")
async def stats() -> dict:
    # What the catalog knows about the dataset: coverage + the cheap row count.
    catalog = await asyncio.to_thread(get_catalog)
    return {
        "total_rows": catalog.total_rows,
        "coverage": catalog.coverage(),
        "sources": len(catalog.sources),
        "columns": catalog.column_names(),
    }


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        question = validate_question(request.message)
    except InvalidQuestion as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    logger.debug("chat message=%r", question)
    # aask() is the async agent path (the hybrid route runs its branches concurrently).
    result = await aask(question)
    return ChatResponse(**result)
