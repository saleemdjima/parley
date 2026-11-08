import asyncio
import logging
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from parley.api.routes.chat import router as chat_router
from parley.api.routes.docs import router as docs_router
from parley.config import settings, setup_logging
from parley.sql.catalog import get_catalog

logger = logging.getLogger(__name__)


async def warm_catalog() -> None:
    try:
        await asyncio.to_thread(get_catalog)
    except Exception:
        logger.exception("catalog warm-up failed")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    task = asyncio.create_task(warm_catalog())
    yield
    task.cancel()


def create_app() -> FastAPI:
    setup_logging()
    app = FastAPI(title="parley", version="0.1.0", lifespan=lifespan)

    origins = [o.strip() for o in settings.cors_allow_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = uuid.uuid4().hex[:8]
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request id=%s %s %s -> %s %.1fms",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response

    app.include_router(chat_router)
    app.include_router(docs_router)
    return app


app = create_app()
