#!/usr/bin/env python3
"""
Obsidian Vault Generator — Phase 5
Reads all_chunks.jsonl + pipeline outputs to generate a structured Obsidian vault.
Output: /Users/lab/research/VectorMap/data/Vector_Obsidian_Vault_V2/
"""
import json
import logging
import sys
import os
import re
from pathlib import Path
from collections import defaultdict

CHUNKS_FILE   = "/Users/lab/research/VaultForge/pipeline_output/chunks/all_chunks.jsonl"
SYMBOL_TABLES = "/Users/lab/research/VaultForge/pipeline_output/symbol_tables"
TRM_PAGES_MAP = "/Users/lab/research/VaultForge/pipeline_output/trm_structured/page_map.json"
TRM_NOTES     = "/Users/lab/research/VaultForge/pipeline_output/trm_structured/developer_notes.json"
TRM_SNIPPETS  = "/Users/lab/research/VaultForge/pipeline_output/trm_structured/code_snippets"
TRM_TABLES    = "/Users/lab/research/VaultForge/pipeline_output/trm_structured/tables"
CLONE_PAIRS   = "/Users/lab/research/VaultForge/pipeline_output/clone_pairs/similarity_pairs.json"
CROSS_IMPORTS = "/Users/lab/research/VaultForge/pipeline_output/symbol_tables/cross_repo_imports.json"
TRM_LINKS     = "/Users/lab/research/VaultForge/pipeline_output/trm_structured/trm_repo_links.json"
LOG_PATH      = "/Users/lab/research/VaultForge/pipeline_output/logs/pipeline.log"

VAULT_ROOT    = "/Users/lab/research/VectorMap/data/Vector_Obsidian_Vault_V2"

REPO_ORDER = [
    "vector", "chipper", "vector-cloud", "vector-python-sdk",
    "vector-go-sdk", "wire-pod", "escape-pod-extension", "hugh",
    "vector-bluetooth", "dev-docs", "vector-web-setup", "vectorx", "vectorx-voiceserver"
]

REPO_DESC = {
    "vector":              "Main robot firmware (Go) — animation, behavior, CozmoSDK-like services",
    "chipper":             "Voice/NLP processing service (Go) — intent classification, STT integration",
    "vector-cloud":        "Cloud backend (Go) — account auth, OTA updates, telemetry",
    "vector-python-sdk":   "Official Python SDK for Vector robot — anki_vector package",
    "vector-go-sdk":       "Official Go SDK for Vector robot",
    "wire-pod":            "Community open-source server replacing Anki/DDLC cloud (Go)",
    "escape-pod-extension": "Escape Pod community extension for self-hosted operation",
    "hugh":                "Home automation bridge (Vector → MQTT/Home Assistant)",
    "vector-bluetooth":    "BLE pairing and setup utilities",
    "dev-docs":            "Developer documentation markdown source",
    "vector-web-setup":    "Web-based setup UI (JavaScript)",
    "vectorx":             "Extended firmware fork with additional features",
    "vectorx-voiceserver": "Voice server companion for VectorX",
}


def slugify(text):
    """Create a filesystem-safe slug from text."""
    text = re.sub(r"[^\w\s\-]", "", str(text))
    text = re.sub(r"[\s]+", "_", text.strip())
    return text[:80]


def write_note(path, content):
    """Write a markdown note, creating parent dirs as needed."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def frontmatter(meta):
    """Generate YAML frontmatter block."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            if v:
                lines.append(f"{k}:")
                for item in v:
                    lines.append(f"  - {item}")
            else:
                lines.append(f"{k}: []")
        elif isinstance(v, str):
            # Escape quotes
            safe = v.replace('"', '\\"')
            lines.append(f'{k}: "{safe}"')
        else:
            lines.append(f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def load_chunks_by_type():
    """Load all_chunks.jsonl, partition by type."""
    by_type = defaultdict(list)
    by_repo = defaultdict(list)
    by_file = defaultdict(list)
    with open(CHUNKS_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            chunk = json.loads(line)
            t = chunk.get("content_type", "unknown")   # chunker uses content_type
            by_type[t].append(chunk)
            r = chunk.get("repo", "")
            if r:
                by_repo[r].append(chunk)
            fp = chunk.get("file", "")                 # chunker uses file not file_path
            if fp:
                by_file[(r, fp)].append(chunk)
    return by_type, by_repo, by_file


def load_annotated_symbols():
    """Load all annotated symbol tables, keyed by (repo, name)."""
    syms = {}
    for repo in REPO_ORDER:
        path = Path(SYMBOL_TABLES) / f"{repo}_symbols_annotated.json"
        if path.exists():
            for s in json.load(open(path)):
                syms[(repo, s.get("name", ""))] = s
    return syms


# ─────────────────────────────────────────────
# Phase A: Repo-level index notes
# ─────────────────────────────────────────────

def generate_repo_notes(by_repo, cross_imports, clone_pairs):
    """One note per repo under Repos/."""
    log = logging.getLogger("vault_gen")
    for repo in REPO_ORDER:
        chunks = by_repo.get(repo, [])
        if not chunks:
            continue

        # Gather files
        files = sorted({c.get("file_path", "") for c in chunks if c.get("file_path")})

        # Gather imports to/from this repo
        imports_out = [(i["resolves_to_repo"], i["import_module"])
                       for i in cross_imports if i.get("source_repo") == repo and i.get("is_cross_repo")]
        imports_in  = [(i["source_repo"], i["import_module"])
                       for i in cross_imports if i.get("resolves_to_repo") == repo and i.get("is_cross_repo")]

        # Clone partners
        partners = set()
        for p in clone_pairs:
            if p["repo_a"] == repo:
                partners.add(p["repo_b"])
            elif p["repo_b"] == repo:
                partners.add(p["repo_a"])

        fm = frontmatter({
            "title": repo,
            "type": "repo_index",
            "repo": repo,
            "chunk_count": len(chunks),
            "file_count": len(files),
            "clone_partners": sorted(partners),
            "tags": ["repo", repo.replace("-", "_")],
        })

        body = f"# {repo}\n\n"
        body += f"> {REPO_DESC.get(repo, '')}\n\n"
        body += f"**Chunks indexed:** {len(chunks)}  \n"
        body += f"**Source files:** {len(files)}\n\n"

        if imports_out:
            body += "## Imports (cross-repo)\n"
            out_by_target = defaultdict(list)
            for target, mod in imports_out[:30]:
                out_by_target[target].append(mod)
            for target, mods in sorted(out_by_target.items()):
                body += f"- → [[{target}]]: `{mods[0]}`"
                if len(mods) > 1:
                    body += f" (+{len(mods)-1} more)"
                body += "\n"
            body += "\n"

        if imports_in:
            body += "## Imported by\n"
            in_by_source = defaultdict(int)
            for src, _ in imports_in:
                in_by_source[src] += 1
            for src, cnt in sorted(in_by_source.items(), key=lambda x: -x[1]):
                body += f"- [[{src}]] ({cnt} imports)\n"
            body += "\n"

        if partners:
            body += "## Clone/Fork Relationships\n"
            for p in sorted(partners):
                pairs = [x for x in clone_pairs
                         if (x["repo_a"] == repo and x["repo_b"] == p) or
                            (x["repo_b"] == repo and x["repo_a"] == p)]
                exact = sum(1 for x in pairs if x["relationship"] == "exact_copy")
                near  = sum(1 for x in pairs if x["relationship"] == "near_identical_fork")
                body += f"- [[{p}]]: {len(pairs)} similar symbols ({exact} exact, {near} near-identical)\n"
            body += "\n"

        if files:
            body += "## Source Files\n"
            for fp in files[:50]:
                slug = slugify(fp)
                body += f"- [[{repo}_{slug}|{fp}]]\n"
            if len(files) > 50:
                body += f"- _(+{len(files)-50} more files)_\n"

        out_path = Path(VAULT_ROOT) / "Repos" / f"{repo}.md"
        write_note(out_path, fm + body)

    log.info(f"Repo notes: {len(REPO_ORDER)}")


# ─────────────────────────────────────────────
# Phase B: Per-file module notes
# ─────────────────────────────────────────────

def generate_module_notes(by_file, all_syms, cross_imports):
    """One note per source file under Modules/<repo>/."""
    log = logging.getLogger("vault_gen")
    count = 0
    for (repo, fp), chunks in by_file.items():
        if not fp:
            continue

        # Find symbols from this file
        file_syms = [s for s in all_syms.values()
                     if s.get("repo") == repo and s.get("file") == fp]
        file_syms.sort(key=lambda s: s.get("line_start", 0))

        # Language (file field is 'file' in chunks, 'language' is same)
        lang = chunks[0].get("language", "unknown") if chunks else "unknown"

        fm = frontmatter({
            "title": fp,
            "type": "module",
            "repo": repo,
            "file_path": fp,
            "language": lang,
            "symbol_count": len(file_syms),
            "chunk_count": len(chunks),
            "tags": ["module", repo.replace("-", "_"), lang],
        })

        slug = slugify(fp)
        body = f"# `{fp}`\n\n"
        body += f"**Repo:** [[{repo}]]  \n"
        body += f"**Language:** {lang}  \n"
        body += f"**Symbols:** {len(file_syms)}  \n"
        body += f"**Chunks:** {len(chunks)}\n\n"

        if file_syms:
            body += "## Symbols\n\n"
            for s in file_syms[:60]:
                stype = s.get("type", "?")
                sname = s.get("name", "?")
                summary = s.get("llm_summary", "")
                lineno = s.get("line_start", "")
                sym_slug = slugify(f"{repo}_{sname}")
                body += f"- **{stype}** [[{sym_slug}|{sname}]]"
                if lineno:
                    body += f" (line {lineno})"
                if summary:
                    body += f" — {summary[:100]}"
                body += "\n"
            if len(file_syms) > 60:
                body += f"\n_(+{len(file_syms)-60} more symbols)_\n"
            body += "\n"

        out_path = Path(VAULT_ROOT) / "Modules" / repo / f"{slug}.md"
        write_note(out_path, fm + body)
        count += 1

    log.info(f"Module notes: {count}")
    return count


# ─────────────────────────────────────────────
# Phase C: Symbol notes (functions/classes)
# ─────────────────────────────────────────────

def generate_symbol_notes(all_syms, clone_pairs, trm_links):
    """One note per significant symbol under Symbols/<repo>/."""
    log = logging.getLogger("vault_gen")

    # Build TRM link index: symbol_name -> [link records]
    trm_by_sym = defaultdict(list)
    for link in trm_links:
        for m in link.get("matches", []):
            if m.get("confidence", 0) >= 0.7:
                trm_by_sym[m.get("symbol", "")].append(link)

    # Build clone partner index
    clone_by_sym = defaultdict(list)
    for p in clone_pairs:
        if p.get("similarity_token", 0) >= 0.8:
            clone_by_sym[p["symbol_a"]].append(p)
            clone_by_sym[p["symbol_b"]].append(p)

    count = 0
    for (repo, name), s in all_syms.items():
        stype = s.get("type", "unknown")
        if stype not in ("function", "method", "class", "struct", "type"):
            continue

        fp = s.get("file", "")
        lang = s.get("language", "unknown")
        summary = s.get("llm_summary", "")
        called_when = s.get("called_when", "")
        tags = s.get("purpose_tags", [])
        complexity = s.get("complexity", "unknown")
        source = s.get("source", "")
        lineno = s.get("line_start", "")
        docstring = s.get("docstring", "")
        sig = s.get("signature", "")

        slug = slugify(f"{repo}_{name}")
        file_slug = slugify(fp)

        fm = frontmatter({
            "title": name,
            "type": "symbol",
            "symbol_type": stype,
            "repo": repo,
            "file_path": fp,
            "language": lang,
            "complexity": complexity,
            "line_start": lineno,
            "tags": ["symbol", repo.replace("-", "_"), lang] + (tags or []),
        })

        body = f"# `{name}`\n\n"
        body += f"**Type:** {stype}  \n"
        body += f"**Repo:** [[{repo}]]  \n"
        body += f"**File:** [[{file_slug}|{fp}]]  \n"
        if lineno:
            body += f"**Line:** {lineno}  \n"
        body += f"**Complexity:** {complexity}\n\n"

        if sig:
            body += f"## Signature\n```{lang}\n{sig}\n```\n\n"

        if docstring:
            body += f"## Docstring\n{docstring[:500]}\n\n"

        if summary:
            body += f"## Summary\n{summary}\n\n"

        if called_when:
            body += f"## Called When\n{called_when}\n\n"

        if source and len(source) < 3000:
            body += f"## Source\n```{lang}\n{source[:2000]}\n```\n\n"
        elif source:
            body += f"## Source (truncated)\n```{lang}\n{source[:1500]}\n...\n```\n\n"

        # TRM links
        if name in trm_by_sym:
            body += "## TRM References\n"
            for link in trm_by_sym[name][:3]:
                body += f"- [[TRM_Page_{link.get('trm_page','?')}|Page {link.get('trm_page','?')}]] — {link.get('trm_function','')}\n"
            body += "\n"

        # Clone partners
        if name in clone_by_sym:
            body += "## Similar Symbols\n"
            for p in clone_by_sym[name][:5]:
                other = p["symbol_b"] if p["symbol_a"] == name else p["symbol_a"]
                other_repo = p["repo_b"] if p["symbol_a"] == name else p["repo_a"]
                rel = p.get("relationship", "")
                sim = p.get("similarity_token", 0)
                other_slug = slugify(f"{other_repo}_{other}")
                body += f"- [[{other_slug}|{other_repo}/{other}]] — {rel} ({sim:.0%})\n"
            body += "\n"

        out_path = Path(VAULT_ROOT) / "Symbols" / repo / f"{slug}.md"
        write_note(out_path, fm + body)
        count += 1

    log.info(f"Symbol notes: {count}")
    return count


# ─────────────────────────────────────────────
# Phase D: TRM notes
# ─────────────────────────────────────────────

def generate_trm_notes(by_type, trm_links):
    """Generate TRM chapter pages, code snippet notes, table notes, dev notes."""
    log = logging.getLogger("vault_gen")
    count = 0

    # ── D1: Developer Notes (highest priority) ──
    if Path(TRM_NOTES).exists():
        notes = json.load(open(TRM_NOTES))
        for note in notes:
            nid = note.get("note_id", "N?")
            page = note.get("page", 0)
            chapter = note.get("chapter", "")
            section = note.get("section", "")
            content = note.get("content", "")
            hw = note.get("hardware_mentions", [])
            ntype = note.get("note_type", "NOTE")
            priority = note.get("priority", "MEDIUM")

            fm = frontmatter({
                "title": f"{ntype}: {nid}",
                "type": "trm_developer_note",
                "note_id": nid,
                "note_type": ntype,
                "priority": priority,
                "trm_page": page,
                "trm_chapter": chapter,
                "hardware_mentions": hw,
                "tags": ["trm", "developer_note", ntype.lower(), "hardware"],
            })

            body = f"# {ntype}: {nid}\n\n"
            body += f"> **Priority:** {priority}\n\n"
            if chapter:
                body += f"**Chapter:** {chapter}  \n"
            if section:
                body += f"**Section:** {section}  \n"
            body += f"**TRM Page:** [[TRM_Page_{page}|Page {page}]]\n\n"
            body += f"## Content\n{content}\n\n"

            if hw:
                body += "## Hardware Mentions\n"
                for h in hw:
                    body += f"- `{h}`\n"
                body += "\n"

            out_path = Path(VAULT_ROOT) / "TRM" / "DeveloperNotes" / f"{nid}.md"
            write_note(out_path, fm + body)
            count += 1

    log.info(f"TRM developer notes: {count}")

    # ── D2: TRM Code Snippets ──
    snippet_count = 0
    if Path(TRM_SNIPPETS).exists():
        for sf in sorted(Path(TRM_SNIPPETS).glob("*.json")):
            try:
                s = json.load(open(sf))
                sid = s.get("snippet_id", sf.stem)
                page = s.get("page", 0)
                chapter = s.get("chapter", "")
                content = s.get("content", "")
                fn_name = s.get("function_name", "")

                # Find matching repo symbols
                matches = [l for l in trm_links if l.get("trm_snippet_id") == sid]

                fm = frontmatter({
                    "title": sid,
                    "type": "trm_code_snippet",
                    "snippet_id": sid,
                    "trm_page": page,
                    "trm_chapter": chapter,
                    "function_name": fn_name,
                    "tags": ["trm", "code_snippet"],
                })

                body = f"# Code Snippet: {sid}\n\n"
                if chapter:
                    body += f"**Chapter:** {chapter}  \n"
                body += f"**Page:** [[TRM_Page_{page}|{page}]]\n\n"

                if fn_name:
                    body += f"**Function:** `{fn_name}`\n\n"

                body += f"## Content\n```\n{content[:2000]}\n```\n\n"

                if matches:
                    body += "## Repo Matches\n"
                    for m_link in matches[:3]:
                        for m in m_link.get("matches", [])[:3]:
                            repo = m.get("repo", "")
                            sym = m.get("symbol", "")
                            conf = m.get("confidence", 0)
                            fp = m.get("file", "")
                            slug = slugify(f"{repo}_{sym}")
                            body += f"- [[{slug}|{repo}/{sym}]] (conf: {conf:.0%})\n"
                    body += "\n"

                out_path = Path(VAULT_ROOT) / "TRM" / "CodeSnippets" / f"{sid}.md"
                write_note(out_path, fm + body)
                snippet_count += 1
            except Exception as e:
                continue

    log.info(f"TRM code snippets: {snippet_count}")

    # ── D3: TRM Tables ──
    table_count = 0
    if Path(TRM_TABLES).exists():
        for tf in sorted(Path(TRM_TABLES).glob("*.json")):
            try:
                t = json.load(open(tf))
                tid = t.get("table_id", tf.stem)
                page = t.get("page", 0)
                chapter = t.get("chapter", "")
                caption = t.get("caption", "")
                headers = t.get("headers", [])
                rows = t.get("rows", [])

                fm = frontmatter({
                    "title": tid,
                    "type": "trm_table",
                    "table_id": tid,
                    "trm_page": page,
                    "trm_chapter": chapter,
                    "caption": caption,
                    "tags": ["trm", "table"],
                })

                body = f"# Table: {tid}\n\n"
                if caption:
                    body += f"**Caption:** {caption}  \n"
                if chapter:
                    body += f"**Chapter:** {chapter}  \n"
                body += f"**Page:** [[TRM_Page_{page}|{page}]]\n\n"

                if headers and rows:
                    body += "## Data\n\n"
                    body += "| " + " | ".join(str(h) for h in headers) + " |\n"
                    body += "| " + " | ".join("---" for _ in headers) + " |\n"
                    for row in rows[:30]:
                        if isinstance(row, dict):
                            vals = [str(row.get(h, "")) for h in headers]
                        elif isinstance(row, list):
                            vals = [str(v) for v in row]
                        else:
                            vals = [str(row)]
                        # Escape pipe chars
                        vals = [v.replace("|", "\\|") for v in vals]
                        body += "| " + " | ".join(vals) + " |\n"
                    if len(rows) > 30:
                        body += f"\n_(+{len(rows)-30} more rows)_\n"
                    body += "\n"

                out_path = Path(VAULT_ROOT) / "TRM" / "Tables" / f"{tid}.md"
                write_note(out_path, fm + body)
                table_count += 1
            except Exception as e:
                continue

    log.info(f"TRM tables: {table_count}")
    return count, snippet_count, table_count


# ─────────────────────────────────────────────
# Phase E: TRM Chapter pages (from page_map)
# ─────────────────────────────────────────────

def generate_trm_chapter_pages(trm_links):
    """Aggregate page_map blocks into chapter-level notes."""
    log = logging.getLogger("vault_gen")

    if not Path(TRM_PAGES_MAP).exists():
        log.warning("page_map.json not found")
        return 0

    page_map = json.load(open(TRM_PAGES_MAP))

    # Group by chapter
    chapters = defaultdict(list)
    for block in page_map:
        ch = block.get("chapter") or "Uncategorized"
        chapters[ch].append(block)

    count = 0
    for chapter, blocks in chapters.items():
        # Get page range
        pages = [b.get("page", 0) for b in blocks if b.get("page")]
        page_start = min(pages) if pages else 0
        page_end = max(pages) if pages else 0

        # Collect sections
        sections = []
        seen_secs = set()
        for b in blocks:
            s = b.get("section") or ""
            if s and s not in seen_secs:
                seen_secs.add(s)
                sections.append(s)

        # Developer notes in this chapter
        dev_note_refs = []
        if Path(TRM_NOTES).exists():
            notes = json.load(open(TRM_NOTES))
            dev_note_refs = [n["note_id"] for n in notes if n.get("chapter") == chapter]

        # Prose blocks
        prose_blocks = [b for b in blocks if b.get("block_type") == "prose"]

        slug = slugify(chapter)
        fm = frontmatter({
            "title": chapter,
            "type": "trm_chapter",
            "trm_pages": f"{page_start}–{page_end}",
            "section_count": len(sections),
            "developer_notes": dev_note_refs,
            "tags": ["trm", "chapter"],
        })

        body = f"# {chapter}\n\n"
        body += f"**TRM Pages:** {page_start}–{page_end}  \n"
        body += f"**Sections:** {len(sections)}\n\n"

        if dev_note_refs:
            body += "## Developer Notes\n"
            for nid in dev_note_refs:
                body += f"- [[{nid}]]\n"
            body += "\n"

        if sections:
            body += "## Sections\n"
            for sec in sections[:20]:
                body += f"- {sec}\n"
            if len(sections) > 20:
                body += f"- _(+{len(sections)-20} more)_\n"
            body += "\n"

        # Include a sample of prose
        if prose_blocks:
            body += "## Content Preview\n\n"
            for pb in prose_blocks[:5]:
                body += pb.get("text", "")[:300] + "\n\n"

        out_path = Path(VAULT_ROOT) / "TRM" / "Chapters" / f"{slug}.md"
        write_note(out_path, fm + body)
        count += 1

    log.info(f"TRM chapter pages: {count}")
    return count


# ─────────────────────────────────────────────
# Phase F: CrossLinks (clone pairs + imports)
# ─────────────────────────────────────────────

def generate_crosslink_notes(clone_pairs, cross_imports, trm_links):
    """Generate summary crosslink notes."""
    log = logging.getLogger("vault_gen")

    # Clone relationships by repo pair
    pair_groups = defaultdict(list)
    for p in clone_pairs:
        key = tuple(sorted([p["repo_a"], p["repo_b"]]))
        pair_groups[key].append(p)

    count = 0
    for (ra, rb), pairs in pair_groups.items():
        pairs.sort(key=lambda x: -x["similarity_token"])
        exact = [p for p in pairs if p["relationship"] == "exact_copy"]
        near  = [p for p in pairs if p["relationship"] == "near_identical_fork"]
        mod   = [p for p in pairs if p["relationship"] == "fork_with_modifications"]

        fm = frontmatter({
            "title": f"Clone: {ra} ↔ {rb}",
            "type": "clone_relationship",
            "repo_a": ra,
            "repo_b": rb,
            "total_pairs": len(pairs),
            "exact_copies": len(exact),
            "near_identical": len(near),
            "tags": ["clone", "crosslink", ra.replace("-","_"), rb.replace("-","_")],
        })

        body = f"# Clone: {ra} ↔ {rb}\n\n"
        body += f"**Total similar symbols:** {len(pairs)}  \n"
        body += f"**Exact copies:** {len(exact)}  \n"
        body += f"**Near-identical forks:** {len(near)}  \n"
        body += f"**Modified forks:** {len(mod)}\n\n"
        body += f"→ [[{ra}]] | [[{rb}]]\n\n"

        if exact:
            body += "## Exact Copies (top 10)\n"
            for p in exact[:10]:
                sa_slug = slugify(f"{ra}_{p['symbol_a']}")
                sb_slug = slugify(f"{rb}_{p['symbol_b']}")
                body += f"- [[{sa_slug}|{p['symbol_a']}]] ↔ [[{sb_slug}|{p['symbol_b']}]] ({p['similarity_token']:.0%})\n"
            body += "\n"

        if near:
            body += "## Near-Identical (top 10)\n"
            for p in near[:10]:
                sa_slug = slugify(f"{ra}_{p['symbol_a']}")
                sb_slug = slugify(f"{rb}_{p['symbol_b']}")
                body += f"- [[{sa_slug}|{p['symbol_a']}]] ↔ [[{sb_slug}|{p['symbol_b']}]] ({p['similarity_token']:.0%})\n"
            body += "\n"

        slug = slugify(f"{ra}_{rb}_clone")
        out_path = Path(VAULT_ROOT) / "CrossLinks" / f"{slug}.md"
        write_note(out_path, fm + body)
        count += 1

    log.info(f"Clone crosslink notes: {count}")

    # Import graph summary
    import_pairs = defaultdict(int)
    for imp in cross_imports:
        if imp.get("is_cross_repo"):
            key = (imp["source_repo"], imp["resolves_to_repo"])
            import_pairs[key] += 1

    fm = frontmatter({
        "title": "Cross-Repo Import Graph",
        "type": "architecture_overview",
        "tags": ["architecture", "imports", "crosslink"],
    })
    body = "# Cross-Repo Import Graph\n\n"
    body += f"**Total cross-repo import relationships:** {len(cross_imports)}\n\n"
    body += "## Import Counts\n\n"
    for (src, dst), cnt in sorted(import_pairs.items(), key=lambda x: -x[1]):
        body += f"- [[{src}]] → [[{dst}]]: {cnt} imports\n"

    out_path = Path(VAULT_ROOT) / "Architecture" / "cross_repo_imports.md"
    write_note(out_path, fm + body)

    log.info(f"CrossLink notes: {count}")
    return count


# ─────────────────────────────────────────────
# Phase G: Vault index (_index/)
# ─────────────────────────────────────────────

def generate_index(all_syms, by_repo, by_type, trm_links, clone_pairs):
    """Generate top-level vault index and README."""
    log = logging.getLogger("vault_gen")

    total_chunks = sum(len(v) for v in by_type.values())
    total_syms = len(all_syms)

    # Main README
    body = "# Vector Obsidian Vault V2\n\n"
    body += "> Auto-generated from VaultForge pipeline. Do not edit manually.\n\n"
    body += f"**Total chunks indexed:** {total_chunks:,}  \n"
    body += f"**Total symbols:** {total_syms:,}  \n"
    body += f"**Repositories:** {len(REPO_ORDER)}  \n"
    body += f"**TRM developer notes:** {len(by_type.get('trm_note', []))}\n\n"

    body += "## Repositories\n\n"
    for repo in REPO_ORDER:
        chunks = by_repo.get(repo, [])
        body += f"- [[{repo}]] — {len(chunks)} chunks — {REPO_DESC.get(repo,'')}\n"

    body += "\n## Navigation\n\n"
    body += "| Section | Contents |\n|---------|----------|\n"
    body += "| [[Repos/]] | Per-repository index notes |\n"
    body += "| [[Modules/]] | Per-source-file notes |\n"
    body += "| [[Symbols/]] | Per-function/class notes |\n"
    body += "| [[TRM/Chapters/]] | TRM chapter summaries |\n"
    body += "| [[TRM/CodeSnippets/]] | TRM register/struct definitions |\n"
    body += "| [[TRM/Tables/]] | TRM hardware tables |\n"
    body += "| [[TRM/DeveloperNotes/]] | NOTE/WARNING/CAUTION annotations |\n"
    body += "| [[CrossLinks/]] | Clone relationships between repos |\n"
    body += "| [[Architecture/]] | Import graphs and architecture overviews |\n"

    body += "\n## TRM Overview\n\n"
    body += "- **TRM pages scanned:** 543\n"
    body += f"- **Code snippets:** {len(list(Path(TRM_SNIPPETS).glob('*.json')) if Path(TRM_SNIPPETS).exists() else [])}\n"
    body += f"- **Tables:** {len(list(Path(TRM_TABLES).glob('*.json')) if Path(TRM_TABLES).exists() else [])}\n"
    body += f"- **Developer notes:** {len(by_type.get('trm_note', []))}\n"
    body += f"- **TRM→Repo links:** {len(trm_links)}\n\n"

    body += "## Clone/Fork Summary\n\n"
    pair_groups = defaultdict(int)
    for p in clone_pairs:
        key = tuple(sorted([p["repo_a"], p["repo_b"]]))
        pair_groups[key] += 1
    for (ra, rb), cnt in sorted(pair_groups.items(), key=lambda x: -x[1])[:10]:
        slug = slugify(f"{ra}_{rb}_clone")
        body += f"- [[{slug}|{ra} ↔ {rb}]]: {cnt} similar symbols\n"

    write_note(Path(VAULT_ROOT) / "README.md", body)
    log.info("Vault README written")


# ─────────────────────────────────────────────
# Main run
# ─────────────────────────────────────────────

def run():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(LOG_PATH, mode="a"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    log = logging.getLogger("vault_gen")
    log.info("=== VAULT GENERATOR START ===")

    # Create vault root
    Path(VAULT_ROOT).mkdir(parents=True, exist_ok=True)

    # Load data
    log.info("Loading chunks...")
    by_type, by_repo, by_file = load_chunks_by_type()
    total_chunks = sum(len(v) for v in by_type.values())
    log.info(f"Loaded {total_chunks} chunks")

    log.info("Loading annotated symbols...")
    all_syms = load_annotated_symbols()
    log.info(f"Loaded {len(all_syms)} symbols")

    log.info("Loading cross-repo imports...")
    cross_imports = json.load(open(CROSS_IMPORTS)) if Path(CROSS_IMPORTS).exists() else []

    log.info("Loading clone pairs...")
    clone_pairs = json.load(open(CLONE_PAIRS)) if Path(CLONE_PAIRS).exists() else []

    log.info("Loading TRM links...")
    trm_links = json.load(open(TRM_LINKS)) if Path(TRM_LINKS).exists() else []

    # Generate all note types
    log.info("Generating repo notes...")
    generate_repo_notes(by_repo, cross_imports, clone_pairs)

    log.info("Generating module notes...")
    mod_count = generate_module_notes(by_file, all_syms, cross_imports)

    log.info("Generating symbol notes...")
    sym_count = generate_symbol_notes(all_syms, clone_pairs, trm_links)

    log.info("Generating TRM notes...")
    dev_count, snip_count, tbl_count = generate_trm_notes(by_type, trm_links)

    log.info("Generating TRM chapter pages...")
    ch_count = generate_trm_chapter_pages(trm_links)

    log.info("Generating crosslink notes...")
    cl_count = generate_crosslink_notes(clone_pairs, cross_imports, trm_links)

    log.info("Generating vault index...")
    generate_index(all_syms, by_repo, by_type, trm_links, clone_pairs)

    # Count all .md files
    all_md = list(Path(VAULT_ROOT).rglob("*.md"))
    log.info(f"Total vault .md files: {len(all_md)}")

    print(f"\n=== VAULT GENERATOR COMPLETE ===")
    print(f"Total .md files: {len(all_md)}")
    print(f"  Repos:          {len(REPO_ORDER)}")
    print(f"  Modules:        {mod_count}")
    print(f"  Symbols:        {sym_count}")
    print(f"  TRM chapters:   {ch_count}")
    print(f"  TRM dev notes:  {dev_count}")
    print(f"  TRM snippets:   {snip_count}")
    print(f"  TRM tables:     {tbl_count}")
    print(f"  CrossLinks:     {cl_count}")


if __name__ == "__main__":
    run()
