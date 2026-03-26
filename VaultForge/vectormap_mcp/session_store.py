"""
Session store — working context that survives Claude context compression.

Claude calls save() after every significant decision or file change.
After compression, Claude calls load() → ~200 tokens to fully reconstruct
where we were, instead of re-reading megabytes of session logs.
"""
import json
import datetime
from pathlib import Path

# Lives in the Claude projects memory dir so it survives across sessions
STORE_PATH = Path.home() / ".claude" / "projects" / "-Users-lab-research" / "vector_session.json"


def load() -> dict:
    """Load current working context. Returns empty template if none exists."""
    if STORE_PATH.exists():
        try:
            return json.loads(STORE_PATH.read_text())
        except Exception:
            pass
    return {
        "task": None,
        "repo": None,
        "decided": [],
        "files_touched": [],
        "symbols_examined": [],
        "hardware_context": [],
        "waiting_on": None,
        "notes": [],
        "last_updated": None,
    }


def save(
    task: str | None = None,
    repo: str | None = None,
    decided: list[str] | None = None,
    files_touched: list[str] | None = None,
    symbols_examined: list[str] | None = None,
    hardware_context: list[str] | None = None,
    waiting_on: str | None = None,
    notes: list[str] | None = None,
) -> dict:
    """
    Save working context. Merges with existing — only overwrites fields
    you explicitly provide. Lists are APPENDED (deduped), not replaced.
    """
    current = load()

    if task is not None:
        current["task"] = task
    if repo is not None:
        current["repo"] = repo
    if waiting_on is not None:
        current["waiting_on"] = waiting_on

    # Append+dedup lists
    for field, new_items in [
        ("decided", decided),
        ("files_touched", files_touched),
        ("symbols_examined", symbols_examined),
        ("hardware_context", hardware_context),
        ("notes", notes),
    ]:
        if new_items:
            existing = set(current.get(field) or [])
            current[field] = list(existing | set(new_items))

    current["last_updated"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STORE_PATH.write_text(json.dumps(current, indent=2))
    return current


def clear() -> None:
    """Clear session context (new task / new project)."""
    if STORE_PATH.exists():
        STORE_PATH.unlink()
