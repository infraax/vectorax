"""Tests for PCA vector map generation — especially the batched fetch fix."""
import pytest
import numpy as np
from unittest.mock import MagicMock, patch, call


def _make_batch(start, size, total_dims=384):
    """Helper: generate a batch response dict as ChromaDB would return."""
    count = min(size, max(0, 100 - start))  # cap at 100 total chunks
    if count == 0:
        return {"embeddings": [], "metadatas": []}
    return {
        "embeddings": np.random.randn(count, total_dims).tolist(),
        "metadatas": [{"source": f"repo__{start + i}"} for i in range(count)],
    }


def test_get_vector_map_data_returns_points():
    """get_vector_map_data should return a list of dicts with x, y, z, name, repo."""
    from langgraph_agent import get_vector_map_data

    col = MagicMock()
    col.count.return_value = 10
    # First batch returns 10 points, second returns empty
    col.get.side_effect = [
        {
            "embeddings": np.random.randn(10, 384).tolist(),
            "metadatas": [{"source": f"sdk__file_{i}"} for i in range(10)],
        },
        {"embeddings": [], "metadatas": []},
    ]

    with patch("langgraph_agent.vector_db") as mock_vdb:
        mock_vdb._collection = col
        points = get_vector_map_data()

    assert len(points) == 10
    for pt in points:
        assert "x" in pt and "y" in pt and "z" in pt
        assert "name" in pt and "repo" in pt
        assert isinstance(pt["x"], float)


def test_get_vector_map_data_batches_correctly():
    """With 1100 chunks and BATCH=500, should call collection.get 3 times."""
    from langgraph_agent import get_vector_map_data

    TOTAL = 1100
    BATCH = 500

    call_count = [0]
    def fake_get(include, limit, offset):
        call_count[0] += 1
        remaining = TOTAL - offset
        size = min(limit, remaining)
        if size <= 0:
            return {"embeddings": [], "metadatas": []}
        return {
            "embeddings": np.random.randn(size, 384).tolist(),
            "metadatas": [{"source": f"repo__f{offset + i}"} for i in range(size)],
        }

    col = MagicMock()
    col.count.return_value = TOTAL
    col.get.side_effect = fake_get

    with patch("langgraph_agent.vector_db") as mock_vdb:
        mock_vdb._collection = col
        points = get_vector_map_data()

    # Should have fetched all 1100 points
    assert len(points) == TOTAL
    # Should have called get 3 times: offsets 0, 500, 1000
    assert call_count[0] == 3


def test_get_vector_map_data_empty_collection():
    from langgraph_agent import get_vector_map_data

    col = MagicMock()
    col.count.return_value = 0

    with patch("langgraph_agent.vector_db") as mock_vdb:
        mock_vdb._collection = col
        points = get_vector_map_data()

    assert points == []


def test_get_vector_map_data_repo_extraction():
    """Repo name should be extracted from source name before '__'."""
    from langgraph_agent import get_vector_map_data

    col = MagicMock()
    col.count.return_value = 5
    col.get.side_effect = [
        {
            "embeddings": np.random.randn(5, 384).tolist(),
            "metadatas": [
                {"source": "vector-python-sdk__some_file"},
                {"source": "wire-pod__module_x"},
                {"source": "no_double_underscore"},
                {"source": "alpha__beta__gamma"},
                {"source": ""},
            ],
        },
        {"embeddings": [], "metadatas": []},
    ]

    with patch("langgraph_agent.vector_db") as mock_vdb:
        mock_vdb._collection = col
        points = get_vector_map_data()

    repos = [pt["repo"] for pt in points]
    assert repos[0] == "vector-python-sdk"
    assert repos[1] == "wire-pod"
    assert repos[2] == "unknown"   # no __ → unknown
    assert repos[3] == "alpha"     # first __ only


def test_vector_map_endpoint(client):
    """GET /api/vector_map should return status and points list."""
    resp = client.get("/api/vector_map")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("online", "error")
    if data["status"] == "online":
        assert isinstance(data["points"], list)
