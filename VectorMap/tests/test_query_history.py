"""Tests for SQLite query history — save, retrieve, scores, templates, hallucinations."""
import json
import pytest


def test_init_db_creates_tables(db):
    import sqlite3
    with sqlite3.connect(db.HISTORY_DB) as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "queries" in tables
    assert "templates" in tables
    assert "hallucination_ledger" in tables


def test_save_and_get_query(db):
    db_id = db.save_query(
        session_id="sess_test",
        query_id=1,
        query="what is the motor controller?",
        response="It controls motors.\n\n## Stack Trace & Sources\n[[file_a]]",
        sources=[{"filename": "file_a", "snippet": "..."}],
        phases={"retrieve": 100, "generate": 500},
        token_usage={"system": 200, "context": 1000},
        total_ms=600,
        rss_delta_mb=0,
    )
    assert db_id is not None

    history = db.get_history(n=10)
    assert len(history) == 1
    assert history[0]["query"] == "what is the motor controller?"


def test_get_history_session_filter(db):
    db.save_query("sess_a", 1, "q1", "r1", [], {}, {}, 100, 0)
    db.save_query("sess_b", 1, "q2", "r2", [], {}, {}, 100, 0)
    only_a = db.get_history(n=10, session_id="sess_a")
    assert len(only_a) == 1
    assert only_a[0]["query"] == "q1"


def test_get_query_detail_includes_response(db):
    db_id = db.save_query("sess_x", 1, "query?", "full response here", [], {}, {}, 200, 0)
    detail = db.get_query_detail(db_id)
    assert detail is not None
    assert detail["response"] == "full response here"


def test_update_retrieval_scores(db):
    db_id = db.save_query("sess_s", 1, "q", "r", [], {}, {}, 0, 0)
    scores = [{"filename": "file_a", "score": 0.85}]
    db.update_retrieval_scores(db_id, scores)
    detail = db.get_query_detail(db_id)
    assert detail["retrieval_scores"] == scores


def test_get_query_detail_not_found(db):
    result = db.get_query_detail(99999)
    assert result is None


def test_save_and_get_template(db):
    tid = db.save_template("Motor Query", "Explain the {component} motor controller")
    assert tid is not None
    templates = db.get_templates()
    assert len(templates) == 1
    assert templates[0]["name"] == "Motor Query"


def test_delete_template(db):
    tid = db.save_template("To Delete", "content")
    assert db.delete_template(tid) is True
    assert db.get_templates() == []


def test_delete_template_nonexistent(db):
    assert db.delete_template(99999) is False


def test_save_and_get_hallucination(db):
    db.save_hallucination(
        session_id="sess_h",
        query="what calls process_image?",
        raw_generation="Some text without wikilinks.",
        violation="missing_wikilinks",
    )
    entries = db.get_hallucinations(n=10)
    assert len(entries) == 1
    assert entries[0]["violation"] == "missing_wikilinks"
    assert entries[0]["query"] == "what calls process_image?"


def test_get_hallucination_detail(db):
    db.save_hallucination("s", "q", "raw text", "hallucinated_source", corrected="fixed")
    entries = db.get_hallucinations()
    detail = db.get_hallucination_detail(entries[0]["id"])
    assert detail["corrected"] == "fixed"
    assert detail["raw_generation"] == "raw text"


def test_phases_json_parsed_on_retrieve(db):
    db.save_query("sess_p", 1, "q", "r", [], {"retrieve": 150, "generate": 800}, {}, 950, 0)
    history = db.get_history()
    assert isinstance(history[0]["phases"], dict)
    assert history[0]["phases"]["retrieve"] == 150
