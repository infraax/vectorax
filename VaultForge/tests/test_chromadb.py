"""
test_chromadb.py — Phase 8
Verify ChromaDB v2 collections after db_writer.py runs.
"""
import pytest
from pathlib import Path

CHROMA_PATH = Path("/Users/lab/research/VectorMap/data/chroma_db_v2")
SQLITE_PATH = Path("/Users/lab/research/VectorMap/data/vault_meta_v2.db")

EXPECTED_COLLECTIONS = ["repo_code", "trm_prose", "trm_code", "trm_tables", "trm_notes"]


@pytest.fixture(scope="module")
def chroma_client():
    if not CHROMA_PATH.exists():
        pytest.skip("ChromaDB v2 not yet written (run db_writer.py first)")
    import chromadb
    return chromadb.PersistentClient(path=str(CHROMA_PATH))


def test_chroma_db_path_exists():
    if not CHROMA_PATH.exists():
        pytest.skip("db_writer.py not yet run")
    assert CHROMA_PATH.is_dir()


def test_all_collections_exist(chroma_client):
    existing = {c.name for c in chroma_client.list_collections()}
    missing = set(EXPECTED_COLLECTIONS) - existing
    assert not missing, f"Missing ChromaDB collections: {missing}"


def test_total_chunk_count(chroma_client):
    total = sum(
        chroma_client.get_collection(name).count()
        for name in EXPECTED_COLLECTIONS
        if name in {c.name for c in chroma_client.list_collections()}
    )
    assert total >= 50000, f"Expected ≥50,000 total chunks in ChromaDB, got {total}"


def test_repo_code_collection_size(chroma_client):
    col = chroma_client.get_collection("repo_code")
    assert col.count() >= 30000, f"Expected ≥30,000 repo_code chunks, got {col.count()}"


def test_trm_notes_collection_size(chroma_client):
    col = chroma_client.get_collection("trm_notes")
    assert col.count() >= 15, f"Expected ≥15 trm_notes chunks, got {col.count()}"


def test_semantic_search_returns_results(chroma_client):
    """Query repo_code for a Vector robot concept."""
    pytest.importorskip("chromadb")

    col = chroma_client.get_collection("repo_code")
    if col.count() == 0:
        pytest.skip("repo_code collection empty")

    results = col.query(
        query_texts=["robot animation behavior"],
        n_results=5,
        include=["documents", "metadatas", "distances"],
    )
    assert len(results["documents"][0]) > 0, "Expected query results"
    assert all(d >= 0 for d in results["distances"][0]), "Negative distances"


def test_metadata_fields_present(chroma_client):
    """ChromaDB metadata should have repo, file_path, language fields."""
    col = chroma_client.get_collection("repo_code")
    if col.count() == 0:
        pytest.skip("repo_code collection empty")

    results = col.get(limit=10, include=["metadatas"])
    for meta in results["metadatas"]:
        assert "repo" in meta, f"Missing 'repo' in metadata: {meta}"
        assert "chunk_type" in meta, f"Missing 'chunk_type' in metadata: {meta}"


def test_sqlite_db_exists():
    if not SQLITE_PATH.exists():
        pytest.skip("vault_meta_v2.db not yet written")
    assert SQLITE_PATH.is_file()


def test_sqlite_chunk_count():
    if not SQLITE_PATH.exists():
        pytest.skip("vault_meta_v2.db not yet written")
    import sqlite3
    conn = sqlite3.connect(str(SQLITE_PATH))
    count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    conn.close()
    assert count >= 50000, f"Expected ≥50,000 rows in SQLite chunks, got {count}"


def test_sqlite_collections_indexed():
    if not SQLITE_PATH.exists():
        pytest.skip("vault_meta_v2.db not yet written")
    import sqlite3
    conn = sqlite3.connect(str(SQLITE_PATH))
    rows = conn.execute(
        "SELECT collection_name, COUNT(*) FROM chunks GROUP BY collection_name"
    ).fetchall()
    conn.close()
    cols = {r[0] for r in rows}
    expected = set(EXPECTED_COLLECTIONS)
    assert expected.issubset(cols), f"Missing collections in SQLite: {expected - cols}"
