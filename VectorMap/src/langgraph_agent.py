"""
VECTORBRAIN LANGGRAPH EXECUTION ENGINE
=========================================================
File: langgraph_agent.py
Purpose: The absolute core architectural logic of the Agentic AI.
Architecture:
  - Initializes ChromaDB using nomic-embed-text embeddings (768-dim, via Ollama).
  - Operates a StateGraph routing workflow (Retrieve -> Generate -> Validate -> End/Loop).
  - Actively prevents LLM hallucinations using a strict Obsidian WikiLink (`[[file]]`) validation loop.
  - Integrates SQLite caching to eliminate duplicate contextual extraction wait times.
  - Provides a multidimensional PCA (Principal Component Analysis) scaling node for UI scatterplots.

Author: Antigravity Agent
Version: 7.0
"""
from __future__ import annotations
import os
import glob
import time
import psutil
from typing import List, Dict, Any, TypedDict
# NOTE: numpy and sklearn are LAZY-LOADED in get_vector_map_data()
# to save ~128MB RAM at startup. They are only needed when the user
# clicks "Generate PCA Projection" on the Vector Map page.
from langchain_core.globals import set_llm_cache
from langchain_community.cache import SQLiteCache
from langchain_community.document_loaders import TextLoader
from langchain_huggingface import HuggingFaceEmbeddings  # kept for index_vault_background compat
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
import chromadb as _chromadb
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage
import tiktoken
from langgraph.graph import StateGraph, END
from profiler import log, Timer, QueryContext, SESSION_FILE

# ==========================================
# 1. Dynamic Path Resolution
# Ensures repository portability globally.
# ==========================================
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
_default_vault = os.path.join(BASE_DIR, "..", "data", "Vector_Obsidian_Vault_V2")
VAULT_DIR = os.environ.get("VAULT_PATH", _default_vault)
DB_DIR    = os.environ.get("CHROMA_PATH", os.path.join(BASE_DIR, "..", "data", "chroma_db_v2"))
CACHE_DIR = os.path.join(BASE_DIR, "..", "data", "langchain_cache.db")

class AgentState(TypedDict):
    """Data constraints passing through the nodes of the graph."""
    query: str
    context: List[Any]          # Retrieved chunk Documents
    retrieval_scores: List[float]  # Similarity scores (0-1) per chunk
    generation: str
    validation_error: str
    attempts: int
    system_logs: List[str]
    token_usage: dict
    injected_docs: List[str]    # Optional manual context injection (bypasses ChromaDB)

# ==========================================
# 2. Environment & Vector Engine Setup
# ==========================================
print("Initializing Environment and Embeddings...")
print(f"[profiler] Session log → {SESSION_FILE}")
log("startup_begin", {"note": "imports complete"})

_t0 = time.perf_counter()
set_llm_cache(SQLiteCache(database_path=CACHE_DIR))

# Phase 7 — VaultForge V2 integration:
# Embedding model changed from all-MiniLM-L6-v2 to nomic-embed-text (768-dim, code-aware).
# Must match the model used by VaultForge/pipeline/db_writer.py to populate chroma_db_v2.
with Timer("embeddings") as _te:
    embeddings = OllamaEmbeddings(model="nomic-embed-text", base_url="http://127.0.0.1:11434")
log("startup_embeddings_done", {"elapsed_ms": _te.elapsed_ms})

# Direct ChromaDB client for multi-collection V2 retrieval (repo_code, trm_notes, trm_code, trm_tables, trm_prose)
_V2_COLLECTIONS = ["repo_code", "trm_notes", "trm_code", "trm_tables", "trm_prose"]
_chroma_v2: _chromadb.PersistentClient | None = None

with Timer("chroma") as _tc:
    # LangChain Chroma wrapper retained for index_vault_background compatibility
    vector_db = Chroma(persist_directory=DB_DIR, embedding_function=embeddings)
    try:
        _chroma_v2 = _chromadb.PersistentClient(path=DB_DIR)
    except Exception as _e:
        print(f"[warn] direct chromadb client failed: {_e}")

def _v2_total_chunks():
    """Sum chunk counts across all 5 V2 collections."""
    if _chroma_v2 is None:
        return vector_db._collection.count() if hasattr(vector_db, '_collection') else 0
    total = 0
    for _cn in _V2_COLLECTIONS:
        try:
            total += _chroma_v2.get_collection(_cn).count()
        except Exception:
            pass
    return total

_chroma_count = _v2_total_chunks()
log("startup_chroma_done", {"elapsed_ms": _tc.elapsed_ms, "chunk_count": _chroma_count})

import getpass as _getpass
CURRENT_USER = _getpass.getuser()

# Configurable agent settings — updated via /api/config
AGENT_CONFIG = {
    "model":                "qwen2.5-coder:7b",
    "temperature":          0.1,
    "retrieval_k":          8,
    "max_attempts":         3,
    "context_budget":       20000,
    "system_prompt":        "",
    "memory_turns":         4,      # conversation turns to keep in context
    "web_search":           False,  # fall back to DuckDuckGo when score < threshold
    "similarity_threshold": 0.0,    # min score to include chunk (reserved)
}

# ==========================================
# Conversation Memory Buffer
# ==========================================
_CONV_BUFFER: list = []  # list of {"role": "user"|"assistant", "content": str}

# Live pipeline state — updated per-node so the UI can highlight the active node
CURRENT_AGENT_NODE = {"name": None, "query_id": None}

INDEX_STATE = {
    "is_indexing":        False,
    "stop_requested":     False,
    "current_file":       "",
    "processed_files":    0,
    "total_files":        0,
    "indexed_chunks":     0,
    "status_msg":         "Idle",
    "start_time":         0.0,
    "files_per_sec":      0.0,
    "est_remaining_sec":  0,
    "all_files":          [],
    # Backfill queue state (Page 4)
    "backfill_running":   False,
    "backfill_file":      "",
    "backfill_done":      0,
    "backfill_total":     0,
    "backfill_log":       [],   # [{file, status, summary_path}]
}

def index_vault_background(limit=None):
    """
    Background worker that transforms the Obsidian markdown files into dense 384D mathematical arrays.
    Employs hardware guardrails via `psutil` to dynamically pause thread execution if system load peaks.
    Uses chunk IDs to prevent vector duplication.
    """
    INDEX_STATE["is_indexing"] = True
    INDEX_STATE["stop_requested"] = False
    INDEX_STATE["status_msg"] = "Indexing Active"
    INDEX_STATE["indexed_chunks"] = 0
    INDEX_STATE["start_time"] = time.time()
    INDEX_STATE["files_per_sec"] = 0.0
    INDEX_STATE["est_remaining_sec"] = 0
    print("Background indexing started.")
    
    md_files = glob.glob(f"{VAULT_DIR}/**/*.md", recursive=True)
    # V2 vault uses repo_Symbol.md naming (single underscore) — index all .md files
    valid_files = [f for f in md_files if not os.path.basename(f).startswith("_")]
    
    if limit:
        valid_files = valid_files[:limit]
        
    INDEX_STATE["total_files"] = len(valid_files)
    INDEX_STATE["all_files"] = [os.path.basename(f) for f in valid_files]

    for count, f in enumerate(valid_files):
        # Stop flag check
        if INDEX_STATE["stop_requested"]:
            INDEX_STATE["status_msg"] = "Stopped by user"
            break

        # Hardware Guardrail — use available (free+inactive) not total percent.
        # Apple Silicon wired memory (Ollama GPU) inflates percent permanently.
        vm = psutil.virtual_memory()
        available_gb = vm.available / (1024 ** 3)
        while psutil.cpu_percent(interval=0.5) > 85.0 or available_gb < 1.5:
            if INDEX_STATE["stop_requested"]:
                break
            vm = psutil.virtual_memory()
            available_gb = vm.available / (1024 ** 3)
            INDEX_STATE["status_msg"] = f"PAUSED — avail={available_gb:.1f}GB (need >1.5GB)"
            time.sleep(2)
        if INDEX_STATE["stop_requested"]:
            INDEX_STATE["status_msg"] = "Stopped by user"
            break
            
        INDEX_STATE["status_msg"] = "Indexing Active"
        INDEX_STATE["current_file"] = os.path.basename(f)
        INDEX_STATE["processed_files"] = count + 1
        elapsed = time.time() - INDEX_STATE["start_time"]
        if elapsed > 0 and (count + 1) > 0:
            fps = (count + 1) / elapsed
            remaining = max(0, (len(valid_files) - count - 1) / fps) if fps > 0 else 0
            INDEX_STATE["files_per_sec"] = round(fps, 2)
            INDEX_STATE["est_remaining_sec"] = int(remaining)

        try:
            loader = TextLoader(f)
            doc_list = loader.load()
            for d in doc_list:
                d.metadata["source"] = os.path.basename(f).replace(".md", "")
            splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
            splits = splitter.split_documents(doc_list)
            
            # Deterministic Hashing to prevent infinite duplication
            ids = [f"{os.path.basename(f)}_{i}" for i in range(len(splits))]
            
            if splits:
                vector_db.add_documents(documents=splits, ids=ids)
                INDEX_STATE["indexed_chunks"] += len(splits)
        except Exception as e:
            print(f"Skipping {f} due to error: {e}")
            
    try:
        vector_db.persist()
        print("VectorDB cache synced to physical disk completely.")
    except Exception as e:
        print(f"Persist skipped (likely using new auto-persist version): {e}")
            
    INDEX_STATE["is_indexing"] = False
    INDEX_STATE["current_file"] = ""
    INDEX_STATE["status_msg"] = "Complete"
    print("Indexing Complete.")

# ==========================================
# 3. LangGraph AI Nodes
# ==========================================
with Timer("llm_init") as _tl:
    llm = ChatOllama(model="qwen2.5-coder:7b", temperature=0.1)
    enc = tiktoken.get_encoding("cl100k_base")
log("startup_llm_done", {"elapsed_ms": _tl.elapsed_ms})
log("startup_ready", {
    "elapsed_ms": round((time.perf_counter() - _t0) * 1000, 1),
    "chunk_count": _chroma_count,
})
print(f"[profiler] Startup complete in {round((time.perf_counter() - _t0), 2)}s")

# Per-request query context — set by server.py before invoking app
_active_qctx: QueryContext | None = None

def retrieve(state: AgentState):
    """Finds top-K most mathematically similar code snippets, with similarity scores.
    If injected_docs are present, bypasses ChromaDB and uses them directly.
    """
    CURRENT_AGENT_NODE["name"] = "retrieve"
    query = state["query"]
    logs = state.get("system_logs", [])
    k = AGENT_CONFIG.get("retrieval_k", 8)

    # Manual context injection bypass
    injected = state.get("injected_docs") or []
    if injected:
        from langchain_core.documents import Document
        docs = [Document(page_content=txt, metadata={"source": f"injected_{i}"})
                for i, txt in enumerate(injected)]
        scores = [1.0] * len(docs)
        logs.append(f"📌 **Retrieval Node**: Using {len(docs)} manually injected context documents.")
        log("node_retrieve", {"query": query[:80], "elapsed_ms": 0, "docs_found": len(docs), "injected": True})
        if _active_qctx: _active_qctx.record_phase("retrieve", 0)
        return {"context": docs, "retrieval_scores": scores, "system_logs": logs}

    logs.append(f"🔍 **Retrieval Node**: Querying ChromaDB V2 for semantic matches to '{query}'...")
    print(f"\n[NODE: Retrieve] Querying ChromaDB V2 for: '{query}'")

    with Timer("retrieve") as t:
        # Multi-collection search across all 5 VaultForge V2 collections.
        # Falls back to single-collection LangChain search if direct client unavailable.
        if _chroma_v2 is not None:
            from langchain_core.documents import Document as _Doc
            try:
                query_emb = embeddings.embed_query(query)
                k_per_col = max(3, k // len(_V2_COLLECTIONS) + 1)
                merged = []
                for col_name in _V2_COLLECTIONS:
                    try:
                        col = _chroma_v2.get_collection(col_name)
                        if col.count() == 0:
                            continue
                        r = col.query(
                            query_embeddings=[query_emb],
                            n_results=min(k_per_col, col.count()),
                            include=["documents", "metadatas", "distances"],
                        )
                        for doc, meta, dist in zip(
                            r["documents"][0], r["metadatas"][0], r["distances"][0]
                        ):
                            merged.append((dist, _Doc(page_content=doc, metadata=meta or {})))
                    except Exception:
                        continue
                # Sort by cosine distance (lower = more similar), take top-K
                merged.sort(key=lambda x: x[0])
                results_raw = merged[:k]
                docs   = [r[1] for r in results_raw]
                # Cosine distance → 0-1 relevance: score = max(0, 1 - dist)
                scores = [round(max(0.0, 1.0 - r[0]), 3) for r in results_raw]
            except Exception as _e:
                print(f"[warn] multi-collection search failed, falling back: {_e}")
                results = vector_db.similarity_search_with_score(query, k=k)
                docs   = [r[0] for r in results]
                scores = [round(max(0.0, 1.0 - r[1] / 2.0), 3) for r in results]
        else:
            results = vector_db.similarity_search_with_score(query, k=k)
            docs   = [r[0] for r in results]
            scores = [round(max(0.0, 1.0 - r[1] / 2.0), 3) for r in results]

    log("node_retrieve", {
        "query":       query[:80],
        "elapsed_ms":  t.elapsed_ms,
        "docs_found":  len(docs),
        "sources":     [d.metadata.get("source", "?") for d in docs],
        "top_score":   scores[0] if scores else 0,
        "min_score":   scores[-1] if scores else 0,
    })
    if _active_qctx:
        _active_qctx.record_phase("retrieve", t.elapsed_ms)

    logs.append(f"✅ **Retrieval Node**: Found {len(docs)} chunks (top score: {scores[0]:.2f}).")
    return {"context": docs, "retrieval_scores": scores, "system_logs": logs}

def generate(state: AgentState):
    """Consults the LLM Engine with heavily guarded system prompts."""
    CURRENT_AGENT_NODE["name"] = "generate"
    print("\n[NODE: Generate] Constructing prompt and consulting local LLM...")
    context = state["context"]
    query = state["query"]
    error = state.get("validation_error", "")
    attempts = state.get("attempts", 0) + 1
    logs = state.get("system_logs", [])
    
    if not context:
        logs.append(f"⚠️ **Generation Node**: Pre-flight check failed (0 Context Files). Bypassing LLM.")
        return {
            "generation": "Insufficient context found in the Vault to answer this query. Please ensure the vault is indexed correctly.",
            "attempts": attempts,
            "system_logs": logs
        }
    
    context_str = "\n".join([f"--- SOURCE FILE: {doc.metadata.get('file') or doc.metadata.get('source') or 'Unknown'} ---\n{doc.page_content}" for doc in context])
    
    context_tokens = len(enc.encode(context_str))
    if context_tokens > 20000:
        context_str = enc.decode(enc.encode(context_str)[:20000])
        context_tokens = 20000

    _custom_sys = AGENT_CONFIG.get("system_prompt", "").strip()
    _custom_block = f"\n\n### User Extension:\n{_custom_sys}" if _custom_sys else ""

    # Conversation memory injection
    _mem_turns = AGENT_CONFIG.get("memory_turns", 4)
    _mem_block = ""
    if _CONV_BUFFER and _mem_turns > 0:
        recent = _CONV_BUFFER[-(  _mem_turns * 2):]
        mem_lines = []
        for turn in recent:
            role_label = "USER" if turn["role"] == "user" else "ASSISTANT"
            mem_lines.append(f"[{role_label}]: {turn['content'][:500]}")
        _mem_block = "\n\n### Conversation Memory (last {} turns):\n{}".format(
            len(recent) // 2, "\n".join(mem_lines)
        )

    sys_prompt = f"""You are the VectorMap Architectural Agent operating purely locally.
You are assisting in analyzing the codebase of the Vector robot across 13 repositories.{_custom_block}{_mem_block}

### Context Budget Active
You are utilizing {context_tokens}/20000 context tokens.

### Traceable Verification Rule (CRITICAL)
Your answer must be grounded ONLY on the provided context.
You MUST format the absolute bottom of your response with a section titled precisely '## Stack Trace & Sources'.
In this section, you must list the exact FILES provided in the context that you used, wrapped in Obsidian WikiLinks: [[filename]].
Do NOT speculate or fabricate files.

CONTEXT SOURCES:
{context_str}
"""
    prompt = f"USER QUERY: {query}"
    if error:
        prompt += f"\n\nPRIOR VALIDATION ERROR (You MUST fix this constraint failure): {error}"

    messages = [SystemMessage(content=sys_prompt), HumanMessage(content=prompt)]
    
    sys_tok = len(enc.encode(sys_prompt))
    q_tok = len(enc.encode(prompt))
    total_tokens = sys_tok + q_tok
    
    state["token_usage"] = {
        "system": 2000,
        "context": context_tokens,
        "chat_history": q_tok,
        "available": 32768 - total_tokens
    }
    
    logs.append(f"🧠 **Generation Node** (Attempt {attempts}/3): Prompting `qwen2.5-coder` (Payload: {total_tokens} tokens)...")
    print(f"Tracking Token Usage: {total_tokens} / 32,768 (SAFE)")

    with Timer("generate") as t:
        res = llm.invoke(messages)

    resp_tokens = len(enc.encode(res.content))
    log("node_generate", {
        "attempt":       attempts,
        "elapsed_ms":    t.elapsed_ms,
        "input_tokens":  total_tokens,
        "output_tokens": resp_tokens,
        "context_tokens": context_tokens,
        "tokens_per_sec": round(resp_tokens / t.elapsed_s, 1) if t.elapsed_s > 0 else 0,
        "cache_hit":     t.elapsed_ms < 500,  # SQLite cache returns near-instantly
    })
    if _active_qctx:
        _active_qctx.record_phase("generate", t.elapsed_ms)

    return {"generation": res.content, "attempts": attempts, "system_logs": logs, "token_usage": state["token_usage"]}

def validate(state: AgentState):
    """The strict syntax and hallucination barrier. Logs all failures to hallucination_ledger."""
    CURRENT_AGENT_NODE["name"] = "validate"
    print("\n[NODE: Validator] Checking LLM generation against Traceable Verification Rules...")
    gen = state["generation"]
    logs = state.get("system_logs", [])
    query = state.get("query", "")

    def _log_hallucination(violation):
        """Persist failure to SQLite hallucination ledger."""
        try:
            import query_history as _qh
            session_id = _active_qctx.session_id if (_active_qctx and hasattr(_active_qctx, 'session_id')) else "unknown"
            _qh.save_hallucination(session_id, query, gen, violation)
        except Exception as _he:
            print(f"[validate] hallucination log error: {_he}")

    with Timer("validate") as t:

        if not state["context"]:
            logs.append("⏭️ **Validation Node**: Bypassed due to empty context.")
            log("node_validate", {"elapsed_ms": t.elapsed_ms, "result": "bypassed"})
            if _active_qctx: _active_qctx.record_phase("validate", t.elapsed_ms)
            return {"validation_error": "", "system_logs": logs}

        if "## Stack Trace & Sources" not in gen:
            err = "Response is missing the mandatory '## Stack Trace & Sources' section block. You must include it."
            logs.append(f"❌ **Validation Node**: Failed (`{err}`)")
            log("node_validate", {"elapsed_ms": t.elapsed_ms, "result": "fail_no_sources_section"})
            if _active_qctx: _active_qctx.record_phase("validate", t.elapsed_ms)
            _log_hallucination("missing_sources_section")
            return {"validation_error": err, "system_logs": logs}

        if "[[" not in gen or "]]" not in gen:
            err = "Sources were not formatted as Obsidian WikiLinks (e.g., [[filename]])."
            logs.append(f"❌ **Validation Node**: Failed (`{err}`)")
            log("node_validate", {"elapsed_ms": t.elapsed_ms, "result": "fail_no_wikilinks"})
            if _active_qctx: _active_qctx.record_phase("validate", t.elapsed_ms)
            _log_hallucination("missing_wikilinks")
            return {"validation_error": err, "system_logs": logs}

    context_sources = [doc.metadata.get("file") or doc.metadata.get("source") or "Unknown" for doc in state["context"]]
    found_valid = any(f"[[{src}]]" in gen for src in context_sources)

    if not found_valid:
        err = f"CRITICAL HALLUCINATION: You cited a file that was not in the provided context! You MUST strictly cite one of these exact files: {', '.join(['[[' + s + ']]' for s in context_sources])}"
        logs.append("🚨 **Validation Node**: Hallucination Detected! Rejected LLM Response.")
        log("node_validate", {"elapsed_ms": 0, "result": "fail_hallucination"})
        if _active_qctx: _active_qctx.record_phase("validate", 0)
        _log_hallucination("hallucinated_source")
        return {"validation_error": err, "system_logs": logs}

    log("node_validate", {"elapsed_ms": 0, "result": "pass"})
    if _active_qctx: _active_qctx.record_phase("validate", 0)
    logs.append("✅ **Validation Node**: Stack trace requirements strictly satisfied.")
    return {"validation_error": "", "system_logs": logs}

def should_loop(state: AgentState):
    if state.get("validation_error") and state.get("attempts", 1) < 3:
        return "generate"
    return "end"

# ==========================================
# 4. Telemetry Analyzers (Optimized)
# ==========================================

# Process scan cache — avoids iterating 300+ processes every 3s
_process_cache = {"data": None, "timestamp": 0}
_PROCESS_CACHE_TTL = 5  # seconds

# Vault file count cache — avoids recursive glob on every poll
_vault_cache = {"count": None, "timestamp": 0}
_VAULT_CACHE_TTL = 30  # seconds

def _get_cached_processes():
    """Returns cached process list, refreshing only if stale (>5s TTL)."""
    now = time.time()
    if _process_cache["data"] is not None and (now - _process_cache["timestamp"]) < _PROCESS_CACHE_TTL:
        return _process_cache["data"]

    processes = []
    for proc in psutil.process_iter(['name', 'memory_percent', 'cpu_percent', 'memory_info', 'username', 'pid']):
        try:
            processes.append(proc.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

    _process_cache["data"] = processes
    _process_cache["timestamp"] = now
    return processes

def _get_cached_vault_count():
    """Returns cached vault file count, refreshing only if stale (>30s TTL)."""
    now = time.time()
    if _vault_cache["count"] is not None and (now - _vault_cache["timestamp"]) < _VAULT_CACHE_TTL:
        return _vault_cache["count"]
    
    count = len(glob.glob(f"{VAULT_DIR}/**/*.md", recursive=True))
    _vault_cache["count"] = count
    _vault_cache["timestamp"] = now
    return count

def get_system_stats():
    """Aggregates hardware telemetry using cached process scans."""
    total_files = _get_cached_vault_count()
    indexed = _v2_total_chunks()
    
    net_io = psutil.net_io_counters()
    ram_info = psutil.virtual_memory()
    
    processes = _get_cached_processes()
            
    # Split processes by ownership — distinguishes our session from other users
    my_procs    = [p for p in processes if p.get('username') == CURRENT_USER]
    other_procs = [p for p in processes if p.get('username') != CURRENT_USER and p.get('username')]

    def _fmt_ram(procs, n=5):
        s = sorted(procs, key=lambda p: p.get('memory_percent') or 0, reverse=True)[:n]
        return [{"name": (p['name'] or 'unknown')[:14], "gb": round((p['memory_info'].rss) / (1024**3), 2),
                 "pct": round(p.get('memory_percent') or 0, 1), "pid": p.get('pid')} for p in s if p.get('memory_info')]

    def _fmt_cpu(procs, n=5):
        s = sorted(procs, key=lambda p: p.get('cpu_percent') or 0, reverse=True)[:n]
        return [{"name": (p['name'] or 'unknown')[:14], "pct": round(p.get('cpu_percent') or 0, 1)} for p in s]

    top_ram_fmt     = _fmt_ram(my_procs)
    top_cpu_fmt     = _fmt_cpu(my_procs)
    other_ram_fmt   = _fmt_ram(other_procs)
    other_cpu_fmt   = _fmt_cpu(other_procs)

    my_rss_gb    = round(sum(p['memory_info'].rss for p in my_procs    if p.get('memory_info')) / (1024**3), 2)
    other_rss_gb = round(sum(p['memory_info'].rss for p in other_procs if p.get('memory_info')) / (1024**3), 2)

    available_gb = round(ram_info.available / (1024**3), 2)
    # Guardrail health: GREEN >4GB avail, YELLOW 1.5-4GB, RED <1.5GB
    guardrail_state = "ok" if available_gb > 4.0 else ("warn" if available_gb > 1.5 else "paused")

    # macOS unified memory breakdown: active+wired = psutil "used"; inactive = reclaimable cache
    mem_breakdown = {
        "active_gb":      round(ram_info.active   / (1024**3), 2) if hasattr(ram_info, 'active')   else None,
        "inactive_gb":    round(ram_info.inactive  / (1024**3), 2) if hasattr(ram_info, 'inactive') else None,
        "wired_gb":       round(ram_info.wired     / (1024**3), 2) if hasattr(ram_info, 'wired')    else None,
        "free_gb":        round(ram_info.free      / (1024**3), 2),
        "available_gb":   available_gb,
        "my_procs_rss_gb":    my_rss_gb,
        "other_procs_rss_gb": other_rss_gb,
        "all_procs_rss_gb":   round(my_rss_gb + other_rss_gb, 2),
        "guardrail_state":    guardrail_state,
        "guardrail_threshold_gb": 1.5,
    }

    import os as _os
    try:
        _server_proc = psutil.Process(_os.getpid())
        server_rss_mb = round(_server_proc.memory_info().rss / 1024**2, 1)
    except:
        server_rss_mb = 0

    return {
        "total_files_vault": total_files,
        "indexed_chunks_total": indexed,
        "llm_model": "qwen2.5-coder:7b",
        "embedding_model": "nomic-embed-text",
        "agent_type": "Reflective LangGraph",
        "is_indexing": INDEX_STATE["is_indexing"],
        "current_file": INDEX_STATE["current_file"],
        "processed_files": INDEX_STATE["processed_files"],
        "total_files_to_index": INDEX_STATE["total_files"],
        "session_chunks": INDEX_STATE.get("indexed_chunks", 0),
        "status_msg": INDEX_STATE.get("status_msg", "Idle"),
        "files_per_sec":     INDEX_STATE.get("files_per_sec", 0.0),
        "est_remaining_sec": INDEX_STATE.get("est_remaining_sec", 0),
        "hardware": {
            "cpu_percent": psutil.cpu_percent(),
            "ram_percent": ram_info.percent,
            "ram_used_gb": round(ram_info.used / (1024**3), 2),
            "ram_total_gb": round(ram_info.total / (1024**3), 2),
            "net_sent_mb": round(net_io.bytes_sent / 1024 / 1024, 2),
            "net_recv_mb": round(net_io.bytes_recv / 1024 / 1024, 2),
            "top_ram":       top_ram_fmt,
            "top_cpu":       top_cpu_fmt,
            "other_ram":     other_ram_fmt,
            "other_cpu":     other_cpu_fmt,
            "mem_breakdown": mem_breakdown,
            "server_rss_mb": server_rss_mb,
        },
        "current_node":  CURRENT_AGENT_NODE["name"],
        "agent_config":  AGENT_CONFIG,
    }

def get_vector_map_data():
    """Lazy-loads sklearn + numpy only when PCA is actually requested. Saves ~128MB at idle."""
    try:
        import numpy as np
        from sklearn.decomposition import PCA

        # Use repo_code from the VaultForge V2 named collections (populated by db_writer).
        # Falls back to langchain collection if _chroma_v2 is unavailable.
        if _chroma_v2 is not None:
            collection = _chroma_v2.get_collection("repo_code")
        else:
            collection = vector_db._collection
        count = collection.count()
        if count == 0:
            return []

        log("pca_start", {"chunk_count": count})

        # SQLite caps variable count — fetch in batches of 500 to avoid
        # "too many SQL variables" error when collection has thousands of chunks.
        BATCH = 500
        all_embs = []
        all_meta = []
        with Timer("chroma_get_embeddings") as t_fetch:
            offset = 0
            while offset < count:
                batch = collection.get(
                    include=['embeddings', 'metadatas'],
                    limit=BATCH,
                    offset=offset
                )
                batch_embs = batch.get('embeddings')
                batch_meta = batch.get('metadatas') or []
                if batch_embs is None or (hasattr(batch_embs, '__len__') and len(batch_embs) == 0):
                    break
                if hasattr(batch_embs, 'tolist'):
                    all_embs.extend(batch_embs.tolist())
                else:
                    all_embs.extend(batch_embs)
                all_meta.extend(batch_meta)
                offset += BATCH
        log("pca_fetch_done", {"elapsed_ms": t_fetch.elapsed_ms, "chunks_fetched": len(all_embs)})

        if not all_embs:
            log("pca_error", {"reason": "embeddings empty after batched fetch"})
            return []

        embs = np.array(all_embs)
        meta = all_meta if all_meta else [{}] * len(embs)
        if len(embs) < 3: return []

        with Timer("sklearn_pca") as t_pca:
            pca = PCA(n_components=3)
            embs_3d = pca.fit_transform(embs)
        log("pca_done", {
            "elapsed_ms":      t_pca.elapsed_ms,
            "fetch_ms":        t_fetch.elapsed_ms,
            "total_ms":        round(t_fetch.elapsed_ms + t_pca.elapsed_ms, 1),
            "chunks_fetched":  len(embs),
            "points":          len(embs_3d),
            "explained_var":   [round(float(v), 4) for v in pca.explained_variance_ratio_],
        })

        points = []
        for i, (x, y, z) in enumerate(embs_3d):
            m = meta[i] if meta[i] else {}
            source = m.get('file') or m.get('source') or f'chunk_{i}'
            repo = m.get('repo') or (source.split('__')[0] if '__' in source else 'unknown')
            sym = m.get('symbol_name', '')
            points.append({"x": float(x), "y": float(y), "z": float(z), "name": source, "repo": repo, "symbol": sym})
        return points
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"PCA Error: {e}\n{tb}")
        log("pca_error", {"reason": str(e), "traceback": tb[-500:]})
        return []

# ==========================================
# 5. Graph Compile Strategy
# ==========================================
workflow = StateGraph(AgentState)
workflow.add_node("retrieve", retrieve)
workflow.add_node("generate", generate)
workflow.add_node("validate", validate)

workflow.set_entry_point("retrieve")
workflow.add_edge("retrieve", "generate")
workflow.add_edge("generate", "validate")
workflow.add_conditional_edges("validate", should_loop, {"generate": "generate", "end": END})

app = workflow.compile()

def start(query: str):
    print("=== INITIALIZING VECTORBRAIN AGENT ===")
    if not os.path.exists(DB_DIR) or len(os.listdir(DB_DIR)) == 0:
        print("DB Dir empty. Wait for indexing.")
    else:
        print(f"Loaded existing ChromaDB from {DB_DIR}")
        
    final_state = app.invoke({"query": query, "attempts": 0, "system_logs": []})
    print("\n================== FULL AGENT OUTPUT ==================\n")
    print(final_state["generation"])
    print("\n=======================================================")

if __name__ == "__main__":
    start("What are the primary C++ files and behaviors responsible for object and cube detection in Cozmo/Vector?")
