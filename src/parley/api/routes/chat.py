import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from parley.agent import aask
from parley.api.models import ChatRequest, ChatResponse
from parley.errors import InvalidQuestion
from parley.graph import astream_run, get_history
from parley.guards import validate_question
from parley.memory.conversations import list_conversations
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
    thread_id = request.thread_id or uuid.uuid4().hex
    logger.debug("chat message=%r thread=%s", question, thread_id)
    # aask() is the async agent path (the hybrid route runs its branches concurrently).
    result = await aask(question, thread_id, request.user_id, request.language)
    return ChatResponse(thread_id=thread_id, **result)


@router.get("/chat/stream")
async def chat_stream(
    message: str,
    thread_id: str | None = None,
    user_id: str | None = None,
    language: str | None = None,
) -> StreamingResponse:
    try:
        question = validate_question(message)
    except InvalidQuestion as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    resolved_thread = thread_id or uuid.uuid4().hex
    logger.debug("chat_stream message=%r thread=%s", question, resolved_thread)

    async def events() -> AsyncIterator[str]:
        async for event in astream_run(question, resolved_thread, user_id, language):
            if event["kind"] == "result":
                event["result"]["thread_id"] = resolved_thread
            payload = json.dumps(event, default=str)
            yield f"event: {event['kind']}\ndata: {payload}\n\n"

    return StreamingResponse(
        events(), media_type="text/event-stream", headers=SSE_HEADERS
    )


@router.get("/conversations")
async def conversations(request: Request, user_id: str) -> dict:
    store = getattr(request.app.state, "store", None)
    if store is None:
        return {"conversations": []}
    return {"conversations": await list_conversations(store, user_id)}


@router.get("/conversations/{thread_id}")
async def conversation(thread_id: str, user_id: str | None = None) -> dict:
    return {"thread_id": thread_id, "history": await get_history(thread_id, user_id)}
