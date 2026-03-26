"""Tests for vault management endpoints: health, heatmap, drift."""
import os
import json
import sqlite3
import pytest
from unittest.mock import patch, MagicMock


def test_vault_heatmap_empty(client):
    resp = client.get("/api/vault/heatmap")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert isinstance(data["files"], list)


def test_vault_heatmap_counts_sources(client, db):
    """Heatmap should count files from query history sources."""
    db.save_query(
        "sess1", 1, "q", "r",
        [{"filename": "repo__file_a", "snippet": "..."}],
        {}, {}, 100, 0
    )
    db.save_query(
        "sess1", 2, "q2", "r2",
        [{"filename": "repo__file_a", "snippet": "..."}, {"filename": "repo__file_b", "snippet": "..."}],
        {}, {}, 100, 0
    )
    resp = client.get("/api/vault/heatmap")
    files = resp.json()["files"]
    by_name = {f["path"]: f["count"] for f in files}
    assert by_name.get("repo__file_a") == 2
    assert by_name.get("repo__file_b") == 1


def test_vault_health_score_range(client):
    resp = client.get("/api/vault/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    score = data["score"]
    assert 0 <= score <= 100


def test_vault_health_has_dimensions(client):
    data = client.get("/api/vault/health").json()
    dims = data["dimensions"]
    expected = {"coverage", "freshness", "documentation", "activity", "hallucination"}
    assert set(dims.keys()) == expected


def test_vault_health_weights_sum_to_100(client):
    data = client.get("/api/vault/health").json()
    total_weight = sum(d["weight"] for d in data["dimensions"].values())
    assert total_weight == 100


def test_vault_drift_returns_structure(client):
    resp = client.get("/api/vault/drift")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "drifted" in data
    assert "fresh" in data
    assert "never_indexed" in data
    assert isinstance(data["drifted"], list)


def test_chunks_stats_structure(client):
    resp = client.get("/api/chunks/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "total_chunks" in data
    assert "avg_size_chars" in data
    assert isinstance(data["size_distribution"], list)
    assert isinstance(data["top_files"], list)
