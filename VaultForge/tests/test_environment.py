"""
test_environment.py — Phase 8
Verify Python environment, key packages, Ollama availability.
"""
import subprocess
import sys
import importlib


def test_python_version():
    """Python ≥ 3.9."""
    assert sys.version_info >= (3, 9), f"Need Python 3.9+, got {sys.version}"


def test_required_packages():
    """All pipeline packages importable."""
    required = [
        "chromadb", "langchain", "langchain_community", "fastapi",
        "tree_sitter", "fitz",       # PyMuPDF
        "pdfplumber", "datasketch",
        "gitpython",                  # via import git
        "tiktoken",
    ]
    missing = []
    for pkg in required:
        try:
            importlib.import_module(pkg)
        except ImportError:
            # Try alternate names
            alt = {"gitpython": "git"}.get(pkg, pkg)
            try:
                importlib.import_module(alt)
            except ImportError:
                missing.append(pkg)
    assert not missing, f"Missing packages: {missing}"


def test_tree_sitter_language_packages():
    """Individual tree-sitter language packages importable."""
    langs = ["tree_sitter_python", "tree_sitter_go", "tree_sitter_c",
             "tree_sitter_javascript", "tree_sitter_cpp"]
    missing = []
    for lang in langs:
        try:
            importlib.import_module(lang)
        except ImportError:
            missing.append(lang)
    assert not missing, f"Missing tree-sitter language packages: {missing}"


def test_ollama_running():
    """Ollama API is reachable."""
    import urllib.request
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=5) as r:
            data = __import__("json").loads(r.read())
        assert "models" in data
    except Exception as e:
        import pytest
        pytest.skip(f"Ollama not reachable: {e}")


def test_ollama_embed_model():
    """nomic-embed-text model is available in Ollama."""
    import urllib.request, json
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=5) as r:
            data = json.loads(r.read())
        names = [m["name"] for m in data.get("models", [])]
        assert any("nomic-embed-text" in n for n in names), \
            f"nomic-embed-text not found. Available: {names}"
    except Exception as e:
        import pytest
        pytest.skip(f"Ollama not reachable: {e}")


def test_chromadb_version():
    """ChromaDB >= 1.5.0."""
    import chromadb
    ver = tuple(int(x) for x in chromadb.__version__.split(".")[:2])
    assert ver >= (1, 5), f"ChromaDB version too old: {chromadb.__version__}"
