from fastapi.testclient import TestClient

from parley.api import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_chat_ok(monkeypatch):
    # ask is imported into routes.chat; patch it there so no LLM/engine runs.
    monkeypatch.setattr(
        "parley.api.routes.chat.ask",
        lambda question: {
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
        },
    )
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
