# VaultForge — Test Plan

All tests must pass before switching VectorMap to use the new vault.

## Running Tests

```bash
cd /Users/lab/research/VaultForge
/Users/lab/research/VectorMap/agent_env/bin/python -m pytest tests/ -v --tb=short
```

Write all tests into `/Users/lab/research/VaultForge/tests/` as you build the pipeline.
Use `conftest.py` for shared fixtures.

---

## Phase 0 — Environment Tests

```python
# tests/test_environment.py

def test_imports():
    import fitz, pdfplumber, pymupdf4llm
    import tree_sitter_languages
    import git, datasketch, tiktoken, rank_bm25
    assert True

def test_pdf_accessible():
    import os
    assert os.path.exists("/Users/lab/research/Sources/VectorTRM.pdf")
    assert os.path.getsize("/Users/lab/research/Sources/VectorTRM.pdf") > 10_000_000  # >10MB

def test_repos_accessible():
    import os
    repos = os.listdir("/Users/lab/research/VectorMap/data/Repositories/")
    repos = [r for r in repos if not r.startswith(".") and r != "INDEX.md"]
    assert len(repos) == 13

def test_repos_have_git():
    import os
    for repo in ["vector", "chipper", "vector-python-sdk", "wire-pod"]:
        git_dir = f"/Users/lab/research/VectorMap/data/Repositories/{repo}/.git"
        assert os.path.isdir(git_dir), f"Missing .git in {repo}"

def test_ollama_running():
    import urllib.request
    try:
        r = urllib.request.urlopen("http://127.0.0.1:11434/api/tags")
        assert r.status == 200
    except Exception as e:
        pytest.skip(f"Ollama not running: {e}")

def test_output_dirs_exist():
    import os
    dirs = [
        "/Users/lab/research/VaultForge/pipeline_output/trm_figures",
        "/Users/lab/research/VaultForge/pipeline_output/trm_structured",
        "/Users/lab/research/VaultForge/pipeline_output/symbol_tables",
        "/Users/lab/research/VaultForge/pipeline_output/chunks",
    ]
    for d in dirs:
        assert os.path.isdir(d), f"Missing output dir: {d}"
```

---

## Phase 1 — TRM Extraction Tests

```python
# tests/test_trm_extraction.py
import json, os

TRM_OUT = "/Users/lab/research/VaultForge/pipeline_output/trm_structured"

def test_page_map_exists():
    path = f"{TRM_OUT}/page_map.json"
    assert os.path.exists(path), "page_map.json not found"
    data = json.load(open(path))
    assert len(data) >= 500, f"Expected ≥500 pages, got {len(data)}"

def test_page_map_has_chapters():
    data = json.load(open(f"{TRM_OUT}/page_map.json"))
    chapters = [p for p in data if any(b["type"] == "chapter_heading" for b in p.get("blocks", []))]
    assert len(chapters) >= 5, f"Expected ≥5 chapters, got {len(chapters)}"

def test_code_snippets_extracted():
    snippets_dir = f"{TRM_OUT}/code_snippets"
    files = os.listdir(snippets_dir)
    assert len(files) >= 50, f"Expected ≥50 code snippets, got {len(files)}"
    # Check one snippet has required fields
    s = json.load(open(os.path.join(snippets_dir, files[0])))
    for field in ["snippet_id", "page", "language", "content", "token_count"]:
        assert field in s, f"Missing field '{field}' in snippet"

def test_tables_extracted():
    tables_dir = f"{TRM_OUT}/tables"
    files = os.listdir(tables_dir)
    assert len(files) >= 30, f"Expected ≥30 tables, got {len(files)}"
    t = json.load(open(os.path.join(tables_dir, files[0])))
    assert "headers" in t and "rows" in t
    assert len(t["rows"]) > 0, "Table has no rows"

def test_developer_notes_extracted():
    path = f"{TRM_OUT}/developer_notes.json"
    assert os.path.exists(path)
    notes = json.load(open(path))
    assert len(notes) >= 20, f"Expected ≥20 developer notes, got {len(notes)}"
    for n in notes[:3]:
        for field in ["note_id", "note_type", "chapter", "page", "content"]:
            assert field in n, f"Missing field '{field}' in developer note"

def test_figures_saved():
    figs_dir = "/Users/lab/research/VaultForge/pipeline_output/trm_figures"
    pngs = [f for f in os.listdir(figs_dir) if f.endswith(".png")]
    assert len(pngs) >= 20, f"Expected ≥20 figure PNGs, got {len(pngs)}"

def test_no_empty_snippets():
    snippets_dir = f"{TRM_OUT}/code_snippets"
    for fname in os.listdir(snippets_dir):
        s = json.load(open(os.path.join(snippets_dir, fname)))
        assert len(s["content"].strip()) > 0, f"Empty snippet: {fname}"
        assert s["token_count"] > 0

def test_cross_reference_map():
    path = f"{TRM_OUT}/cross_reference_map.json"
    assert os.path.exists(path)
    refs = json.load(open(path))
    assert len(refs) >= 50, f"Expected ≥50 cross-references, got {len(refs)}"
```

---

## Phase 2 — Repository Parse Tests

```python
# tests/test_repo_parsing.py
import json, os

SYM_DIR = "/Users/lab/research/VaultForge/pipeline_output/symbol_tables"

def test_symbol_tables_exist():
    for repo in ["vector", "chipper", "vector-python-sdk"]:
        path = f"{SYM_DIR}/{repo}_symbols.json"
        assert os.path.exists(path), f"Missing symbol table: {repo}"

def test_python_sdk_has_expected_symbols():
    symbols = json.load(open(f"{SYM_DIR}/vector-python-sdk_symbols.json"))
    names = {s["name"] for s in symbols}
    expected = {"set_eye_color", "drive_straight", "BehaviorComponent", "Robot"}
    found = expected & names
    assert len(found) >= 3, f"Missing expected SDK symbols. Found: {found}"

def test_symbol_required_fields():
    symbols = json.load(open(f"{SYM_DIR}/vector-python-sdk_symbols.json"))
    required = ["type", "name", "repo", "file", "line_start", "language"]
    for sym in symbols[:20]:
        for field in required:
            assert field in sym, f"Symbol {sym.get('name')} missing field '{field}'"

def test_no_symbols_without_line_numbers():
    for fname in os.listdir(SYM_DIR):
        if not fname.endswith("_symbols.json"):
            continue
        symbols = json.load(open(os.path.join(SYM_DIR, fname)))
        for s in symbols:
            assert s.get("line_start", 0) > 0, f"Symbol {s.get('name')} in {fname} has no line number"

def test_go_repo_parsed():
    path = f"{SYM_DIR}/chipper_symbols.json"
    assert os.path.exists(path)
    symbols = json.load(open(path))
    funcs = [s for s in symbols if s["type"] == "function" and s["language"] == "go"]
    assert len(funcs) >= 20, f"Expected ≥20 Go functions in chipper, got {len(funcs)}"

def test_cross_repo_imports_exist():
    path = f"{SYM_DIR}/cross_repo_imports.json"
    assert os.path.exists(path)
    imports = json.load(open(path))
    cross = [i for i in imports if i.get("is_cross_repo")]
    assert len(cross) >= 5, f"Expected ≥5 cross-repo imports, got {len(cross)}"

def test_git_meta_collected():
    for repo in ["vector", "chipper", "vector-python-sdk"]:
        path = f"{SYM_DIR}/{repo}_git_meta.json"
        assert os.path.exists(path), f"Missing git meta: {repo}"
        meta = json.load(open(path))
        assert "commit_sha" in meta
        assert "files" in meta
        assert len(meta["files"]) > 0

def test_trm_repo_links_exist():
    path = "/Users/lab/research/VaultForge/pipeline_output/trm_structured/trm_repo_links.json"
    assert os.path.exists(path)
    links = json.load(open(path))
    assert len(links) >= 10, f"Expected ≥10 TRM→repo links, got {len(links)}"
    # At least some should have high-confidence matches
    high_conf = [l for l in links if any(m["confidence"] >= 0.8 for m in l.get("matches", []))]
    assert len(high_conf) >= 3, f"Expected ≥3 high-confidence TRM→repo links"

def test_clone_pairs_detected():
    path = "/Users/lab/research/VaultForge/pipeline_output/clone_pairs/similarity_pairs.json"
    assert os.path.exists(path)
    pairs = json.load(open(path))
    # chipper and wire-pod should have many similar functions
    chipper_wirepod = [p for p in pairs if
        ("chipper" in p.get("repo_a","") and "wire-pod" in p.get("repo_b","")) or
        ("wire-pod" in p.get("repo_a","") and "chipper" in p.get("repo_b",""))
    ]
    assert len(chipper_wirepod) >= 5, f"Expected chipper/wire-pod clones, got {len(chipper_wirepod)}"
```

---

## Phase 3 — Chunk Tests

```python
# tests/test_chunks.py
import json

CHUNKS_FILE = "/Users/lab/research/VaultForge/pipeline_output/chunks/all_chunks.jsonl"

def load_chunks():
    chunks = []
    with open(CHUNKS_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))
    return chunks

def test_chunks_file_exists():
    import os
    assert os.path.exists(CHUNKS_FILE)

def test_chunk_count():
    chunks = load_chunks()
    # Old vault had 41,363 chunks (Gemini, basic). New vault should have more.
    assert len(chunks) >= 50_000, f"Expected ≥50k chunks, got {len(chunks)}"

def test_all_chunks_have_required_fields():
    required = [
        "chunk_id", "repo", "file", "line_start", "line_end",
        "content", "token_count", "language", "symbol_type"
    ]
    chunks = load_chunks()
    for i, chunk in enumerate(chunks[:100]):
        for field in required:
            assert field in chunk, f"Chunk {i} missing field '{field}'"

def test_no_chunks_exceed_token_limit():
    chunks = load_chunks()
    overlimit = [c for c in chunks if c.get("token_count", 0) > 768]
    assert len(overlimit) == 0, f"{len(overlimit)} chunks exceed 768 token limit"

def test_no_empty_chunks():
    chunks = load_chunks()
    empty = [c for c in chunks if len(c.get("content","").strip()) < 10]
    assert len(empty) == 0, f"{len(empty)} chunks have empty content"

def test_trm_chunks_have_types():
    chunks = load_chunks()
    trm = [c for c in chunks if c.get("repo") == "TRM" or "trm" in c.get("chunk_id","")]
    assert len(trm) >= 500, f"Expected ≥500 TRM chunks, got {len(trm)}"
    types = {c.get("content_type") for c in trm}
    expected_types = {"trm_prose", "trm_code", "trm_table", "trm_note"}
    assert expected_types <= types, f"Missing TRM content types: {expected_types - types}"

def test_chunks_have_line_numbers():
    chunks = load_chunks()
    no_lines = [c for c in chunks if c.get("line_start", 0) == 0 and c.get("repo") != "TRM"]
    assert len(no_lines) == 0, f"{len(no_lines)} repo chunks have no line numbers"

def test_developer_notes_present():
    chunks = load_chunks()
    notes = [c for c in chunks if c.get("content_type") == "trm_note"]
    assert len(notes) >= 20, f"Expected ≥20 developer note chunks, got {len(notes)}"
    # Check priority field
    for n in notes:
        assert n.get("priority") == "HIGH", "Developer notes must have HIGH priority"
```

---

## Phase 4 — Vault Structure Tests

```python
# tests/test_vault_structure.py
import os

VAULT = "/Users/lab/research/VectorMap/data/Vector_Obsidian_Vault_V2"

def test_vault_exists():
    assert os.path.isdir(VAULT)

def test_required_directories():
    required = ["Repos", "Modules", "Symbols", "TRM", "TRM/CodeSnippets",
                "TRM/Tables", "TRM/DeveloperNotes", "TRM/Components",
                "Architecture", "Canvas", "_index"]
    for d in required:
        assert os.path.isdir(f"{VAULT}/{d}"), f"Missing vault directory: {d}"

def test_master_index_exists():
    assert os.path.exists(f"{VAULT}/_MASTER_INDEX.md")

def test_repo_notes_exist():
    repos = ["vector", "chipper", "vector-python-sdk", "wire-pod"]
    for repo in repos:
        assert os.path.exists(f"{VAULT}/Repos/{repo}.md"), f"Missing repo note: {repo}.md"

def test_trm_components_exist():
    components = [
        "TRM__Snapdragon_212.md",
        "TRM__STM32_Body_Board.md",
        "TRM__Face_Display_IPS.md",
        "TRM__Motors_Wheels_Head_Lift.md"
    ]
    for c in components:
        assert os.path.exists(f"{VAULT}/TRM/Components/{c}"), f"Missing TRM component: {c}"

def test_developer_notes_in_vault():
    notes = [f for f in os.listdir(f"{VAULT}/TRM/DeveloperNotes") if f.endswith(".md")]
    assert len(notes) >= 15, f"Expected ≥15 developer note files, got {len(notes)}"

def test_canvas_files_exist():
    canvases = ["System_Architecture.canvas", "Hardware_Binding_Map.canvas"]
    for c in canvases:
        assert os.path.exists(f"{VAULT}/Canvas/{c}"), f"Missing canvas: {c}"

def test_notes_have_frontmatter():
    import re
    # Check a sample of notes
    for dirpath, _, files in os.walk(VAULT):
        for fname in files[:3]:
            if fname.endswith(".md") and not fname.startswith("_"):
                with open(os.path.join(dirpath, fname)) as f:
                    content = f.read()
                assert content.startswith("---"), f"No frontmatter in {fname}"
                assert "type:" in content, f"No 'type:' in frontmatter of {fname}"
        break  # just check first dir

def test_no_broken_wikilinks():
    """All [[WikiLinks]] must correspond to existing notes"""
    import re
    all_notes = set()
    for root, dirs, files in os.walk(VAULT):
        # Exclude .obsidian
        dirs[:] = [d for d in dirs if d != ".obsidian"]
        for f in files:
            if f.endswith(".md"):
                all_notes.add(f[:-3])  # remove .md

    broken = []
    for root, dirs, files in os.walk(VAULT):
        dirs[:] = [d for d in dirs if d != ".obsidian"]
        for f in files:
            if not f.endswith(".md"):
                continue
            content = open(os.path.join(root, f)).read()
            links = re.findall(r'\[\[([^\]|#]+)', content)
            for link in links:
                link = link.strip()
                if link not in all_notes:
                    broken.append(f"{f}: [[{link}]]")

    assert len(broken) == 0, f"{len(broken)} broken WikiLinks:\n" + "\n".join(broken[:10])
```

---

## Phase 5 — ChromaDB Tests

```python
# tests/test_chromadb.py
import chromadb

DB_PATH = "/Users/lab/research/VectorMap/data/chroma_db_v2"

def get_client():
    return chromadb.PersistentClient(path=DB_PATH)

def test_chroma_v2_accessible():
    client = get_client()
    assert client is not None

def test_required_collections_exist():
    client = get_client()
    names = {c.name for c in client.list_collections()}
    required = {"repo_code", "trm_prose", "trm_code", "trm_tables", "trm_notes"}
    assert required <= names, f"Missing collections: {required - names}"

def test_repo_code_chunk_count():
    client = get_client()
    col = client.get_collection("repo_code")
    count = col.count()
    assert count >= 40_000, f"Expected ≥40k repo chunks, got {count}"

def test_trm_notes_in_chroma():
    client = get_client()
    col = client.get_collection("trm_notes")
    count = col.count()
    assert count >= 20, f"Expected ≥20 TRM developer notes in ChromaDB, got {count}"

def test_semantic_search_returns_results():
    client = get_client()
    col = client.get_collection("repo_code")
    results = col.query(query_texts=["how does Vector set eye color"], n_results=5)
    assert len(results["documents"][0]) == 5
    # Top result should be from vector-python-sdk behavior module
    top_meta = results["metadatas"][0][0]
    assert "repo" in top_meta

def test_trm_code_searchable():
    client = get_client()
    col = client.get_collection("trm_code")
    results = col.query(query_texts=["PID motor control loop"], n_results=3)
    assert len(results["documents"][0]) > 0

def test_table_search():
    client = get_client()
    col = client.get_collection("trm_tables")
    results = col.query(query_texts=["GPIO pin assignment STM32"], n_results=3)
    docs = results["documents"][0]
    assert len(docs) > 0
    # Should find the GPIO table
    found_gpio = any("GPIO" in doc or "PA0" in doc for doc in docs)
    assert found_gpio, "GPIO table not found in TRM tables collection"

def test_chunk_metadata_complete():
    client = get_client()
    col = client.get_collection("repo_code")
    results = col.get(limit=10)
    for meta in results["metadatas"]:
        assert "repo" in meta
        assert "file" in meta
        assert "line_start" in meta
        assert "token_count" in meta
```

---

## Phase 6 — VectorMap Integration Tests

```python
# tests/test_vectormap_integration.py
import urllib.request, json

BASE = "http://127.0.0.1:61392"  # adjust port if needed

def test_server_online():
    r = urllib.request.urlopen(f"{BASE}/status")
    d = json.load(r)
    assert d["status"] == "online"

def test_new_vault_reflected_in_chunk_count():
    r = urllib.request.urlopen(f"{BASE}/status")
    d = json.load(r)
    count = d["stats"]["indexed_chunks_total"]
    # New vault should have significantly more chunks than old (41,363)
    assert count >= 50_000, f"VectorMap still using old vault? Chunk count: {count}"

def test_query_returns_trm_sources():
    """A hardware question should return TRM chunks as sources"""
    data = json.dumps({
        "message": "How does the Vector PID motor control loop work?",
        "session_id": "test_integration"
    }).encode()
    req = urllib.request.Request(f"{BASE}/chat", data=data,
                                  headers={"Content-Type": "application/json"})
    r = urllib.request.urlopen(req)
    resp = json.load(r)
    sources = resp.get("sources", [])
    trm_sources = [s for s in sources if "TRM" in s.get("filename", "")]
    assert len(trm_sources) >= 1, "No TRM sources returned for hardware question"

def test_query_returns_line_numbers():
    """Sources should have line numbers in new vault"""
    data = json.dumps({
        "message": "Show me the set_eye_color function",
        "session_id": "test_integration_2"
    }).encode()
    req = urllib.request.Request(f"{BASE}/chat", data=data,
                                  headers={"Content-Type": "application/json"})
    r = urllib.request.urlopen(req)
    resp = json.load(r)
    sources = resp.get("sources", [])
    sources_with_lines = [s for s in sources if s.get("line_start", 0) > 0]
    assert len(sources_with_lines) >= 1, "No sources with line numbers returned"
```

---

## Final Checklist

Before declaring the build complete, verify all of the following manually:

- [ ] `pytest tests/ -v` — all tests pass
- [ ] Vault directory has > 5,000 `.md` files
- [ ] `TRM/DeveloperNotes/` has > 15 notes
- [ ] Open vault in Obsidian — graph view shows colored nodes by type
- [ ] Graph view shows connections between TRM components and repo symbols
- [ ] Canvas files open and display node graphs
- [ ] Dataview queries in `_index/` render tables
- [ ] VectorMap chunk count > 50,000
- [ ] Ask VectorMap: "What is the PID loop for Vector's motors?" — response cites TRM
- [ ] Ask VectorMap: "Show me the set_eye_color function" — response includes line number
- [ ] Ask VectorMap: "What warning does the TRM give about the integrator?" — finds developer note
- [ ] Check that chipper vs wire-pod clone relationships appear in a query about gRPC setup
