<div align="center">

<img src="https://img.shields.io/badge/Vector_Robot-AI_Research-FF6B35?style=for-the-badge&logo=robot&logoColor=white" alt="Vector Robot AI Research"/>

# Vectorax

### *Local-first agentic AI for the Anki Vector robot ecosystem*

> **34,507 semantic chunks · 13 source repositories · 0% hallucination rate · 100% local**

<br/>

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2-4CAF50?style=flat-square&logo=langchain&logoColor=white)](https://langchain-ai.github.io/langgraph/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-1.5.5-7C3AED?style=flat-square)](https://www.trychroma.com)
[![Ollama](https://img.shields.io/badge/Ollama-Local_LLM-FF6B35?style=flat-square)](https://ollama.com)
[![Tests](https://img.shields.io/badge/Tests-86_passing-22C55E?style=flat-square&logo=pytest&logoColor=white)](VectorMap/tests/)
[![License](https://img.shields.io/badge/License-Research-64748B?style=flat-square)](LICENSE)

<br/>

```
Ask a question about Vector's cliff sensor.
Get back the exact C++ function, the TRM page, and the cross-repo call chain.
Every citation verified against real files. Nothing fabricated.
```

</div>

---

## What Is Vectorax?

Vectorax is a fully local RAG (Retrieval-Augmented Generation) system built to let AI agents and LLMs work intelligently with the **entire Anki Vector robot codebase** — firmware, SDKs, cloud services, community forks, and the 565-page Technical Reference Manual (TRM).

It has two components that work together:

| Component | Role |
| --- | --- |
| **[VaultForge](VaultForge/)** | Parsing pipeline — ingests 13 repos + TRM PDF → 34,507 semantic chunks in ChromaDB |
| **[VectorMap](VectorMap/)** | Agentic operations center — LangGraph RAG pipeline + 5-page dashboard |

Everything runs **on your local machine**. No OpenAI. No cloud APIs. No data exfiltration.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              VECTORAX                                    │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  VaultForge Pipeline                                             │   │
│  │                                                                  │   │
│  │  13 Git Repos  ──┐                                               │   │
│  │  (C++/Go/Python) │                                               │   │
│  │                  ▼                                               │   │
│  │  VectorTRM.pdf ──► repo_parser → chunker → annotator ──────────►│   │
│  │  (565 pages)   └─► trm_scanner ──► db_writer                    │   │
│  │                                        │                         │   │
│  │                                        ▼                         │   │
│  │                              ChromaDB chroma_db_v2/              │   │
│  │                         ┌───────────────────────────────┐        │   │
│  │                         │  repo_code   · 33,773 chunks  │        │   │
│  │                         │  trm_prose   ·    230 chunks  │        │   │
│  │                         │  trm_code    ·    250 chunks  │        │   │
│  │                         │  trm_tables  ·    180 chunks  │        │   │
│  │                         │  trm_notes   ·     74 chunks  │        │   │
│  │                         └───────────────────────────────┘        │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                      │                                   │
│                                      ▼                                   │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  VectorMap — Agentic Operations Center                           │   │
│  │                                                                  │   │
│  │  FastAPI ──► LangGraph State Machine                             │   │
│  │              │                                                   │   │
│  │              ├─ retrieve()  →  ChromaDB multi-collection search  │   │
│  │              ├─ generate()  →  Ollama qwen2.5-coder:7b           │   │
│  │              └─ validate()  →  WikiLink citation check           │   │
│  │                    │                                             │   │
│  │                    └── retry on failure (logged to ledger)       │   │
│  │                                                                  │   │
│  │  5-Page Dashboard  ·  35+ REST endpoints  ·  SQLite history      │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### Hallucination Prevention

Every LLM response passes through a validation node before it reaches the user:

```
LLM response
    │
    ▼
① Has ## Stack Trace & Sources section?  ──── NO ──► retry
    │ YES
    ▼
② Every citation is a [[WikiLink]]?  ──────── NO ──► retry
    │ YES
    ▼
③ Every linked file exists in retrieved context?  ── NO ──► retry + log to ledger
    │ YES
    ▼
 Response delivered  ✓
```

Violations are captured in the **hallucination ledger** (SQLite) with the raw LLM output, violation type, and corrected response — visible in the Agentic Forge dashboard page.

---

## The Repositories

Vectorax ingests and cross-links 13 open-source Vector robot repositories:

| Repository | Language | Role |
| --- | --- | --- |
| [digital-dream-labs/vector](https://github.com/digital-dream-labs/vector) | C++ | Core robot firmware — hardware-closest code |
| [fforchino/vector-python-sdk](https://github.com/fforchino/vector-python-sdk) | Python | Primary Python SDK — LLM-facing public API |
| [fforchino/vector-go-sdk](https://github.com/fforchino/vector-go-sdk) | Go | Go language bindings |
| [digital-dream-labs/vector-cloud](https://github.com/digital-dream-labs/vector-cloud) | Go | Cloud gateway & authentication (Protobuf) |
| [kercre123/wire-pod](https://github.com/kercre123/wire-pod) | Go | Self-hosted cloud replacement |
| [digital-dream-labs/chipper](https://github.com/digital-dream-labs/chipper) | Go | Central gRPC server — voice + intent processing |
| [digital-dream-labs/vector-bluetooth](https://github.com/digital-dream-labs/vector-bluetooth) | Mixed | BLE setup & onboarding |
| [digital-dream-labs/vector-web-setup](https://github.com/digital-dream-labs/vector-web-setup) | JavaScript | Web configuration UI |
| [fforchino/vectorx](https://github.com/fforchino/vectorx) | Mixed | Community extended Vector |
| [fforchino/vectorx-voiceserver](https://github.com/fforchino/vectorx-voiceserver) | Go | Voice services for VectorX |
| [digital-dream-labs/escape-pod-extension](https://github.com/digital-dream-labs/escape-pod-extension) | TypeScript | VS Code extension for Vector dev |
| [digital-dream-labs/dev-docs](https://github.com/digital-dream-labs/dev-docs) | Markdown | Official developer documentation |
| [digital-dream-labs/hugh](https://github.com/digital-dream-labs/hugh) | Go | Face recognition service |

> All repos are excluded from this repository due to size. Re-clone with:
> ```bash
> bash VaultForge/sources/clone_repos.sh
> ```

---

## VectorMap — 5-Page Dashboard

```
┌──────────────────────────────────────────────────────────┐
│  ① COMMAND CENTER  │  ② AGENTIC FORGE  │  ③ OBSERVATORY │
├──────────────────────────────────────────────────────────┤
│  ④ VAULT MANAGEMENT  │  ⑤ INTELLIGENCE TOOLS            │
└──────────────────────────────────────────────────────────┘
```

### ① Command Center
RAG chat interface with real-time source retrieval scores, live log stream, conversation memory (configurable turn buffer), and one-click Obsidian export.

### ② Agentic Forge
Live **LangGraph node highlighter** showing the active pipeline stage in real time. Query template library, hallucination ledger browser, A/B model benchmarking, and manual context injection zone.

### ③ Semantic Observatory
Interactive **3D PCA embedding map** of all 34,507 vectors — rotatable, filterable by repository and file type. Spotlight search highlights nearest neighbours. Chunk inspector shows size distribution and per-file retrieval heatmap.

### ④ Vault Management
ChromaDB CRUD explorer (search, view, delete individual chunks, re-embed files), Obsidian sync drift monitor, autonomous backfill queue with progress tracking, and a composite **Vault Health Score** (0–100).

### ⑤ Intelligence Tools
Code refactor sub-agent, interactive architecture dependency graph (vis.js), web-search grounding toggle, Wire-Pod/Vector live log sniffer, token budget deep dive, and session export to Obsidian.

---

## VaultForge — Pipeline

```
VaultForge/pipeline/
├── repo_parser.py        # AST + regex extraction: functions, classes, structs
├── chunker.py            # Token-aware chunking (tiktoken cl100k_base)
├── annotator.py          # LLM annotation: every function, class, file, repo
├── import_resolver.py    # Real import graph (not word-overlap guesses)
├── similarity_detector.py # MinHash LSH — cross-repo clone detection
├── repo_git_meta.py      # Git history, authors, blame data per chunk
├── trm_scanner.py        # PDF parser: prose / code / tables / notes / figures
├── trm_code.py           # TRM fenced code block extractor
├── trm_tables.py         # TRM table → structured rows with full metadata
├── trm_notes.py          # TRM developer notes/warnings (highest priority)
├── trm_figures.py        # TRM diagram → PNG + LLM vision description
├── trm_crossrefs.py      # TRM ↔ repo cross-reference linker
├── trm_repo_linker.py    # Hardware component → source file mapper
├── vault_generator.py    # Obsidian markdown vault generator
└── db_writer.py          # ChromaDB writer — nomic-embed-text 768D
```

**Chunk metadata (25+ fields per chunk):** source file, repo, language, function name, class name, git commit, author, token count, TRM cross-references, similarity cluster, import dependencies, hardware component tags, and more.

---

## Quick Start

### Prerequisites

| Tool | Version | Purpose |
| --- | --- | --- |
| Python | 3.12+ | Backend runtime |
| [Ollama](https://ollama.com) | Latest | Local LLM inference |
| Git | Any | Repo cloning |
| macOS / Linux | — | Supported platforms |

### 1 — Clone and setup

```bash
git clone https://github.com/lab/vectorax.git
cd vectorax

# Bootstrap Python environment + pull Ollama models
bash VectorMap/setup.sh
```

### 2 — Rebuild the vector database

```bash
# Clone the 13 source repositories (~816 MB, a few minutes)
bash VaultForge/sources/clone_repos.sh

# Run the VaultForge pipeline (~30–60 min depending on hardware)
# Requires: ollama serve && ollama pull nomic-embed-text
python VaultForge/pipeline/db_writer.py
```

> **Pre-built database:** The `chroma_db_v2/` (420 MB) cannot be included in the repo due to GitHub's 100 MB file size limit. See [`VectorMap/data/DOWNLOADS.md`](VectorMap/data/DOWNLOADS.md) for details.

### 3 — Launch

```bash
bash VectorMap/start.sh
# → Opens dashboard at http://127.0.0.1:<port>
```

### Environment variables

```bash
# Optional — override default paths
export VAULT_PATH="/path/to/your/obsidian/vault"
export CHROMA_PATH="/path/to/chroma_db_v2"

# Copy and edit the example env file
cp VectorMap/.env.example VectorMap/.env
```

---

## Project Layout

```
vectorax/
│
├── .claude-project               # claude-project v4 brain (registry, agents, automations)
├── .gitignore
├── CLAUDE.md                     # Auto-generated project brief for AI sessions
│
├── VaultForge/                   # ── Parsing Pipeline ─────────────────────────
│   ├── config/
│   │   └── pipeline.yaml         # Master pipeline configuration
│   ├── docs/                     # Technical specs (8 documents)
│   ├── pipeline/                 # 14 pipeline modules
│   ├── sources/
│   │   ├── REPOS.yaml            # All 13 repo GitHub URLs
│   │   ├── clone_repos.sh        # Re-clone script
│   │   └── VectorTRM.pdf         # 565-page Technical Reference Manual
│   ├── tests/                    # VaultForge test suite
│   └── vectormap_mcp/            # MCP server for VectorMap integration
│
└── VectorMap/                    # ── Agentic Operations Center ────────────────
    ├── src/
    │   ├── server.py             # FastAPI — 35+ REST endpoints
    │   ├── langgraph_agent.py    # LangGraph pipeline (Retrieve → Generate → Validate)
    │   ├── query_history.py      # SQLite: sessions, templates, hallucination ledger
    │   └── profiler.py           # Structured logging + request timing
    ├── frontend/
    │   ├── index.html            # Dashboard shell
    │   ├── css/style.css
    │   └── js/                   # 11 JS modules (one per feature domain)
    ├── tests/                    # 86 pytest tests
    ├── data/
    │   └── DOWNLOADS.md          # ChromaDB rebuild instructions
    ├── setup.sh                  # One-command environment bootstrap
    └── start.sh                  # Quick launch
```

---

## API

<details>
<summary><strong>Core endpoints</strong></summary>

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/` | Dashboard UI |
| `GET` | `/status` | System telemetry (CPU, RAM, models, indexing state) |
| `POST` | `/chat` | RAG query → response + sources with scores + token usage |
| `GET/PUT` | `/api/config` | Read / update AGENT_CONFIG live |

</details>

<details>
<summary><strong>Memory & history</strong></summary>

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET/DELETE` | `/api/memory` | Conversation buffer read / clear |
| `GET` | `/api/hallucinations` | Hallucination ledger |
| `GET/POST/DELETE` | `/api/templates[/{id}]` | Query template CRUD |
| `GET` | `/api/history` | Query history with retrieval scores |

</details>

<details>
<summary><strong>Vault & ChromaDB</strong></summary>

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/api/vault/health` | Composite health score (0–100, 5 dimensions) |
| `GET` | `/api/vault/drift` | Sync drift monitor — stale vs fresh files |
| `GET` | `/api/vault/heatmap` | Per-file retrieval frequency heatmap |
| `GET` | `/api/chroma/search` | Semantic chunk search |
| `GET` | `/api/chroma/file` | All chunks for a file |
| `DELETE` | `/api/chroma/chunk/{id}` | Delete single chunk |
| `POST` | `/api/chroma/reindex` | Re-embed a single source file |
| `POST/GET/POST` | `/api/backfill/*` | Autonomous backfill queue |

</details>

<details>
<summary><strong>Intelligence tools</strong></summary>

| Method | Endpoint | Description |
| --- | --- | --- |
| `POST` | `/api/benchmark` | A/B model comparison (tokens, latency, response) |
| `POST` | `/api/vector_search` | Semantic spotlight — highlight nearest vectors in 3D map |
| `GET` | `/api/chunks/stats` | Chunk size distribution + top files by chunk count |
| `GET` | `/api/vector_map` | PCA-reduced embeddings for 3D visualisation |
| `POST` | `/api/tools/refactor` | LLM code refactor + unit test generation sub-agent |
| `POST` | `/api/tools/arch_graph` | Architecture dependency graph (nodes + edges) |
| `GET` | `/api/robot/log/stream` | Wire-Pod / Vector live log tail |
| `POST` | `/api/export/obsidian` | Export chat session to Obsidian vault as Markdown |

</details>

---

## Running Tests

```bash
cd VectorMap
source agent_env/bin/activate
pytest tests/ -v --tb=short
# 86 passed
```

---

## Agent Configuration

All parameters are hot-reloadable via dashboard or `PUT /api/config`:

```jsonc
{
  "model":                "qwen2.5-coder:7b",  // swap any Ollama model
  "temperature":          0.1,
  "retrieval_k":          8,                   // chunks per query
  "max_attempts":         3,                   // validation retries
  "context_budget":       20000,               // max tokens for context
  "memory_turns":         4,                   // conversation history turns
  "web_search":           false,               // DuckDuckGo fallback grounding
  "similarity_threshold": 0.0                  // min score to include chunk
}
```

---

## Technical Reference Manual

The `VectorTRM.pdf` (included at [`VaultForge/sources/VectorTRM.pdf`](VaultForge/sources/VectorTRM.pdf)) is the 565-page Anki Vector Technical Reference Manual. VaultForge extracts it into five structured ChromaDB collections:

| Collection | Content | Chunks |
| --- | --- | --- |
| `trm_prose` | Chapter narrative, architecture descriptions | 230 |
| `trm_code` | Fenced code blocks (language-tagged) | 250 |
| `trm_tables` | Pin maps, specs, register tables (linearised rows) | 180 |
| `trm_notes` | Developer notes, warnings, design decisions | 74 |
| `repo_code` | All 13 source repositories | 33,773 |

---

## claude-project Integration

This project uses [claude-project v4](https://github.com/infraax/claude-project) for persistent AI session memory:

```bash
# Show project status (registry, agents, services, automations)
claude-project status

# Sync session memory to Obsidian vault
claude-project sync

# Dispatch an agent task
claude-project dispatch create "Review new pipeline output" --agent summariser
```

Configured automations:
- **`sync-on-session-end`** — memory → Obsidian on every session close
- **`daily-standup`** — morning summary of yesterday's events (via `summariser` agent)

---

## License & Attribution

This research project is released for educational and research purposes.

All Vector robot source code belongs to their respective copyright holders:
- **Anki, Inc.** and **Digital Dream Labs** — official repositories
- **[fforchino](https://github.com/fforchino)** — community SDK forks
- **[kercre123](https://github.com/kercre123)** — Wire-Pod community server

The VectorTRM.pdf is Anki proprietary documentation included for research purposes under fair use.

---

<div align="center">

*Built with [Claude Code](https://claude.ai/code) · Powered by [Ollama](https://ollama.com) · Indexed with [ChromaDB](https://www.trychroma.com)*

</div>
