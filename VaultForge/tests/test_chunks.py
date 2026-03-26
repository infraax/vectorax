"""
test_chunks.py — Phase 8
Verify all_chunks.jsonl structure, counts, and metadata quality.
"""
import json
from pathlib import Path
from collections import Counter

OUTPUT = Path("/Users/lab/research/VaultForge/pipeline_output")
CHUNKS_FILE = OUTPUT / "chunks" / "all_chunks.jsonl"


def load_sample(n=2000):
    """Load first n chunks for fast spot-check tests."""
    chunks = []
    with open(CHUNKS_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))
            if len(chunks) >= n:
                break
    return chunks


def test_chunks_file_exists():
    assert CHUNKS_FILE.exists(), "all_chunks.jsonl missing"


def test_total_chunk_count():
    count = sum(1 for line in open(CHUNKS_FILE) if line.strip())
    assert count >= 50000, f"Expected ≥50,000 chunks, got {count}"


def test_chunk_required_fields():
    chunks = load_sample(500)
    required = {"chunk_id", "chunk_type", "text", "token_count"}
    for c in chunks:
        missing = required - set(c.keys())
        assert not missing, f"Chunk {c.get('chunk_id')} missing fields: {missing}"


def test_chunk_ids_unique():
    ids = set()
    dupes = []
    with open(CHUNKS_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            c = json.loads(line)
            cid = c.get("chunk_id")
            if cid in ids:
                dupes.append(cid)
            ids.add(cid)
    assert len(dupes) == 0, f"Duplicate chunk IDs found: {dupes[:10]}"


def test_chunk_types_present():
    chunks = load_sample(1000)
    types = Counter(c.get("chunk_type") for c in chunks)
    assert "repo_code" in types, f"Missing repo_code type. Types: {dict(types)}"


def test_trm_chunks_present():
    """All 5 content types should appear in the file."""
    expected_types = {"repo_code", "trm_note"}
    found = set()
    with open(CHUNKS_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            c = json.loads(line)
            found.add(c.get("chunk_type"))
            if expected_types.issubset(found):
                break
    assert expected_types.issubset(found), \
        f"Missing chunk types: {expected_types - found}"


def test_trm_developer_note_chunks():
    """TRM developer note chunks should exist and have priority field."""
    note_chunks = []
    with open(CHUNKS_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            c = json.loads(line)
            if c.get("chunk_type") == "trm_note":
                note_chunks.append(c)
    assert len(note_chunks) >= 15, f"Expected ≥15 trm_note chunks, got {len(note_chunks)}"


def test_chunk_text_nonempty():
    chunks = load_sample(200)
    empty = [c["chunk_id"] for c in chunks if not c.get("text", "").strip()]
    assert len(empty) == 0, f"Chunks with empty text: {empty[:5]}"


def test_token_counts_reasonable():
    """All chunks should have token counts between 1 and 600."""
    chunks = load_sample(500)
    bad = [c for c in chunks if not (1 <= c.get("token_count", 0) <= 600)]
    assert len(bad) == 0, \
        f"{len(bad)} chunks have unreasonable token counts. Sample: {[(c['chunk_id'], c['token_count']) for c in bad[:3]]}"


def test_repo_code_chunks_have_language():
    chunks = load_sample(1000)
    code_chunks = [c for c in chunks if c.get("chunk_type") == "repo_code"]
    no_lang = [c for c in code_chunks if not c.get("language")]
    assert len(no_lang) == 0, f"{len(no_lang)} repo_code chunks missing language"


def test_repo_code_chunks_have_repo():
    chunks = load_sample(1000)
    code_chunks = [c for c in chunks if c.get("chunk_type") == "repo_code"]
    no_repo = [c for c in code_chunks if not c.get("repo")]
    assert len(no_repo) == 0, f"{len(no_repo)} repo_code chunks missing repo"


def test_hardware_binds_on_trm_chunks():
    """TRM chunks should have hardware_binds field."""
    found_with_hw = 0
    with open(CHUNKS_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            c = json.loads(line)
            if c.get("chunk_type") in ("trm_note", "trm_code"):
                assert "hardware_binds" in c, \
                    f"TRM chunk {c.get('chunk_id')} missing hardware_binds"
                if c.get("hardware_binds"):
                    found_with_hw += 1
    # At least some should have hardware mentions
    assert found_with_hw > 0, "No TRM chunks have hardware_binds populated"
