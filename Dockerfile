FROM python:3.14-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1
WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

COPY scripts ./scripts
COPY data/docs ./data/docs
RUN --mount=type=secret,id=google_api_key \
    GOOGLE_API_KEY="$(cat /run/secrets/google_api_key)" \
    /app/.venv/bin/python scripts/build_index.py


FROM python:3.14-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"
WORKDIR /app

RUN useradd --create-home --uid 1000 appuser
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/data /app/data
USER appuser

EXPOSE 8080

# Cloud Run injects $PORT (defaults to 8080).
CMD ["sh", "-c", "uvicorn parley.api:app --host 0.0.0.0 --port ${PORT:-8080}"]
