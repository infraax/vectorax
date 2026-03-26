"""
Shared pytest fixtures for VectorMap test suite.
Uses FastAPI TestClient, a temp SQLite DB, and a temp vault directory.
Mocks ChromaDB and LLM calls to avoid hitting live services.
"""
import os
import sys
import json
import sqlite3
import tempfile
import pytest
from unittest.mock import MagicMock, patch

# Add src/ to path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# ──────────────────────────────────────────
# Vault directory fixture
# ──────────────────────────────────────────
@pytest.fixture
def vault_dir(tmp_path):
    """Creates a temp Obsidian vault with a handful of .md files."""
    for name in ["alpha__module_a", "beta__module_b", "gamma__module_c"]:
        md = tmp_path / f"{name}.md"
        md.write_text(f"# {name}\n\nThis is the content of {name}.\n" * 50)
    return tmp_path

# ──────────────────────────────────────────
# SQLite DB fixture
# ──────────────────────────────────────────
@pytest.fixture
def db(tmp_path):
    """Temp SQLite database with full schema initialised."""
    db_path = tmp_path / "test_history.db"
    import query_history as qh
    original = qh.HISTORY_DB
    qh.HISTORY_DB = str(db_path)
    qh.init_db()
    yield qh
    qh.HISTORY_DB = original

# ──────────────────────────────────────────
# Mock ChromaDB collection
# ──────────────────────────────────────────
@pytest.fixture
def mock_collection():
    """A MagicMock mimicking a ChromaDB collection."""
    col = MagicMock()
    col.count.return_value = 100
    # Returns a dict with numpy-array-like embeddings
    import numpy as np
    dummy_embs = np.random.randn(100, 384).tolist()
    dummy_meta = [{"source": f"repo__{i}"} for i in range(100)]
    dummy_ids  = [f"chunk_{i}" for i in range(100)]
    col.get.return_value = {
        "embeddings": dummy_embs,
        "metadatas": dummy_meta,
        "documents": [f"content of chunk {i}" for i in range(100)],
        "ids": dummy_ids,
    }
    col.delete.return_value = None
    return col

# ──────────────────────────────────────────
# FastAPI TestClient
# ──────────────────────────────────────────
@pytest.fixture
def client(tmp_path, db, mock_collection):
    """
    FastAPI TestClient with ChromaDB, LLM, and SQLite all mocked.
    Patches langgraph_agent internals so no Ollama or HuggingFace calls happen.
    """
    from fastapi.testclient import TestClient

    with patch("langgraph_agent.vector_db") as mock_vdb, \
         patch("langgraph_agent.llm") as mock_llm, \
         patch("langgraph_agent.embeddings") as mock_emb:

        # Mock vector_db
        mock_vdb._collection = mock_collection
        mock_vdb.similarity_search_with_score.return_value = [
            (MagicMock(page_content="test content", metadata={"source": "repo__file_a"}), 0.3),
            (MagicMock(page_content="more content",  metadata={"source": "repo__file_b"}), 0.5),
        ]
        mock_vdb.similarity_search.return_value = [
            MagicMock(page_content="test content", metadata={"source": "repo__file_a"}),
        ]

        # Mock LLM
        mock_llm.invoke.return_value = MagicMock(
            content="Answer here.\n\n## Stack Trace & Sources\n[[repo__file_a]]"
        )

        import server
        from server import fastapi_app
        yield TestClient(fastapi_app)
