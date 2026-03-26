"""
Pytest configuration and shared fixtures for VaultForge pipeline tests.
"""
import json
import os
import pytest
from pathlib import Path

# ── Root paths ────────────────────────────────────────────────────────────────
PIPELINE_ROOT  = Path("/Users/lab/research/VaultForge")
OUTPUT_ROOT    = PIPELINE_ROOT / "pipeline_output"
VAULT_ROOT     = Path("/Users/lab/research/VectorMap/data/Vector_Obsidian_Vault_V2")
CHROMA_PATH    = Path("/Users/lab/research/VectorMap/data/chroma_db_v2")
SQLITE_PATH    = Path("/Users/lab/research/VectorMap/data/vault_meta_v2.db")

REPOS = [
    "vector", "chipper", "vector-cloud", "vector-python-sdk",
    "vector-go-sdk", "wire-pod", "escape-pod-extension", "hugh",
    "vector-bluetooth", "dev-docs", "vector-web-setup", "vectorx", "vectorx-voiceserver"
]


@pytest.fixture(scope="session")
def output_root():
    return OUTPUT_ROOT


@pytest.fixture(scope="session")
def vault_root():
    return VAULT_ROOT


@pytest.fixture(scope="session")
def all_chunks():
    """Load all chunks from JSONL once per session."""
    p = OUTPUT_ROOT / "chunks" / "all_chunks.jsonl"
    chunks = []
    with open(p, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))
    return chunks


@pytest.fixture(scope="session")
def developer_notes():
    p = OUTPUT_ROOT / "trm_structured" / "developer_notes.json"
    return json.load(open(p))


@pytest.fixture(scope="session")
def page_map():
    p = OUTPUT_ROOT / "trm_structured" / "page_map.json"
    return json.load(open(p))


@pytest.fixture(scope="session")
def similarity_pairs():
    p = OUTPUT_ROOT / "clone_pairs" / "similarity_pairs.json"
    return json.load(open(p))


@pytest.fixture(scope="session")
def cross_imports():
    p = OUTPUT_ROOT / "symbol_tables" / "cross_repo_imports.json"
    return json.load(open(p))


@pytest.fixture(scope="session")
def trm_links():
    p = OUTPUT_ROOT / "trm_structured" / "trm_repo_links.json"
    return json.load(open(p))


@pytest.fixture(scope="session")
def annotated_symbols():
    """Load all annotated symbol tables."""
    syms = []
    for repo in REPOS:
        p = OUTPUT_ROOT / "symbol_tables" / f"{repo}_symbols_annotated.json"
        if p.exists():
            syms.extend(json.load(open(p)))
    return syms
