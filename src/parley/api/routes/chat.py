import asyncio
import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from parley.agent import aask
from parley.api.models import ChatRequest, ChatResponse
from parley.errors import InvalidQuestion
from parley.graph import astream_run
from parley.guards import validate_question
from parley.sql.catalog import get_catalog

logger = logging.getLogger(__name__)

router = APIRouter()

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


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


@router.get("/chat/stream")
async def chat_stream(message: str) -> StreamingResponse:
    try:
        question = validate_question(message)
    except InvalidQuestion as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    logger.debug("chat_stream message=%r", question)

    async def events() -> AsyncIterator[str]:
        async for event in astream_run(question):
            payload = json.dumps(event, default=str)
            yield f"event: {event['kind']}\ndata: {payload}\n\n"

    return StreamingResponse(
        events(), media_type="text/event-stream", headers=SSE_HEADERS
    )
