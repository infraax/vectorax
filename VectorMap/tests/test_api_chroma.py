"""Tests for ChromaDB CRUD explorer endpoints."""
import pytest
from unittest.mock import MagicMock, patch


def test_chroma_search_returns_chunks(client):
    resp = client.get("/api/chroma/search?q=motor+controller&limit=5")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert isinstance(data["chunks"], list)
    # Each chunk has required fields
    if data["chunks"]:
        chunk = data["chunks"][0]
        assert "source" in chunk
        assert "snippet" in chunk
        assert "score" in chunk


def test_chroma_search_score_range(client):
    resp = client.get("/api/chroma/search?q=test&limit=10")
    for chunk in resp.json()["chunks"]:
        assert 0.0 <= chunk["score"] <= 1.0


def test_chroma_file_returns_chunks(client, mock_collection):
    mock_collection.get.return_value = {
        "ids": ["chunk_0", "chunk_1"],
        "documents": ["content A", "content B"],
        "metadatas": [{"source": "file_a"}, {"source": "file_a"}],
        "embeddings": None,
    }
    resp = client.get("/api/chroma/file?source=file_a")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["source"] == "file_a"
    assert len(data["chunks"]) == 2


def test_chroma_delete_chunk(client, mock_collection):
    resp = client.delete("/api/chroma/chunk/chunk_0")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["deleted"] == "chunk_0"
    mock_collection.delete.assert_called_once_with(ids=["chunk_0"])


def test_chroma_reindex_file_not_found(client):
    resp = client.post("/api/chroma/reindex", json={"source": "nonexistent_file_xyz"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "error"
    assert "not found" in resp.json()["message"].lower()


def test_vector_search_returns_hits(client):
    resp = client.post("/api/vector_search", json={"query": "motor driver", "k": 5})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert isinstance(data["hits"], list)
    if data["hits"]:
        hit = data["hits"][0]
        assert "name" in hit
        assert "score" in hit
        assert 0.0 <= hit["score"] <= 1.0
