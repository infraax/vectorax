"""
test_repo_parsing.py — Phase 8
Verify repo symbol extraction results.
"""
import json
from pathlib import Path
from collections import Counter

OUTPUT  = Path("/Users/lab/research/VaultForge/pipeline_output")
SYMTAB  = OUTPUT / "symbol_tables"

REPOS = [
    "vector", "chipper", "vector-cloud", "vector-python-sdk",
    "vector-go-sdk", "wire-pod", "escape-pod-extension", "hugh",
    "vector-bluetooth", "dev-docs", "vector-web-setup", "vectorx", "vectorx-voiceserver"
]


def test_all_symbol_tables_exist():
    missing = [r for r in REPOS if not (SYMTAB / f"{r}_symbols.json").exists()]
    assert not missing, f"Missing symbol tables: {missing}"


def test_all_annotated_tables_exist():
    missing = [r for r in REPOS if not (SYMTAB / f"{r}_symbols_annotated.json").exists()]
    assert not missing, f"Missing annotated symbol tables: {missing}"


def test_total_symbol_count():
    total = 0
    for repo in REPOS:
        p = SYMTAB / f"{repo}_symbols.json"
        if p.exists():
            total += len(json.load(open(p)))
    assert total >= 5000, f"Expected ≥5000 total symbols, got {total}"


def test_vector_repo_symbols():
    """vector repo should have the most symbols (main firmware)."""
    p = SYMTAB / "vector_symbols.json"
    syms = json.load(open(p))
    assert len(syms) >= 5000, f"Expected ≥5000 symbols in vector, got {len(syms)}"


def test_symbols_have_required_fields():
    p = SYMTAB / "vector_symbols.json"
    syms = json.load(open(p))
    required = {"name", "type", "file", "repo", "language", "source"}
    for sym in syms[:20]:
        missing = required - set(sym.keys())
        assert not missing, f"Symbol '{sym.get('name')}' missing: {missing}"


def test_symbol_types_distribution():
    """Should have a mix of functions, methods, classes, structs."""
    all_types = Counter()
    for repo in REPOS:
        p = SYMTAB / f"{repo}_symbols.json"
        if p.exists():
            for s in json.load(open(p)):
                all_types[s.get("type", "unknown")] += 1

    assert all_types.get("function", 0) > 1000, "Too few functions"
    # At least 2 of the major types should be present
    major = sum(1 for t in ("function", "method", "class", "struct", "type")
                if all_types.get(t, 0) > 0)
    assert major >= 2, f"Need ≥2 symbol types present, got: {dict(all_types)}"


def test_cross_repo_imports_exist():
    p = SYMTAB / "cross_repo_imports.json"
    assert p.exists(), "cross_repo_imports.json missing"
    imports = json.load(open(p))
    assert len(imports) >= 100, f"Expected ≥100 cross-repo imports, got {len(imports)}"


def test_wire_pod_imports_chipper():
    """wire-pod should import from chipper (or vector-cloud)."""
    p = SYMTAB / "cross_repo_imports.json"
    imports = json.load(open(p))
    wire_imports = [i for i in imports
                    if i.get("source_repo") == "wire-pod" and i.get("is_cross_repo")]
    targets = {i.get("resolves_to_repo") for i in wire_imports}
    assert targets, "wire-pod should have cross-repo imports"


def test_similarity_pairs_exist():
    p = OUTPUT / "clone_pairs" / "similarity_pairs.json"
    assert p.exists(), "similarity_pairs.json missing"
    pairs = json.load(open(p))
    assert len(pairs) >= 100, f"Expected ≥100 similarity pairs, got {len(pairs)}"


def test_chipper_wirepod_clone_pairs():
    """chipper ↔ wire-pod should have clone pairs (shared codebase origin)."""
    p = OUTPUT / "clone_pairs" / "similarity_pairs.json"
    pairs = json.load(open(p))
    chipper_wire = [
        p for p in pairs
        if set([p.get("repo_a"), p.get("repo_b")]) == {"chipper", "wire-pod"}
    ]
    assert len(chipper_wire) >= 5, \
        f"Expected ≥5 chipper↔wire-pod pairs, got {len(chipper_wire)}"


def test_annotated_symbols_have_metadata_fields():
    """Annotated symbols should have the annotation fields (even if empty)."""
    p = SYMTAB / "vector-python-sdk_symbols_annotated.json"
    if not p.exists():
        import pytest; pytest.skip("vector-python-sdk annotated file missing")
    syms = json.load(open(p))
    for sym in syms[:10]:
        assert "llm_summary" in sym, f"Missing llm_summary in {sym.get('name')}"
        assert "purpose_tags" in sym, f"Missing purpose_tags in {sym.get('name')}"
        assert "complexity" in sym, f"Missing complexity in {sym.get('name')}"


def test_git_meta_exists():
    p = OUTPUT / "git_meta"
    if not p.exists():
        import pytest; pytest.skip("git_meta dir not generated")
    files = list(p.glob("*.json"))
    assert len(files) >= 5, f"Expected ≥5 git meta files, got {len(files)}"
