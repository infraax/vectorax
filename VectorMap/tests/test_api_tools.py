"""Tests for intelligence tool endpoints: benchmark, refactor, arch graph, export, robot log."""
import os
import json
import pytest
from unittest.mock import MagicMock, patch


def test_benchmark_returns_results(client):
    """POST /api/benchmark should return results for both models."""
    with patch("langchain_ollama.ChatOllama") as MockOllama:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="Answer from model.")
        MockOllama.return_value = mock_llm

        resp = client.post("/api/benchmark", json={
            "message": "What is the drive system?",
            "model_a": "qwen2.5-coder:7b",
            "model_b": "llama3:latest",
        })

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "qwen2.5-coder:7b" in data["results"]
    assert "llama3:latest" in data["results"]


def test_benchmark_model_error_handled(client):
    """If one model fails, its result should have an 'error' key."""
    with patch("langchain_ollama.ChatOllama") as MockOllama:
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = Exception("Model not found")
        MockOllama.return_value = mock_llm

        resp = client.post("/api/benchmark", json={
            "message": "test",
            "model_a": "bad_model",
            "model_b": "also_bad",
        })

    data = resp.json()
    assert data["status"] == "ok"
    for model_result in data["results"].values():
        assert "error" in model_result


def test_refactor_file_not_found(client):
    resp = client.post("/api/tools/refactor", json={
        "filepath": "/nonexistent/path/file.py",
        "mode": "refactor",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "error"


def test_refactor_real_file(client, tmp_path):
    """Refactor a real temp file — LLM is mocked."""
    test_file = tmp_path / "sample.py"
    test_file.write_text("def foo():\n    return 1+1\n")

    with patch("langgraph_agent.llm") as mock_llm:
        mock_llm.invoke.return_value = MagicMock(content="def foo():\n    return 2\n")
        resp = client.post("/api/tools/refactor", json={
            "filepath": str(test_file),
            "mode": "refactor",
        })

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "original" in data
    assert "refactored" in data


def test_arch_graph_returns_nodes_and_edges(client, tmp_path):
    """Arch graph with a real temp file and mocked LLM."""
    f1 = tmp_path / "module_a.py"
    f1.write_text("import os\ndef func_a(): pass\n")

    graph_json = '{"nodes": [{"id": "module_a", "label": "module_a", "type": "file"}], "edges": []}'

    with patch("langgraph_agent.llm") as mock_llm:
        mock_llm.invoke.return_value = MagicMock(content=graph_json)
        resp = client.post("/api/tools/arch_graph", json={"files": [str(f1)]})

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "nodes" in data["graph"]
    assert "edges" in data["graph"]


def test_robot_log_stream_file_not_found(client):
    resp = client.get("/api/robot/log/stream?path=/nonexistent/log.txt")
    assert resp.status_code == 200
    assert resp.json()["status"] == "error"


def test_robot_log_stream_reads_lines(client, tmp_path):
    log_file = tmp_path / "vector.log"
    log_file.write_text("\n".join(f"log line {i}" for i in range(200)))
    resp = client.get(f"/api/robot/log/stream?path={log_file}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert len(data["lines"]) <= 100
    assert data["total_lines"] == 200


def test_obsidian_export_no_history(client):
    resp = client.post("/api/export/obsidian", json={
        "session_id": "nonexistent_session_xyz",
        "title": "Test Export",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "error"


def test_obsidian_export_writes_file(client, db, tmp_path):
    """Export should write a .md file when history exists."""
    db.save_query("sess_export", 1, "What is X?", "X is Y.\n\n## Stack Trace & Sources\n[[f]]",
                  [{"filename": "f", "snippet": "..."}], {}, {}, 500, 0)

    with patch("langgraph_agent.VAULT_DIR", str(tmp_path)):
        resp = client.post("/api/export/obsidian", json={
            "session_id": "sess_export",
            "title": "My Export",
        })

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert os.path.exists(data["path"])
    content = open(data["path"]).read()
    assert "My Export" in content
    assert "What is X?" in content
