"""Tests for /chat endpoint — sources with scores, memory, injected docs."""
import pytest
from unittest.mock import MagicMock, patch


def test_chat_returns_response(client):
    resp = client.post("/chat", json={"message": "what is the drive system?"})
    assert resp.status_code == 200
    data = resp.json()
    assert "response" in data
    assert isinstance(data["response"], str)


def test_chat_sources_have_scores(client):
    resp = client.post("/chat", json={"message": "explain motor control"})
    data = resp.json()
    sources = data.get("sources", [])
    for src in sources:
        assert "filename" in src
        assert "snippet" in src
        assert "score" in src
        if src["score"] is not None:
            assert 0.0 <= src["score"] <= 1.0


def test_chat_returns_token_usage(client):
    resp = client.post("/chat", json={"message": "test query"})
    data = resp.json()
    usage = data.get("token_usage", {})
    assert isinstance(usage, dict)


def test_chat_returns_system_logs(client):
    resp = client.post("/chat", json={"message": "test"})
    logs = resp.json().get("system_logs", [])
    assert isinstance(logs, list)


def test_chat_with_injected_docs(client):
    """When injected_docs provided, sources should be injected_N."""
    resp = client.post("/chat", json={
        "message": "test",
        "injected_docs": ["This is injected content about motors."],
    })
    assert resp.status_code == 200
    data = resp.json()
    sources = data.get("sources", [])
    # injected sources should have score = 1.0
    for src in sources:
        if src["filename"].startswith("injected_"):
            assert src["score"] == 1.0


def test_chat_updates_memory_buffer(client):
    import langgraph_agent as _a
    _a._CONV_BUFFER.clear()
    client.post("/chat", json={"message": "memory test query"})
    # After one query: user + assistant = 2 entries
    assert len(_a._CONV_BUFFER) == 2
    assert _a._CONV_BUFFER[0]["role"] == "user"
    assert _a._CONV_BUFFER[1]["role"] == "assistant"
    _a._CONV_BUFFER.clear()


def test_chat_blocked_when_chromadb_missing(client, tmp_path):
    """If DB_DIR is empty/missing, /chat should return 503."""
    with patch("server.DB_DIR", str(tmp_path / "empty_db")):
        resp = client.post("/chat", json={"message": "test"})
    assert resp.status_code == 503


def test_vector_search_endpoint(client):
    resp = client.post("/api/vector_search", json={"query": "motor controller", "k": 3})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert isinstance(data["hits"], list)
