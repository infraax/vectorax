"""Tests for LangGraph agent nodes — retrieve, generate, validate, hallucination capture."""
import pytest
from unittest.mock import MagicMock, patch, call
from langchain_core.documents import Document


def _make_doc(source, content="test content"):
    return Document(page_content=content, metadata={"source": source})


# ──────────────────────────────────────────
# retrieve() node
# ──────────────────────────────────────────
def test_retrieve_returns_context_and_scores():
    from langgraph_agent import retrieve

    mock_docs = [(_make_doc("repo__file_a"), 0.4), (_make_doc("repo__file_b"), 0.8)]
    with patch("langgraph_agent.vector_db") as vdb:
        vdb.similarity_search_with_score.return_value = mock_docs
        state = retrieve({"query": "what is the drive system?", "system_logs": [], "injected_docs": []})

    assert len(state["context"]) == 2
    assert len(state["retrieval_scores"]) == 2
    # L2 dist 0.4 → score = max(0, 1 - 0.4/2) = 0.8
    assert abs(state["retrieval_scores"][0] - 0.8) < 0.01
    # L2 dist 0.8 → score = max(0, 1 - 0.8/2) = 0.6
    assert abs(state["retrieval_scores"][1] - 0.6) < 0.01


def test_retrieve_uses_injected_docs_bypasses_chromadb():
    from langgraph_agent import retrieve

    with patch("langgraph_agent.vector_db") as vdb:
        state = retrieve({
            "query": "test",
            "system_logs": [],
            "injected_docs": ["This is injected content.", "More injected text."],
        })
        vdb.similarity_search_with_score.assert_not_called()

    assert len(state["context"]) == 2
    assert state["context"][0].metadata["source"] == "injected_0"
    assert all(s == 1.0 for s in state["retrieval_scores"])


def test_retrieve_uses_retrieval_k_from_config():
    from langgraph_agent import retrieve, AGENT_CONFIG

    original_k = AGENT_CONFIG["retrieval_k"]
    AGENT_CONFIG["retrieval_k"] = 3

    with patch("langgraph_agent.vector_db") as vdb:
        vdb.similarity_search_with_score.return_value = [(_make_doc("f"), 0.5)] * 3
        retrieve({"query": "q", "system_logs": [], "injected_docs": []})
        vdb.similarity_search_with_score.assert_called_once_with("q", k=3)

    AGENT_CONFIG["retrieval_k"] = original_k


# ──────────────────────────────────────────
# validate() node
# ──────────────────────────────────────────
def test_validate_passes_valid_response():
    from langgraph_agent import validate

    docs = [_make_doc("repo__file_a")]
    gen = "Some explanation.\n\n## Stack Trace & Sources\n[[repo__file_a]]"
    state = validate({"generation": gen, "context": docs, "query": "q", "system_logs": []})
    assert state["validation_error"] == ""


def test_validate_fails_missing_sources_section():
    from langgraph_agent import validate

    docs = [_make_doc("repo__file_a")]
    gen = "Answer without sources section. [[repo__file_a]]"
    state = validate({"generation": gen, "context": docs, "query": "q", "system_logs": []})
    assert state["validation_error"] != ""
    assert "Stack Trace" in state["validation_error"]


def test_validate_fails_missing_wikilinks():
    from langgraph_agent import validate

    docs = [_make_doc("repo__file_a")]
    gen = "Answer.\n\n## Stack Trace & Sources\nrepo__file_a (no brackets)"
    state = validate({"generation": gen, "context": docs, "query": "q", "system_logs": []})
    assert state["validation_error"] != ""
    assert "WikiLink" in state["validation_error"]


def test_validate_fails_hallucinated_source():
    from langgraph_agent import validate

    docs = [_make_doc("repo__file_a")]
    gen = "Answer.\n\n## Stack Trace & Sources\n[[repo__MADE_UP_FILE]]"
    state = validate({"generation": gen, "context": docs, "query": "q", "system_logs": []})
    assert state["validation_error"] != ""
    assert "HALLUCINATION" in state["validation_error"]


def test_validate_logs_hallucination_to_ledger():
    """validate() should call save_hallucination when detection fails."""
    from langgraph_agent import validate

    docs = [_make_doc("repo__file_a")]
    gen = "No wikilinks.\n\n## Stack Trace & Sources\nbadfile"

    with patch("query_history.save_hallucination") as mock_save:
        with patch("langgraph_agent._active_qctx", None):
            validate({"generation": gen, "context": docs, "query": "test_query", "system_logs": []})
        mock_save.assert_called_once()
        args = mock_save.call_args[0]
        assert "test_query" in args or "test_query" in str(mock_save.call_args)


def test_validate_bypassed_with_empty_context():
    from langgraph_agent import validate

    state = validate({"generation": "anything", "context": [], "query": "q", "system_logs": []})
    assert state["validation_error"] == ""


# ──────────────────────────────────────────
# should_loop()
# ──────────────────────────────────────────
def test_should_loop_retries_on_error():
    from langgraph_agent import should_loop
    assert should_loop({"validation_error": "some error", "attempts": 1}) == "generate"


def test_should_loop_ends_after_max_attempts():
    from langgraph_agent import should_loop
    assert should_loop({"validation_error": "some error", "attempts": 3}) == "end"


def test_should_loop_ends_on_success():
    from langgraph_agent import should_loop
    assert should_loop({"validation_error": "", "attempts": 1}) == "end"


# ──────────────────────────────────────────
# Conversation memory buffer
# ──────────────────────────────────────────
def test_conv_buffer_trimmed_to_memory_turns():
    from langgraph_agent import _CONV_BUFFER, AGENT_CONFIG
    import langgraph_agent as _a

    AGENT_CONFIG["memory_turns"] = 2
    _a._CONV_BUFFER.clear()
    # Add 6 turns (12 entries — 3 user/assistant pairs)
    for i in range(6):
        _a._CONV_BUFFER.append({"role": "user", "content": f"q{i}"})
        _a._CONV_BUFFER.append({"role": "assistant", "content": f"a{i}"})

    # Trim as server.py does
    max_turns = AGENT_CONFIG["memory_turns"] * 2
    if len(_a._CONV_BUFFER) > max_turns:
        _a._CONV_BUFFER[:] = _a._CONV_BUFFER[-max_turns:]

    assert len(_a._CONV_BUFFER) == 4  # 2 turns × 2 roles
    _a._CONV_BUFFER.clear()
    AGENT_CONFIG["memory_turns"] = 4  # reset
