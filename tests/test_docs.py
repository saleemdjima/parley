from fastapi.testclient import TestClient

import parley.api.routes.docs as docs_route
from parley.api import app
from parley.config import settings

client = TestClient(app)

TXT = {"file": ("notes.txt", b"hello world", "text/plain")}


def test_documents_locked_without_configured_key(monkeypatch):
    monkeypatch.setattr(settings, "api_key", "")
    resp = client.post("/documents", files=TXT)
    assert resp.status_code == 503


def test_documents_rejects_bad_key(monkeypatch):
    monkeypatch.setattr(settings, "api_key", "secret")
    resp = client.post("/documents", files=TXT, headers={"X-API-Key": "wrong"})
    assert resp.status_code == 401


def test_documents_rejects_unsupported_type(monkeypatch):
    monkeypatch.setattr(settings, "api_key", "secret")
    resp = client.post(
        "/documents",
        files={"file": ("x.exe", b"data", "application/octet-stream")},
        headers={"X-API-Key": "secret"},
    )
    assert resp.status_code == 415


def test_documents_ok(monkeypatch):
    # Patch the ingest path so no embedding / Chroma write happens.
    monkeypatch.setattr(settings, "api_key", "secret")
    monkeypatch.setattr(docs_route, "documents_from_upload", lambda name, data: ["doc"])
    monkeypatch.setattr(docs_route, "ingest_documents", lambda chunks: 3)
    resp = client.post("/documents", files=TXT, headers={"X-API-Key": "secret"})
    assert resp.status_code == 200
    assert resp.json() == {"source": "notes.txt", "added_chunks": 3}
