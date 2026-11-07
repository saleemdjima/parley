from fastapi import Header, HTTPException

from parley.config import settings


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if not settings.api_key:
        raise HTTPException(status_code=503, detail="Server API key not configured.")
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")
