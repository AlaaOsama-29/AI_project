import threading
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = "interview.db"
answers_lock = threading.Lock()

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id   TEXT PRIMARY KEY,
                student_name TEXT,
                status       TEXT,
                question     TEXT,
                level        TEXT,
                question_num INTEGER,
                topic        TEXT,
                timestamp    TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS answers (
                session_id TEXT PRIMARY KEY,
                answer     TEXT,
                created_at TEXT
            )
        """)

init_db()

# ─── Sessions ─────────────────────────────────────────────
class SessionsStore:
    def get(self, session_id):
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
            return dict(row) if row else None

    def __setitem__(self, session_id, state):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO sessions
                (session_id, student_name, status, question, level, question_num, topic, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                state.get("student_name", ""),
                state.get("status", ""),
                state.get("question", ""),
                state.get("level", ""),
                state.get("question_num", 0),
                state.get("topic", ""),
                state.get("timestamp", datetime.now().isoformat()),
            ))

    def values(self):
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM sessions").fetchall()
            return [dict(r) for r in rows]

# ─── Answers ──────────────────────────────────────────────
class AnswersStore:
    def pop(self, session_id, default=None):
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute(
                "SELECT answer FROM answers WHERE session_id = ?", (session_id,)
            ).fetchone()
            if row:
                conn.execute(
                    "DELETE FROM answers WHERE session_id = ?", (session_id,)
                )
                return row[0]
            return default

    def __setitem__(self, session_id, answer):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO answers (session_id, answer, created_at)
                VALUES (?, ?, ?)
            """, (session_id, answer, datetime.now().isoformat()))

sessions_store = SessionsStore()
answers_store  = AnswersStore()