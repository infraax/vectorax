"""
test_vault_structure.py — Phase 8
Verify Obsidian vault structure and note counts.
"""
from pathlib import Path

VAULT = Path("/Users/lab/research/VectorMap/data/Vector_Obsidian_Vault_V2")

REPOS = [
    "vector", "chipper", "vector-cloud", "vector-python-sdk",
    "vector-go-sdk", "wire-pod", "escape-pod-extension", "hugh",
    "vector-bluetooth", "dev-docs", "vector-web-setup", "vectorx", "vectorx-voiceserver"
]


def test_vault_exists():
    assert VAULT.exists(), f"Vault root missing: {VAULT}"


def test_vault_readme():
    assert (VAULT / "README.md").exists(), "Vault README.md missing"


def test_vault_total_note_count():
    all_md = list(VAULT.rglob("*.md"))
    assert len(all_md) >= 5000, f"Expected ≥5000 .md files, got {len(all_md)}"


def test_required_folders_exist():
    folders = [
        "Repos", "Modules", "Symbols", "TRM/Chapters",
        "TRM/CodeSnippets", "TRM/Tables", "TRM/DeveloperNotes",
        "CrossLinks", "Architecture",
    ]
    missing = [f for f in folders if not (VAULT / f).exists()]
    assert not missing, f"Missing vault folders: {missing}"


def test_repo_notes_exist():
    """Each repo should have a top-level note in Repos/."""
    missing = [r for r in REPOS if not (VAULT / "Repos" / f"{r}.md").exists()]
    assert not missing, f"Missing repo notes: {missing}"


def test_repo_notes_have_content():
    for repo in REPOS:
        p = VAULT / "Repos" / f"{repo}.md"
        if p.exists():
            content = p.read_text(encoding="utf-8")
            assert len(content) > 100, f"Repo note {repo}.md is too short"
            assert "---" in content, f"Repo note {repo}.md missing frontmatter"


def test_module_notes_exist():
    modules_dir = VAULT / "Modules"
    all_modules = list(modules_dir.rglob("*.md"))
    assert len(all_modules) >= 100, f"Expected ≥100 module notes, got {len(all_modules)}"


def test_symbol_notes_exist():
    symbols_dir = VAULT / "Symbols"
    all_symbols = list(symbols_dir.rglob("*.md"))
    assert len(all_symbols) >= 1000, f"Expected ≥1000 symbol notes, got {len(all_symbols)}"


def test_trm_developer_notes_exist():
    notes_dir = VAULT / "TRM" / "DeveloperNotes"
    notes = list(notes_dir.glob("*.md"))
    assert len(notes) >= 15, f"Expected ≥15 TRM developer notes, got {len(notes)}"


def test_trm_developer_notes_have_priority():
    """Developer notes should mention priority in their content."""
    notes_dir = VAULT / "TRM" / "DeveloperNotes"
    notes = list(notes_dir.glob("*.md"))
    for note_path in notes[:5]:
        content = note_path.read_text(encoding="utf-8")
        assert "Priority" in content or "priority" in content.lower(), \
            f"Note {note_path.name} missing priority info"


def test_trm_code_snippets_exist():
    snips_dir = VAULT / "TRM" / "CodeSnippets"
    snips = list(snips_dir.glob("*.md"))
    assert len(snips) >= 100, f"Expected ≥100 TRM code snippet notes, got {len(snips)}"


def test_trm_tables_exist():
    tables_dir = VAULT / "TRM" / "Tables"
    tables = list(tables_dir.glob("*.md"))
    assert len(tables) >= 50, f"Expected ≥50 TRM table notes, got {len(tables)}"


def test_crosslink_notes_exist():
    cl_dir = VAULT / "CrossLinks"
    cls = list(cl_dir.glob("*.md"))
    assert len(cls) >= 5, f"Expected ≥5 crosslink notes, got {len(cls)}"


def test_symbol_notes_have_frontmatter():
    symbols_dir = VAULT / "Symbols"
    sample = list(symbols_dir.rglob("*.md"))[:20]
    for p in sample:
        content = p.read_text(encoding="utf-8")
        assert content.startswith("---"), f"Symbol note {p.name} missing YAML frontmatter"


def test_obsidian_wikilinks_in_repo_notes():
    """Repo notes should contain [[wikilinks]] to related repos or symbols."""
    for repo in ["vector", "wire-pod", "chipper"]:
        p = VAULT / "Repos" / f"{repo}.md"
        if p.exists():
            content = p.read_text(encoding="utf-8")
            assert "[[" in content, f"Repo note {repo}.md has no wikilinks"
