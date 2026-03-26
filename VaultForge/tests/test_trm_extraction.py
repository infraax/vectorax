"""
test_trm_extraction.py — Phase 8
Verify TRM PDF extraction results.
"""
import json
from pathlib import Path
from collections import Counter

OUTPUT = Path("/Users/lab/research/VaultForge/pipeline_output")


def test_page_map_exists_and_nonempty():
    p = OUTPUT / "trm_structured" / "page_map.json"
    assert p.exists(), "page_map.json missing"
    blocks = json.load(open(p))
    assert len(blocks) > 500, f"Expected >500 blocks, got {len(blocks)}"


def test_page_map_covers_full_document():
    p = OUTPUT / "trm_structured" / "page_map.json"
    blocks = json.load(open(p))
    pages = {b["page"] for b in blocks if b.get("page")}
    assert len(pages) >= 500, f"Expected ≥500 pages covered, got {len(pages)}"
    assert max(pages) >= 540, f"Expected max page ≥540, got {max(pages)}"


def test_developer_notes_count():
    p = OUTPUT / "trm_structured" / "developer_notes.json"
    assert p.exists(), "developer_notes.json missing"
    notes = json.load(open(p))
    assert len(notes) >= 15, f"Expected ≥15 developer notes, got {len(notes)}"


def test_developer_notes_have_required_fields():
    p = OUTPUT / "trm_structured" / "developer_notes.json"
    notes = json.load(open(p))
    required = {"note_id", "note_type", "page", "content", "priority"}
    for note in notes[:10]:
        missing = required - set(note.keys())
        assert not missing, f"Note {note.get('note_id')} missing fields: {missing}"


def test_developer_notes_have_high_priority():
    p = OUTPUT / "trm_structured" / "developer_notes.json"
    notes = json.load(open(p))
    high = [n for n in notes if n.get("priority") == "HIGH"]
    assert len(high) > 0, "Expected at least 1 HIGH priority developer note"


def test_code_snippets_exist():
    p = OUTPUT / "trm_structured" / "code_snippets"
    assert p.exists(), "code_snippets dir missing"
    snippets = list(p.glob("*.json"))
    assert len(snippets) >= 100, f"Expected ≥100 code snippets, got {len(snippets)}"


def test_code_snippet_content():
    p = OUTPUT / "trm_structured" / "code_snippets"
    snippets = list(p.glob("*.json"))
    # Check a few have actual content
    non_empty = 0
    for sf in snippets[:20]:
        s = json.load(open(sf))
        if len(s.get("content", "")) > 10:
            non_empty += 1
    assert non_empty >= 10, f"Too many empty code snippets (only {non_empty}/20 had content)"


def test_tables_exist():
    p = OUTPUT / "trm_structured" / "tables"
    assert p.exists(), "tables dir missing"
    tables = list(p.glob("*.json"))
    assert len(tables) >= 50, f"Expected ≥50 tables, got {len(tables)}"


def test_trm_repo_links_exist():
    p = OUTPUT / "trm_structured" / "trm_repo_links.json"
    assert p.exists(), "trm_repo_links.json missing"
    links = json.load(open(p))
    assert len(links) >= 50, f"Expected ≥50 TRM→repo links, got {len(links)}"


def test_cross_references_exist():
    p = OUTPUT / "trm_structured" / "cross_references.json"
    if not p.exists():
        import pytest; pytest.skip("cross_references.json not generated yet")
    refs = json.load(open(p))
    assert len(refs) >= 50, f"Expected ≥50 cross-references, got {len(refs)}"
