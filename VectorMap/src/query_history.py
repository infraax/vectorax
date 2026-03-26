"""
Query History — SQLite-backed persistence for cross-session retrieval.
Stores full query/response records with timing, source attribution,
retrieval scores, query templates, and hallucination ledger.
"""
import os
import sqlite3
import json
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_DB = os.path.join(BASE_DIR, "..", "data", "query_history.db")

def init_db():
    os.makedirs(os.path.dirname(HISTORY_DB), exist_ok=True)
    with sqlite3.connect(HISTORY_DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS queries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                query_id INTEGER,
                timestamp TEXT,
                query TEXT,
                response TEXT,
                sources TEXT,
                phases TEXT,
                token_usage TEXT,
                total_ms REAL,
                rss_delta_mb REAL,
                retrieval_scores TEXT
            )
        """)
        # Add retrieval_scores column to existing DBs that predate this schema
        try:
            conn.execute("ALTER TABLE queries ADD COLUMN retrieval_scores TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists

        conn.execute("""
            CREATE TABLE IF NOT EXISTS templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                template TEXT NOT NULL,
                created_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS hallucination_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                timestamp TEXT,
                query TEXT,
                raw_generation TEXT,
                violation TEXT,
                corrected TEXT
            )
        """)
        conn.commit()

# ==========================================
# Query CRUD
# ==========================================

def save_query(session_id, query_id, query, response, sources, phases, token_usage, total_ms, rss_delta_mb):
    try:
        with sqlite3.connect(HISTORY_DB) as conn:
            cur = conn.execute("""
                INSERT INTO queries
                    (session_id, query_id, timestamp, query, response, sources, phases, token_usage, total_ms, rss_delta_mb)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id, query_id, datetime.now().isoformat(),
                query, response,
                json.dumps(sources), json.dumps(phases),
                json.dumps(token_usage), total_ms, rss_delta_mb,
            ))
            conn.commit()
            return cur.lastrowid
    except Exception as e:
        print(f"[query_history] save error: {e}")
        return None

def update_retrieval_scores(db_id, scores):
    """Patch retrieval scores onto an existing query row after it's been saved."""
    try:
        with sqlite3.connect(HISTORY_DB) as conn:
            conn.execute(
                "UPDATE queries SET retrieval_scores=? WHERE id=?",
                (json.dumps(scores), db_id)
            )
            conn.commit()
    except Exception as e:
        print(f"[query_history] score update error: {e}")

def get_history(n=50, session_id=None):
    try:
        with sqlite3.connect(HISTORY_DB) as conn:
            conn.row_factory = sqlite3.Row
            if session_id:
                rows = conn.execute(
                    "SELECT id,session_id,query_id,timestamp,query,phases,token_usage,total_ms,rss_delta_mb FROM queries WHERE session_id=? ORDER BY id DESC LIMIT ?",
                    (session_id, n)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id,session_id,query_id,timestamp,query,phases,token_usage,total_ms,rss_delta_mb FROM queries ORDER BY id DESC LIMIT ?",
                    (n,)
                ).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                for f in ('phases', 'token_usage'):
                    if d.get(f):
                        try: d[f] = json.loads(d[f])
                        except: pass
                result.append(d)
            return result
    except Exception as e:
        print(f"[query_history] get_history error: {e}")
        return []

def get_query_detail(db_id):
    try:
        with sqlite3.connect(HISTORY_DB) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM queries WHERE id=?", (db_id,)).fetchone()
            if row:
                d = dict(row)
                for f in ('sources', 'phases', 'token_usage', 'retrieval_scores'):
                    if d.get(f):
                        try: d[f] = json.loads(d[f])
                        except: pass
                return d
    except Exception as e:
        print(f"[query_history] get_query_detail error: {e}")
    return None

# ==========================================
# Query Templates
# ==========================================

def save_template(name, template):
    try:
        with sqlite3.connect(HISTORY_DB) as conn:
            cur = conn.execute(
                "INSERT INTO templates (name, template, created_at) VALUES (?, ?, ?)",
                (name, template, datetime.now().isoformat())
            )
            conn.commit()
            return cur.lastrowid
    except Exception as e:
        print(f"[query_history] save_template error: {e}")
        return None

def get_templates():
    try:
        with sqlite3.connect(HISTORY_DB) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM templates ORDER BY id DESC").fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        print(f"[query_history] get_templates error: {e}")
        return []

def delete_template(template_id):
    try:
        with sqlite3.connect(HISTORY_DB) as conn:
            affected = conn.execute(
                "DELETE FROM templates WHERE id=?", (template_id,)
            ).rowcount
            conn.commit()
            return affected > 0
    except Exception as e:
        print(f"[query_history] delete_template error: {e}")
        return False

# ==========================================
# Hallucination Ledger
# ==========================================

def save_hallucination(session_id, query, raw_generation, violation, corrected=""):
    try:
        with sqlite3.connect(HISTORY_DB) as conn:
            conn.execute("""
                INSERT INTO hallucination_ledger
                    (session_id, timestamp, query, raw_generation, violation, corrected)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                session_id, datetime.now().isoformat(),
                query, raw_generation, violation, corrected
            ))
            conn.commit()
    except Exception as e:
        print(f"[query_history] save_hallucination error: {e}")

def get_hallucinations(n=100):
    try:
        with sqlite3.connect(HISTORY_DB) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT id,session_id,timestamp,query,violation FROM hallucination_ledger ORDER BY id DESC LIMIT ?",
                (n,)
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        print(f"[query_history] get_hallucinations error: {e}")
        return []

def get_hallucination_detail(ledger_id):
    try:
        with sqlite3.connect(HISTORY_DB) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM hallucination_ledger WHERE id=?", (ledger_id,)
            ).fetchone()
            return dict(row) if row else None
    except Exception as e:
        print(f"[query_history] get_hallucination_detail error: {e}")
        return None
