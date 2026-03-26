# VectorBrain — System Architecture Document

> This document is intended for AI agents, developers, and maintainers who need to understand, modify, or extend the VectorBrain system. It provides a complete technical mapping of every component, data flow, and design decision.

---

## 1. System Overview

VectorBrain is a **Retrieval-Augmented Generation (RAG)** system with a strict **anti-hallucination validation loop**. It operates entirely locally using:

- **Ollama** as the LLM inference engine (default: `qwen2.5-coder:7b`)
- **ChromaDB** as the vector similarity database
- **LangGraph** as the agentic state machine orchestrator
- **FastAPI** as the HTTP API layer
- **Custom HTML/JS** as the multi-page dashboard frontend

The system analyzes 13 source code repositories for the Anki Vector robot by:
1. Converting source files into Obsidian-formatted markdown nodes
2. Chunking and embedding those nodes into 384-dimensional vectors via `all-MiniLM-L6-v2`
3. Performing semantic similarity search against user queries
4. Generating LLM responses constrained to only cite retrieved source files
5. Validating every response through an automated hallucination detector

---

## 2. Directory Layout

```
VectorBrain/
├── src/
│   ├── server.py               # FastAPI application entry point
│   └── langgraph_agent.py      # Core AI logic (graph nodes, embeddings, telemetry)
├── frontend/
│   └── vectorbrain_ui.html     # Single-file multi-page dashboard
├── data/
│   ├── Repositories/           # 13 original git repositories
│   ├── Vector_Obsidian_Vault_TEST/  # ~3000+ markdown code nodes
│   ├── chroma_db_test/         # ChromaDB persistent storage (SQLite + parquet)
│   └── langchain_cache.db      # LLM response cache (SQLite)
├── agent_env/                  # Python virtual environment (created by setup.sh)
├── requirements.txt            # Frozen dependencies
├── setup.sh                    # Environment bootstrapper
├── README.md                   # User-facing documentation
└── SYSTEM_ARCHITECTURE.md      # This file
```

---

## 3. Data Flow Pipeline

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│  Obsidian Vault  │────▶│  Text Chunker    │────▶│  ChromaDB Embedder  │
│  (.md files)     │     │  (1000 chars,    │     │  (all-MiniLM-L6-v2) │
│                  │     │   200 overlap)   │     │  384-dim vectors     │
└─────────────────┘     └──────────────────┘     └─────────┬───────────┘
                                                           │
                                                           ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│  User Query      │────▶│  Retrieval Node  │────▶│  Top 8 Similar      │
│  (via /chat API) │     │  (similarity_    │     │  Code Chunks        │
│                  │     │   search, k=8)   │     │                     │
└─────────────────┘     └──────────────────┘     └─────────┬───────────┘
                                                           │
                                                           ▼
                        ┌──────────────────┐     ┌─────────────────────┐
                        │  Validate Node   │◀────│  Generate Node      │
                        │  (WikiLink       │     │  (Qwen 2.5 Coder   │
                        │   enforcement)   │     │   via Ollama)       │
                        └────────┬─────────┘     └─────────────────────┘
                                 │
                          ┌──────┴──────┐
                          │             │
                       PASS          FAIL (max 3 retries)
                          │             │
                          ▼             ▼
                     Return to      Re-prompt LLM
                     User           with error context
```

---

## 4. Component Details

### 4.1 `langgraph_agent.py`

This is the brain of the system. Key components:

| Component | Purpose |
|-----------|---------|
| `BASE_DIR`, `VAULT_DIR`, `DB_DIR`, `CACHE_DIR` | Relative path constants — all derived from `__file__` |
| `AgentState` (TypedDict) | Typed state object flowing through graph nodes |
| `index_vault_background(limit)` | Threaded indexer with hardware guardrails and dedup IDs |
| `retrieve(state)` | Queries ChromaDB for top-8 similar chunks |
| `generate(state)` | Constructs system prompt, enforces token budget, calls Ollama |
| `validate(state)` | Checks for `## Stack Trace & Sources`, WikiLinks, and source validity |
| `should_loop(state)` | Routes to retry (max 3) or exit |
| `get_system_stats()` | Aggregates CPU/RAM/network/process telemetry via psutil |
| `get_vector_map_data()` | Runs PCA (384D → 3D) for the Plotly scatterplot |

**Anti-Hallucination Rules:**
1. Response must contain `## Stack Trace & Sources` section
2. Sources must use `[[WikiLink]]` format
3. Every cited file must exist in the retrieved context documents
4. On failure: re-prompt the LLM with the specific error (up to 3 attempts)

### 4.2 `server.py`

The HTTP layer connecting the frontend to the agent:

| Endpoint | Method | Body | Returns |
|----------|--------|------|---------|
| `/` | GET | — | HTML dashboard |
| `/status` | GET | — | Full system telemetry JSON |
| `/chat` | POST | `{"message": "..."}` | Agent response + sources + logs + token usage |
| `/start_index` | POST | `{"limit": N or null}` | Indexing confirmation |
| `/api/vector_map` | GET | — | PCA-projected 3D points array |

**Port Management:** The server dynamically finds a free port on startup using `socket.bind(('', 0))`. This avoids conflicts when running multiple instances.

### 4.3 `vectorbrain_ui.html`

A single-file multi-page dashboard using:
- **Tailwind CSS** (CDN) for styling
- **Chart.js** for token optimizer pie chart and hardware timeline
- **Plotly.js** for 3D semantic scatterplot
- **Marked.js** for rendering markdown responses
- **Font Awesome** for icons

**Pages:**
1. **Command Center** — Chat interface, hardware telemetry, port monitor, token optimizer, indexing controls
2. **Agentic Forge** — (Planned) LangGraph node editor, backfill queue, refactor sub-agent
3. **Vector Map** — 3D PCA scatterplot of all ChromaDB embeddings
4. **Vault Ledger** — (Planned) ChromaDB CRUD, sync drift monitor, hallucination ledger

---

## 5. Key Design Decisions

### Why Local-Only?
Privacy and control. All LLM inference runs on-device via Ollama. No API keys, no cloud egress, no token billing.

### Why ChromaDB?
Lightweight embedded vector database with native Python support. Persists to disk automatically. Supports metadata filtering for source tracing.

### Why LangGraph over LangChain Agents?
LangGraph provides explicit state machine control. Each node (Retrieve, Generate, Validate) has deterministic routing. The validation loop is a conditional edge, not an implicit agent decision — this is critical for the anti-hallucination guarantee.

### Why Deterministic Chunk IDs?
Each document chunk gets an ID like `filename.md_0`, `filename.md_1`, etc. This prevents duplicate embeddings when re-indexing. ChromaDB's `add_documents` with explicit IDs performs an upsert.

### Why SQLite LLM Cache?
If the same query hits the same context, the cached response is returned instantly without invoking Ollama. This dramatically speeds up repeated queries during development.

---

## 6. Extending the System

### Adding a New LangGraph Node
1. Define a function with signature `def my_node(state: AgentState) -> dict`
2. Add it to the workflow: `workflow.add_node("my_node", my_node)`
3. Wire edges: `workflow.add_edge("validate", "my_node")`
4. Return updated state keys as a dict

### Adding a New API Endpoint
1. Define a FastAPI route in `server.py`
2. Import any needed functions from `langgraph_agent.py`
3. The frontend can call it via `fetch('/your_endpoint')`

### Adding a New Dashboard Page
1. Add HTML content inside a `<div id="page-N">` in `vectorbrain_ui.html`
2. Add a nav button with `onclick="switchPage(N)"`
3. Register the page number in the `switchPage()` JavaScript function

---

## 7. Dependencies

Core dependencies (see `requirements.txt` for full list):

| Package | Version | Purpose |
|---------|---------|---------|
| `langchain` | 0.3.x | LLM orchestration framework |
| `langchain-ollama` | latest | Ollama LLM integration |
| `langchain-chroma` | latest | ChromaDB vector store |
| `langchain-huggingface` | latest | HuggingFace embeddings |
| `langgraph` | latest | State machine graph builder |
| `chromadb` | latest | Vector similarity database |
| `fastapi` | latest | HTTP API framework |
| `uvicorn` | latest | ASGI server |
| `psutil` | latest | Hardware telemetry |
| `scikit-learn` | latest | PCA dimensionality reduction |
| `tiktoken` | latest | Token counting |
| `numpy` | latest | Numerical operations |

---

## 8. Troubleshooting

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError` | Run `source agent_env/bin/activate` before launching |
| Empty ChromaDB | Click **UPDATE VAULT CACHE** in the UI and select a batch size |
| Ollama connection refused | Ensure Ollama is running: `ollama serve` |
| Port already in use | The server auto-selects a free port — check terminal output |
| Slow first query | The embedding model downloads on first run (~80MB). Subsequent runs are instant |
| `lsof` not found | Port monitor requires macOS/Linux. Gracefully degrades on other systems |
