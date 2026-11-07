import logging

from fastapi import APIRouter, HTTPException

from parley.agent import aask
from parley.api.models import ChatRequest, ChatResponse
from parley.errors import InvalidQuestion
from parley.guards import validate_question

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


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
