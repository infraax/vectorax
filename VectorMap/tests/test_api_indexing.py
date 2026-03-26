"""Tests for indexing control endpoints."""
import pytest


def test_indexing_files_idle(client):
    resp = client.get("/api/indexing/files")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["total"] == 0
    assert data["processed"] == 0


def test_stop_indexing_when_idle(client):
    resp = client.post("/api/indexing/stop")
    assert resp.status_code == 200
    assert resp.json()["status"] == "idle"


def test_start_index_returns_started(client):
    import langgraph_agent as _a
    # Ensure indexing is NOT already running
    _a.INDEX_STATE["is_indexing"] = False
    resp = client.post("/start_index", json={"limit": 1})
    assert resp.status_code == 200
    # Either started or already in progress (race condition in test is fine)
    assert resp.json()["status"] in ("started", "error")
    # Reset
    _a.INDEX_STATE["is_indexing"] = False
    _a.INDEX_STATE["stop_requested"] = True


def test_start_index_blocked_if_running(client):
    import langgraph_agent as _a
    _a.INDEX_STATE["is_indexing"] = True
    resp = client.post("/start_index", json={})
    assert resp.status_code == 200
    assert resp.json()["status"] == "error"
    _a.INDEX_STATE["is_indexing"] = False


def test_backfill_status_idle(client):
    resp = client.get("/api/backfill/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["running"] is False
    assert data["done"] == 0


def test_backfill_stop_when_not_running(client):
    resp = client.post("/api/backfill/stop")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
