import logging

from fastapi import APIRouter, HTTPException, Request
from langgraph.store.base import BaseStore

from parley.api.models import UserCreate, UserProfile
from parley.memory.users import create_user, get_user

logger = logging.getLogger(__name__)

router = APIRouter()


def require_store(request: Request) -> BaseStore:
    store = getattr(request.app.state, "store", None)
    if store is None:
        raise HTTPException(
            status_code=503, detail="User accounts require conversation memory."
        )
    return store


@router.post("/users", response_model=UserProfile)
async def post_user(body: UserCreate, request: Request) -> UserProfile:
    store = require_store(request)
    try:
        profile = await create_user(store, body.pseudo)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    logger.debug("post_user user=%s", profile["user_id"])
    return UserProfile(**profile)


@router.get("/users/{user_id}", response_model=UserProfile)
async def read_user(user_id: str, request: Request) -> UserProfile:
    store = require_store(request)
    profile = await get_user(store, user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Unknown user.")
    return UserProfile(**profile)
