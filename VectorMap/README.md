# VectorMap — Agentic Operations Center

> A fully local, zero-hallucination AI system for deep codebase analysis. Powered by LangGraph, ChromaDB, and Ollama — nothing leaves your machine.

![Python](https://img.shields.io/badge/Python-3.9+-blue)
![FastAPI](https://img.shields.io/badge/Backend-FastAPI-teal)
![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-green)
![ChromaDB](https://img.shields.io/badge/VectorDB-ChromaDB_1.5-purple)
![Ollama](https://img.shields.io/badge/LLM-Ollama_Local-orange)
![Tests](https://img.shields.io/badge/Tests-86_passing-brightgreen)

---

## What Is VectorMap?

VectorMap ingests source code repositories via an Obsidian Vault, transforms them into dense 384-dimensional vector embeddings stored in ChromaDB, and answers architectural questions using a local LLM orchestrated through a LangGraph state machine.

Every answer is **strictly verified** against physical source files. If the LLM fabricates a filename, the Validation Node automatically rejects the response and forces a retry — achieving a **0% hallucination rate** on file citations. All computation is 100% local — no cloud APIs, no data exfiltration.

---

## Dashboard Pages

| Page | Name | Key Features |
| ---- | ---- | ------------ |
| **1** | Command Center | RAG chat with source scores, live log stream, conversation memory, Obsidian export |
| **2** | Agentic Forge | LangGraph node highlighter, hallucination ledger, query templates, A/B benchmark, context injection |
| **3** | Semantic Observatory | 3D PCA embedding map, spotlight search, chunk inspector, retrieval heatmap |
| **4** | Vault Management | ChromaDB CRUD explorer, sync drift monitor, autonomous backfill queue, vault health score |
| **5** | Intelligence Tools | Code refactor agent, architecture graph, web search grounding, robot log sniffer, token optimizer |

---

## Architecture

```
                    ┌─────────────────────────────────────────┐
                    │          FastAPI Backend (server.py)     │
                    │    35+ REST endpoints  ·  StaticFiles    │
                    └──────────────┬──────────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────────┐
                    │       LangGraph State Machine            │
                    │                                          │
                    │   retrieve() ──► generate() ──► validate()
                    │                      ▲               │  │
                    │                      └── retry ◄─────┘  │
                    │                                       end│
                    └──────────────┬────────────────────────--┘
                                   │
               ┌───────────────────┼───────────────────┐
               ▼                   ▼                   ▼
        ChromaDB 1.5.5       Ollama LLM          SQLite (query_history)
     (384-dim embeddings)  (qwen2.5-coder:7b)   (sessions · templates ·
                                                  hallucination ledger)
```

### Hallucination Prevention

The validate node checks every LLM response against three rules:

1. Must contain `## Stack Trace & Sources` section
2. Every citation must be a `[[WikiLink]]`
3. Every linked file must exist in the retrieved context (no fabrication)

Violations are logged to the hallucination ledger and the query is retried up to `MAX_ATTEMPTS` times.

---

## Quick Start

### Prerequisites

- **Python 3.9+**
- **[Ollama](https://ollama.com)** installed and running
- **macOS** (Linux supported with minor path adjustments)

### 1. Setup

```bash
git clone https://github.com/yourusername/VectorMap.git
cd VectorMap

# One-command environment bootstrap
bash setup.sh
```

This creates `agent_env/`, installs all dependencies, pulls the default LLM model, and creates the required data directories.

### 2. Add Your Data

```
data/
├── Repositories/           ← Clone source repos here
├── Vector_Obsidian_Vault_TEST/  ← Place your Obsidian .md files here
└── chroma_db_test/         ← Auto-created by the indexer
```

### 3. Launch

```bash
bash start.sh
```

The server starts, finds a free port, and opens the dashboard in your browser. On first run, click **UPDATE VAULT CACHE** to index your vault into ChromaDB.

---

## Project Structure

```
VectorMap/
├── README.md                    # This file
├── SYSTEM_ARCHITECTURE.md       # Deep technical reference for AI agents
├── requirements.txt             # Python dependencies
├── setup.sh                     # One-command environment bootstrapper
├── start.sh                     # Quick-launch script
├── .env.example                 # Environment variable reference
├── .gitignore
│
├── src/
│   ├── server.py                # FastAPI backend (35+ endpoints)
│   ├── langgraph_agent.py       # LangGraph pipeline (Retrieve → Generate → Validate)
│   ├── query_history.py         # SQLite — sessions, templates, hallucination ledger
│   └── profiler.py              # Request timing and structured logging
│
├── frontend/
│   ├── index.html               # HTML shell — 5 page containers + nav
│   ├── css/style.css            # Custom styles
│   └── js/
│       ├── constants.js         # Global state, color maps
│       ├── api.js               # Fetch wrappers, history, config
│       ├── chat.js              # Chat, memory, log stream, export
│       ├── telemetry.js         # Hardware UI, node highlighter, process table
│       ├── models.js            # Ollama model cards
│       ├── indexing.js          # Index / stop controls
│       ├── plotly-map.js        # 3D embedding map, spotlight search
│       ├── page2.js             # Templates, benchmark, hallucinations, injection
│       ├── page3.js             # Chunk stats, heatmap, repo filter
│       ├── page4.js             # Health score, CRUD, drift, backfill
│       └── page5.js             # Refactor, arch graph, log sniffer, token deep dive
│
├── tests/                       # 86 pytest tests
│   ├── conftest.py              # Fixtures (TestClient, temp DB, mock ChromaDB)
│   ├── test_api_chat.py
│   ├── test_api_chroma.py
│   ├── test_api_core.py
│   ├── test_api_history.py
│   ├── test_api_indexing.py
│   ├── test_api_tools.py
│   ├── test_api_vault.py
│   ├── test_langgraph.py
│   ├── test_pca.py
│   └── test_query_history.py
│
└── data/                        # Runtime data — gitignored
    ├── Repositories/            # Source code repos to index
    ├── Vector_Obsidian_Vault_TEST/  # Obsidian vault (markdown files)
    └── chroma_db_test/          # ChromaDB persistent storage
```

---

## API Reference

### Core

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/` | Dashboard UI |
| `GET`  | `/status` | System telemetry (CPU, RAM, GPU, ports, indexing) |
| `POST` | `/chat` | RAG query — returns response, sources with scores, token usage |
| `GET`  | `/api/config` | Current AGENT_CONFIG |
| `PUT`  | `/api/config` | Update agent parameters live |

### Memory & History

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/api/memory` | Conversation buffer |
| `DELETE` | `/api/memory` | Clear conversation buffer |
| `GET`  | `/api/hallucinations` | Hallucination ledger |
| `GET/POST/DELETE` | `/api/templates[/{id}]` | Query template CRUD |

### Vault & ChromaDB

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/api/vault/health` | Composite health score (0–100) |
| `GET`  | `/api/vault/drift` | Obsidian sync drift monitor |
| `GET`  | `/api/vault/heatmap` | Per-file retrieval frequency |
| `GET`  | `/api/chroma/search` | Semantic chunk search |
| `GET`  | `/api/chroma/file` | All chunks for a file |
| `DELETE` | `/api/chroma/chunk/{id}` | Delete single chunk |
| `POST` | `/api/chroma/reindex` | Re-embed a single file |
| `POST/GET` | `/api/backfill/*` | Autonomous backfill queue |

### Intelligence Tools

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/benchmark` | A/B model comparison |
| `POST` | `/api/vector_search` | Semantic spotlight search |
| `GET`  | `/api/chunks/stats` | Chunk size distribution |
| `POST` | `/api/tools/refactor` | LLM code refactor sub-agent |
| `POST` | `/api/tools/arch_graph` | Architecture dependency graph |
| `GET`  | `/api/robot/log/stream` | Wire-Pod/Vector log tail |
| `POST` | `/api/export/obsidian` | Export session to Obsidian vault |

---

## Running Tests

```bash
source agent_env/bin/activate
pytest tests/ -v --tb=short
# 86 passed
```

---

## Configuration

All agent parameters can be changed live via the dashboard or the API:

```json
{
  "model": "qwen2.5-coder:7b",
  "temperature": 0.1,
  "retrieval_k": 8,
  "max_attempts": 3,
  "context_budget": 20000,
  "memory_turns": 4,
  "web_search": false,
  "similarity_threshold": 0.0
}
```

---

## License

This project is for research and educational purposes. All original Vector/Cozmo source code belongs to their respective copyright holders (Anki, Inc. / Digital Dream Labs).
