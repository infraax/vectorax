# VaultForge — Vector Ecosystem Knowledge Pipeline

## What This Is

VaultForge is the build system for the VectorMap knowledge base. It transforms raw source
repositories and the VectorTRM technical reference manual into a rich, LLM-optimized
Obsidian vault + ChromaDB index that VectorMap uses as its data source.

## The Problem With the Current Vault

The existing vault at `sources/existing_vault_reference/` was created by Gemini using:
- `pdftotext` on the 565-page TRM → 50,000 line flat text file (lost all tables, figures, code blocks, developer notes)
- Line-by-line string scanning on repos → missed function signatures, parameters, docstrings
- Word-overlap "dependency detection" → massive false positives in cross-links
- 1500-char source truncation → LLM only sees first 2-3 functions per file
- No LLM annotations → raw code, no interpretation
- No cross-repo similarity detection
- No token-awareness in chunks

## What VaultForge Builds

A new vault at `/Users/lab/research/VectorMap/data/Vector_Obsidian_Vault_V2/` with:

| Content | Old Vault | New Vault |
|---|---|---|
| TRM tables (pin maps, specs) | Lost | Structured rows, fully linked |
| TRM code snippets | Indistinct from prose | Fenced, language-tagged, repo-linked |
| TRM figures/diagrams | Lost | PNG + LLM vision description |
| Developer notes/warnings | Lost | Highest-priority content type |
| Function signatures | `def foo` only | Full sig, params, return types, docstrings |
| Import dependencies | Word-overlap guesses | Resolved module paths |
| Cross-repo relationships | None | Clone detection + true import graph |
| LLM annotations | None | Every function, class, file, repo |
| Chunk metadata | 4 fields | 25+ fields with full provenance |
| Token counting | Char/word estimate | tiktoken exact count |
| Embedding model | Generic sentence transformer | Code-aware (Jina Code) |

## Directory Layout

```
VaultForge/
├── README.md                    ← You are here
├── docs/
│   ├── 01_OVERVIEW.md           ← Architecture and goals
│   ├── 02_SEQUENCE.md           ← Step-by-step execution order (START HERE)
│   ├── 03_PIPELINE_SPEC.md      ← Technical spec: all 8 stages
│   ├── 04_TRM_SPEC.md           ← VectorTRM.pdf parsing (565 pages)
│   ├── 05_VAULT_SPEC.md         ← Obsidian vault structure
│   ├── 06_DATABASE_SPEC.md      ← ChromaDB, SQLite, BM25
│   ├── 07_TEST_PLAN.md          ← Verification tests
│   └── 08_VECTORMAP_INTEGRATION.md ← Connecting to VectorMap
├── config/
│   └── pipeline.yaml            ← Master pipeline configuration
├── sources/
│   ├── repositories/            ← symlink → /VectorMap/data/Repositories/ (13 repos, 816MB)
│   ├── VectorTRM.pdf            ← symlink → /research/Sources/VectorTRM.pdf (565 pages)
│   ├── existing_vault_reference/← symlink → current vault (Gemini-generated, for reference only)
│   └── gemini_scripts_reference/← symlink → original Gemini scripts (for reference only)
└── NEW_SESSION_PROMPT.md        ← Paste this to Claude to start the build session
```

## Quick Facts for the Build Session

| Item | Path |
|---|---|
| 13 Repositories | `sources/repositories/` → actual path: `/Users/lab/research/VectorMap/data/Repositories/` |
| VectorTRM PDF | `sources/VectorTRM.pdf` → actual path: `/Users/lab/research/Sources/VectorTRM.pdf` |
| Python venv | `/Users/lab/research/VectorMap/agent_env/` |
| pip | `/Users/lab/research/VectorMap/agent_env/bin/pip` |
| python | `/Users/lab/research/VectorMap/agent_env/bin/python` |
| New vault output | `/Users/lab/research/VectorMap/data/Vector_Obsidian_Vault_V2/` (create this) |
| New ChromaDB output | `/Users/lab/research/VectorMap/data/chroma_db_v2/` (create this) |
| VectorMap server | `/Users/lab/research/VectorMap/src/server.py` |
| VectorMap config | `/Users/lab/research/VectorMap/src/langgraph_agent.py` — VAULT_PATH and DB_PATH |
| Existing vault (Gemini) | `/Users/lab/research/VectorMap/data/Vector_Obsidian_Vault_TEST/` |
| Existing ChromaDB | `/Users/lab/research/VectorMap/data/chroma_db_test/` (41,363 chunks — DO NOT MODIFY) |

## Repositories to Process (in dependency order)

1. `vector` — core robot firmware (C++) — most hardware-adjacent
2. `chipper` — voice processing + gRPC server (Go) — central hub
3. `vector-cloud` — cloud backend (Go)
4. `vector-python-sdk` — Python SDK (Python) — primary LLM-facing API
5. `vector-go-sdk` — Go SDK (Go)
6. `wire-pod` — community local server (Go) — many chipper forks
7. `escape-pod-extension` — local AI processing (Go)
8. `hugh` — face recognition (Go)
9. `vector-bluetooth` — BLE onboarding (Go/JS)
10. `dev-docs` — documentation (Markdown)
11. `vector-web-setup` — web UI (JS/HTML)
12. `vectorx` — community extensions
13. `vectorx-voiceserver` — voice server extension

## Read Order for New Claude Session

```
README.md (this file)
  → docs/02_SEQUENCE.md        (the playbook — what to do in what order)
  → docs/01_OVERVIEW.md        (understand the architecture)
  → docs/03_PIPELINE_SPEC.md   (technical details for implementation)
  → docs/04_TRM_SPEC.md        (TRM-specific parsing)
  → docs/05_VAULT_SPEC.md      (what the vault should look like)
  → docs/06_DATABASE_SPEC.md   (ChromaDB + SQLite setup)
  → docs/07_TEST_PLAN.md       (how to verify everything)
  → config/pipeline.yaml       (configuration reference)
```
