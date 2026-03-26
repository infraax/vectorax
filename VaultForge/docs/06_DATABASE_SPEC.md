# VaultForge — Database Specification

## ChromaDB V2

**Location:** `/Users/lab/research/VectorMap/data/chroma_db_v2/`
**DO NOT touch:** `/Users/lab/research/VectorMap/data/chroma_db_test/` (old Gemini vault — keep as fallback)

### Collections

| Collection | Contents | n_results default |
|---|---|---|
| `repo_code` | All repository symbols (functions, classes, structs) | 8 |
| `trm_prose` | TRM chapter/section narrative text | 5 |
| `trm_code` | TRM extracted code snippets | 5 |
| `trm_tables` | TRM tables linearized as text | 5 |
| `trm_notes` | TRM developer notes — HIGH PRIORITY | 3 |

### Required Metadata Fields Per Collection

**`repo_code`:**
```python
{
    "content_type":  "repo_code",
    "repo":          str,      # "vector-python-sdk"
    "file":          str,      # "anki_vector/behavior.py"
    "line_start":    int,      # 247
    "line_end":      int,      # 283
    "language":      str,      # "python"
    "symbol_type":   str,      # "method" | "function" | "class" | "struct"
    "symbol_name":   str,      # "set_eye_color"
    "class_context": str,      # "BehaviorComponent" (empty string if not in class)
    "token_count":   int,      # 187
    "commit_sha":    str,      # "a3f2b1c"
    "llm_summary":   str,      # LLM-generated summary (empty string if not annotated)
    "hardware_binds":str,      # JSON array string: '["TRM__Face_Display_IPS"]'
    "has_trm_link":  bool,     # True if TRM code snippet links to this
}
```

**`trm_notes`:**
```python
{
    "content_type":       "trm_note",
    "note_id":            str,      # "N4.1"
    "note_type":          str,      # "NOTE" | "WARNING" | "DESIGN_DECISION"
    "chapter":            str,
    "section":            str,
    "page":               int,
    "priority":           str,      # always "HIGH"
    "hardware_mentions":  str,      # JSON array string
    "token_count":        int,
}
```

**`trm_tables`:**
```python
{
    "content_type":       "trm_table",
    "table_id":           str,      # "T4.1"
    "caption":            str,
    "chapter":            str,
    "page":               int,
    "hardware_component": str,      # "TRM__STM32_Body_Board"
    "token_count":        int,
}
```

### Multi-Collection Query Pattern

When VectorMap searches, it should query across collections and merge:

```python
def multi_search(query_text, k_per_collection=5):
    results = []
    for col_name in ["repo_code", "trm_notes", "trm_code", "trm_tables", "trm_prose"]:
        col = client.get_collection(col_name)
        r = col.query(query_texts=[query_text], n_results=k_per_collection)
        for doc, meta, dist in zip(r["documents"][0], r["metadatas"][0], r["distances"][0]):
            results.append({
                "content": doc,
                "metadata": meta,
                "score": 1 - dist/2,   # convert L2 distance to 0-1 score
                "collection": col_name,
            })
    # Sort by score, return top k
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:20]
```

---

## SQLite Metadata Database

**Location:** `/Users/lab/research/VaultForge/pipeline_output/pipeline_metadata.db`

This is NOT the VectorMap query_history.db — it's the pipeline's own metadata store.

```sql
-- Pipeline run tracking
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at      TEXT NOT NULL,
    completed_at    TEXT,
    phase           TEXT,           -- which phase completed
    repos_processed INTEGER DEFAULT 0,
    files_processed INTEGER DEFAULT 0,
    symbols_extracted INTEGER DEFAULT 0,
    chunks_created  INTEGER DEFAULT 0,
    trm_blocks      INTEGER DEFAULT 0,
    annotations_generated INTEGER DEFAULT 0,
    errors          INTEGER DEFAULT 0,
    status          TEXT            -- running | complete | failed
);

-- File index (fast lookups, avoid re-parsing)
CREATE TABLE IF NOT EXISTS file_index (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    repo            TEXT NOT NULL,
    file_path       TEXT NOT NULL,
    language        TEXT,
    line_count      INTEGER,
    token_count     INTEGER,
    commit_sha      TEXT,
    commit_date     TEXT,
    last_author     TEXT,
    hotness         INTEGER,        -- commit count
    complexity      TEXT,
    symbol_count    INTEGER,
    chunk_ids       TEXT,           -- JSON array of chunk_id strings
    parsed_at       TEXT,
    UNIQUE(repo, file_path)
);

-- Symbol index
CREATE TABLE IF NOT EXISTS symbol_index (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    qualified_name  TEXT,
    type            TEXT,           -- function | class | method | struct | interface
    repo            TEXT NOT NULL,
    file_path       TEXT NOT NULL,
    line_start      INTEGER NOT NULL,
    line_end        INTEGER,
    language        TEXT,
    signature       TEXT,
    docstring       TEXT,
    llm_summary     TEXT,
    complexity      TEXT,
    token_count     INTEGER,
    hardware_binds  TEXT,           -- JSON array
    trm_snippet_id  TEXT,           -- if linked to TRM code snippet
    chunk_id        TEXT
);

-- Clone/similarity pairs
CREATE TABLE IF NOT EXISTS clone_pairs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol_a_id     INTEGER REFERENCES symbol_index(id),
    symbol_b_id     INTEGER REFERENCES symbol_index(id),
    repo_a          TEXT,
    repo_b          TEXT,
    similarity_token REAL,
    similarity_ast  REAL,
    relationship    TEXT,           -- exact_copy | near_identical_fork | fork_with_modifications
    llm_narrative   TEXT,           -- LLM explanation of the differences
    detected_at     TEXT
);

-- TRM content index
CREATE TABLE IF NOT EXISTS trm_index (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    block_type      TEXT NOT NULL,  -- prose | code | table | figure | developer_note
    block_id        TEXT UNIQUE,    -- e.g. "C4.1", "T4.1", "N4.1", "F4.3"
    chapter         TEXT,
    section         TEXT,
    page            INTEGER,
    content_preview TEXT,           -- first 200 chars
    token_count     INTEGER,
    priority        TEXT,           -- HIGH for developer notes
    vault_note_path TEXT,           -- relative path in vault
    chunk_id        TEXT
);

-- TRM to repository links
CREATE TABLE IF NOT EXISTS trm_repo_links (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    trm_block_id    TEXT,           -- references trm_index.block_id
    repo            TEXT,
    file_path       TEXT,
    symbol_name     TEXT,
    confidence      REAL,           -- 0.0-1.0
    match_type      TEXT            -- exact_name | near_match | type_match
);

-- LLM annotation cache
CREATE TABLE IF NOT EXISTS annotation_cache (
    content_hash    TEXT PRIMARY KEY,   -- sha256 of source content
    annotation_level TEXT,              -- function | class | file | repo
    llm_summary     TEXT,
    purpose_tags    TEXT,               -- JSON array
    complexity      TEXT,
    model_used      TEXT,
    annotated_at    TEXT
);

-- TODO/FIXME/HACK tracker
CREATE TABLE IF NOT EXISTS code_todos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    repo            TEXT,
    file_path       TEXT,
    line_number     INTEGER,
    todo_type       TEXT,           -- TODO | FIXME | HACK | DEPRECATED | XXX
    text            TEXT,
    author          TEXT,           -- from git blame
    commit_sha      TEXT
);

-- Create indexes for fast lookup
CREATE INDEX IF NOT EXISTS idx_symbol_repo ON symbol_index(repo);
CREATE INDEX IF NOT EXISTS idx_symbol_name ON symbol_index(name);
CREATE INDEX IF NOT EXISTS idx_file_repo   ON file_index(repo);
CREATE INDEX IF NOT EXISTS idx_trm_type    ON trm_index(block_type);
CREATE INDEX IF NOT EXISTS idx_trm_page    ON trm_index(page);
```

---

## BM25 Index

**Location:** `pipeline_output/bm25_index.pkl`

```python
from rank_bm25 import BM25Okapi
import pickle, re

def tokenize_for_bm25(text):
    """Simple tokenizer: lowercase, split on non-alphanumeric"""
    return re.findall(r'[a-z0-9_]+', text.lower())

def build_bm25_index(all_chunks):
    """
    Build BM25 index over:
    - symbol names
    - function signatures
    - docstrings
    - LLM summaries
    - TRM developer note content
    """
    corpus = []
    chunk_index = []  # parallel list: chunk_index[i] = chunk for corpus[i]

    for chunk in all_chunks:
        # Concatenate all searchable text fields
        text_fields = [
            chunk.get("symbol_name", ""),
            chunk.get("signature", ""),
            chunk.get("docstring", ""),
            chunk.get("llm_summary", ""),
            chunk.get("content", "")[:500],  # first 500 chars of source
        ]
        combined = " ".join(f for f in text_fields if f)
        tokens = tokenize_for_bm25(combined)
        corpus.append(tokens)
        chunk_index.append(chunk["chunk_id"])

    bm25 = BM25Okapi(corpus)

    with open("pipeline_output/bm25_index.pkl", "wb") as f:
        pickle.dump({"bm25": bm25, "chunk_ids": chunk_index}, f)

    return bm25

def bm25_search(query, bm25_data, top_k=10):
    tokens = tokenize_for_bm25(query)
    scores = bm25_data["bm25"].get_scores(tokens)
    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
    return [(bm25_data["chunk_ids"][i], scores[i]) for i in top_indices if scores[i] > 0]
```

---

## VectorMap Integration — langgraph_agent.py Changes

After the pipeline completes, update these two variables in
`/Users/lab/research/VectorMap/src/langgraph_agent.py`:

```python
# OLD (Gemini vault):
VAULT_PATH = os.path.join(os.path.dirname(__file__), "../data/Vector_Obsidian_Vault_TEST")
DB_PATH    = os.path.join(os.path.dirname(__file__), "../data/chroma_db_test")

# NEW (VaultForge vault):
VAULT_PATH = os.path.join(os.path.dirname(__file__), "../data/Vector_Obsidian_Vault_V2")
DB_PATH    = os.path.join(os.path.dirname(__file__), "../data/chroma_db_v2")
```

Also update the ChromaDB collection name if the agent uses a hardcoded collection:
Search `langgraph_agent.py` for any hardcoded collection name and update to `repo_code`
(or update the agent to query across all 5 collections using the multi-collection search pattern above).
