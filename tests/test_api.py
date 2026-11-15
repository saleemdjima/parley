from fastapi.testclient import TestClient

from parley.api import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_chat_ok(monkeypatch):
    # aask is imported into routes.chat; patch with an async stub so no LLM runs.
    async def fake_aask(question: str) -> dict:
        return {
            "route": "sql",
            "answer": "42",
            "sql": "SELECT COUNT(*) FROM t",
            "params": [],
            "rows": [],
            "context": None,
            "metrics": {
                "input_tokens": 10,
                "output_tokens": 2,
                "cost_usd": 0.0,
                "latency_s": 0.1,
            },
        }

    monkeypatch.setattr("parley.api.routes.chat.aask", fake_aask)
    resp = client.post("/chat", json={"message": "how many trips?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["route"] == "sql"
    assert body["answer"] == "42"
    assert body["sql"].startswith("SELECT")
    assert body["metrics"]["input_tokens"] == 10


def test_chat_rejects_empty():
    resp = client.post("/chat", json={"message": "   "})
    assert resp.status_code == 400


def test_chat_stream_emits_sse(monkeypatch):
    async def fake_stream(question: str):
        yield {"kind": "step", "node": "classify", "state": {"route": "sql"}}
        yield {"kind": "result", "result": {"route": "sql", "answer": "42"}}

    monkeypatch.setattr("parley.api.routes.chat.astream_run", fake_stream)
    with client.stream(
        "GET", "/chat/stream", params={"message": "how many trips?"}
    ) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        body = "".join(resp.iter_text())
    assert "event: step" in body
    assert "event: result" in body
    assert "42" in body


def test_chat_stream_rejects_empty():
    resp = client.get("/chat/stream", params={"message": "   "})
    assert resp.status_code == 400
