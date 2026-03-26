#!/usr/bin/env python3
"""
Token-Aware Chunker — Phase 4
Builds all chunks from repo symbols + TRM content with 25+ metadata fields.
Output: pipeline_output/chunks/all_chunks.jsonl
"""
import json
import logging
import sys
import hashlib
import os
from pathlib import Path

SYMBOL_TABLES_DIR = "/Users/lab/research/VaultForge/pipeline_output/symbol_tables"
TRM_STRUCTURED    = "/Users/lab/research/VaultForge/pipeline_output/trm_structured"
TRM_FIGURES       = "/Users/lab/research/VaultForge/pipeline_output/trm_structured/figures.json"
CLONE_PAIRS       = "/Users/lab/research/VaultForge/pipeline_output/clone_pairs/similarity_pairs.json"
TRM_REPO_LINKS    = f"{TRM_STRUCTURED}/trm_repo_links.json"
OUT_FILE          = "/Users/lab/research/VaultForge/pipeline_output/chunks/all_chunks.jsonl"
LOG_PATH          = "/Users/lab/research/VaultForge/pipeline_output/logs/pipeline.log"

REPO_ORDER = [
    "vector", "chipper", "vector-cloud", "vector-python-sdk",
    "vector-go-sdk", "wire-pod", "escape-pod-extension", "hugh",
    "vector-bluetooth", "dev-docs", "vector-web-setup", "vectorx", "vectorx-voiceserver"
]

MAX_TOKENS = {
    "code":      512,
    "trm_prose": 768,
    "trm_table": 256,
    "trm_note":  256,
    "trm_code":  512,
    "trm_figure": 384,
}
OVERLAP_TOKENS = 50
MIN_TOKENS = 10

import tiktoken
_enc = None

def get_enc():
    global _enc
    if _enc is None:
        _enc = tiktoken.get_encoding("cl100k_base")
    return _enc


def count_tokens(text):
    try:
        return len(get_enc().encode(text))
    except Exception:
        return max(1, len(text.split()))


def chunk_id(content):
    return hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()[:16]


def split_large_source(source, max_tokens, overlap_tokens):
    """Split large source code into overlapping chunks at line boundaries."""
    lines = source.split("\n")
    chunks = []
    current_lines = []
    current_tokens = 0
    signature = lines[0] if lines else ""  # Keep first line (signature) in each chunk

    for line in lines:
        line_tokens = count_tokens(line)
        if current_tokens + line_tokens > max_tokens and current_lines:
            chunk_text = "\n".join(current_lines)
            chunks.append(chunk_text)
            # Keep overlap: last few lines
            overlap_lines = []
            overlap_count = 0
            for prev_line in reversed(current_lines):
                pt = count_tokens(prev_line)
                if overlap_count + pt > overlap_tokens:
                    break
                overlap_lines.insert(0, prev_line)
                overlap_count += pt
            current_lines = [signature] + overlap_lines  # prepend signature
            current_tokens = count_tokens("\n".join(current_lines))
        current_lines.append(line)
        current_tokens += line_tokens

    if current_lines:
        chunks.append("\n".join(current_lines))
    return chunks if chunks else [source]


def load_clone_map():
    """Build a map from (repo, name) → list of similar symbols in other repos."""
    clone_map = {}  # (repo, name) -> [(other_repo, other_name, similarity)]
    try:
        pairs = json.load(open(CLONE_PAIRS))
        for p in pairs:
            key_a = (p.get("repo_a"), p.get("symbol_a"))
            key_b = (p.get("repo_b"), p.get("symbol_b"))
            sim = p.get("similarity_token", 0)
            rel = p.get("relationship", "")
            clone_map.setdefault(key_a, []).append({
                "repo": p.get("repo_b"), "symbol": p.get("symbol_b"),
                "file": p.get("file_b"), "similarity": sim, "relationship": rel,
            })
            clone_map.setdefault(key_b, []).append({
                "repo": p.get("repo_a"), "symbol": p.get("symbol_a"),
                "file": p.get("file_a"), "similarity": sim, "relationship": rel,
            })
    except Exception:
        pass
    return clone_map


def load_trm_links():
    """Build a map from (repo, symbol_name) → TRM link info."""
    trm_map = {}  # symbol_name_lower -> list of trm link records
    try:
        links = json.load(open(TRM_REPO_LINKS))
        for link in links:
            for match in link.get("matches", []):
                key = (match.get("repo"), (match.get("symbol") or "").lower())
                trm_map.setdefault(key, []).append({
                    "trm_snippet_id": link.get("trm_snippet_id"),
                    "trm_page": link.get("trm_page"),
                    "trm_chapter": link.get("trm_chapter"),
                    "confidence": match.get("confidence", 0),
                })
    except Exception:
        pass
    return trm_map


def run():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(LOG_PATH, mode="a"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    log = logging.getLogger("chunker")
    log.info("=== CHUNKER START ===")

    Path(OUT_FILE).parent.mkdir(parents=True, exist_ok=True)

    clone_map = load_clone_map()
    trm_links = load_trm_links()
    log.info(f"Clone map: {len(clone_map)} entries, TRM links: {len(trm_links)} entries")

    chunk_count = 0
    failed_count = 0

    with open(OUT_FILE, "w") as out_f:
        # ── REPO CODE CHUNKS ────────────────────────────────────────────────
        for repo_name in REPO_ORDER:
            # Use annotated version if available, else plain
            ann_path = Path(SYMBOL_TABLES_DIR) / f"{repo_name}_symbols_annotated.json"
            sym_path = Path(SYMBOL_TABLES_DIR) / f"{repo_name}_symbols.json"

            path_to_use = ann_path if ann_path.exists() else sym_path
            if not path_to_use.exists():
                continue

            try:
                symbols = json.load(open(path_to_use))
            except Exception as e:
                log.error(f"Load symbols {repo_name}: {e}")
                continue

            for sym in symbols:
                try:
                    source = sym.get("source", "").strip()
                    if not source:
                        continue

                    token_count = count_tokens(source)
                    if token_count < MIN_TOKENS:
                        continue

                    # Split large symbols
                    if token_count > MAX_TOKENS["code"]:
                        parts = split_large_source(source, MAX_TOKENS["code"], OVERLAP_TOKENS)
                    else:
                        parts = [source]

                    # Get TRM reference
                    trm_refs = trm_links.get(
                        (repo_name, (sym.get("name") or "").lower()), []
                    )
                    trm_ref = trm_refs[0] if trm_refs else {}
                    has_trm_link = bool(trm_refs)

                    # Get clone info
                    clone_refs = clone_map.get((repo_name, sym.get("name")), [])

                    # Build obsidian node name
                    fn_name = sym.get("name", "?")
                    cls_ctx = sym.get("class_context", "")
                    repo_slug = repo_name.replace("-", "_")
                    file_slug = (sym.get("file") or "").replace("/", "__").replace(".", "_")
                    obs_node = f"{repo_slug}__{file_slug}__{fn_name}.md"

                    for part_idx, part_content in enumerate(parts):
                        part_tokens = count_tokens(part_content)
                        if part_tokens < MIN_TOKENS:
                            continue

                        chunk = {
                            # Core identity
                            "chunk_id": chunk_id(part_content + repo_name + str(sym.get("line_start", 0))),
                            "content": part_content,
                            "content_type": "repo_code",
                            "token_count": part_tokens,
                            "part_index": part_idx,

                            # Symbol metadata
                            "symbol_type": sym.get("type", "unknown"),
                            "symbol_name": fn_name,
                            "class_context": cls_ctx,
                            "qualified_name": sym.get("qualified_name", ""),
                            "signature": sym.get("signature", ""),
                            "docstring": sym.get("docstring", "")[:300],

                            # Location
                            "repo": repo_name,
                            "file": sym.get("file", ""),
                            "line_start": sym.get("line_start", 0),
                            "line_end": sym.get("line_end", 0),
                            "language": sym.get("language", ""),

                            # Git provenance
                            "commit_sha": sym.get("commit_sha", ""),
                            "last_author": sym.get("last_author", ""),
                            "commit_date": sym.get("commit_date", ""),

                            # LLM annotation
                            "llm_summary": sym.get("llm_summary", ""),
                            "purpose_tags": sym.get("purpose_tags", []),
                            "complexity": sym.get("complexity", ""),
                            "called_when": sym.get("called_when", ""),

                            # Cross-references
                            "hardware_binds": sym.get("hardware_binds", []),
                            "has_trm_link": has_trm_link,
                            "trm_reference": trm_ref,
                            "similar_to": clone_refs[:3],  # top 3 clone refs

                            # Vault
                            "obsidian_node": obs_node,
                        }

                        out_f.write(json.dumps(chunk) + "\n")
                        chunk_count += 1

                except Exception as e:
                    log.warning(f"Symbol chunk failed {sym.get('name','?')}: {e}")
                    failed_count += 1
                    continue

            log.info(f"{repo_name}: chunks written so far = {chunk_count}")

        # ── TRM CODE CHUNKS ─────────────────────────────────────────────────
        log.info("Writing TRM code chunks...")
        snippet_dir = Path(TRM_STRUCTURED) / "code_snippets"
        for snippet_file in sorted(snippet_dir.glob("*.json")):
            try:
                snippet = json.load(open(snippet_file))
                content = snippet.get("content", "").strip()
                if not content:
                    continue
                tokens = count_tokens(content)
                if tokens < MIN_TOKENS:
                    continue

                chunk = {
                    "chunk_id": "trm_code_" + chunk_id(content),
                    "content": content,
                    "content_type": "trm_code",
                    "token_count": tokens,
                    "symbol_type": "trm_code",
                    "symbol_name": snippet.get("function_name") or snippet.get("snippet_id", ""),
                    "repo": "TRM",
                    "file": f"VectorTRM.pdf:page{snippet.get('page',0)}",
                    "line_start": snippet.get("page", 0),
                    "line_end": snippet.get("page", 0),
                    "language": snippet.get("language", ""),
                    "chapter": snippet.get("chapter", ""),
                    "section": snippet.get("section", ""),
                    "snippet_id": snippet.get("snippet_id", ""),
                    "llm_summary": "",
                    "purpose_tags": ["trm_code"],
                    "hardware_binds": [],
                    "has_trm_link": False,
                    "trm_reference": {},
                    "similar_to": [],
                    "obsidian_node": f"TRM_Code__{snippet.get('snippet_id','').replace('.','_')}.md",
                }
                out_f.write(json.dumps(chunk) + "\n")
                chunk_count += 1
            except Exception as e:
                log.warning(f"TRM code chunk {snippet_file.name}: {e}")
                continue

        # ── TRM TABLE CHUNKS ─────────────────────────────────────────────────
        log.info("Writing TRM table chunks...")
        tables_dir = Path(TRM_STRUCTURED) / "tables"
        for table_file in sorted(tables_dir.glob("*.json")):
            try:
                table = json.load(open(table_file))
                struct_text = table.get("structured_text", "").strip()
                if not struct_text:
                    # Build from rows
                    rows = table.get("rows", [])
                    struct_text = " | ".join(
                        " ".join(str(v) for v in (r.values() if isinstance(r, dict) else [r]))
                        for r in rows[:50]
                    )
                if not struct_text:
                    continue
                tokens = count_tokens(struct_text)
                if tokens < MIN_TOKENS:
                    continue
                if tokens > MAX_TOKENS["trm_table"]:
                    struct_text = struct_text[:MAX_TOKENS["trm_table"] * 4]  # approx trim
                    tokens = count_tokens(struct_text)

                table_id = table.get("table_id", table_file.stem)
                hw = table.get("hardware_components", table.get("hardware_component"))
                if isinstance(hw, str):
                    hw = [hw] if hw else []
                chunk = {
                    "chunk_id": "trm_table_" + chunk_id(struct_text),
                    "content": struct_text,
                    "content_type": "trm_table",
                    "token_count": tokens,
                    "symbol_type": "trm_table",
                    "symbol_name": table.get("caption", table_id),
                    "repo": "TRM",
                    "file": f"VectorTRM.pdf:page{table.get('page',0)}",
                    "line_start": table.get("page", 0),
                    "line_end": table.get("page", 0),
                    "language": "tabular",
                    "chapter": table.get("chapter", ""),
                    "section": table.get("section", ""),
                    "table_id": table_id,
                    "caption": table.get("caption", ""),
                    "hardware_component": hw[0] if hw else "",
                    "hardware_binds": hw or [],
                    "llm_summary": "",
                    "purpose_tags": ["trm_table"],
                    "has_trm_link": False,
                    "trm_reference": {},
                    "similar_to": [],
                    "obsidian_node": f"TRM_Table__{table_id.replace('.','_')}.md",
                }
                out_f.write(json.dumps(chunk) + "\n")
                chunk_count += 1
            except Exception as e:
                log.warning(f"TRM table chunk {table_file.name}: {e}")
                continue

        # ── TRM PROSE CHUNKS ─────────────────────────────────────────────────
        log.info("Writing TRM prose chunks...")
        page_map = json.load(open(f"{TRM_STRUCTURED}/page_map.json"))
        prose_buffer = []
        prose_buffer_tokens = 0
        prose_chapter = None
        prose_section = None
        prose_page_start = None
        chunk_idx = 0

        def flush_prose():
            nonlocal prose_buffer, prose_buffer_tokens, chunk_idx
            if not prose_buffer or prose_buffer_tokens < MIN_TOKENS:
                prose_buffer = []
                prose_buffer_tokens = 0
                return
            content = " ".join(prose_buffer)
            chunk = {
                "chunk_id": "trm_prose_" + chunk_id(content),
                "content": content,
                "content_type": "trm_prose",
                "token_count": prose_buffer_tokens,
                "symbol_type": "trm_prose",
                "symbol_name": prose_section or prose_chapter or "TRM",
                "repo": "TRM",
                "file": f"VectorTRM.pdf:page{prose_page_start or 0}",
                "line_start": prose_page_start or 0,
                "line_end": prose_page_start or 0,
                "language": "en",
                "chapter": prose_chapter,
                "section": prose_section,
                "llm_summary": "",
                "purpose_tags": ["trm_prose"],
                "hardware_binds": [],
                "has_trm_link": False,
                "trm_reference": {},
                "similar_to": [],
                "obsidian_node": "",
            }
            out_f.write(json.dumps(chunk) + "\n")
            prose_buffer = []
            prose_buffer_tokens = 0
            chunk_idx += 1
            return chunk

        for page in page_map:
            page_num = page["page"]
            chapter = page.get("chapter")
            section = page.get("section")

            # Flush on chapter/section change
            if chapter != prose_chapter or section != prose_section:
                flush_prose()
                prose_chapter = chapter
                prose_section = section
                prose_page_start = page_num

            for block in page.get("blocks", []):
                btype = block.get("type")
                text = block.get("text", "").strip()
                if btype not in ("prose", "subsection_heading", "section_heading") or not text:
                    continue
                if len(text) < 20:
                    continue

                block_tokens = count_tokens(text)
                if prose_buffer_tokens + block_tokens > MAX_TOKENS["trm_prose"]:
                    flush_prose()
                    prose_chapter = chapter
                    prose_section = section
                    prose_page_start = page_num

                if not prose_buffer:
                    prose_page_start = page_num
                prose_buffer.append(text)
                prose_buffer_tokens += block_tokens

        flush_prose()  # Final flush

        # ── TRM DEVELOPER NOTE CHUNKS ────────────────────────────────────────
        log.info("Writing TRM developer note chunks...")
        notes = json.load(open(f"{TRM_STRUCTURED}/developer_notes.json"))
        for note in notes:
            try:
                content = note.get("full_text", note.get("content", "")).strip()
                if not content:
                    continue
                tokens = count_tokens(content)
                if tokens < MIN_TOKENS:
                    continue

                note_id = note.get("note_id", "")
                hw = note.get("hardware_mentions", [])
                chunk = {
                    "chunk_id": "trm_note_" + chunk_id(content),
                    "content": content,
                    "content_type": "trm_note",
                    "token_count": tokens,
                    "symbol_type": "trm_note",
                    "symbol_name": note_id,
                    "repo": "TRM",
                    "file": f"VectorTRM.pdf:page{note.get('page',0)}",
                    "line_start": note.get("page", 0),
                    "line_end": note.get("page", 0),
                    "language": "en",
                    "note_id": note_id,
                    "note_type": note.get("note_type", "NOTE"),
                    "chapter": note.get("chapter", ""),
                    "section": note.get("section", ""),
                    "priority": "HIGH",
                    "hardware_binds": hw,
                    "llm_summary": "",
                    "purpose_tags": ["trm_note", "developer_note"],
                    "has_trm_link": False,
                    "trm_reference": {},
                    "similar_to": [],
                    "obsidian_node": note.get("vault_note", f"TRM_Note__{note_id}.md"),
                }
                out_f.write(json.dumps(chunk) + "\n")
                chunk_count += 1
            except Exception as e:
                log.warning(f"TRM note chunk {note.get('note_id','?')}: {e}")
                continue

    log.info(f"Total chunks: {chunk_count}, failed: {failed_count}")
    print(f"\n=== CHUNKER COMPLETE ===")
    print(f"Total chunks: {chunk_count}")
    print(f"Failed: {failed_count}")

    # Quick stats
    types = {}
    with open(OUT_FILE) as f:
        for line in f:
            if line.strip():
                c = json.loads(line)
                t = c.get("content_type", "?")
                types[t] = types.get(t, 0) + 1
    print("\nChunks by type:")
    for t, n in sorted(types.items(), key=lambda x: -x[1]):
        print(f"  {t:20s}: {n}")


if __name__ == "__main__":
    run()
