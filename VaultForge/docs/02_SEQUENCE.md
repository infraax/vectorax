# VaultForge — Execution Sequence

This is the playbook. Execute phases in order. Do not skip ahead.
Each phase has a verification step before proceeding.

---

## PHASE 0 — Environment Setup

### 0.1 — Install Required Packages

Use the VectorMap venv exclusively. Do NOT create a new venv.

```bash
/Users/lab/research/VectorMap/agent_env/bin/pip install \
  pymupdf \
  pymupdf4llm \
  pdfplumber \
  tree-sitter \
  tree-sitter-languages \
  gitpython \
  datasketch \
  tiktoken \
  rank-bm25 \
  libcst \
  radon \
  pyarrow \
  kuzu
```

### 0.2 — Verify Imports

```python
# Run this as a quick sanity check:
import fitz          # PyMuPDF
import pdfplumber
import pymupdf4llm
import tree_sitter_languages
import git
import datasketch
import tiktoken
import rank_bm25
import libcst
import radon
print("All imports OK")
```

### 0.3 — Create Output Directories

```bash
mkdir -p /Users/lab/research/VectorMap/data/Vector_Obsidian_Vault_V2
mkdir -p /Users/lab/research/VectorMap/data/chroma_db_v2
mkdir -p /Users/lab/research/VaultForge/pipeline_output/trm_figures
mkdir -p /Users/lab/research/VaultForge/pipeline_output/trm_structured
mkdir -p /Users/lab/research/VaultForge/pipeline_output/symbol_tables
mkdir -p /Users/lab/research/VaultForge/pipeline_output/chunks
mkdir -p /Users/lab/research/VaultForge/pipeline_output/annotations_cache
mkdir -p /Users/lab/research/VaultForge/pipeline_output/clone_pairs
mkdir -p /Users/lab/research/VaultForge/pipeline_output/logs
```

### 0.4 — Verify Source Access

```bash
# Should show 13 repo directories
ls /Users/lab/research/VectorMap/data/Repositories/ | wc -l

# Should show file size > 500MB
ls -lh /Users/lab/research/Sources/VectorTRM.pdf

# Should show existing vault files
ls /Users/lab/research/VectorMap/data/Vector_Obsidian_Vault_TEST/ | head -5
```

**STOP if any of the above fail.**

---

## PHASE 1 — TRM Processing (The Root Source of Truth)

Start with the TRM because:
- It defines the canonical hardware specifications that all code references
- TRM code snippets must be linked to repo symbols — repos must not be processed yet
- TRM developer notes are the highest-value content in the entire system
- The TRM component registry feeds into hardware binding tags for repo chunks

### 1.1 — Structural Scan

Script: write `pipeline/trm_scanner.py`

For each page of `sources/VectorTRM.pdf`:
- Extract all text blocks with font metadata (size, bold, monospace flags)
- Classify each block: `chapter_heading | section_heading | prose | code | table_region | figure_region | developer_note`
- Output: `pipeline_output/trm_structured/page_map.json`

Block classification rules (use PyMuPDF `page.get_text("dict")`):
- `font_size > 16 AND bold` → `chapter_heading`
- `font_size 12–16 AND bold` → `section_heading`
- `font_name contains "Mono" OR "Courier" OR "Code"` → `code`
- `block has no text lines (only image bbox)` → `figure_region`
- `text starts with "NOTE:", "WARNING:", "IMPORTANT:", "DESIGN DECISION:", "CAUTION:"` → `developer_note`
- All remaining → `prose`

### 1.2 — Table Extraction

Script: write `pipeline/trm_tables.py`

For each page in `page_map.json` that has a `table_region`:
- Use `pdfplumber` to extract structured table data (preserves column alignment)
- Also extract caption text (typically the line above or below the table region)
- Output: one JSON file per table in `pipeline_output/trm_structured/tables/`

Format: `{"table_id": "T4.1", "caption": "GPIO Pin Assignments", "page": 47, "headers": [...], "rows": [...]}`

### 1.3 — Code Snippet Extraction

Script: write `pipeline/trm_code.py`

For each code block identified in `page_map.json`:
- Extract raw text preserving indentation
- Detect language: C patterns (`void`, `uint8_t`, `#define`, `->`, `{}`), Go patterns, Python patterns, Proto patterns
- Try to extract function name from first line
- Output: one JSON file per snippet in `pipeline_output/trm_structured/code_snippets/`

Format: `{"snippet_id": "C4.1", "page": 47, "chapter": "...", "section": "...", "language": "c", "function_name": "PID_Update", "content": "..."}`

### 1.4 — Figure Extraction

Script: write `pipeline/trm_figures.py`

For each `figure_region` in `page_map.json`:
- Use PyMuPDF to render that page region to PNG at 200 DPI
- Save to `pipeline_output/trm_figures/fig_PAGE_IDX.png`
- Use Ollama (already running in VectorMap stack) with a vision-capable model to describe the figure
  - If no vision model available, store placeholder and skip — figure PNGs are still saved for manual review
- Output: JSON with `{"figure_id": "F4.3", "page": 47, "caption": "...", "image_path": "...", "llm_description": "..."}`

Check which vision model is available:
```bash
curl -s http://127.0.0.1:11434/api/tags | python3 -c "import sys,json; [print(m['name']) for m in json.load(sys.stdin)['models']]"
```

### 1.5 — Developer Note Extraction

Script: write `pipeline/trm_notes.py`

For each `developer_note` block in `page_map.json`:
- Extract full text
- Classify note type: `WARNING | NOTE | DESIGN_DECISION | IMPORTANT | CAUTION`
- Record context: which chapter/section it appears in, surrounding prose block
- Output: `pipeline_output/trm_structured/developer_notes.json`

Developer notes are HIGH PRIORITY — they contain engineering decisions that exist NOWHERE ELSE.

### 1.6 — Cross-Reference Resolution

Script: write `pipeline/trm_crossrefs.py`

Scan all prose blocks for patterns: `see Section X.X`, `refer to Figure X.X`, `Table X.X`, `Chapter X`
Build a reference map: `{"Section 4.2": {"page": 47, "vault_note": "TRM_Ch04_Sec4.2_PID_Loop.md"}}`
This map is used during vault generation to convert references to WikiLinks.

Output: `pipeline_output/trm_structured/cross_reference_map.json`

### 1.7 — TRM Verification

```bash
# Check outputs exist and are non-empty
python3 -c "
import json, os
page_map = json.load(open('pipeline_output/trm_structured/page_map.json'))
tables   = os.listdir('pipeline_output/trm_structured/tables/')
snippets = os.listdir('pipeline_output/trm_structured/code_snippets/')
figures  = os.listdir('pipeline_output/trm_figures/')
notes    = json.load(open('pipeline_output/trm_structured/developer_notes.json'))
print(f'Pages mapped:      {len(page_map)}')
print(f'Tables extracted:  {len(tables)}')
print(f'Code snippets:     {len(snippets)}')
print(f'Figures extracted: {len(figures)}')
print(f'Developer notes:   {len(notes)}')
"
```

Expected: pages ≈ 565, tables > 50, code snippets > 100, developer notes > 30

**STOP AND REVIEW if developer_notes < 20 or code_snippets < 50 — extraction is likely failing.**

---

## PHASE 2 — Repository Deep Parse

Process repos in the dependency order listed in README. Do NOT parallelize across repos during initial build (symbol table must be built incrementally).

### 2.1 — Git Metadata Collection

Script: write `pipeline/repo_git_meta.py`

For each repo in `sources/repositories/`:
```python
import git
repo = git.Repo(repo_path)
# Per-repo: collect head commit SHA, date, contributors
# Per-file: collect last commit SHA, last author, commit count (hotness), file age
```
Output: `pipeline_output/symbol_tables/{repo_name}_git_meta.json`

### 2.2 — Multi-Language AST Parse

Script: write `pipeline/repo_parser.py`

Use `tree-sitter-languages` which provides pre-compiled parsers for all needed languages.

```python
from tree_sitter_languages import get_parser
parser = get_parser('python')  # or 'go', 'c', 'cpp', 'javascript', 'typescript'
```

**Per file, extract:**

| Language | Extensions | Extract |
|---|---|---|
| Python | `.py` | classes (with bases, methods, properties), functions (sig, params, return, decorators), imports, module docstring, `__all__` |
| Go | `.go` | packages, structs (with fields), interfaces, functions (with receivers), imports, build tags |
| C/C++ | `.c .h .cpp .hpp` | structs, enums, typedefs, function prototypes, `#include` graph, `#define` macros |
| JavaScript | `.js .mjs` | classes, functions, arrow functions, `require()`/`import`, exports |
| TypeScript | `.ts .tsx` | all JS + interfaces, type aliases, generics, decorators |
| Proto | `.proto` | service definitions, RPC methods, message types, field names + numbers |
| Bash | `.sh` | functions, sourced files, key env vars |
| YAML | `.yaml .yml` | top-level structure keys (depth 1–2) |
| Markdown | `.md` | heading hierarchy, code block languages |

For each symbol, record minimum:
```json
{
  "type": "function",
  "name": "set_eye_color",
  "qualified_name": "anki_vector.behavior.BehaviorComponent.set_eye_color",
  "repo": "vector-python-sdk",
  "file": "anki_vector/behavior.py",
  "line_start": 247,
  "line_end": 283,
  "signature": "def set_eye_color(self, hue: float, saturation: float) -> None",
  "docstring": "Set Vector's eye color...",
  "token_count": 187
}
```

Output: `pipeline_output/symbol_tables/{repo_name}_symbols.json`

### 2.3 — Import Resolution

Script: write `pipeline/import_resolver.py`

After ALL repos have been parsed (symbol tables complete), run resolution:
- For each import in each file, determine if it resolves to another indexed repo
- Python: check if module name matches a package in another repo
- Go: check `go.mod` module path against indexed repos
- Proto: resolve `import "path/to.proto"` against indexed `.proto` files

Output: `pipeline_output/symbol_tables/cross_repo_imports.json`

Format:
```json
[
  {
    "source_repo": "vector-python-sdk",
    "source_file": "anki_vector/behavior.py",
    "import_statement": "from . import messaging",
    "resolves_to_repo": "vector-python-sdk",
    "resolves_to_file": "anki_vector/messaging/__init__.py",
    "is_cross_repo": false
  },
  {
    "source_repo": "wire-pod",
    "source_file": "chipper/cmd/main.go",
    "import_statement": "\"github.com/digital-dream-labs/chipper/pkg/vtt\"",
    "resolves_to_repo": "chipper",
    "is_cross_repo": true,
    "confidence": 0.95
  }
]
```

### 2.4 — TRM ↔ Repository Cross-Linking

Script: write `pipeline/trm_repo_linker.py`

For each TRM code snippet extracted in Phase 1.3:
- Search its function name against all symbol tables
- Search its variable/type names against all `#define` and struct names
- Record matches with confidence score

For each TRM table row with hardware identifiers (GPIO names, register names, constants):
- Search against C `#define` names across repos
- Search against Go constant definitions

Output: `pipeline_output/trm_structured/trm_repo_links.json`
```json
[
  {
    "trm_snippet_id": "C4.1",
    "trm_function": "PID_Update",
    "matches": [
      {"repo": "vector", "file": "hal/motor/stm32_pid.c", "function": "PID_Update", "confidence": 0.95},
      {"repo": "chipper", "file": "motor_ctrl.go", "function": "UpdatePID", "confidence": 0.61}
    ]
  }
]
```

### 2.5 — Code Similarity Detection

Script: write `pipeline/similarity_detector.py`

Use `datasketch` MinHash for fast similarity:
```python
from datasketch import MinHash, MinHashLSH

# Tokenize each function body at the token level
# Compute MinHash signature (128 permutations)
# Use LSH with threshold=0.60 to find candidate pairs
# For each candidate pair above threshold: record similarity score
```

Output: `pipeline_output/clone_pairs/similarity_pairs.json`
Classify each pair:
- `similarity > 0.95` → `exact_copy`
- `0.80–0.95` → `near_identical_fork`
- `0.60–0.80` → `fork_with_modifications`

### 2.6 — Metrics Collection

Script: write `pipeline/metrics_collector.py`

Use `radon` for Python files:
```python
from radon.complexity import cc_visit    # cyclomatic complexity
from radon.metrics import mi_visit       # maintainability index
```

For all files: count TODO/FIXME/HACK/DEPRECATED/XXX comments with line numbers.

Output: `pipeline_output/symbol_tables/metrics.json`

---

## PHASE 3 — LLM Annotation Pass

Use Ollama (already running at `http://127.0.0.1:11434`) to annotate all extracted symbols.

### 3.1 — Check Annotation Cache

Script: write `pipeline/annotator.py`

Before annotating: hash the source content. Check SQLite cache (`pipeline_output/annotations_cache/cache.db`).
Only annotate if not in cache. This makes re-runs fast.

```sql
CREATE TABLE annotations (
  content_hash TEXT PRIMARY KEY,
  annotation_level TEXT,  -- function | class | file | repo
  llm_summary TEXT,
  purpose_tags TEXT,       -- JSON array
  complexity TEXT,
  annotated_at TEXT,
  model_used TEXT
);
```

### 3.2 — Function-Level Annotation (Level 1 — run for all)

For every function/method with at least a docstring or >5 lines of code:
```
Prompt:
Repository: {repo} | File: {file} | Language: {lang}
Signature: {signature}
Docstring: {docstring or 'none'}
Body:
{source_code}

In 2 sentences: (1) what this function does, (2) when it is called.
Return JSON only: {"summary": "...", "called_when": "...", "tags": [...], "complexity": "simple|moderate|complex"}
```

Batch process: group 10 functions per Ollama request if model supports it.

### 3.3 — Class-Level Annotation (Level 2)

For each class/struct: summarize role, responsibilities, key methods, thread-safety notes.

### 3.4 — File-Level Annotation (Level 3)

For each file: what problem does this module solve, what is its public API surface, key dependencies explained.

### 3.5 — Repo-Level Annotation (Level 4)

For each repo: purpose in the Vector ecosystem, relationships to other repos, main data flows.

### 3.6 — Cross-Repo Clone Narratives (Level 5)

For each clone pair with `fork_with_modifications`:
- Feed both function bodies to LLM
- Ask: "What changes were made in the fork and why might they have been made?"
- Store narrative in clone_pairs record

---

## PHASE 4 — Chunk Construction

Script: write `pipeline/chunker.py`

### Rules

1. **Function-level first:** If a function is <300 tokens, it is one chunk.
2. **Class-level for small classes:** Class header + all methods < 400 tokens combined = one chunk.
3. **Split large classes:** At method boundaries. Keep class header (first 3 lines) prepended to each method chunk.
4. **Overlap:** 50-token overlap between sequential chunks from the same file.
5. **TRM chunks:** Each TRM content block (prose/code/table/note) becomes one chunk with its own type.
6. **Never split mid-function, mid-sentence, or mid-table-row.**

### Token counting

```python
import tiktoken
enc = tiktoken.get_encoding("cl100k_base")
token_count = len(enc.encode(text))
```

Max chunk size: 512 tokens for code, 768 tokens for prose, 256 tokens for tables.

### Chunk Metadata (required fields on every chunk)

```json
{
  "chunk_id": "sha256 of content",
  "repo": "vector-python-sdk",
  "file": "anki_vector/behavior.py",
  "line_start": 247,
  "line_end": 283,
  "commit_sha": "a3f2b1c",
  "last_author": "aDeveloper",
  "symbol_type": "method",
  "symbol_name": "set_eye_color",
  "class_context": "BehaviorComponent",
  "language": "python",
  "content": "...",
  "token_count": 187,
  "llm_summary": "...",
  "purpose_tags": ["hardware_control", "eye", "grpc"],
  "complexity": "simple",
  "hardware_binds": ["TRM__Face_Display"],
  "imports_from": ["anki_vector.connection"],
  "similar_to": [{"chunk_id": "...", "repo": "wire-pod", "similarity": 0.74}],
  "trm_reference": {"page": 47, "section": "4.2", "snippet_id": "C4.1"},
  "has_todo": false,
  "obsidian_node": "vector-python-sdk__behavior_py__BehaviorComponent__set_eye_color.md"
}
```

Output: `pipeline_output/chunks/all_chunks.jsonl` (one JSON object per line)

---

## PHASE 5 — Obsidian Vault Generation

Script: write `pipeline/vault_generator.py`

Output directory: `/Users/lab/research/VectorMap/data/Vector_Obsidian_Vault_V2/`

See `docs/05_VAULT_SPEC.md` for the complete folder structure and note formats.

### Key rules:
- Every WikiLink `[[Note Name]]` must correspond to a note that will actually be created
- YAML frontmatter on every note — Dataview-compatible
- Every cross-link derived from resolved imports (Phase 2.3) — no word-matching
- TRM cross-links come from Phase 2.4 trm_repo_links
- Canvas files for: System Architecture, gRPC Map, Hardware Binding Map, Clone Detection Graph

---

## PHASE 6 — Database Population

Script: write `pipeline/db_writer.py`

See `docs/06_DATABASE_SPEC.md` for full schema.

### 6.1 — SQLite Metadata DB

Write to `/Users/lab/research/VaultForge/pipeline_output/pipeline_metadata.db`:
- `file_index` table — all files, languages, metrics
- `symbol_index` table — all functions, classes, structs
- `clone_pairs` table — similarity results
- `trm_chunks` table — TRM-specific chunks with type classification
- `annotations` table — LLM annotation cache
- `pipeline_runs` table — build metadata

### 6.2 — ChromaDB Population

Write to `/Users/lab/research/VectorMap/data/chroma_db_v2/`

Four collections (see `docs/06_DATABASE_SPEC.md`):
- `repo_code` — all repository code chunks
- `trm_prose` — TRM narrative text
- `trm_code` — TRM code snippets
- `trm_tables` — TRM table rows (linearized)
- `trm_notes` — TRM developer notes (priority: HIGH)

Use embedding model: `nomic-embed-text` via Ollama (already in your stack).
Batch size: 32 chunks per embed call.

### 6.3 — BM25 Index

```python
from rank_bm25 import BM25Okapi
# Index: symbol names, function signatures, docstrings, LLM summaries
# Save index with pickle for fast reload
```

---

## PHASE 7 — VectorMap Integration

See `docs/08_VECTORMAP_INTEGRATION.md` for full steps.

Short version:
1. Update `VAULT_PATH` and `DB_PATH` in `/Users/lab/research/VectorMap/src/langgraph_agent.py`
2. Run VectorMap indexer via the dashboard (Page 1 → UPDATE VAULT CACHE)
3. Verify chunk count increases from 41,363 to expected new count

---

## PHASE 8 — Testing

Run ALL tests before declaring success.
See `docs/07_TEST_PLAN.md` for the full test suite.

Quick smoke test:
```bash
cd /Users/lab/research/VaultForge
/Users/lab/research/VectorMap/agent_env/bin/python -m pytest tests/ -v --tb=short
```

---

## Logging

Every script should log to `pipeline_output/logs/pipeline.log`:
```python
import logging
logging.basicConfig(
    filename='/Users/lab/research/VaultForge/pipeline_output/logs/pipeline.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s'
)
```

On error: log the full traceback, file path, and continue to the next file. Do NOT crash the pipeline on a single file parse failure.
