#!/usr/bin/env python3
"""
ChromaDB + SQLite DB Writer — Phase 6
Populates 5 ChromaDB collections and SQLite metadata DB from all_chunks.jsonl.
Also builds BM25 search index.

Embedding model: nomic-embed-text via Ollama (per config/pipeline.yaml)
  — VectorMap langgraph_agent.py will be updated in Phase 7 to use the same model.

Collections:
  repo_code   — source code symbols
  trm_prose   — TRM running prose
  trm_code    — TRM register/struct code snippets
  trm_tables  — TRM hardware tables
  trm_notes   — TRM developer notes (NOTE/WARNING/CAUTION)

Outputs:
  /Users/lab/research/VectorMap/data/chroma_db_v2/   (ChromaDB)
  /Users/lab/research/VectorMap/data/vault_meta_v2.db (SQLite metadata)
  /Users/lab/research/VaultForge/pipeline_output/bm25_index.pkl (BM25 index, per pipeline.yaml)
"""
import json
import logging
import sys
import sqlite3
import pickle
import re
import time
import urllib.request
from pathlib import Path
from collections import defaultdict

CHUNKS_FILE  = "/Users/lab/research/VaultForge/pipeline_output/chunks/all_chunks.jsonl"
CHROMA_PATH  = "/Users/lab/research/VectorMap/data/chroma_db_v2"
SQLITE_PATH  = "/Users/lab/research/VectorMap/data/vault_meta_v2.db"
BM25_PATH    = "/Users/lab/research/VaultForge/pipeline_output/bm25_index.pkl"
LOG_PATH     = "/Users/lab/research/VaultForge/pipeline_output/logs/pipeline.log"

# Per pipeline.yaml: embedding_model: "nomic-embed-text" via Ollama
EMBED_MODEL  = "nomic-embed-text"
OLLAMA_URL   = "http://127.0.0.1:11434"

# Chunk type → collection name
COLLECTION_MAP = {
    "repo_code":  "repo_code",
    "trm_prose":  "trm_prose",
    "trm_code":   "trm_code",
    "trm_table":  "trm_tables",
    "trm_note":   "trm_notes",
}

BATCH_SIZE    = 64    # ChromaDB add batch size (also used as embed batch size)
LOG_EVERY     = 500   # log progress every N chunks per collection
PROGRESS_FILE = "/Users/lab/research/VaultForge/pipeline_output/progress.json"


# ── Embedding ──────────────────────────────────────────────────────────────

def embed_batch(texts, log=None):
    """Batch embed via Ollama /api/embed (supports array input, ~10x faster than /api/embeddings).
    Returns list of vectors. Falls back to empty lists on error."""
    if not texts:
        return []
    # Truncate to 4096 chars each (nomic-embed-text context limit)
    safe_texts = [t[:4096] if t else "" for t in texts]
    payload = json.dumps({"model": EMBED_MODEL, "input": safe_texts}).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/embed",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read())
            embs = data.get("embeddings", [])
            # Pad with empty if count doesn't match
            while len(embs) < len(texts):
                embs.append([])
            return embs
    except Exception as e:
        if log:
            log.warning(f"embed batch failed: {e}")
        return [[] for _ in texts]


def embed_text(text, log=None):
    """Single-text wrapper (for test/verify only)."""
    result = embed_batch([text], log)
    return result[0] if result else []


# ── Progress reporting ────────────────────────────────────────────────────

def write_progress(total_chunks, total_indexed, total_failed, total_skipped,
                   elapsed, col_state, status="running"):
    import datetime
    eta = 0
    rate = total_indexed / elapsed if elapsed > 0 else 0
    remaining = total_chunks - total_indexed - total_skipped
    if rate > 0:
        eta = remaining / rate
    data = {
        "status":        status,
        "embed_model":   EMBED_MODEL,
        "total_chunks":  total_chunks,
        "total_indexed": total_indexed,
        "total_failed":  total_failed,
        "total_skipped": total_skipped,
        "elapsed_sec":   round(elapsed, 1),
        "rate_per_sec":  round(rate, 1),
        "eta_sec":       round(eta, 0),
        "collections":   col_state,
        "updated_at":    datetime.datetime.now().strftime("%H:%M:%S"),
    }
    try:
        with open(PROGRESS_FILE, "w") as f:
            json.dump(data, f)
    except Exception:
        pass


# ── ChromaDB ───────────────────────────────────────────────────────────────

def get_chroma_client():
    import chromadb
    return chromadb.PersistentClient(path=CHROMA_PATH)


def get_or_create_collections(client):
    cols = {}
    for col_name in set(COLLECTION_MAP.values()):
        cols[col_name] = client.get_or_create_collection(
            name=col_name,
            metadata={"hnsw:space": "cosine"}
        )
    return cols


def get_existing_ids(col):
    """Return the set of chunk_ids already in this collection (for resume)."""
    existing = set()
    try:
        # ChromaDB 1.x: .get() with no filter returns all, need limit
        offset = 0
        page = 1000
        while True:
            result = col.get(limit=page, offset=offset, include=[])
            ids = result.get("ids", [])
            existing.update(ids)
            if len(ids) < page:
                break
            offset += page
    except Exception:
        pass
    return existing


# ── ChromaDB metadata ──────────────────────────────────────────────────────

def build_chroma_metadata(chunk):
    """Build ChromaDB metadata — only str/int/float/bool values allowed."""
    meta = {}
    # String fields (per 06_DATABASE_SPEC.md)
    for field in ("repo", "language", "symbol_name", "symbol_type",
                  "class_context", "complexity", "llm_summary"):
        val = chunk.get(field) or ""
        meta[field] = str(val)[:500]

    # content_type and file use different internal names in chunk schema
    meta["content_type"] = str(chunk.get("content_type", ""))[:100]
    meta["file"]         = str(chunk.get("file", ""))[:500]

    # trm_reference is a dict in chunks — flatten the key fields
    trm_ref = chunk.get("trm_reference") or {}
    if isinstance(trm_ref, dict):
        meta["trm_snippet_id"] = str(trm_ref.get("trm_snippet_id", ""))
        meta["trm_page"]       = int(trm_ref.get("trm_page", 0) or 0)
    else:
        meta["trm_snippet_id"] = ""

    # TRM-specific fields
    meta["note_type"]   = str(chunk.get("note_type", ""))
    meta["note_id"]     = str(chunk.get("note_id", ""))
    meta["priority"]    = str(chunk.get("priority", ""))
    meta["chapter"]     = str(chunk.get("chapter", ""))[:200]
    meta["caption"]     = str(chunk.get("caption", ""))[:200]

    # Integer fields
    for int_field in ("line_start", "line_end", "token_count"):
        val = chunk.get(int_field)
        meta[int_field] = val if isinstance(val, int) else 0

    # Bool fields
    meta["has_trm_link"] = bool(chunk.get("has_trm_link", False))

    # List fields → pipe-separated strings
    hw = chunk.get("hardware_binds") or []
    meta["hardware_binds"] = "|".join(str(h) for h in hw[:10]) if hw else ""

    sim = chunk.get("similar_to") or []
    meta["similar_to"] = "|".join(str(s) for s in sim[:5]) if sim else ""

    return meta


# ── SQLite ─────────────────────────────────────────────────────────────────

def setup_sqlite(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            chunk_id        TEXT PRIMARY KEY,
            content_type    TEXT,
            repo            TEXT,
            file_path       TEXT,
            language        TEXT,
            symbol_name     TEXT,
            symbol_type     TEXT,
            line_start      INTEGER,
            token_count     INTEGER,
            llm_summary     TEXT,
            complexity      TEXT,
            trm_reference   TEXT,
            hardware_binds  TEXT,
            similar_to      TEXT,
            collection_name TEXT,
            indexed_at      TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_repo       ON chunks(repo)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ctype      ON chunks(content_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_symbol     ON chunks(symbol_name)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_collection ON chunks(collection_name)")
    conn.commit()
    return conn


def chunk_to_sqlite_row(chunk, collection_name):
    import datetime
    return (
        chunk.get("chunk_id", ""),
        chunk.get("content_type", ""),
        chunk.get("repo", ""),
        chunk.get("file", ""),
        chunk.get("language", ""),
        chunk.get("symbol_name", ""),
        chunk.get("symbol_type", ""),
        chunk.get("line_start"),
        chunk.get("token_count"),
        chunk.get("llm_summary", ""),
        chunk.get("complexity", ""),
        json.dumps(chunk.get("trm_reference") or {}),  # dict → JSON string
        json.dumps(chunk.get("hardware_binds") or []),
        json.dumps(chunk.get("similar_to") or []),
        collection_name,
        datetime.datetime.now().isoformat(),
    )


# ── Main ───────────────────────────────────────────────────────────────────

def run():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(LOG_PATH, mode="a"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    log = logging.getLogger("db_writer")
    log.info("=== DB WRITER START ===")
    log.info(f"Embedding model: {EMBED_MODEL} via Ollama at {OLLAMA_URL}")

    # Verify Ollama + model available
    try:
        test_vec = embed_text("test", log)
        if not test_vec:
            log.error(f"nomic-embed-text not responding — is Ollama running with this model?")
            log.error(f"Run: ollama pull {EMBED_MODEL}")
            sys.exit(1)
        log.info(f"Embedding dim: {len(test_vec)} (nomic-embed-text confirmed)")
    except Exception as e:
        log.error(f"Cannot reach Ollama: {e}")
        sys.exit(1)

    # Ensure output dirs
    Path(CHROMA_PATH).mkdir(parents=True, exist_ok=True)
    Path(SQLITE_PATH).parent.mkdir(parents=True, exist_ok=True)

    # Setup ChromaDB
    log.info("Connecting to ChromaDB...")
    chroma = get_chroma_client()
    cols = get_or_create_collections(chroma)

    # Setup SQLite
    log.info("Setting up SQLite metadata DB...")
    conn = setup_sqlite(SQLITE_PATH)

    # Load all chunks
    log.info("Loading chunks from JSONL...")
    all_chunks = []
    with open(CHUNKS_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                all_chunks.append(json.loads(line))
    log.info(f"Loaded {len(all_chunks)} chunks")

    # Partition by collection
    by_col = defaultdict(list)
    for chunk in all_chunks:
        ctype = chunk.get("content_type", "unknown")
        col_name = COLLECTION_MAP.get(ctype, "repo_code")
        by_col[col_name].append(chunk)

    for col_name, col_chunks in by_col.items():
        log.info(f"  '{col_name}': {len(col_chunks)} chunks")

    # ── Index each collection ──
    total_indexed = 0
    total_skipped = 0
    total_failed  = 0
    t_start = time.time()
    total_chunks  = sum(len(v) for v in by_col.values())

    # col_state tracks per-collection progress for the monitor
    col_state = {cn: {"total": len(cv), "indexed": 0} for cn, cv in by_col.items()}
    write_progress(total_chunks, 0, 0, 0, 0, col_state, "starting")

    for col_name, col_chunks in by_col.items():
        col = cols[col_name]
        log.info(f"Indexing {col_name}: {len(col_chunks)} chunks...")

        # Resume support — skip already-indexed IDs
        existing_ids = get_existing_ids(col)
        if existing_ids:
            log.info(f"  Resuming: {len(existing_ids)} already indexed, skipping")

        col_indexed = 0
        col_failed  = 0

        for batch_start in range(0, len(col_chunks), BATCH_SIZE):
            batch = col_chunks[batch_start:batch_start + BATCH_SIZE]

            # Filter out already-indexed IDs
            batch = [c for c in batch if c["chunk_id"] not in existing_ids]
            if not batch:
                total_skipped += len(col_chunks[batch_start:batch_start + BATCH_SIZE])
                continue

            ids       = [c["chunk_id"] for c in batch]
            texts     = [c.get("content", "") for c in batch]
            metadatas = [build_chroma_metadata(c) for c in batch]

            # Embed batch via Ollama
            embeddings = embed_batch(texts, log)

            # Filter empty embeddings
            valid = [(i, e) for i, e in enumerate(embeddings) if e]
            if not valid:
                col_failed += len(batch)
                total_failed += len(batch)
                log.warning(f"  All embeddings empty for batch at {batch_start}")
                continue

            valid_idx = [i for i, _ in valid]
            v_ids  = [ids[i]  for i in valid_idx]
            v_embs = [embeddings[i] for i in valid_idx]
            v_meta = [metadatas[i] for i in valid_idx]
            v_docs = [texts[i]  for i in valid_idx]

            try:
                col.add(
                    ids=v_ids,
                    embeddings=v_embs,
                    metadatas=v_meta,
                    documents=v_docs,
                )
                col_indexed += len(v_ids)
                total_indexed += len(v_ids)
                col_failed += len(batch) - len(v_ids)
                total_failed += len(batch) - len(v_ids)
                existing_ids.update(v_ids)
            except Exception as e:
                log.warning(f"  ChromaDB add error {col_name}@{batch_start}: {e}")
                col_failed += len(batch)
                total_failed += len(batch)
                continue

            # SQLite — write all (even if some embeddings failed)
            rows = [chunk_to_sqlite_row(c, col_name) for c in batch]
            conn.executemany("""
                INSERT OR REPLACE INTO chunks
                (chunk_id, content_type, repo, file_path, language, symbol_name,
                 symbol_type, line_start, token_count, llm_summary, complexity,
                 trm_reference, hardware_binds, similar_to, collection_name, indexed_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, rows)
            conn.commit()
            col_state[col_name]["indexed"] = col_indexed

            elapsed = time.time() - t_start
            rate    = total_indexed / elapsed if elapsed > 0 else 0
            eta     = (total_chunks - total_indexed - total_skipped) / rate if rate > 0 else 0
            write_progress(total_chunks, total_indexed, total_failed, total_skipped,
                           elapsed, col_state)

            done = batch_start + BATCH_SIZE
            if done % LOG_EVERY < BATCH_SIZE:
                log.info(
                    f"  {col_name}: {col_indexed}/{len(col_chunks)} indexed "
                    f"| total={total_indexed} | {rate:.0f}/s | ETA {eta/60:.1f}min"
                )

        log.info(f"  {col_name} done: indexed={col_indexed}, failed={col_failed}")

    conn.close()
    write_progress(total_chunks, total_indexed, total_failed, total_skipped,
                   time.time() - t_start, col_state, "bm25")

    # ── BM25 index ────────────────────────────────────────────────────────
    log.info("Building BM25 index...")
    Path(BM25_PATH).parent.mkdir(parents=True, exist_ok=True)
    try:
        from rank_bm25 import BM25Okapi
        corpus_ids, corpus_tokens = [], []
        for chunk in all_chunks:
            text = chunk.get("content", "")
            if text.strip():
                corpus_ids.append(chunk["chunk_id"])
                corpus_tokens.append(re.findall(r"\w+", text.lower()))
        bm25 = BM25Okapi(corpus_tokens)
        with open(BM25_PATH, "wb") as f:
            pickle.dump({"bm25": bm25, "ids": corpus_ids}, f)
        log.info(f"BM25 index: {len(corpus_ids)} documents → {BM25_PATH}")
    except ImportError:
        log.warning("rank_bm25 not installed — skipping BM25 (pip install rank_bm25)")
    except Exception as e:
        log.warning(f"BM25 build failed: {e}")

    elapsed = time.time() - t_start
    log.info(f"DB writer complete in {elapsed/60:.1f}min")

    print(f"\n=== DB WRITER COMPLETE ===")
    print(f"Embedding model : {EMBED_MODEL}")
    print(f"ChromaDB path   : {CHROMA_PATH}")
    print(f"Total indexed   : {total_indexed:,}")
    print(f"Skipped (exist) : {total_skipped:,}")
    print(f"Failed          : {total_failed:,}")
    print(f"SQLite DB       : {SQLITE_PATH}")
    print(f"BM25 index      : {BM25_PATH}")
    print(f"\nCollection sizes:")
    chroma2 = get_chroma_client()
    for col_name in sorted(set(COLLECTION_MAP.values())):
        try:
            count = chroma2.get_collection(col_name).count()
            print(f"  {col_name:15s}: {count:,}")
            col_state[col_name]["indexed"] = count
        except Exception:
            print(f"  {col_name:15s}: (error)")

    write_progress(total_chunks, total_indexed, total_failed, total_skipped,
                   time.time() - t_start, col_state, "complete")


if __name__ == "__main__":
    run()
