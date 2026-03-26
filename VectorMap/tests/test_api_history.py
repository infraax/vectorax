"""Tests for query history, template, and hallucination endpoints."""
import pytest


def test_query_history_empty(client):
    resp = client.get("/api/query_history")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert isinstance(data["history"], list)


def test_query_history_detail_not_found(client):
    resp = client.get("/api/query_history/99999")
    assert resp.status_code == 200
    assert resp.json()["status"] == "error"


def test_templates_empty(client):
    resp = client.get("/api/templates")
    assert resp.status_code == 200
    assert resp.json()["templates"] == []


def test_create_template(client):
    resp = client.post("/api/templates", json={"name": "Motor Query", "template": "Explain {component}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "id" in data

    templates = client.get("/api/templates").json()["templates"]
    assert len(templates) == 1
    assert templates[0]["name"] == "Motor Query"


def test_delete_template(client):
    tid = client.post("/api/templates", json={"name": "Del", "template": "t"}).json()["id"]
    resp = client.delete(f"/api/templates/{tid}")
    assert resp.status_code == 200
    assert client.get("/api/templates").json()["templates"] == []


def test_delete_template_not_found(client):
    resp = client.delete("/api/templates/99999")
    assert resp.status_code == 404


def test_hallucinations_empty(client):
    resp = client.get("/api/hallucinations")
    assert resp.status_code == 200
    assert resp.json()["hallucinations"] == []


def test_hallucination_detail_not_found(client):
    resp = client.get("/api/hallucinations/99999")
    assert resp.status_code == 200
    assert resp.json()["status"] == "error"
