#!/usr/bin/env python3
"""
TRM ↔ Repository Cross-Linker — Phase 2.4
Matches TRM code snippets and table entries against repo symbol tables.
Output: pipeline_output/trm_structured/trm_repo_links.json
"""
import json
import logging
import sys
import os
import re
from pathlib import Path

TRM_SNIPPETS_DIR = "/Users/lab/research/VaultForge/pipeline_output/trm_structured/code_snippets"
TRM_TABLES_DIR   = "/Users/lab/research/VaultForge/pipeline_output/trm_structured/tables"
SYMBOL_TABLES_DIR = "/Users/lab/research/VaultForge/pipeline_output/symbol_tables"
OUT_FILE = "/Users/lab/research/VaultForge/pipeline_output/trm_structured/trm_repo_links.json"
LOG_PATH = "/Users/lab/research/VaultForge/pipeline_output/logs/pipeline.log"

REPO_ORDER = [
    "vector", "chipper", "vector-cloud", "vector-python-sdk",
    "vector-go-sdk", "wire-pod", "escape-pod-extension", "hugh",
    "vector-bluetooth", "dev-docs", "vector-web-setup", "vectorx", "vectorx-voiceserver"
]


def normalize(name):
    """Normalize a name for comparison: lowercase, remove underscores/hyphens."""
    return re.sub(r"[_\-\s]+", "", name.lower())


def load_all_symbols():
    """Load all symbols from all repos into a lookup dict."""
    all_symbols = {}  # normalized_name → list of symbol records
    for repo in REPO_ORDER:
        sym_path = Path(SYMBOL_TABLES_DIR) / f"{repo}_symbols.json"
        if not sym_path.exists():
            continue
        try:
            symbols = json.load(open(sym_path))
            for sym in symbols:
                name = sym.get("name", "")
                if name:
                    norm = normalize(name)
                    all_symbols.setdefault(norm, []).append(sym)
                # Also index qualified names
                for kw in re.findall(r"[A-Z][A-Z_]{2,}", sym.get("source", "")[:300]):
                    all_symbols.setdefault(normalize(kw), []).append(sym)
        except Exception:
            pass
    return all_symbols


def search_symbols(name, all_symbols, repo_hint=None):
    """Search for a name in all symbols. Returns list of (symbol, confidence) tuples."""
    results = []
    norm = normalize(name)

    # Exact match
    if norm in all_symbols:
        for sym in all_symbols[norm]:
            conf = 0.95 if sym.get("repo") == repo_hint else 0.90
            results.append((sym, conf))

    # Substring match: normalized name contains the search term
    if len(norm) > 4:
        for key, syms in all_symbols.items():
            if key != norm and norm in key:
                for sym in syms:
                    results.append((sym, 0.65))
            elif key != norm and key in norm:
                for sym in syms:
                    results.append((sym, 0.60))

    # Deduplicate by symbol identity
    seen = set()
    unique = []
    for sym, conf in results:
        key = (sym.get("repo"), sym.get("file"), sym.get("name"))
        if key not in seen:
            seen.add(key)
            unique.append((sym, conf))

    # Sort by confidence
    unique.sort(key=lambda x: -x[1])
    return unique[:5]  # top 5 matches


def run():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(LOG_PATH, mode="a"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    log = logging.getLogger("trm_repo_linker")
    log.info("=== TRM REPO LINKER START ===")

    all_symbols = load_all_symbols()
    log.info(f"Loaded {len(all_symbols)} normalized symbol names from all repos")

    links = []

    # --- Link TRM code snippets to repo symbols ---
    snippet_files = list(Path(TRM_SNIPPETS_DIR).glob("*.json"))
    log.info(f"Processing {len(snippet_files)} TRM code snippets")

    for snippet_file in snippet_files:
        try:
            snippet = json.load(open(snippet_file))
            snippet_id = snippet.get("snippet_id", snippet_file.stem)
            fn_name = snippet.get("function_name")
            struct_names = snippet.get("struct_names", [])
            content = snippet.get("content", "")

            matches = []

            # Search by function name
            if fn_name:
                for sym, conf in search_symbols(fn_name, all_symbols):
                    matches.append({
                        "repo": sym.get("repo"),
                        "file": sym.get("file"),
                        "symbol": sym.get("name"),
                        "symbol_type": sym.get("type"),
                        "line_start": sym.get("line_start"),
                        "confidence": conf,
                        "match_type": "function_name",
                    })

            # Search by struct names
            for struct_name in struct_names[:3]:
                for sym, conf in search_symbols(struct_name, all_symbols):
                    matches.append({
                        "repo": sym.get("repo"),
                        "file": sym.get("file"),
                        "symbol": sym.get("name"),
                        "symbol_type": sym.get("type"),
                        "line_start": sym.get("line_start"),
                        "confidence": conf * 0.8,  # lower conf for struct match
                        "match_type": "struct_name",
                    })

            # Search for all-caps identifiers in content (register names)
            for const_name in re.findall(r"\b([A-Z][A-Z_]{3,})\b", content):
                for sym, conf in search_symbols(const_name, all_symbols):
                    matches.append({
                        "repo": sym.get("repo"),
                        "file": sym.get("file"),
                        "symbol": sym.get("name"),
                        "confidence": conf * 0.5,
                        "match_type": "constant_name",
                    })

            if matches:
                # Deduplicate and take top 5
                seen = set()
                deduped = []
                for m in sorted(matches, key=lambda x: -x["confidence"]):
                    key = (m["repo"], m["file"], m.get("symbol"))
                    if key not in seen:
                        seen.add(key)
                        deduped.append(m)
                        if len(deduped) >= 5:
                            break

                link = {
                    "trm_snippet_id": snippet_id,
                    "trm_function": fn_name,
                    "trm_page": snippet.get("page"),
                    "trm_chapter": snippet.get("chapter"),
                    "matches": deduped,
                }
                links.append(link)

        except Exception as e:
            log.warning(f"Snippet {snippet_file.name}: {e}")
            continue

    # --- Link TRM tables to repo symbols (via header/field names) ---
    table_files = list(Path(TRM_TABLES_DIR).glob("*.json"))
    log.info(f"Processing {len(table_files)} TRM tables")

    for table_file in table_files:
        try:
            table = json.load(open(table_file))
            table_id = table.get("table_id", table_file.stem)
            caption = table.get("caption", "")
            headers = table.get("headers", [])
            rows = table.get("rows", [])

            # Extract identifiers from table content
            identifiers = set()
            for h in headers:
                # Extract all-caps words (GPIO names, register names)
                for m in re.findall(r"\b([A-Z][A-Z_0-9]{2,})\b", str(h)):
                    identifiers.add(m)
            for row in rows[:20]:
                for val in (row.values() if isinstance(row, dict) else [str(row)]):
                    for m in re.findall(r"\b([A-Z][A-Z_0-9]{2,})\b", str(val)):
                        identifiers.add(m)

            if not identifiers:
                continue

            matches = []
            for ident in list(identifiers)[:10]:
                for sym, conf in search_symbols(ident, all_symbols):
                    matches.append({
                        "repo": sym.get("repo"),
                        "file": sym.get("file"),
                        "symbol": sym.get("name"),
                        "confidence": conf * 0.6,
                        "match_type": "table_identifier",
                        "identifier": ident,
                    })

            if matches:
                seen = set()
                deduped = []
                for m in sorted(matches, key=lambda x: -x["confidence"]):
                    key = (m["repo"], m["file"], m.get("symbol"))
                    if key not in seen:
                        seen.add(key)
                        deduped.append(m)
                        if len(deduped) >= 5:
                            break

                if deduped:
                    link = {
                        "trm_snippet_id": table_id,
                        "trm_function": caption,
                        "trm_page": table.get("page"),
                        "trm_chapter": table.get("chapter"),
                        "matches": deduped,
                        "link_type": "table",
                    }
                    links.append(link)

        except Exception as e:
            log.warning(f"Table {table_file.name}: {e}")
            continue

    with open(OUT_FILE, "w") as f:
        json.dump(links, f, indent=2)

    high_conf = [l for l in links if any(m["confidence"] >= 0.8 for m in l.get("matches", []))]
    log.info(f"TRM repo links: {len(links)} total, {len(high_conf)} high-confidence (≥0.8)")
    print(f"\n=== TRM REPO LINKER COMPLETE ===")
    print(f"Total links: {len(links)}")
    print(f"High-confidence (≥0.8): {len(high_conf)}")


if __name__ == "__main__":
    run()
