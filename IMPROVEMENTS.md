# Improvements backlog

Deferred work, roughly in priority order. Nothing here blocks the current demo.

## Latency (single query ~10s; dominated by 2 sequential Gemini calls)

- **Cheaper router model.** `classify` only needs one word (`sql`/`rag`/`hybrid`);
  run it on a `flash-lite`-class model via a `router_model` setting while keeping
  `flash` for extraction. Est. ~2s saved. (Measured: DuckDB-over-HTTP is only 0.76s,
  so the LLM calls are the whole cost.)
- **Memoize `chat_model()`** so the HTTP connection is pooled across calls instead of
  a fresh TLS handshake each time. Small (~0.3-0.5s), cheap, no downside.
- **One LLM call instead of two.** Merge routing + intent extraction into a single
  structured-output call. Biggest cut (~3-4s) but collapses the router/extractor
  separation -- architectural trade-off, not a free win.

## Correctness / UX

- **SQL-path prose answer.** Pure-SQL queries return `rows` but `answer` is null.
  Add a one-line `llm.answer(...)` summary (or decide the UI formats rows).

## Features not yet reproduced

- **RAG path** (`rag/` + Chroma index) -- unlocks definitional + hybrid questions.
- **Parallelize the hybrid route.** `sql_node` and `rag_node` are independent until
  `merge` -- they could run concurrently (async/threads) instead of sequentially.
  The one place concurrency genuinely helps per-query latency.
- **API layer** (`api.py` + typed models) for HTTP / the frontend.
- **Eval harness** (`eval/`) -- regression cases with latency/token/cost (now that
  tracking is wired).
- **Slack connector**.

## Security

- **Protect `POST /documents`.** It's a write endpoint that mutates the shared Chroma
  index -- unauthenticated, anyone reachable can poison the RAG knowledge base or run
  up embedding cost. Add an API-key / auth dependency before any real deployment.
  (Type allowlist + 10 MB cap are in place, but that's not auth.)

## Tests to add

- `test_engines.py` (engine seam), `test_graph_routing.py`, `test_graph_integration.py`.
- `test_docs.py` for `/documents` (415/413/empty + a mocked-ingest success).
