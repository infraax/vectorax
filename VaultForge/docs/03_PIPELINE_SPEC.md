# VaultForge — Pipeline Technical Specification

## Python Environment

**ALWAYS use:**
```bash
/Users/lab/research/VectorMap/agent_env/bin/python
/Users/lab/research/VectorMap/agent_env/bin/pip
```

**Required packages (install in Phase 0):**
```
pymupdf          — PDF layout extraction (import as fitz)
pymupdf4llm      — PDF to markdown conversion helper
pdfplumber       — Table extraction from PDFs
tree-sitter      — Multi-language parser framework
tree-sitter-languages — Pre-compiled parsers (40+ languages, one install)
gitpython        — Git repository metadata (commits, blame, authors)
datasketch       — MinHash LSH for code similarity detection
tiktoken         — Accurate token counting (OpenAI tokenizer)
rank-bm25        — BM25 lexical search index
libcst           — Python CST parser (for more detailed Python analysis)
radon            — Python code metrics (cyclomatic complexity, maintainability)
pyarrow          — Parquet file export for analytics
kuzu             — Embedded graph database (optional, for Neo4j-style queries)
chromadb         — Already installed (vector database)
```

---

## Stage 1: TRM Processing — Script Specifications

### Script: `pipeline/trm_scanner.py`

**Input:** `/Users/lab/research/Sources/VectorTRM.pdf`
**Output:** `pipeline_output/trm_structured/page_map.json`

```python
#!/usr/bin/env python3
"""
TRM Scanner — Phase 1.1
Builds a structural page map of VectorTRM.pdf.
For each page: identify content block types using font metadata.
"""
import fitz
import json
import logging
from pathlib import Path

PDF_PATH  = "/Users/lab/research/Sources/VectorTRM.pdf"
OUT_PATH  = "pipeline_output/trm_structured/page_map.json"

MONO_FONTS = ["Courier", "Mono", "Code", "Consolas", "Letter Gothic", "Lucida Console"]
NOTE_PREFIXES = ("NOTE:", "WARNING:", "IMPORTANT:", "CAUTION:", "DESIGN DECISION:", "DESIGN NOTE:")
CAPTION_PREFIXES = ("Figure", "Table", "Fig.", "Listing", "Diagram")

def classify_block(block):
    if block["type"] == 1:  # image block
        return "figure_region"
    spans = [s for line in block.get("lines", []) for s in line.get("spans", [])]
    if not spans:
        return "figure_region"
    primary   = spans[0]
    font_size = primary["size"]
    font_name = primary["font"]
    is_bold   = "Bold" in font_name or bool(primary["flags"] & 16)
    is_mono   = any(m in font_name for m in MONO_FONTS)
    text      = " ".join(s["text"] for s in spans).strip()

    if is_mono and len(text) > 20:
        return "code"
    if font_size >= 18 and is_bold:
        return "chapter_heading"
    if font_size >= 13 and is_bold:
        return "section_heading"
    if font_size >= 11 and is_bold:
        return "subsection_heading"
    if any(text.upper().startswith(p) for p in NOTE_PREFIXES):
        return "developer_note"
    if any(text.startswith(p) for p in CAPTION_PREFIXES) and len(text) < 200:
        return "caption"
    return "prose"

def run():
    doc = fitz.open(PDF_PATH)
    page_map = []
    current_chapter = None
    current_section = None

    for page_num in range(len(doc)):
        page = doc[page_num]
        blocks_raw = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
        page_data = {"page": page_num, "chapter": current_chapter, "section": current_section, "blocks": []}

        for block in blocks_raw:
            btype = classify_block(block)
            spans = [s for line in block.get("lines", []) for s in line.get("spans", [])]
            text  = " ".join(s["text"] for s in spans).strip()

            if btype == "chapter_heading":
                current_chapter = text
                page_data["chapter"] = current_chapter
            elif btype == "section_heading":
                current_section = text
                page_data["section"] = current_section

            page_data["blocks"].append({
                "type": btype,
                "text": text if btype != "figure_region" else "",
                "bbox": list(block.get("bbox", [])),
            })

        page_map.append(page_data)
        if page_num % 50 == 0:
            logging.info(f"Scanned page {page_num}/{len(doc)}")

    with open(OUT_PATH, "w") as f:
        json.dump(page_map, f, indent=2)
    logging.info(f"Page map written: {len(page_map)} pages")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
```

---

## Stage 2: Repository Parse — Script Specifications

### Script: `pipeline/repo_parser.py`

**Input:** All repos in `/Users/lab/research/VectorMap/data/Repositories/`
**Output:** `pipeline_output/symbol_tables/{repo}_symbols.json` per repo

```python
#!/usr/bin/env python3
"""
Repository Parser — Phase 2.2
Uses tree-sitter to extract symbols from all supported languages.
Outputs a symbol table JSON per repository.
"""
from tree_sitter_languages import get_parser, get_language
import json, os, logging
from pathlib import Path

REPOS_PATH = "/Users/lab/research/VectorMap/data/Repositories"
OUT_DIR    = "pipeline_output/symbol_tables"

EXTENSION_MAP = {
    ".py":   "python",
    ".go":   "go",
    ".c":    "c",
    ".h":    "c",
    ".cpp":  "cpp",
    ".hpp":  "cpp",
    ".js":   "javascript",
    ".ts":   "typescript",
    ".tsx":  "typescript",
    ".proto":"proto3",
}

SKIP_DIRS = {".git", "vendor", "node_modules", "build", "dist", "__pycache__", ".cache"}

def get_symbols_python(code_bytes, filepath, repo):
    """Extract Python symbols using tree-sitter"""
    parser = get_parser("python")
    tree   = parser.parse(code_bytes)
    root   = tree.root_node
    symbols = []

    def walk(node, class_context=None):
        if node.type == "class_definition":
            name_node = node.child_by_field_name("name")
            class_name = name_node.text.decode() if name_node else "?"
            sym = {
                "type": "class", "name": class_name,
                "repo": repo, "file": filepath,
                "line_start": node.start_point[0] + 1,
                "line_end": node.end_point[0] + 1,
                "language": "python",
            }
            # Try to get docstring
            body = node.child_by_field_name("body")
            if body and body.children and body.children[0].type == "expression_statement":
                ds = body.children[0]
                if ds.children and ds.children[0].type == "string":
                    sym["docstring"] = ds.children[0].text.decode().strip("'\"")
            symbols.append(sym)
            for child in node.children:
                walk(child, class_context=class_name)
        elif node.type in ("function_definition", "decorated_definition"):
            fn = node if node.type == "function_definition" else node.child_by_field_name("definition")
            if not fn:
                return
            name_node = fn.child_by_field_name("name")
            if not name_node:
                return
            sym = {
                "type": "method" if class_context else "function",
                "name": name_node.text.decode(),
                "class_context": class_context,
                "repo": repo, "file": filepath,
                "line_start": fn.start_point[0] + 1,
                "line_end": fn.end_point[0] + 1,
                "language": "python",
            }
            symbols.append(sym)
        else:
            for child in node.children:
                walk(child, class_context=class_context)

    walk(root)
    return symbols

def get_symbols_go(code_bytes, filepath, repo):
    """Extract Go symbols using tree-sitter"""
    parser  = get_parser("go")
    tree    = parser.parse(code_bytes)
    root    = tree.root_node
    symbols = []

    def walk(node):
        if node.type == "function_declaration":
            name = node.child_by_field_name("name")
            symbols.append({
                "type": "function", "name": name.text.decode() if name else "?",
                "repo": repo, "file": filepath, "language": "go",
                "line_start": node.start_point[0] + 1,
                "line_end": node.end_point[0] + 1,
            })
        elif node.type == "method_declaration":
            name = node.child_by_field_name("name")
            receiver = node.child_by_field_name("receiver")
            symbols.append({
                "type": "method", "name": name.text.decode() if name else "?",
                "receiver": receiver.text.decode() if receiver else "",
                "repo": repo, "file": filepath, "language": "go",
                "line_start": node.start_point[0] + 1,
                "line_end": node.end_point[0] + 1,
            })
        elif node.type == "type_declaration":
            for child in node.children:
                if child.type == "type_spec":
                    name = child.child_by_field_name("name")
                    symbols.append({
                        "type": "struct", "name": name.text.decode() if name else "?",
                        "repo": repo, "file": filepath, "language": "go",
                        "line_start": node.start_point[0] + 1,
                        "line_end": node.end_point[0] + 1,
                    })
        for child in node.children:
            walk(child)

    walk(root)
    return symbols

def process_repo(repo_name):
    repo_path = os.path.join(REPOS_PATH, repo_name)
    all_symbols = []

    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fname in files:
            ext = Path(fname).suffix.lower()
            if ext not in EXTENSION_MAP:
                continue
            lang     = EXTENSION_MAP[ext]
            fpath    = os.path.join(root, fname)
            rel_path = os.path.relpath(fpath, repo_path)

            try:
                code = open(fpath, "rb").read()
                if lang == "python":
                    syms = get_symbols_python(code, rel_path, repo_name)
                elif lang == "go":
                    syms = get_symbols_go(code, rel_path, repo_name)
                else:
                    syms = []  # add more language handlers here
                all_symbols.extend(syms)
            except Exception as e:
                logging.warning(f"Parse error {fpath}: {e}")

    out_path = os.path.join(OUT_DIR, f"{repo_name}_symbols.json")
    with open(out_path, "w") as f:
        json.dump(all_symbols, f, indent=2)
    logging.info(f"{repo_name}: {len(all_symbols)} symbols extracted")
    return all_symbols

REPO_ORDER = [
    "vector", "chipper", "vector-cloud", "vector-python-sdk",
    "vector-go-sdk", "wire-pod", "escape-pod-extension", "hugh",
    "vector-bluetooth", "dev-docs", "vector-web-setup", "vectorx", "vectorx-voiceserver"
]

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    os.makedirs(OUT_DIR, exist_ok=True)
    for repo in REPO_ORDER:
        repo_path = os.path.join(REPOS_PATH, repo)
        if os.path.isdir(repo_path):
            process_repo(repo)
        else:
            logging.warning(f"Repo not found: {repo}")
```

---

## Stage 4: LLM Annotation — Ollama Integration

**Ollama endpoint:** `http://127.0.0.1:11434`

Check available models before running annotations:
```bash
curl -s http://127.0.0.1:11434/api/tags | python3 -c "import sys,json; [print(m['name']) for m in json.load(sys.stdin)['models']]"
```

**Recommended models (in preference order):**
1. `phi4` — best quality local annotation (if available)
2. `qwen2.5-coder` — good for code-specific annotations
3. `smollm2` — fastest, lower quality

**Annotation prompt template:**
```python
FUNCTION_PROMPT = """Repository: {repo} | File: {file} | Language: {language}
Function signature: {signature}
Docstring: {docstring}
Source code:
{source_code}

In exactly 2 sentences:
1. What this function does
2. When/why it would be called

Then provide tags (3-6 keywords).
Respond in JSON only:
{{"summary": "...", "called_when": "...", "tags": ["...", "..."], "complexity": "simple|moderate|complex"}}"""
```

**Caching:** Hash the source code. Check SQLite before calling Ollama:
```python
import hashlib, sqlite3
def get_cache_key(source): return hashlib.sha256(source.encode()).hexdigest()
def check_cache(db_conn, key):
    row = db_conn.execute("SELECT annotation FROM annotations WHERE content_hash=?", (key,)).fetchone()
    return json.loads(row[0]) if row else None
```

---

## Stage 5: Chunk Construction — Token-Aware Rules

```python
import tiktoken
enc = tiktoken.get_encoding("cl100k_base")

MAX_TOKENS = {
    "code":      512,
    "trm_prose": 768,
    "trm_table": 256,
    "trm_note":  256,
    "trm_code":  512,
}

def count_tokens(text):
    return len(enc.encode(text))

def chunk_function(symbol, source_code, repo_meta):
    """One function = one chunk if under MAX_TOKENS"""
    tokens = count_tokens(source_code)
    if tokens > MAX_TOKENS["code"]:
        # Split at logical boundaries within the function
        # Keep first line (signature) in every sub-chunk
        return split_large_function(symbol, source_code)
    return [{
        "chunk_id": hashlib.sha256(source_code.encode()).hexdigest()[:16],
        "content": source_code,
        "token_count": tokens,
        **symbol,  # all symbol metadata
        **repo_meta,  # git metadata
    }]
```

---

## Stage 6: Vault Generation — Key Rules

1. **Every WikiLink must have a corresponding note.** Build the note index first, then generate links.
2. **YAML frontmatter is required on every note.** Minimum fields: `id`, `type`, `repo` (or `source`), `tags`.
3. **No word-overlap cross-links.** Only create WikiLinks from:
   - Resolved imports (Phase 2.3 output)
   - TRM→Repo links (Phase 2.4 output)
   - Clone pairs (Phase 2.5 output)
   - Explicit structural relationships (file→repo, symbol→file)
4. **Canvas files** are JSON. Format: `{"nodes": [...], "edges": [...]}` — see Obsidian Canvas spec.
5. **Dataview fields** must use `::` syntax in body (not frontmatter) for inline fields:
   `Hardware_Link:: [[TRM__STM32_Body_Board]]`

---

## Stage 7: ChromaDB — Collections and Schema

```python
import chromadb

client = chromadb.PersistentClient(path="/Users/lab/research/VectorMap/data/chroma_db_v2")

# Create with metadata
col_repo = client.get_or_create_collection(
    name="repo_code",
    metadata={"hnsw:space": "cosine"}
)

# Add chunks in batches of 100
col_repo.add(
    documents=[chunk["content"] for chunk in batch],
    ids=[chunk["chunk_id"] for chunk in batch],
    metadatas=[{
        "repo": chunk["repo"],
        "file": chunk["file"],
        "line_start": chunk["line_start"],
        "language": chunk["language"],
        "symbol_type": chunk["symbol_type"],
        "token_count": chunk["token_count"],
        "content_type": "repo_code",
        "llm_summary": chunk.get("llm_summary", ""),
    } for chunk in batch]
)
```

**Five collections required:**
- `repo_code` — all repository symbols
- `trm_prose` — TRM narrative text blocks
- `trm_code` — TRM code snippets
- `trm_tables` — TRM table rows (use `structured_text` field as document)
- `trm_notes` — TRM developer notes (add `"priority": "HIGH"` to metadata)

---

## Error Handling

Every file-processing loop MUST use try/except:

```python
for repo, filepath in all_files:
    try:
        result = process_file(filepath)
        all_results.append(result)
    except Exception as e:
        logging.error(f"FAILED: {filepath} | {type(e).__name__}: {e}", exc_info=True)
        failed_files.append({"file": filepath, "error": str(e)})
        continue  # never crash the pipeline

# Save failed files for review
with open("pipeline_output/logs/failed_files.json", "w") as f:
    json.dump(failed_files, f, indent=2)
logging.info(f"Pipeline complete. Failed: {len(failed_files)} files.")
```

Acceptable failure rate: < 2% of files. If > 5% fail, stop and investigate.
