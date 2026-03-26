#!/usr/bin/env python3
"""
LLM Annotator — Phase 3
Uses Ollama (phi4 preferred) to annotate functions/classes/files with summaries.
Caches all annotations in SQLite to avoid re-annotating.
Output: annotations stored in pipeline_output/annotations_cache/cache.db
        annotated symbols saved as {repo}_symbols_annotated.json
"""
import json
import logging
import sys
import os
import sqlite3
import hashlib
import urllib.request
import urllib.error
import time
from pathlib import Path

SYMBOL_TABLES_DIR = "/Users/lab/research/VaultForge/pipeline_output/symbol_tables"
CACHE_DB = "/Users/lab/research/VaultForge/pipeline_output/annotations_cache/cache.db"
LOG_PATH = "/Users/lab/research/VaultForge/pipeline_output/logs/pipeline.log"
OLLAMA_URL = "http://127.0.0.1:11434"

# Models in preference order
PREFERRED_MODELS = ["phi4:latest", "qwen2.5-coder:7b", "llama3.2:3b", "smollm2:1.7b"]

REPO_ORDER = [
    "vector", "chipper", "vector-cloud", "vector-python-sdk",
    "vector-go-sdk", "wire-pod", "escape-pod-extension", "hugh",
    "vector-bluetooth", "dev-docs", "vector-web-setup", "vectorx", "vectorx-voiceserver"
]

MAX_SOURCE_CHARS = 1200  # Trim very long functions before sending to LLM
BATCH_PAUSE = 0.1        # Small pause between requests to avoid overwhelming Ollama


def setup_cache(db_path):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS annotations (
            content_hash TEXT PRIMARY KEY,
            annotation_level TEXT,
            llm_summary TEXT,
            called_when TEXT,
            purpose_tags TEXT,
            complexity TEXT,
            model_used TEXT,
            annotated_at TEXT
        )
    """)
    conn.commit()
    return conn


def hash_source(source):
    return hashlib.sha256(source.encode("utf-8", errors="replace")).hexdigest()


def get_cached(conn, content_hash):
    row = conn.execute(
        "SELECT llm_summary, called_when, purpose_tags, complexity, model_used FROM annotations WHERE content_hash=?",
        (content_hash,)
    ).fetchone()
    if row:
        return {
            "llm_summary": row[0],
            "called_when": row[1],
            "purpose_tags": json.loads(row[2]) if row[2] else [],
            "complexity": row[3],
            "model_used": row[4],
        }
    return None


def save_cache(conn, content_hash, level, annotation, model):
    import datetime
    conn.execute(
        """INSERT OR REPLACE INTO annotations
           (content_hash, annotation_level, llm_summary, called_when, purpose_tags, complexity, model_used, annotated_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (
            content_hash, level,
            annotation.get("summary", ""),
            annotation.get("called_when", ""),
            json.dumps(annotation.get("tags", [])),
            annotation.get("complexity", "unknown"),
            model,
            datetime.datetime.now().isoformat(),
        )
    )
    conn.commit()


def get_available_model():
    """Find the best available model from preferred list."""
    try:
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
        available = {m["name"] for m in data.get("models", [])}
        for model in PREFERRED_MODELS:
            if model in available:
                return model
        # Return first available
        if available:
            return next(iter(available))
    except Exception:
        pass
    return None


def call_ollama(prompt, model, timeout=30):
    """Call Ollama API and return response text."""
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 256},
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read())
            return data.get("response", "").strip()
    except Exception as e:
        return None


def parse_json_response(text):
    """Try to extract JSON from LLM response."""
    if not text:
        return {}
    # Find JSON object in response
    import re
    m = re.search(r"\{[^{}]+\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    # Try to parse as-is
    try:
        return json.loads(text)
    except Exception:
        pass
    return {}


FUNCTION_PROMPT = """Repository: {repo} | File: {file} | Language: {language}
Function/method: {name}
Signature: {signature}
Docstring: {docstring}
Source (truncated):
{source}

In exactly 2 sentences: (1) what this does, (2) when it would be called.
Return ONLY valid JSON:
{{"summary": "...", "called_when": "...", "tags": ["tag1","tag2","tag3"], "complexity": "simple|moderate|complex"}}"""


def annotate_symbol(sym, model, conn, log):
    """Annotate a single symbol with LLM. Returns annotation dict."""
    source = sym.get("source", "")[:MAX_SOURCE_CHARS]
    if not source.strip():
        return {}

    content_hash = hash_source(sym.get("source", ""))
    cached = get_cached(conn, content_hash)
    if cached:
        return cached

    prompt = FUNCTION_PROMPT.format(
        repo=sym.get("repo", ""),
        file=sym.get("file", ""),
        language=sym.get("language", ""),
        name=sym.get("name", ""),
        signature=sym.get("signature", f"{sym.get('type','?')} {sym.get('name','?')}"),
        docstring=sym.get("docstring", "")[:200],
        source=source,
    )

    response = call_ollama(prompt, model)
    if not response:
        return {}

    annotation = parse_json_response(response)
    if annotation.get("summary"):
        save_cache(conn, content_hash, "function", annotation, model)
        time.sleep(BATCH_PAUSE)
        return annotation

    return {}


def run():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(LOG_PATH, mode="a"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    log = logging.getLogger("annotator")
    log.info("=== LLM ANNOTATOR START ===")

    model = get_available_model()
    if not model:
        log.error("No Ollama model available — skipping annotation phase")
        print("WARNING: Ollama not available. Annotations will be empty strings.")
        # Create empty annotated files for all repos
        for repo in REPO_ORDER:
            sym_path = Path(SYMBOL_TABLES_DIR) / f"{repo}_symbols.json"
            if sym_path.exists():
                import shutil
                shutil.copy(sym_path, Path(SYMBOL_TABLES_DIR) / f"{repo}_symbols_annotated.json")
        return

    log.info(f"Using model: {model}")
    conn = setup_cache(CACHE_DB)

    total_annotated = 0
    total_cached = 0
    total_skipped = 0

    for repo_name in REPO_ORDER:
        sym_path = Path(SYMBOL_TABLES_DIR) / f"{repo_name}_symbols.json"
        if not sym_path.exists():
            continue

        symbols = json.load(open(sym_path))
        annotated_symbols = []
        repo_annotated = 0
        repo_cached = 0

        # Only annotate functions and methods (most important)
        # Skip classes and structs to keep runtime manageable
        for sym in symbols:
            try:
                sym_type = sym.get("type", "")
                source = sym.get("source", "")

                if sym_type not in ("function", "method", "class"):
                    annotated_symbols.append(sym)
                    continue

                # Skip very short symbols (not worth annotating)
                if len(source.strip()) < 30:
                    annotated_symbols.append(sym)
                    total_skipped += 1
                    continue

                # Check cache first
                content_hash = hash_source(source)
                cached = get_cached(conn, content_hash)
                if cached:
                    sym["llm_summary"] = cached.get("llm_summary", "")
                    sym["purpose_tags"] = cached.get("purpose_tags", [])
                    sym["complexity"] = cached.get("complexity", "")
                    sym["called_when"] = cached.get("called_when", "")
                    annotated_symbols.append(sym)
                    repo_cached += 1
                    total_cached += 1
                    continue

                # Annotate
                annotation = annotate_symbol(sym, model, conn, log)
                if annotation:
                    sym["llm_summary"] = annotation.get("summary", "")
                    sym["purpose_tags"] = annotation.get("tags", [])
                    sym["complexity"] = annotation.get("complexity", "unknown")
                    sym["called_when"] = annotation.get("called_when", "")
                    repo_annotated += 1
                    total_annotated += 1
                else:
                    sym["llm_summary"] = ""
                    sym["purpose_tags"] = []
                    sym["complexity"] = "unknown"

                annotated_symbols.append(sym)

            except Exception as e:
                log.warning(f"Annotation error {sym.get('name','?')}: {e}")
                sym.setdefault("llm_summary", "")
                sym.setdefault("purpose_tags", [])
                sym.setdefault("complexity", "unknown")
                annotated_symbols.append(sym)
                continue

        # Save annotated symbols
        out_path = Path(SYMBOL_TABLES_DIR) / f"{repo_name}_symbols_annotated.json"
        with open(out_path, "w") as f:
            json.dump(annotated_symbols, f, indent=2)

        log.info(f"{repo_name}: annotated={repo_annotated}, cached={repo_cached}, skipped={total_skipped}")

    conn.close()
    log.info(f"Total annotated: {total_annotated}, cached: {total_cached}, skipped: {total_skipped}")
    print(f"\n=== ANNOTATOR COMPLETE ===")
    print(f"New annotations: {total_annotated}")
    print(f"From cache: {total_cached}")


if __name__ == "__main__":
    run()
