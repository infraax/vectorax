#!/usr/bin/env python3
"""
VectorMap MCP Server
====================
Exposes VaultForge knowledge (35K code chunks, 77 TRM developer notes,
212 hardware tables, 40K parsed symbols) as MCP tools for Claude Code.

Tools:
  vector_search          — token-budgeted semantic search across all collections
  get_symbol             — full symbol definition with context + TRM links
  get_hardware_context   — everything about a hardware component in one shot
  get_task_briefing      — pre-assembled context package, uses local LLM to synthesize
  get_grpc_map           — proto + server + client assembled for a gRPC service
  ask_local_coder        — dispatch to qwen2.5-coder, save Anthropic tokens
  save_session_context   — persist working state, survives context compression
  load_session_context   — restore working state after compression (<<200 tokens)

Start:
  python vectormap_mcp/server.py
  — or via MCP config (stdio transport, registered in ~/.claude/settings.json)
"""
import sys
import json
import re
from pathlib import Path
from typing import Optional

# Add parent dir so relative imports work when run directly
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server.fastmcp import FastMCP
from vectormap_mcp import session_store, local_llm

# ── Config ─────────────────────────────────────────────────────────────────
CHROMA_PATH = "/Users/lab/research/VectorMap/data/chroma_db_v2"
VAULT_PATH  = "/Users/lab/research/VectorMap/data/Vector_Obsidian_Vault_V2"
CHUNKS_FILE = "/Users/lab/research/VaultForge/pipeline_output/chunks/all_chunks.jsonl"

COLLECTIONS = ["repo_code", "trm_notes", "trm_code", "trm_tables", "trm_prose"]

# Tokens-per-char approximation for budget control (conservative)
CHARS_PER_TOKEN = 3.5

mcp = FastMCP(
    "vectormap",
    instructions=(
        "Knowledge base for the Vector (Anki/DDL) robot ecosystem. "
        "13 repositories + 565-page hardware TRM. "
        "Always check trm_notes when working near hardware. "
        "Use save_session_context after decisions to survive context compression. "
        "Use ask_local_coder for simple lookups to preserve Anthropic tokens."
    ),
)

# ── ChromaDB client (lazy init) ────────────────────────────────────────────
_chroma = None

def _get_chroma():
    global _chroma
    if _chroma is None:
        import chromadb
        _chroma = chromadb.PersistentClient(path=CHROMA_PATH)
    return _chroma


def _get_col(name: str):
    try:
        return _get_chroma().get_collection(name)
    except Exception:
        return None


def _embed(text: str) -> list[float]:
    vecs = local_llm.embed([text])
    return vecs[0] if vecs else []


def _tokens(text: str) -> int:
    return int(len(text) / CHARS_PER_TOKEN)


def _trim_to_budget(items: list[dict], max_tokens: int, key: str = "content") -> list[dict]:
    """Return items until token budget is exhausted."""
    budget = max_tokens
    result = []
    for item in items:
        t = _tokens(str(item.get(key, "")))
        if t > budget and result:  # always include at least 1 result
            break
        result.append(item)
        budget -= t
    return result


# ══════════════════════════════════════════════════════════════════════════
# TOOL 1 — vector_search
# ══════════════════════════════════════════════════════════════════════════
@mcp.tool()
def vector_search(
    query: str,
    types: str = "all",
    repo: Optional[str] = None,
    max_tokens: int = 2000,
    detail: str = "summary",
) -> str:
    """
    Semantic search across VaultForge knowledge base.

    Args:
        query:      What you're looking for in plain English or code terms.
        types:      Comma-separated subset: "code,trm_note,table,trm_code,prose"
                    or "all". trm_notes are ALWAYS included when type is "all"
                    because they contain critical engineering warnings.
        repo:       Filter to a specific repo (e.g. "vector", "chipper", "wire-pod",
                    "vector-python-sdk"). None = search all repos.
        max_tokens: Hard limit on returned content. Controls your context budget.
                    Use 500 for a quick scan, 2000 for working context, 4000 for
                    deep dive. Default 2000.
        detail:     "summary" = symbol name + file + line + 1-line description.
                    "full"    = complete code body. Use full only when you need
                    to read or modify the actual code.

    Returns:
        Ranked results grouped by collection type, never exceeding max_tokens.
    """
    query_emb = _embed(query)
    if not query_emb:
        return "ERROR: Could not embed query — is Ollama running with nomic-embed-text?"

    # Determine which collections to search
    type_map = {
        "code":     ["repo_code"],
        "trm_note": ["trm_notes"],
        "table":    ["trm_tables"],
        "trm_code": ["trm_code"],
        "prose":    ["trm_prose"],
        "all":      COLLECTIONS,
    }
    search_cols = []
    if types == "all":
        search_cols = COLLECTIONS
    else:
        for t in types.split(","):
            search_cols.extend(type_map.get(t.strip(), []))
    # Always include trm_notes when searching all
    if types == "all" and "trm_notes" not in search_cols:
        search_cols.insert(0, "trm_notes")

    k_per_col = max(3, (max_tokens // 200) // max(1, len(search_cols)))
    all_results = []

    for col_name in search_cols:
        col = _get_col(col_name)
        if col is None or col.count() == 0:
            continue
        try:
            where = {"repo": {"$eq": repo}} if repo and col_name == "repo_code" else None
            r = col.query(
                query_embeddings=[query_emb],
                n_results=min(k_per_col, col.count()),
                include=["documents", "metadatas", "distances"],
                where=where,
            )
            for doc, meta, dist in zip(
                r["documents"][0], r["metadatas"][0], r["distances"][0]
            ):
                all_results.append({
                    "distance":    dist,
                    "collection":  col_name,
                    "content":     doc,
                    "meta":        meta or {},
                })
        except Exception as e:
            all_results.append({"collection": col_name, "error": str(e)})

    # Sort by similarity (lower cosine distance = more relevant)
    all_results.sort(key=lambda x: x.get("distance", 1.0))

    # Format output
    lines = [f"## VectorMap Search: '{query}'\n"]
    budget = max_tokens
    shown = 0

    # Always surface TRM developer notes first if present
    trm_hits = [r for r in all_results if r.get("collection") == "trm_notes"]
    other_hits = [r for r in all_results if r.get("collection") != "trm_notes"]

    for r in trm_hits + other_hits:
        if "error" in r:
            continue
        meta = r["meta"]
        col  = r["collection"]
        dist = r.get("distance", 1.0)
        relevance = max(0.0, 1.0 - dist)

        # Build result block
        if col == "trm_notes":
            block = (
                f"### ⚠ TRM {meta.get('note_type','NOTE')} [{meta.get('note_id','')}] "
                f"(relevance {relevance:.0%})\n"
                f"**Chapter:** {meta.get('chapter','')[:60]}\n"
                f"**Content:** {r['content'][:400]}\n"
            )
        elif col == "repo_code":
            repo_name = meta.get("repo", "")
            sym_name  = meta.get("symbol_name", "")
            sym_type  = meta.get("symbol_type", "")
            file_path = meta.get("file", "")
            line      = meta.get("line_start", "")
            summary   = meta.get("llm_summary", "")
            hw_binds  = meta.get("hardware_binds", "")

            if detail == "summary":
                body = f"  {r['content'][:120]}…" if len(r['content']) > 120 else f"  {r['content']}"
            else:
                body = r['content']

            block = (
                f"### {sym_type} `{sym_name}` — {repo_name} (relevance {relevance:.0%})\n"
                f"**File:** `{file_path}:{line}`\n"
            )
            if summary:
                block += f"**Summary:** {summary}\n"
            if hw_binds:
                block += f"**Hardware:** {hw_binds}\n"
            block += f"```\n{body}\n```\n"

        elif col in ("trm_tables", "trm_code"):
            block = (
                f"### TRM {col.replace('trm_','')} [{meta.get('table_id') or meta.get('note_id','')}] "
                f"(relevance {relevance:.0%})\n"
                f"**Caption:** {meta.get('caption','')[:80]}\n"
                f"{r['content'][:300]}\n"
            )
        else:
            block = f"### Prose (relevance {relevance:.0%})\n{r['content'][:200]}\n"

        cost = _tokens(block)
        if cost > budget and shown > 0:
            break
        lines.append(block)
        budget -= cost
        shown += 1

    if shown == 0:
        return f"No results found for '{query}'. ChromaDB may still be indexing."

    lines.append(f"\n---\n*{shown} results shown | budget used: {max_tokens - budget}/{max_tokens} tokens*")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════
# TOOL 2 — get_symbol
# ══════════════════════════════════════════════════════════════════════════
@mcp.tool()
def get_symbol(
    name: str,
    repo: Optional[str] = None,
    detail: str = "full",
) -> str:
    """
    Get a specific symbol (function, class, struct) by exact or partial name.

    Returns the full definition with file path, line numbers, LLM summary,
    hardware bindings, TRM cross-references, and similar functions in other repos.
    This is the tool to call before modifying any function.

    Args:
        name:   Symbol name. Exact match tried first, then partial.
                Examples: "SetMotorVelocity", "set_eye_color", "BehaviorManager"
        repo:   Optional repo filter: "vector", "chipper", "wire-pod",
                "vector-python-sdk", "vector-go-sdk", "vectorx", etc.
        detail: "full" = complete code body (default).
                "summary" = signature + description only (faster).
    """
    col = _get_col("repo_code")
    if col is None or col.count() == 0:
        return "ChromaDB repo_code collection is empty — db_writer may still be running."

    # Try exact name match via metadata filter
    where: dict = {"symbol_name": {"$eq": name}}
    if repo:
        where = {"$and": [{"symbol_name": {"$eq": name}}, {"repo": {"$eq": repo}}]}

    try:
        r = col.get(where=where, include=["documents", "metadatas"], limit=5)
        docs, metas = r.get("documents", []), r.get("metadatas", [])
    except Exception:
        docs, metas = [], []

    # Fallback: semantic search if exact match fails
    if not docs:
        query_emb = _embed(name)
        if query_emb:
            qr = col.query(
                query_embeddings=[query_emb],
                n_results=3,
                include=["documents", "metadatas", "distances"],
                where={"repo": {"$eq": repo}} if repo else None,
            )
            docs  = qr["documents"][0]
            metas = qr["metadatas"][0]

    if not docs:
        return f"Symbol `{name}` not found. Try vector_search('{name}', types='code')."

    lines = [f"## Symbol: `{name}`\n"]

    for doc, meta in zip(docs, metas):
        sym_name  = meta.get("symbol_name", name)
        sym_type  = meta.get("symbol_type", "")
        repo_name = meta.get("repo", "")
        file_path = meta.get("file", "")
        line_s    = meta.get("line_start", "")
        line_e    = meta.get("line_end", "")
        lang      = meta.get("language", "")
        summary   = meta.get("llm_summary", "")
        hw_binds  = meta.get("hardware_binds", "")
        similar   = meta.get("similar_to", "")
        trm_id    = meta.get("trm_snippet_id", "")

        lines.append(f"### {sym_type} `{sym_name}` in **{repo_name}**")
        lines.append(f"**File:** `{file_path}` lines {line_s}–{line_e}")
        if summary:
            lines.append(f"**Summary:** {summary}")
        if hw_binds:
            lines.append(f"**Hardware bindings:** {hw_binds}")
            lines.append(f"  → Call `get_hardware_context('{hw_binds.split('|')[0]}')` for TRM notes on this hardware.")
        if trm_id:
            lines.append(f"**TRM cross-reference:** {trm_id}")
        if similar:
            sim_list = similar.split("|")[:3]
            lines.append(f"**Similar in other repos:** {', '.join(sim_list)}")
            lines.append(f"  → These may be clone/fork pairs (e.g. chipper↔wire-pod).")

        if detail == "full":
            lines.append(f"\n```{lang}\n{doc}\n```")
        else:
            preview = doc[:200] + "…" if len(doc) > 200 else doc
            lines.append(f"\n```{lang}\n{preview}\n```")
        lines.append("")

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════
# TOOL 3 — get_hardware_context
# ══════════════════════════════════════════════════════════════════════════
@mcp.tool()
def get_hardware_context(component: str) -> str:
    """
    Get everything about a Vector hardware component in one call.

    Returns TRM developer notes (WARNING/NOTE/CAUTION), hardware tables
    (pin assignments, voltages, registers), and code symbols that interact
    with this component. This is your first call when touching any hardware.

    Common components: "STM32", "motor", "encoder", "IPS_display", "body_board",
    "head_board", "IMU", "cliff_sensor", "touch_sensor", "speaker", "microphone",
    "bluetooth", "WiFi", "camera", "battery"

    Args:
        component: Hardware component name or partial name.
    """
    query_emb = _embed(f"{component} hardware Vector robot")
    if not query_emb:
        return "ERROR: Embedding failed."

    lines = [f"## Hardware Context: `{component}`\n"]

    # 1. TRM developer notes (most valuable — engineering warnings)
    notes_col = _get_col("trm_notes")
    if notes_col and notes_col.count() > 0:
        try:
            r = notes_col.query(
                query_embeddings=[query_emb],
                n_results=min(5, notes_col.count()),
                include=["documents", "metadatas", "distances"],
            )
            hits = [(d, m, dist) for d, m, dist in
                    zip(r["documents"][0], r["metadatas"][0], r["distances"][0])
                    if (1.0 - dist) > 0.35]  # relevance threshold
            if hits:
                lines.append("### ⚠ TRM Developer Notes (engineering warnings & decisions)\n")
                for doc, meta, dist in hits:
                    lines.append(
                        f"**{meta.get('note_type','NOTE')} {meta.get('note_id','')}** "
                        f"(p.{meta.get('trm_page','')} — {(1-dist):.0%} relevant)\n"
                        f"{doc[:400]}\n"
                    )
        except Exception as e:
            lines.append(f"[trm_notes error: {e}]")

    # 2. TRM tables (pin assignments, register maps, voltages)
    tables_col = _get_col("trm_tables")
    if tables_col and tables_col.count() > 0:
        try:
            r = tables_col.query(
                query_embeddings=[query_emb],
                n_results=min(3, tables_col.count()),
                include=["documents", "metadatas", "distances"],
            )
            hits = [(d, m, dist) for d, m, dist in
                    zip(r["documents"][0], r["metadatas"][0], r["distances"][0])
                    if (1.0 - dist) > 0.30]
            if hits:
                lines.append("### 📋 TRM Hardware Tables\n")
                for doc, meta, dist in hits:
                    lines.append(
                        f"**{meta.get('caption', 'Table')}** "
                        f"(p.{meta.get('trm_page','')})\n"
                        f"{doc[:300]}\n"
                    )
        except Exception as e:
            lines.append(f"[trm_tables error: {e}]")

    # 3. TRM code snippets (register definitions, protocol structs)
    code_col = _get_col("trm_code")
    if code_col and code_col.count() > 0:
        try:
            r = code_col.query(
                query_embeddings=[query_emb],
                n_results=min(3, code_col.count()),
                include=["documents", "metadatas", "distances"],
            )
            hits = [(d, m, dist) for d, m, dist in
                    zip(r["documents"][0], r["metadatas"][0], r["distances"][0])
                    if (1.0 - dist) > 0.35]
            if hits:
                lines.append("### 💾 TRM Code / Register Definitions\n")
                for doc, meta, dist in hits:
                    lines.append(f"```\n{doc[:250]}\n```\n")
        except Exception as e:
            lines.append(f"[trm_code error: {e}]")

    # 4. Repo code that touches this hardware
    repo_col = _get_col("repo_code")
    if repo_col and repo_col.count() > 0:
        try:
            r = repo_col.query(
                query_embeddings=[query_emb],
                n_results=5,
                include=["documents", "metadatas", "distances"],
            )
            hits = [(d, m, dist) for d, m, dist in
                    zip(r["documents"][0], r["metadatas"][0], r["distances"][0])
                    if (1.0 - dist) > 0.40]
            if hits:
                lines.append("### 🔧 Code Symbols Touching This Hardware\n")
                for doc, meta, dist in hits:
                    lines.append(
                        f"- `{meta.get('symbol_type','')} {meta.get('symbol_name','')}` "
                        f"in **{meta.get('repo','')}** "
                        f"`{meta.get('file','')}:{meta.get('line_start','')}`  "
                        f"({(1-dist):.0%} relevant)"
                    )
                lines.append("")
        except Exception as e:
            lines.append(f"[repo_code error: {e}]")

    if len(lines) == 1:
        return (
            f"No hardware context found for '{component}'. "
            f"Try vector_search('{component}', types='trm_note,table')."
        )

    lines.append(
        "\n---\n*Tip: Use `get_symbol(name)` on any function above for full source. "
        "TRM notes contain engineering decisions not in the code.*"
    )
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════
# TOOL 4 — get_task_briefing
# ══════════════════════════════════════════════════════════════════════════
@mcp.tool()
def get_task_briefing(task: str) -> str:
    """
    Get a focused briefing to orient yourself before starting a task.
    Searches all collections, identifies relevant hardware, surfaces TRM
    warnings, finds key symbols, and uses the local LLM to synthesize
    a compact summary — saving Anthropic tokens.

    Call this at the start of any non-trivial task on Vector code.

    Args:
        task: Plain-English task description.
              Examples:
                "add a new behavior command that makes Vector spin in place"
                "fix motor encoder overflow at high RPM in firmware"
                "understand how chipper handles voice commands end-to-end"
                "add OAuth2 to vector-cloud authentication flow"
    """
    # Search broadly
    query_emb = _embed(task)
    if not query_emb:
        return "ERROR: Embedding failed."

    collected = {"trm_notes": [], "repo_code": [], "trm_tables": []}

    for col_name, n in [("trm_notes", 4), ("repo_code", 6), ("trm_tables", 2)]:
        col = _get_col(col_name)
        if col is None or col.count() == 0:
            continue
        try:
            r = col.query(
                query_embeddings=[query_emb],
                n_results=min(n, col.count()),
                include=["documents", "metadatas", "distances"],
            )
            for doc, meta, dist in zip(
                r["documents"][0], r["metadatas"][0], r["distances"][0]
            ):
                if (1.0 - dist) > 0.25:
                    collected[col_name].append({"doc": doc, "meta": meta, "dist": dist})
        except Exception:
            pass

    # Build context string for local LLM synthesis
    ctx_parts = []

    if collected["trm_notes"]:
        ctx_parts.append("TRM DEVELOPER NOTES (engineering warnings):")
        for item in collected["trm_notes"][:3]:
            m = item["meta"]
            ctx_parts.append(
                f"  [{m.get('note_type','')} {m.get('note_id','')}] {item['doc'][:200]}"
            )

    if collected["repo_code"]:
        ctx_parts.append("\nRELEVANT CODE SYMBOLS:")
        for item in collected["repo_code"][:5]:
            m = item["meta"]
            ctx_parts.append(
                f"  {m.get('symbol_type','')} `{m.get('symbol_name','')}` "
                f"in {m.get('repo','')} ({m.get('file','')}) "
                f"— {m.get('llm_summary','')}"
            )

    context = "\n".join(ctx_parts)

    # Ask local LLM to synthesize — don't burn Anthropic tokens for this
    synthesis = local_llm.ask(
        question=(
            f"Given this task: '{task}'\n\n"
            f"Based on the context below from the Vector robot codebase, write a "
            f"focused 5-bullet briefing covering: "
            f"(1) which repos/files are most relevant, "
            f"(2) critical hardware or TRM warnings to be aware of, "
            f"(3) key functions to look at first, "
            f"(4) likely clone/fork relationships to check, "
            f"(5) suggested first steps. Be concise, max 300 words."
        ),
        context=context,
        max_tokens=400,
    )

    # Format final output
    lines = [f"## Task Briefing: '{task}'\n"]

    if collected["trm_notes"]:
        lines.append("### ⚠ Critical TRM Notes")
        for item in collected["trm_notes"][:2]:
            m = item["meta"]
            lines.append(
                f"- **{m.get('note_type','')} {m.get('note_id','')}** "
                f"(p.{m.get('trm_page','')}): {item['doc'][:150]}"
            )
        lines.append("")

    lines.append("### 🧭 Orientation (via local LLM)\n")
    lines.append(synthesis)
    lines.append("")

    lines.append("### 🔧 Key Symbols to Start With")
    for item in collected["repo_code"][:4]:
        m = item["meta"]
        lines.append(
            f"- `{m.get('symbol_name','')}` in **{m.get('repo','')}** "
            f"`{m.get('file','')}:{m.get('line_start','')}`"
        )

    lines.append(
        "\n---\n"
        "*Next: use `get_symbol(name)` for full source, "
        "`get_hardware_context(component)` for hardware details, "
        "`save_session_context(task=...)` to persist this briefing.*"
    )
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════
# TOOL 5 — get_grpc_map
# ══════════════════════════════════════════════════════════════════════════
@mcp.tool()
def get_grpc_map(service: Optional[str] = None) -> str:
    """
    Get the full gRPC picture for a service: proto definition, server
    implementation (chipper + wire-pod), and client usage (SDK).

    Vector uses gRPC extensively. Modifying any endpoint requires understanding
    all three layers simultaneously — this assembles them for you.

    Args:
        service: Service or method name, e.g. "BehaviorControl", "SayText",
                 "NavMapFeed", "AudioFeed". None returns the top-level service map.
    """
    query = f"gRPC {service or 'service'} proto definition Vector robot"
    query_emb = _embed(query)
    if not query_emb:
        return "ERROR: Embedding failed."

    lines = [f"## gRPC Map: `{service or 'all services'}`\n"]
    found_any = False

    # Search each relevant repo layer
    repo_col = _get_col("repo_code")
    if repo_col is None or repo_col.count() == 0:
        return "repo_code collection empty — db_writer may still be indexing."

    layers = [
        ("proto definition",         ["vector", "chipper", "wire-pod"], "proto"),
        ("server implementation",    ["chipper", "wire-pod"],           "go"),
        ("client / SDK",             ["vector-python-sdk", "vector-go-sdk"], None),
    ]

    for layer_name, repos, lang_hint in layers:
        layer_hits = []
        for repo_name in repos:
            try:
                r = repo_col.query(
                    query_embeddings=[query_emb],
                    n_results=3,
                    include=["documents", "metadatas", "distances"],
                    where={"repo": {"$eq": repo_name}},
                )
                for doc, meta, dist in zip(
                    r["documents"][0], r["metadatas"][0], r["distances"][0]
                ):
                    if (1.0 - dist) > 0.30:
                        layer_hits.append((doc, meta, dist, repo_name))
            except Exception:
                pass

        if layer_hits:
            found_any = True
            layer_hits.sort(key=lambda x: x[2])
            lines.append(f"### {layer_name.title()}")
            for doc, meta, dist, repo_name in layer_hits[:2]:
                lines.append(
                    f"**{repo_name}** — `{meta.get('symbol_name','')}` "
                    f"`{meta.get('file','')}:{meta.get('line_start','')}`  "
                    f"({(1-dist):.0%} relevant)"
                )
                lang = meta.get("language", lang_hint or "")
                preview = doc[:300] + "…" if len(doc) > 300 else doc
                lines.append(f"```{lang}\n{preview}\n```\n")

    if not found_any:
        lines.append(
            f"No gRPC results for '{service}'. "
            f"Try `vector_search('{service}', types='code')` for broader results."
        )

    lines.append(
        "\n---\n"
        "*Tip: chipper and wire-pod often have clone implementations of the same service. "
        "Check both when modifying behavior. Use `get_symbol(name)` for full bodies.*"
    )
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════
# TOOL 6 — ask_local_coder
# ══════════════════════════════════════════════════════════════════════════
@mcp.tool()
def ask_local_coder(
    question: str,
    context: str = "",
    model: str = "qwen2.5-coder:7b",
    max_tokens: int = 512,
) -> str:
    """
    Ask qwen2.5-coder (local, free, instant) instead of using Anthropic tokens.

    Use for:
    - "What does this function do?" (paste code as context)
    - "Generate a stub for a new gRPC handler"
    - "Is this proto change backward-compatible?"
    - "Summarize these chunks"
    - Any rote code question that doesn't need architecture reasoning

    Args:
        question:   Your question in plain English.
        context:    Code or text to give the model (up to 3000 chars).
        model:      Ollama model to use. Default: qwen2.5-coder:7b.
                    Other options: "qwen2.5:14b", "phi4:latest"
        max_tokens: Max response length. Default 512.
    """
    models = local_llm.available_models()
    if not models:
        return (
            "Ollama is not running or has no models loaded. "
            "Start Ollama and ensure qwen2.5-coder:7b is pulled."
        )
    if model not in models:
        # Try to find a close match
        available = ", ".join(models)
        alt = next((m for m in models if "coder" in m or "qwen" in m), models[0])
        question_with_note = f"[Note: {model} not available, using {alt}]\n{question}"
        return local_llm.ask(question_with_note, context, model=alt, max_tokens=max_tokens)

    result = local_llm.ask(question, context, model=model, max_tokens=max_tokens)
    return f"**qwen2.5-coder response:**\n\n{result}"


# ══════════════════════════════════════════════════════════════════════════
# TOOL 7 — save_session_context
# ══════════════════════════════════════════════════════════════════════════
@mcp.tool()
def save_session_context(
    task: Optional[str] = None,
    repo: Optional[str] = None,
    decided: Optional[list] = None,
    files_touched: Optional[list] = None,
    symbols_examined: Optional[list] = None,
    hardware_context: Optional[list] = None,
    waiting_on: Optional[str] = None,
    notes: Optional[list] = None,
) -> str:
    """
    Save working context to persistent storage. Survives context compression.

    Call this:
    - After making any architectural decision
    - After identifying the key files/symbols for a task
    - When switching focus to a different area
    - Before any long operation (so you can resume if compressed)

    All list parameters APPEND to existing values (deduped). To start fresh
    for a new task, call with only task= set — it resets the focus.

    Args:
        task:              Current task in one sentence.
        repo:              Primary repo being worked on.
        decided:           List of decisions made (e.g. ["use int32_t for encoder counter"]).
        files_touched:     Files read or modified (e.g. ["motorController.cpp"]).
        symbols_examined:  Functions/classes looked at.
        hardware_context:  Hardware components involved (e.g. ["STM32", "motor_encoder"]).
        waiting_on:        Blocking item (e.g. "db_writer to finish before running tests").
        notes:             Any other important notes.
    """
    state = session_store.save(
        task=task,
        repo=repo,
        decided=decided,
        files_touched=files_touched,
        symbols_examined=symbols_examined,
        hardware_context=hardware_context,
        waiting_on=waiting_on,
        notes=notes,
    )
    return (
        f"✅ Session context saved.\n"
        f"**Task:** {state.get('task','(none)')}\n"
        f"**Repo:** {state.get('repo','(none)')}\n"
        f"**Decisions recorded:** {len(state.get('decided',[]))}\n"
        f"**Files touched:** {len(state.get('files_touched',[]))}\n"
        f"**Last updated:** {state.get('last_updated','')}\n\n"
        f"After context compression, call `load_session_context()` to restore."
    )


# ══════════════════════════════════════════════════════════════════════════
# TOOL 8 — load_session_context
# ══════════════════════════════════════════════════════════════════════════
@mcp.tool()
def load_session_context() -> str:
    """
    Restore working context after Claude context compression.

    Call this at the start of any session or after noticing context was
    compressed. Returns a compact summary (~200 tokens) that fully orients
    you without re-reading session logs.
    """
    state = session_store.load()

    if not state.get("task") and not state.get("decided"):
        return (
            "No saved session context found.\n"
            "Start a task with `get_task_briefing(task)` and then "
            "`save_session_context(task=...)` to begin tracking."
        )

    lines = ["## Restored Session Context\n"]
    lines.append(f"**Task:** {state.get('task','(none)')}")
    lines.append(f"**Primary repo:** {state.get('repo','(none)')}")
    lines.append(f"**Last updated:** {state.get('last_updated','unknown')}")

    if state.get("waiting_on"):
        lines.append(f"\n⏳ **Waiting on:** {state['waiting_on']}")

    if state.get("hardware_context"):
        lines.append(f"\n**Hardware involved:** {', '.join(state['hardware_context'])}")
        lines.append(
            f"  → Run `get_hardware_context('{state['hardware_context'][0]}')` "
            f"to restore TRM notes."
        )

    if state.get("decided"):
        lines.append("\n**Decisions already made:**")
        for d in state["decided"]:
            lines.append(f"  - {d}")

    if state.get("files_touched"):
        lines.append(f"\n**Files in scope:** {', '.join(state['files_touched'][:8])}")

    if state.get("symbols_examined"):
        lines.append(f"**Symbols examined:** {', '.join(state['symbols_examined'][:8])}")

    if state.get("notes"):
        lines.append("\n**Notes:**")
        for n in state["notes"]:
            lines.append(f"  - {n}")

    lines.append(
        "\n---\n"
        "*Context restored. Continue from where you left off. "
        "Use `get_task_briefing` if you need to re-orient on the task details.*"
    )
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    mcp.run()
