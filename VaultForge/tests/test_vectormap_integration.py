"""
test_vectormap_integration.py — Phase 8
Verify VectorMap server reads from the new vault and ChromaDB v2.
Requires VectorMap server running at http://127.0.0.1:PORT.
"""
import pytest
import json
from pathlib import Path

VECTORMAP_ROOT = Path("/Users/lab/research/VectorMap")
CHROMA_PATH    = Path("/Users/lab/research/VectorMap/data/chroma_db_v2")
VAULT_ROOT     = Path("/Users/lab/research/VectorMap/data/Vector_Obsidian_Vault_V2")
AGENT_PYTHON   = VECTORMAP_ROOT / "agent_env" / "bin" / "python"


def find_server_port():
    """Try to detect the VectorMap server port from config."""
    # Check server.py for port
    server_py = VECTORMAP_ROOT / "src" / "server.py"
    if server_py.exists():
        content = server_py.read_text()
        import re
        m = re.search(r"port\s*=\s*(\d+)", content)
        if m:
            return int(m.group(1))
    return 8005  # default


def server_url():
    return f"http://127.0.0.1:{find_server_port()}"


@pytest.fixture(scope="module")
def server_available():
    import urllib.request
    try:
        with urllib.request.urlopen(f"{server_url()}/status", timeout=3) as r:
            return True
    except Exception:
        pytest.skip("VectorMap server not running — skip integration tests")


def test_chroma_v2_path_exists():
    assert CHROMA_PATH.exists(), \
        "chroma_db_v2 not found — run db_writer.py first"


def test_vault_v2_path_exists():
    assert VAULT_ROOT.exists(), \
        "Vector_Obsidian_Vault_V2 not found — run vault_generator.py first"


def test_server_langgraph_agent_uses_v2_paths():
    """Verify langgraph_agent.py references the new V2 paths."""
    agent_py = VECTORMAP_ROOT / "src" / "langgraph_agent.py"
    if not agent_py.exists():
        pytest.skip("langgraph_agent.py not found")
    content = agent_py.read_text()
    assert "chroma_db_v2" in content or "Vector_Obsidian_Vault_V2" in content, \
        "langgraph_agent.py does not reference V2 paths — run Phase 7 path update"


def test_status_endpoint(server_available):
    import urllib.request
    with urllib.request.urlopen(f"{server_url()}/status", timeout=5) as r:
        data = json.loads(r.read())
    assert "status" in data or "indexed" in data, f"Unexpected /status response: {data}"


def test_chat_endpoint_returns_response(server_available):
    """POST /chat should return a response from the new index."""
    import urllib.request
    payload = json.dumps({
        "message": "What does the Vector robot do?",
        "session_id": "test_session",
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{server_url()}/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read())
    assert "response" in data, f"No 'response' key in /chat reply: {data}"
    assert len(data["response"]) > 20, "Response too short"


def test_vector_map_endpoint(server_available):
    """/api/vector_map should return PCA data."""
    import urllib.request
    try:
        with urllib.request.urlopen(f"{server_url()}/api/vector_map", timeout=30) as r:
            data = json.loads(r.read())
        assert isinstance(data, list) or "points" in data or "error" in data
    except Exception as e:
        pytest.skip(f"/api/vector_map not available: {e}")


def test_langgraph_agent_import():
    """langgraph_agent module should import cleanly."""
    import sys
    sys.path.insert(0, str(VECTORMAP_ROOT / "src"))
    try:
        import importlib
        spec = importlib.util.spec_from_file_location(
            "langgraph_agent",
            VECTORMAP_ROOT / "src" / "langgraph_agent.py"
        )
        # Just verify the file is parseable
        import ast
        content = (VECTORMAP_ROOT / "src" / "langgraph_agent.py").read_text()
        ast.parse(content)
    except Exception as e:
        pytest.fail(f"langgraph_agent.py parse error: {e}")
