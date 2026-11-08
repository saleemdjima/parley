# parley

parley is a small analytics agent for New York City's yellow-taxi data. You ask it
something in plain English — *"what was the average fare last January?"*, *"which
payment type tips the most?"*, *"what does RatecodeID 5 actually mean?"* — and it
works out whether that's a question for the data, for the documentation, or both,
answers it, and shows its work.

There's one rule it never breaks: **the language model doesn't write SQL.** It reads
your question and fills in a small, typed description of what you're after — a metric,
some filters, maybe a grouping. Ordinary Python turns that into the real query. The
model is a translator, not something you'd ever hand a database connection to, so the
worst it can do is misunderstand you. It can't drop a table, invent a column, or slip
something past a `WHERE` clause.

## Running it

You'll need [uv](https://docs.astral.sh/uv/) and a Google Gemini API key.

```bash
uv sync
export GOOGLE_API_KEY=your-key-here        # or put it in a .env file
uv run uvicorn parley.api:app --port 8080
```

Then ask it something:

```bash
curl -s localhost:8080/chat \
  -H 'content-type: application/json' \
  -d '{"message": "what was the average fare in January?"}'
```

Notice there's no year in that question. parley knows which years the data actually
covers (more on that below), so instead of guessing, it answers for the latest year
it has — and hands back the exact SQL it ran, so you can check it.

## How it works

When a question arrives, a classifier decides where it goes: to the **data** (SQL over
the trip records), to the **docs** (a retrieval step over NYC's official data
dictionary), to **both** when you need a number *and* its definition, or — if the
question is vague or not about taxis at all — politely back to you, with a note about
what it can actually answer. No silently guessing.

The data path is the careful one. At startup parley scans the Parquet files and builds
a little catalog: which columns exist, what they're called, how many rows there are,
and which years are covered. That catalog does three jobs — it's the whitelist the
query builder checks every column against, it's what grounds the model so it stops
inventing years that aren't in the data, and it's where the row counts come from (read
straight out of the file footers, so counting a few hundred million rows is basically
free). From there a deterministic builder assembles the SQL and DuckDB runs it.

The docs path is a straightforward RAG setup: the TLC guides are chunked, embedded,
and stored in Chroma, and definitional questions pull the relevant passages before the
model answers from them.

Every response carries its own cost — tokens, dollars, latency — because an LLM feature
you can't measure is one you can't really run.

## About the data

NYC publishes years of trip records as Parquet, and parley queries them where they
live rather than copying them around. DuckDB reads only the columns and row-groups a
question needs, so a monthly average doesn't drag the whole dataset off the network.
The query engine sits behind a seam, too: DuckDB handles the lake today, and the same
typed-intent layer can point at a warehouse like ClickHouse or BigQuery when the scale
calls for it — without touching how queries are built.

## A few decisions worth calling out

- **The model is treated as untrusted.** It parses questions into typed intent; it
  never emits SQL. Columns are whitelisted, values are bound parameters.
- **Business logic lives in code, not prompts.** Metrics are a small registry mapping
  names to SQL expressions, and the prompt is rendered *from* that registry — so adding
  a dataset is a registry, not a rewrite.
- **The catalog is built once, at startup**, and grounds the whole thing in what the
  data really contains.

## Tests

There's a normal unit suite, plus a small regression set: a handful of reference
questions pinned to the SQL they're expected to produce. If a prompt tweak or a model
update quietly changes the generated SQL, the regression run catches it — and reports
the latency, tokens, and cost along the way.

## Status

This is a portfolio project and a work in progress. It runs locally today and is on its
way to Cloud Run. Still on the list: turning raw result rows into a written sentence,
a Slack bot, a web front end, and a BigQuery engine for the full multi-year dataset.
