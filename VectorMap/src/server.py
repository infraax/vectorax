"""
VECTORBRAIN AGENTIC OPERATIONS CENTER
=========================================================
File: server.py
Purpose: Main initialization hub for the FastAPI interactive dashboard.
Architecture: 
  - Exposes REST routes for background ChromaDB indexing arrays using threading.
  - Serves `vectorbrain_ui.html` dynamically matching user's architecture.
  - Intercepts and calculates hardware telemetry natively off the M-Series SoC 
    using `psutil` and `lsof` for sub-process Port tracking (Ollama, FastAPI, Obsidian).
    
Author: Antigravity Agent
Version: 7.0 (Multi-Page Agentic Forge)
"""
import os
import sys
import json
import glob
import subprocess
import psutil
import threading
import urllib.request
from typing import Optional
from pydantic import BaseModel
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
import webbrowser
import time
import socket

# Dynamic relative pathing to ensure portability across open-source clones
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

# Import compiled LangGraph engine and execution states
from langgraph_agent import (app, DB_DIR, get_system_stats, index_vault_background,
                              INDEX_STATE, get_vector_map_data, _active_qctx, AGENT_CONFIG)
import langgraph_agent as _agent
from profiler import log, QueryContext, SESSION_FILE
import query_history as _qh
_qh.init_db()

fastapi_app = FastAPI(title="VectorMap Command Center")
ACTIVE_SERVER_PORT = 0
SESSION_ID = os.path.basename(SESSION_FILE).replace(".jsonl", "")

# ==========================================
# Telemetry Hardware Pingers (Optimized)
# ==========================================
def get_port_status(port, health_url=None):
    """
    Uses HTTP health checks instead of lsof. The old lsof approach failed for
    processes owned by other system users (e.g. Ollama running under 'gebruiker').
    Falls back to a raw TCP socket check if no health URL is provided.
    Obsidian Local REST API uses self-signed HTTPS on port 27124 — SSL is not verified.
    """
    import urllib.request
    import ssl
    import socket as sock

    _ssl_ctx = ssl.create_default_context()
    _ssl_ctx.check_hostname = False
    _ssl_ctx.verify_mode = ssl.CERT_NONE

    def _pid_for_port(p):
        """Return PID of the process LISTENING on port p, not clients connected to it."""
        try:
            out = subprocess.check_output(
                ['lsof', '-nP', f'-iTCP:{p}', '-sTCP:LISTEN'],
                stderr=subprocess.DEVNULL
            ).decode().strip().split('\n')
            # output lines: header + data; grab first data line PID column (index 1)
            for line in out[1:]:
                parts = line.split()
                if len(parts) >= 2:
                    return int(parts[1])
        except:
            pass
        return None

    if health_url:
        try:
            urllib.request.urlopen(health_url, timeout=2, context=_ssl_ctx)
            pid = _pid_for_port(port)
            if pid:
                try:
                    proc = psutil.Process(pid)
                    return {"status": "ONLINE", "pid": proc.pid, "ram_mb": round(proc.memory_info().rss / 1024**2, 1)}
                except:
                    pass
            return {"status": "ONLINE", "pid": "—", "ram_mb": "—"}
        except:
            pass

    # Fallback: raw TCP socket probe
    try:
        s = sock.socket(sock.AF_INET, sock.SOCK_STREAM)
        s.settimeout(1)
        result = s.connect_ex(('127.0.0.1', port))
        s.close()
        if result == 0:
            pid = _pid_for_port(port)
            if pid:
                try:
                    proc = psutil.Process(pid)
                    return {"status": "ONLINE", "pid": proc.pid, "ram_mb": round(proc.memory_info().rss / 1024**2, 1)}
                except:
                    pass
            return {"status": "ONLINE", "pid": "—", "ram_mb": "—"}
    except:
        pass
    
    return {"status": "OFFLINE", "pid": "--", "ram_mb": 0}

class IndexRequest(BaseModel):
    limit: Optional[int] = None

# ==========================================
# Backend API Endpoints (V7 Extensions)
# ==========================================
@fastapi_app.post("/start_index")
async def start_index_endpoint(req: IndexRequest):
    """Disabled — ChromaDB is pre-populated by the VaultForge db_writer pipeline.
    The 5 named collections (repo_code, trm_notes, trm_code, trm_tables, trm_prose)
    contain 34,507 chunks indexed by db_writer using nomic-embed-text (768D).
    To re-index, run: cd /Users/lab/research/VaultForge && python pipeline/db_writer.py
    """
    from langgraph_agent import _v2_total_chunks
    total = _v2_total_chunks()
    return {
        "status": "noop",
        "message": f"ChromaDB is pre-populated via db_writer ({total:,} chunks across 5 collections). No re-indexing needed.",
        "collections": ["repo_code", "trm_notes", "trm_code", "trm_tables", "trm_prose"],
        "total_chunks": total,
    }

@fastapi_app.get("/api/vector_map")
async def get_vector_map_endpoint():
    """Proxy endpoint that calls Scikit-Learn PCA projection logic from Chroma arrays."""
    try:
        from langgraph_agent import _v2_total_chunks
        chunk_count = _v2_total_chunks()
        points = get_vector_map_data()
        if not points and chunk_count > 0:
            return {"status": "error", "message": f"Embedding extraction returned 0 points despite {chunk_count} chunks in ChromaDB. Check server terminal for PCA Error traceback."}
        return {"status": "online", "points": points}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@fastapi_app.get("/status")
async def status_endpoint():
    """Heartbeat endpoint for the Page 1 V7 Operations Center array."""
    try:
        stats = get_system_stats()
        import os as _os
        try:
            _own = psutil.Process(_os.getpid())
            _fastapi_info = {"status": "ONLINE", "pid": _own.pid, "ram_mb": round(_own.memory_info().rss / 1024**2, 1)}
        except:
            _fastapi_info = {"status": "ONLINE", "pid": "—", "ram_mb": "—"}
        stats["ports"] = {
            "fastapi": _fastapi_info,
            "ollama": get_port_status(11434, health_url="http://127.0.0.1:11434/api/tags"),
            "obsidian": get_port_status(27124, health_url="https://127.0.0.1:27124")
        }
        return {"status": "online", "stats": stats}
    except Exception as e:
        return {"status": "error", "message": str(e)}

fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend static files (css/, js/) at /static/
_frontend_dir = os.path.join(BASE_DIR, "..", "frontend")
fastapi_app.mount("/static", StaticFiles(directory=_frontend_dir), name="static")

class ChatRequest(BaseModel):
    message: str
    injected_docs: Optional[list] = None  # optional manual context injection

@fastapi_app.get("/", response_class=HTMLResponse)
async def serve_ui():
    """Serves the multi-file dashboard shell (index.html)."""
    ui_path = os.path.join(BASE_DIR, "..", "frontend", "index.html")
    with open(ui_path, "r") as f:
        return f.read()

@fastapi_app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    """
    Core entrypoint for user interaction. Pings the Compiled LangGraph and passes contextual logs
    along with strictly enforced deduplicated WikiLink data sources and LLM Token usages.
    Supports optional manual context injection (bypasses ChromaDB semantic search).
    """
    print(f"Server received query: {req.message}")
    if not os.path.exists(DB_DIR) or len(os.listdir(DB_DIR)) == 0:
        return JSONResponse(status_code=503, content={"error": "ChromaDB is currently indexing. Please wait..."})

    qctx = QueryContext(req.message)
    _agent._active_qctx = qctx
    with qctx:
        final_state = app.invoke({
            "query": req.message,
            "attempts": 0,
            "system_logs": [],
            "retrieval_scores": [],
            "injected_docs": req.injected_docs or [],
        })
    _agent._active_qctx = None

    # Build source list with retrieval scores attached
    raw_scores = final_state.get("retrieval_scores", [])
    sources = []
    if "context" in final_state and final_state["context"]:
        for i, doc in enumerate(final_state["context"]):
            extracted_source = doc.metadata.get("file") or doc.metadata.get("source") or "Unknown_File"
            snippet = doc.page_content[:250].replace("\n", " ").strip() + "..."
            score = raw_scores[i] if i < len(raw_scores) else None
            sources.append({"filename": extracted_source, "snippet": snippet, "score": score})

    unique_sources = []
    seen = set()
    for s in sources:
        if s["filename"] not in seen:
            unique_sources.append(s)
            seen.add(s["filename"])

    _token_usage = final_state.get("token_usage", {})
    _phases = qctx.phases if hasattr(qctx, 'phases') else {}
    _total_ms = sum(_phases.values()) if _phases else 0
    _db_id = _qh.save_query(
        session_id=SESSION_ID,
        query_id=qctx.query_id if hasattr(qctx, 'query_id') else 0,
        query=req.message,
        response=final_state["generation"],
        sources=unique_sources,
        phases=_phases,
        token_usage=_token_usage,
        total_ms=_total_ms,
        rss_delta_mb=0,
    )
    # Patch retrieval scores into the row
    if _db_id and unique_sources:
        _score_map = [{"filename": s["filename"], "score": s.get("score")} for s in unique_sources]
        _qh.update_retrieval_scores(_db_id, _score_map)

    # Update conversation memory buffer
    _agent._CONV_BUFFER.append({"role": "user", "content": req.message})
    _agent._CONV_BUFFER.append({"role": "assistant", "content": final_state["generation"]})
    max_turns = AGENT_CONFIG.get("memory_turns", 4) * 2
    if len(_agent._CONV_BUFFER) > max_turns:
        _agent._CONV_BUFFER[:] = _agent._CONV_BUFFER[-max_turns:]

    return {
        "response": final_state["generation"],
        "sources": unique_sources,
        "system_logs": final_state.get("system_logs", []),
        "token_usage": _token_usage,
    }

# ==========================================
# Ollama Model Management
# ==========================================
def _ollama_ps() -> list:
    """Query Ollama /api/ps for loaded models. Returns [] on failure."""
    try:
        import ssl
        ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen("http://127.0.0.1:11434/api/ps", timeout=2) as r:
            return json.loads(r.read()).get("models", [])
    except:
        return []

def _ollama_tags() -> list:
    """Query Ollama /api/tags for all installed models."""
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2) as r:
            return json.loads(r.read()).get("models", [])
    except:
        return []

@fastapi_app.get("/api/ollama/models")
async def ollama_models_endpoint():
    """List loaded (wired) and all available Ollama models with RAM estimates."""
    loaded  = _ollama_ps()
    all_mdl = _ollama_tags()
    loaded_names = {m["name"] for m in loaded}
    return {
        "loaded":    [{"name": m["name"], "size_gb": round(m.get("size_vram", m.get("size", 0)) / 1024**3, 2),
                       "expires_at": m.get("expires_at", "")} for m in loaded],
        "available": [{"name": m["name"], "size_gb": round(m.get("size", 0) / 1024**3, 2),
                       "loaded": m["name"] in loaded_names} for m in all_mdl],
    }

class EvictRequest(BaseModel):
    model: str

@fastapi_app.post("/api/ollama/evict")
async def ollama_evict_endpoint(req: EvictRequest):
    """Evict a model from Ollama's GPU memory by setting keep_alive=0."""
    try:
        payload = json.dumps({"model": req.model, "keep_alive": 0}).encode()
        r = urllib.request.urlopen(
            urllib.request.Request("http://127.0.0.1:11434/api/generate",
                                   data=payload, headers={"Content-Type": "application/json"}),
            timeout=10)
        log("ollama_evict", {"model": req.model})
        return {"status": "evicted", "model": req.model}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ==========================================
# Indexing Controls
# ==========================================
@fastapi_app.get("/api/indexing/files")
async def indexing_files_endpoint():
    """Return the full file list for the current/last indexing job with completion status."""
    all_files = INDEX_STATE.get("all_files", [])
    processed = INDEX_STATE.get("processed_files", 0)
    return {
        "status": "ok",
        "total": len(all_files),
        "processed": processed,
        "files": [
            {"name": f, "done": i < processed}
            for i, f in enumerate(all_files)
        ]
    }

@fastapi_app.post("/api/indexing/stop")
async def stop_indexing_endpoint():
    """Signal the background indexing thread to stop after the current file."""
    if not INDEX_STATE["is_indexing"]:
        return {"status": "idle", "message": "No indexing in progress."}
    INDEX_STATE["stop_requested"] = True
    INDEX_STATE["status_msg"] = "Stop requested..."
    return {"status": "stopping", "message": "Stop signal sent. Current file will finish."}

# ==========================================
# Query History
# ==========================================
@fastapi_app.get("/api/query_history")
async def query_history_endpoint(n: int = 50, session: str = None):
    """Return recent queries from SQLite history database."""
    try:
        history = _qh.get_history(n=n, session_id=session)
        return {"status": "ok", "history": history}
    except Exception as e:
        return {"status": "error", "history": [], "message": str(e)}

@fastapi_app.get("/api/query_history/{db_id}")
async def query_detail_endpoint(db_id: int):
    """Return a full query record including response and sources."""
    d = _qh.get_query_detail(db_id)
    if d:
        return {"status": "ok", "query": d}
    return {"status": "error", "message": "Not found"}

# ==========================================
# Agent Configuration
# ==========================================
class ConfigUpdate(BaseModel):
    model:                Optional[str]   = None
    temperature:          Optional[float] = None
    retrieval_k:          Optional[int]   = None
    max_attempts:         Optional[int]   = None
    context_budget:       Optional[int]   = None
    system_prompt:        Optional[str]   = None
    memory_turns:         Optional[int]   = None
    web_search:           Optional[bool]  = None
    similarity_threshold: Optional[float] = None

@fastapi_app.get("/api/config")
async def get_config():
    return {"status": "ok", "config": AGENT_CONFIG}

@fastapi_app.post("/api/config")
async def update_config(req: ConfigUpdate):
    """Live-update agent settings without restarting the server."""
    changed = {}
    for field, val in req.model_dump(exclude_none=True).items():
        if field in AGENT_CONFIG:
            AGENT_CONFIG[field] = val
            changed[field] = val
    if "model" in changed or "temperature" in changed:
        from langchain_ollama import ChatOllama
        _agent.llm = ChatOllama(model=AGENT_CONFIG["model"], temperature=AGENT_CONFIG["temperature"])
        log("config_updated", changed)
    return {"status": "ok", "applied": changed, "config": AGENT_CONFIG}

# ==========================================
# Conversation Memory
# ==========================================
@fastapi_app.get("/api/memory")
async def get_memory():
    """Return the current conversation memory buffer."""
    return {"status": "ok", "buffer": _agent._CONV_BUFFER, "turns": len(_agent._CONV_BUFFER) // 2}

@fastapi_app.delete("/api/memory")
async def clear_memory():
    """Clear conversation memory buffer."""
    _agent._CONV_BUFFER.clear()
    return {"status": "ok", "message": "Memory cleared."}

# ==========================================
# Live Session Log Stream
# ==========================================
@fastapi_app.get("/api/log/stream")
async def log_stream_endpoint(since: float = 0.0):
    """Return new JSONL log entries since the given session-relative timestamp."""
    try:
        entries = []
        with open(SESSION_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                    if e.get("ts", 0) > since:
                        entries.append(e)
                except:
                    pass
        return {"status": "ok", "entries": entries}
    except Exception as ex:
        return {"status": "error", "entries": [], "message": str(ex)}

# ==========================================
# Hallucination Ledger
# ==========================================
@fastapi_app.get("/api/hallucinations")
async def hallucinations_endpoint(n: int = 100):
    """Return recent hallucination ledger entries."""
    try:
        rows = _qh.get_hallucinations(n=n)
        return {"status": "ok", "hallucinations": rows}
    except Exception as e:
        return {"status": "error", "hallucinations": [], "message": str(e)}

@fastapi_app.get("/api/hallucinations/{ledger_id}")
async def hallucination_detail_endpoint(ledger_id: int):
    """Return full detail for one hallucination entry."""
    d = _qh.get_hallucination_detail(ledger_id)
    if d:
        return {"status": "ok", "entry": d}
    return {"status": "error", "message": "Not found"}

# ==========================================
# Query Templates
# ==========================================
class TemplateRequest(BaseModel):
    name: str
    template: str

@fastapi_app.get("/api/templates")
async def list_templates():
    return {"status": "ok", "templates": _qh.get_templates()}

@fastapi_app.post("/api/templates")
async def create_template(req: TemplateRequest):
    tid = _qh.save_template(req.name, req.template)
    if tid:
        return {"status": "ok", "id": tid}
    return {"status": "error", "message": "Failed to save template"}

@fastapi_app.delete("/api/templates/{template_id}")
async def delete_template(template_id: int):
    ok = _qh.delete_template(template_id)
    if ok:
        return {"status": "ok"}
    return JSONResponse(status_code=404, content={"status": "error", "message": "Template not found"})

# ==========================================
# Benchmark / A-B Mode
# ==========================================
class BenchmarkRequest(BaseModel):
    message: str
    model_a: str
    model_b: str

@fastapi_app.post("/api/benchmark")
async def benchmark_endpoint(req: BenchmarkRequest):
    """Run the same query against two models and return side-by-side results."""
    from langchain_ollama import ChatOllama
    from langchain_core.messages import SystemMessage, HumanMessage
    import tiktoken as _tik

    enc = _tik.get_encoding("cl100k_base")
    results = {}
    for model_name in (req.model_a, req.model_b):
        try:
            _llm = ChatOllama(model=model_name, temperature=AGENT_CONFIG["temperature"])
            _prompt = [SystemMessage(content="You are a helpful code assistant."),
                       HumanMessage(content=req.message)]
            _t0 = time.time()
            _res = _llm.invoke(_prompt)
            _elapsed = round((time.time() - _t0) * 1000)
            _out_tok = len(enc.encode(_res.content))
            results[model_name] = {
                "response": _res.content,
                "ms": _elapsed,
                "output_tokens": _out_tok,
                "tokens_per_sec": round(_out_tok / (_elapsed / 1000), 1) if _elapsed > 0 else 0,
            }
        except Exception as e:
            results[model_name] = {"error": str(e)}
    return {"status": "ok", "results": results}

# ==========================================
# Vector Semantic Search
# ==========================================
class VectorSearchRequest(BaseModel):
    query: str
    k: int = 20

@fastapi_app.post("/api/vector_search")
async def vector_search_endpoint(req: VectorSearchRequest):
    """Encode query text with the embedding model and return the k nearest chunk names."""
    try:
        from langgraph_agent import vector_db
        results = vector_db.similarity_search_with_score(req.query, k=req.k)
        hits = []
        for doc, dist in results:
            score = round(max(0.0, 1.0 - dist / 2.0), 3)
            hits.append({
                "name": doc.metadata.get("source", "unknown"),
                "score": score,
                "snippet": doc.page_content[:120].replace("\n", " "),
            })
        return {"status": "ok", "hits": hits}
    except Exception as e:
        return {"status": "error", "hits": [], "message": str(e)}

# ==========================================
# Chunk Statistics
# ==========================================
@fastapi_app.get("/api/chunks/stats")
async def chunks_stats_endpoint():
    """Chunk size distribution and top files by chunk count. Samples up to 2000 chunks."""
    try:
        from langgraph_agent import vector_db
        import collections
        collection = vector_db._collection
        total = collection.count()
        sample_limit = min(total, 2000)
        data = collection.get(include=["documents", "metadatas"], limit=sample_limit)
        docs = data.get("documents") or []
        metas = data.get("metadatas") or []

        sizes = [len(d) for d in docs]
        avg_size = round(sum(sizes) / len(sizes)) if sizes else 0

        # Histogram: buckets of 200 chars
        buckets = {}
        for s in sizes:
            b = (s // 200) * 200
            buckets[b] = buckets.get(b, 0) + 1
        size_dist = sorted([{"bucket": k, "count": v} for k, v in buckets.items()], key=lambda x: x["bucket"])

        # Top files by chunk count
        file_counts = collections.Counter(m.get("file") or m.get("source") or "unknown" for m in metas)
        top_files = [{"source": k, "chunk_count": v} for k, v in file_counts.most_common(20)]

        return {
            "status": "ok",
            "total_chunks": total,
            "sampled": len(docs),
            "avg_size_chars": avg_size,
            "size_distribution": size_dist,
            "top_files": top_files,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ==========================================
# Vault Heatmap (retrieval frequency)
# ==========================================
@fastapi_app.get("/api/vault/heatmap")
async def vault_heatmap_endpoint():
    """Per-file retrieval frequency from query_history.db sources."""
    try:
        import collections
        import sqlite3 as _sl
        from query_history import HISTORY_DB
        counts = collections.Counter()
        last_access = {}
        with _sl.connect(HISTORY_DB) as conn:
            rows = conn.execute("SELECT sources, timestamp FROM queries WHERE sources IS NOT NULL").fetchall()
        for sources_json, ts in rows:
            try:
                srcs = json.loads(sources_json)
                for s in srcs:
                    fname = s.get("filename", "")
                    if fname:
                        counts[fname] += 1
                        if fname not in last_access or ts > last_access[fname]:
                            last_access[fname] = ts
            except:
                pass
        files = [{"path": k, "count": v, "last_accessed": last_access.get(k, "")}
                 for k, v in counts.most_common(200)]
        return {"status": "ok", "files": files}
    except Exception as e:
        return {"status": "error", "files": [], "message": str(e)}

# ==========================================
# ChromaDB CRUD Explorer
# ==========================================
@fastapi_app.get("/api/chroma/search")
async def chroma_search_endpoint(q: str, limit: int = 20):
    """Semantic search in ChromaDB, returns chunk IDs + source + snippet."""
    try:
        from langgraph_agent import vector_db
        results = vector_db.similarity_search_with_score(q, k=limit)
        chunks = []
        for doc, dist in results:
            score = round(max(0.0, 1.0 - dist / 2.0), 3)
            chunks.append({
                "id": doc.metadata.get("id", ""),
                "source": doc.metadata.get("source", "unknown"),
                "snippet": doc.page_content[:200].replace("\n", " "),
                "score": score,
            })
        return {"status": "ok", "chunks": chunks}
    except Exception as e:
        return {"status": "error", "chunks": [], "message": str(e)}

@fastapi_app.get("/api/chroma/file")
async def chroma_file_endpoint(source: str):
    """Return all chunks for a given source file."""
    try:
        from langgraph_agent import vector_db
        collection = vector_db._collection
        data = collection.get(where={"source": source}, include=["documents", "metadatas"])
        ids = data.get("ids", [])
        docs = data.get("documents", [])
        chunks = [{"id": ids[i], "snippet": (docs[i] or "")[:300].replace("\n", " ")} for i in range(len(ids))]
        return {"status": "ok", "source": source, "chunks": chunks}
    except Exception as e:
        return {"status": "error", "chunks": [], "message": str(e)}

@fastapi_app.delete("/api/chroma/chunk/{chunk_id}")
async def chroma_delete_chunk_endpoint(chunk_id: str):
    """Delete a single chunk from ChromaDB by ID."""
    try:
        from langgraph_agent import vector_db
        vector_db._collection.delete(ids=[chunk_id])
        log("chroma_delete", {"chunk_id": chunk_id})
        return {"status": "ok", "deleted": chunk_id}
    except Exception as e:
        return {"status": "error", "message": str(e)}

class ReindexRequest(BaseModel):
    source: str   # filename (basename without .md)

@fastapi_app.post("/api/chroma/reindex")
async def chroma_reindex_endpoint(req: ReindexRequest):
    """Re-embed and re-insert chunks for a single source file."""
    try:
        from langgraph_agent import vector_db, VAULT_DIR, INDEX_STATE
        from langchain_community.document_loaders import TextLoader
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        import glob as _glob

        matches = _glob.glob(f"{VAULT_DIR}/**/{req.source}.md", recursive=True)
        if not matches:
            return {"status": "error", "message": f"File not found: {req.source}.md"}

        filepath = matches[0]
        # Delete existing chunks for this source
        try:
            vector_db._collection.delete(where={"source": req.source})
        except:
            pass

        loader = TextLoader(filepath)
        doc_list = loader.load()
        for d in doc_list:
            d.metadata["source"] = req.source
        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        splits = splitter.split_documents(doc_list)
        ids = [f"{req.source}_{i}" for i in range(len(splits))]
        vector_db.add_documents(documents=splits, ids=ids)
        log("chroma_reindex", {"source": req.source, "chunks": len(splits)})
        return {"status": "ok", "source": req.source, "chunks_added": len(splits)}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ==========================================
# Vault Sync Drift Monitor
# ==========================================
@fastapi_app.get("/api/vault/drift")
async def vault_drift_endpoint():
    """Compare Obsidian .md file mtimes against ChromaDB indexed timestamps."""
    try:
        from langgraph_agent import vector_db, VAULT_DIR
        import glob as _glob

        # Get all indexed sources with their metadata
        collection = vector_db._collection
        total = collection.count()
        # Sample metadatas only (no embeddings needed)
        BATCH = 500
        source_times = {}
        offset = 0
        while offset < total:
            batch = collection.get(include=["metadatas"], limit=BATCH, offset=offset)
            for m in (batch.get("metadatas") or []):
                src = m.get("source", "")
                ts = m.get("indexed_at", "") or m.get("timestamp", "")
                if src and src not in source_times:
                    source_times[src] = ts
            offset += BATCH

        md_files = _glob.glob(f"{VAULT_DIR}/**/*.md", recursive=True)
        drifted = []
        fresh = 0
        never_indexed = []

        for f in md_files:
            basename = os.path.basename(f).replace(".md", "")
            mtime = os.path.getmtime(f)
            if basename not in source_times:
                never_indexed.append({"file": basename})
            else:
                chroma_ts = source_times[basename]
                # If chroma_ts is empty or mtime is very recent, flag as drifted
                try:
                    from datetime import datetime as _dt
                    if chroma_ts:
                        chroma_dt = _dt.fromisoformat(chroma_ts)
                        mtime_dt = _dt.fromtimestamp(mtime)
                        delta_days = (mtime_dt - chroma_dt).total_seconds() / 86400
                        if delta_days > 1:
                            drifted.append({
                                "file": basename,
                                "md_mtime": _dt.fromtimestamp(mtime).isoformat(),
                                "chroma_ts": chroma_ts,
                                "delta_days": round(delta_days, 1),
                            })
                        else:
                            fresh += 1
                    else:
                        fresh += 1
                except:
                    fresh += 1

        return {
            "status": "ok",
            "drifted": sorted(drifted, key=lambda x: -x["delta_days"]),
            "fresh": fresh,
            "never_indexed": never_indexed[:100],
            "total_vault_files": len(md_files),
            "total_indexed_sources": len(source_times),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ==========================================
# Vault Health Score
# ==========================================
@fastapi_app.get("/api/vault/health")
async def vault_health_endpoint():
    """Compute a composite 0-100 vault health score across 5 dimensions."""
    try:
        from langgraph_agent import vector_db, VAULT_DIR
        import glob as _glob
        import sqlite3 as _sl
        from query_history import HISTORY_DB
        from datetime import datetime as _dt, timedelta as _td

        md_files = _glob.glob(f"{VAULT_DIR}/**/*.md", recursive=True)
        total_vault = len(md_files)

        # 1. Index coverage (30%) — % of vault files with ≥1 chunk in ChromaDB
        collection = vector_db._collection
        indexed_count = collection.count()
        # Get unique sources
        BATCH = 500; offset = 0; indexed_sources = set()
        while offset < indexed_count:
            batch = collection.get(include=["metadatas"], limit=BATCH, offset=offset)
            for m in (batch.get("metadatas") or []):
                src = m.get("source", "")
                if src: indexed_sources.add(src)
            offset += BATCH
        coverage_pct = len(indexed_sources) / total_vault if total_vault else 0

        # 2. Freshness (25%) — placeholder (metadata timestamps not written yet → grant 50%)
        freshness_pct = 0.5

        # 3. Documentation (20%) — % of files with non-trivial content (>500 chars)
        doc_count = sum(1 for f in md_files if os.path.getsize(f) > 500)
        doc_pct = doc_count / total_vault if total_vault else 0

        # 4. Query activity (15%) — any query in last 7 days
        try:
            with _sl.connect(HISTORY_DB) as conn:
                cutoff = (_dt.now() - _td(days=7)).isoformat()
                recent = conn.execute("SELECT COUNT(*) FROM queries WHERE timestamp > ?", (cutoff,)).fetchone()[0]
            activity_pct = min(1.0, recent / 10)  # 10+ queries = full score
        except:
            activity_pct = 0

        # 5. Hallucination rate (10%) — 1 - (failures / total queries)
        try:
            with _sl.connect(HISTORY_DB) as conn:
                total_q = conn.execute("SELECT COUNT(*) FROM queries").fetchone()[0]
                total_h = conn.execute("SELECT COUNT(*) FROM hallucination_ledger").fetchone()[0]
            hall_pct = 1.0 - (total_h / total_q) if total_q > 0 else 1.0
        except:
            hall_pct = 1.0

        weights = {"coverage": 0.30, "freshness": 0.25, "documentation": 0.20, "activity": 0.15, "hallucination": 0.10}
        scores = {"coverage": coverage_pct, "freshness": freshness_pct, "documentation": doc_pct,
                  "activity": activity_pct, "hallucination": hall_pct}
        composite = round(sum(scores[k] * weights[k] for k in weights) * 100, 1)

        return {
            "status": "ok",
            "score": composite,
            "dimensions": {k: {"score": round(scores[k] * 100, 1), "weight": int(weights[k] * 100)} for k in scores},
            "details": {
                "vault_files": total_vault,
                "indexed_sources": len(indexed_sources),
                "documented_files": doc_count,
                "recent_queries": int(activity_pct * 10),
                "total_hallucinations": int(total_h) if total_q > 0 else 0,
            },
        }
    except Exception as e:
        return {"status": "error", "score": 0, "message": str(e)}

# ==========================================
# Autonomous Backfill Queue
# ==========================================
class BackfillRequest(BaseModel):
    files: list   # list of source basenames (without .md)

def _run_backfill(files: list):
    """Background thread: generate Markdown summaries for files using the LLM."""
    from langgraph_agent import llm, VAULT_DIR, INDEX_STATE
    from langchain_core.messages import SystemMessage, HumanMessage
    import glob as _glob

    INDEX_STATE["backfill_running"] = True
    INDEX_STATE["backfill_total"] = len(files)
    INDEX_STATE["backfill_done"] = 0
    INDEX_STATE["backfill_log"] = []
    INDEX_STATE["backfill_file"] = ""

    for fname in files:
        if not INDEX_STATE.get("backfill_running"):
            break
        INDEX_STATE["backfill_file"] = fname
        try:
            matches = _glob.glob(f"{VAULT_DIR}/**/{fname}.md", recursive=True)
            if not matches:
                INDEX_STATE["backfill_log"].append({"file": fname, "status": "not_found"})
                INDEX_STATE["backfill_done"] += 1
                continue
            content = open(matches[0]).read()[:3000]
            msgs = [
                SystemMessage(content="You are a technical documentation writer. Summarize the following file content in structured Markdown with sections: Overview, Key Functions/Classes, Dependencies, Purpose. Be concise and accurate."),
                HumanMessage(content=f"FILE: {fname}\n\n{content}"),
            ]
            result = llm.invoke(msgs)
            summary_path = os.path.join(VAULT_DIR, f"SUMMARY__{fname}.md")
            with open(summary_path, "w") as sf:
                sf.write(f"# {fname} — Auto-Generated Summary\n\n")
                sf.write(result.content)
            INDEX_STATE["backfill_log"].append({"file": fname, "status": "done", "summary_path": summary_path})
            log("backfill_file_done", {"file": fname})
        except Exception as e:
            INDEX_STATE["backfill_log"].append({"file": fname, "status": "error", "error": str(e)})
        INDEX_STATE["backfill_done"] += 1

    INDEX_STATE["backfill_running"] = False
    INDEX_STATE["backfill_file"] = ""
    log("backfill_complete", {"total": len(files), "done": INDEX_STATE["backfill_done"]})

@fastapi_app.post("/api/backfill/start")
async def backfill_start_endpoint(req: BackfillRequest):
    if INDEX_STATE.get("backfill_running"):
        return {"status": "error", "message": "Backfill already running."}
    threading.Thread(target=_run_backfill, args=(req.files,), daemon=True).start()
    return {"status": "started", "total": len(req.files)}

@fastapi_app.get("/api/backfill/status")
async def backfill_status_endpoint():
    return {
        "status": "ok",
        "running": INDEX_STATE.get("backfill_running", False),
        "current_file": INDEX_STATE.get("backfill_file", ""),
        "done": INDEX_STATE.get("backfill_done", 0),
        "total": INDEX_STATE.get("backfill_total", 0),
        "log": INDEX_STATE.get("backfill_log", [])[-20:],
    }

@fastapi_app.post("/api/backfill/stop")
async def backfill_stop_endpoint():
    INDEX_STATE["backfill_running"] = False
    return {"status": "ok", "message": "Backfill stop signal sent."}

# ==========================================
# Code Refactor Sub-Agent
# ==========================================
class RefactorRequest(BaseModel):
    filepath: str
    mode: str = "both"   # "refactor" | "tests" | "both"

@fastapi_app.post("/api/tools/refactor")
async def refactor_endpoint(req: RefactorRequest):
    """Read a file and ask the LLM to refactor it and/or write tests."""
    try:
        from langgraph_agent import llm
        from langchain_core.messages import SystemMessage, HumanMessage

        if not os.path.exists(req.filepath):
            return {"status": "error", "message": "File not found"}
        original = open(req.filepath).read()
        ext = os.path.splitext(req.filepath)[1]

        if req.mode in ("refactor", "both"):
            msgs = [
                SystemMessage(content="You are an expert software engineer. Refactor the following code to improve readability, efficiency, and maintainability. Return ONLY the refactored code, no explanation."),
                HumanMessage(content=f"```{ext}\n{original[:4000]}\n```"),
            ]
            refactored = llm.invoke(msgs).content
        else:
            refactored = original

        tests = ""
        if req.mode in ("tests", "both"):
            msgs = [
                SystemMessage(content="You are a senior engineer writing pytest unit tests. Write comprehensive tests for the following code. Return ONLY the test code."),
                HumanMessage(content=f"```{ext}\n{original[:4000]}\n```"),
            ]
            tests = llm.invoke(msgs).content

        log("refactor_done", {"filepath": req.filepath, "mode": req.mode})
        return {"status": "ok", "original": original[:4000], "refactored": refactored, "tests": tests}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ==========================================
# Architecture Graph
# ==========================================
class ArchGraphRequest(BaseModel):
    files: list   # list of file paths

@fastapi_app.post("/api/tools/arch_graph")
async def arch_graph_endpoint(req: ArchGraphRequest):
    """Extract import/call relationships from selected files using the LLM."""
    try:
        from langgraph_agent import llm
        from langchain_core.messages import SystemMessage, HumanMessage

        combined = ""
        for fp in req.files[:5]:  # cap at 5 files to stay in token budget
            if os.path.exists(fp):
                combined += f"\n\n--- FILE: {os.path.basename(fp)} ---\n" + open(fp).read()[:1500]

        msgs = [
            SystemMessage(content="""You are a code analysis tool. Analyze the provided files and return ONLY valid JSON in this exact format:
{"nodes": [{"id": "FileName", "label": "FileName", "type": "file|class|function"}],
 "edges": [{"from": "A", "to": "B", "label": "imports|calls|inherits"}]}
Include files, key classes, and key functions as nodes. Return raw JSON only."""),
            HumanMessage(content=combined),
        ]
        result = llm.invoke(msgs).content.strip()
        # Extract JSON block if wrapped in markdown
        if "```" in result:
            result = result.split("```")[1]
            if result.startswith("json"):
                result = result[4:]
        graph_data = json.loads(result)
        return {"status": "ok", "graph": graph_data}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ==========================================
# Obsidian Export
# ==========================================
class ObsidianExportRequest(BaseModel):
    session_id: str
    title: str

@fastapi_app.post("/api/export/obsidian")
async def export_obsidian_endpoint(req: ObsidianExportRequest):
    """Export a session's Q&A history as a Markdown note in the Obsidian vault."""
    try:
        from langgraph_agent import VAULT_DIR
        history = _qh.get_history(n=200, session_id=req.session_id)
        if not history:
            return {"status": "error", "message": "No history found for session."}

        lines = [f"# {req.title}\n", f"*Session: {req.session_id}*\n", "---\n"]
        for entry in reversed(history):
            detail = _qh.get_query_detail(entry["id"])
            if not detail:
                continue
            lines.append(f"\n## Q: {detail['query']}\n")
            lines.append(f"*{detail['timestamp']} — {round(detail.get('total_ms',0)/1000,1)}s*\n\n")
            lines.append(detail.get("response", "") + "\n")
            sources = detail.get("sources") or []
            if sources:
                lines.append("\n**Sources:** " + ", ".join(f"[[{s['filename']}]]" for s in sources) + "\n")
            lines.append("\n---\n")

        safe_title = req.title.replace(" ", "_").replace("/", "-")
        note_path = os.path.join(VAULT_DIR, f"EXPORT__{safe_title}.md")
        with open(note_path, "w") as nf:
            nf.writelines(lines)
        log("obsidian_export", {"session": req.session_id, "path": note_path})
        return {"status": "ok", "path": note_path, "note_count": len(history)}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ==========================================
# Robot Log Sniffer
# ==========================================
@fastapi_app.get("/api/robot/log/stream")
async def robot_log_stream_endpoint(path: str, since: float = 0.0):
    """Return tail lines from a Wire-Pod or Vector log file."""
    try:
        if not os.path.exists(path):
            return {"status": "error", "message": "Log file not found", "lines": []}
        stat = os.stat(path)
        mtime = stat.st_mtime
        with open(path, "r", errors="replace") as f:
            lines = f.readlines()
        # Return last 100 lines, or lines newer than `since` mtime
        recent = lines[-100:]
        return {
            "status": "ok",
            "lines": [l.rstrip() for l in recent],
            "mtime": mtime,
            "total_lines": len(lines),
        }
    except Exception as e:
        return {"status": "error", "lines": [], "message": str(e)}

@fastapi_app.post("/api/robot/log/analyse")
async def robot_log_analyse_endpoint(body: dict):
    """Send last N log lines to LLM for anomaly detection."""
    try:
        from langgraph_agent import llm
        from langchain_core.messages import SystemMessage, HumanMessage
        lines = body.get("lines", [])
        log_text = "\n".join(lines[-50:])
        msgs = [
            SystemMessage(content="You are a robotics log analysis expert. Analyze the following Vector robot/Wire-Pod log lines. Identify anomalies, errors, or unusual patterns. Be concise."),
            HumanMessage(content=log_text),
        ]
        result = llm.invoke(msgs).content
        return {"status": "ok", "analysis": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ==========================================
# Orchestrator Execution Start
# ==========================================
if __name__ == "__main__":
    def find_free_port():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            return s.getsockname()[1]
            
    ACTIVE_SERVER_PORT = find_free_port()
    
    if not os.path.exists(DB_DIR) or len(os.listdir(DB_DIR)) == 0:
        print("WARNING: VectorDB not found. Please click UPDATE VAULT CACHE in your browser.")
        
    def open_browser():
        time.sleep(1.5)
        webbrowser.open(f"http://127.0.0.1:{ACTIVE_SERVER_PORT}")
        
    print(f"Launching VectorMap Backend Node on dynamically assigned port: {ACTIVE_SERVER_PORT}")
    print(f"[profiler] Session log → {SESSION_FILE}")
    log("server_start", {"port": ACTIVE_SERVER_PORT})
    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run(fastapi_app, host="127.0.0.1", port=ACTIVE_SERVER_PORT, log_level="warning")
