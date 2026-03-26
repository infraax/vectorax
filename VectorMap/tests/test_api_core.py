"""Tests for core API endpoints: /status, /api/config, /api/memory, /api/log/stream."""
import json
import pytest


def test_status_returns_online(client):
    resp = client.get("/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "online"


def test_status_has_hardware(client):
    data = client.get("/status").json()
    hw = data["stats"]["hardware"]
    assert "cpu_percent" in hw
    assert "ram_percent" in hw
    assert "server_rss_mb" in hw


def test_status_has_ports(client):
    data = client.get("/status").json()
    ports = data["stats"]["ports"]
    assert "fastapi" in ports
    assert "ollama" in ports
    assert "obsidian" in ports
    assert ports["fastapi"]["status"] == "ONLINE"


def test_get_config(client):
    resp = client.get("/api/config")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    cfg = data["config"]
    assert "model" in cfg
    assert "temperature" in cfg
    assert "memory_turns" in cfg
    assert "web_search" in cfg


def test_update_config_temperature(client):
    resp = client.post("/api/config", json={"temperature": 0.5})
    assert resp.status_code == 200
    data = resp.json()
    assert data["applied"]["temperature"] == 0.5
    assert data["config"]["temperature"] == 0.5


def test_update_config_memory_turns(client):
    resp = client.post("/api/config", json={"memory_turns": 6})
    assert resp.status_code == 200
    assert client.get("/api/config").json()["config"]["memory_turns"] == 6


def test_update_config_web_search(client):
    resp = client.post("/api/config", json={"web_search": True})
    assert resp.status_code == 200
    assert client.get("/api/config").json()["config"]["web_search"] is True
    # Reset
    client.post("/api/config", json={"web_search": False})


def test_memory_starts_empty(client):
    resp = client.get("/api/memory")
    assert resp.status_code == 200
    assert resp.json()["turns"] == 0
    assert resp.json()["buffer"] == []


def test_clear_memory(client):
    import langgraph_agent as _a
    _a._CONV_BUFFER.append({"role": "user", "content": "hello"})
    resp = client.delete("/api/memory")
    assert resp.status_code == 200
    assert client.get("/api/memory").json()["turns"] == 0


def test_log_stream_returns_entries(client):
    resp = client.get("/api/log/stream?since=0")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert isinstance(data["entries"], list)


def test_log_stream_since_filter(client):
    # Large since value should return no entries
    resp = client.get("/api/log/stream?since=999999")
    assert resp.json()["entries"] == []


def test_serve_ui_returns_html(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "<!DOCTYPE html>" in resp.text or "<html" in resp.text
