"""
VECTORBRAIN PERFORMANCE PROFILER
=================================
Writes structured JSONL to logs/session_<timestamp>.jsonl
Each entry:  { "ts": float, "event": str, "rss_mb": float, ...data }

Usage:
    from profiler import log, Timer, SESSION_FILE

    with Timer("retrieve") as t:
        docs = vector_db.similarity_search(...)
    log("node_retrieve", {"elapsed_ms": t.elapsed_ms, "docs_found": len(docs)})
"""
import os
import time
import json
import psutil
from datetime import datetime

# ── paths ──────────────────────────────────────────────────────────────────────
_BASE    = os.path.dirname(os.path.abspath(__file__))
_LOG_DIR = os.path.normpath(os.path.join(_BASE, "..", "logs"))
os.makedirs(_LOG_DIR, exist_ok=True)

SESSION_FILE = os.path.join(
    _LOG_DIR,
    f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
)

# ── internal state ─────────────────────────────────────────────────────────────
_proc          = psutil.Process()
_session_start = time.time()
_query_counter = 0


def _rss_mb() -> float:
    return round(_proc.memory_info().rss / 1024 ** 2, 1)


def _sys_snapshot() -> dict:
    vm = psutil.virtual_memory()
    return {
        "sys_ram_used_gb":  round(vm.used   / 1024 ** 3, 2),
        "sys_ram_total_gb": round(vm.total  / 1024 ** 3, 2),
        "sys_cpu_pct":      psutil.cpu_percent(interval=None),
        "active_gb":   round(vm.active   / 1024 ** 3, 2) if hasattr(vm, "active")   else None,
        "wired_gb":    round(vm.wired    / 1024 ** 3, 2) if hasattr(vm, "wired")    else None,
        "inactive_gb": round(vm.inactive / 1024 ** 3, 2) if hasattr(vm, "inactive") else None,
        "free_gb":     round(vm.free     / 1024 ** 3, 2),
    }


# ── public API ─────────────────────────────────────────────────────────────────
def log(event_type: str, data: dict | None = None) -> dict:
    """Write one JSONL entry and return it."""
    entry = {
        "ts":       round(time.time() - _session_start, 3),
        "wall":     datetime.now().isoformat(timespec="milliseconds"),
        "event":    event_type,
        "rss_mb":   _rss_mb(),
        **(data or {}),
    }
    with open(SESSION_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


class Timer:
    """Context-manager that measures wall-clock time in ms."""
    def __init__(self, label: str = ""):
        self.label       = label
        self.elapsed_ms  = 0.0
        self.elapsed_s   = 0.0
        self._start      = 0.0

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *_):
        self.elapsed_ms = round((time.perf_counter() - self._start) * 1000, 1)
        self.elapsed_s  = round(self.elapsed_ms / 1000, 3)


class QueryContext:
    """
    Tracks one full query lifecycle.  Usage:

        with QueryContext(query) as qc:
            with qc.phase("retrieve"):  ...
            with qc.phase("generate"):  ...
            with qc.phase("validate"):  ...
        # on __exit__ writes the summary entry
    """
    def __init__(self, query: str):
        global _query_counter
        _query_counter += 1
        self.query_id   = _query_counter
        self.query      = query[:120]
        self.phases: dict[str, float] = {}
        self._rss_start = _rss_mb()
        self._wall_start = time.perf_counter()

    def phase(self, name: str) -> Timer:
        t = Timer(name)
        self._active_phase = name
        self._active_timer = t
        return t

    def record_phase(self, name: str, elapsed_ms: float):
        self.phases[name] = elapsed_ms

    def __enter__(self):
        log("query_start", {
            "query_id": self.query_id,
            "query":    self.query,
            "rss_start_mb": self._rss_start,
        })
        return self

    def __exit__(self, *_):
        total_ms   = round((time.perf_counter() - self._wall_start) * 1000, 1)
        rss_end_mb = _rss_mb()
        log("query_end", {
            "query_id":    self.query_id,
            "query":       self.query,
            "total_ms":    total_ms,
            "phases":      self.phases,
            "rss_delta_mb": round(rss_end_mb - self._rss_start, 1),
            **_sys_snapshot(),
        })
