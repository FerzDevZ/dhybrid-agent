"""SessionStore — SQLite local-first (own-your-data ala OpenClaw).

Tabel: sessions, messages, usage. Semua data lokal, tanpa server.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    created TEXT,
    title TEXT,
    summary TEXT,
    final_text TEXT,
    cwd TEXT
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    role TEXT,
    content TEXT,
    tool_calls TEXT,
    created TEXT,
    FOREIGN KEY(session_id) REFERENCES sessions(id)
);
CREATE TABLE IF NOT EXISTS usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    model TEXT,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    cached_tokens INTEGER,
    cost REAL,
    created TEXT
);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat()


class SessionStore:
    def __init__(self, db_path: Path | None = None):
        self.db_path = Path(db_path or Path.home() / ".dhybrid" / "sessions.sqlite")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.executescript(SCHEMA)
        # migrasi: DB lama (tanpa kolom cwd) → tambahkan kolom
        cols = {r[1] for r in self.conn.execute("PRAGMA table_info(sessions)")}
        if "cwd" not in cols:
            self.conn.execute("ALTER TABLE sessions ADD COLUMN cwd TEXT")
            self.conn.commit()

    def new_session(self, title: str = "untitled", cwd: str | None = None) -> str:
        sid = uuid.uuid4().hex[:12]
        self.conn.execute(
            "INSERT INTO sessions (id, created, title, summary, final_text, cwd) VALUES (?,?,?,?,?,?)",
            (sid, _now(), title, "", "", cwd or ""),
        )
        self.conn.commit()
        return sid

    def last_session_for_cwd(self, cwd: str) -> str | None:
        """Sesi terbaru untuk proyek (cwd) tertentu — dipakai auto-resume."""
        row = self.conn.execute(
            "SELECT id FROM sessions WHERE cwd=? ORDER BY created DESC LIMIT 1",
            (cwd,),
        ).fetchone()
        return row[0] if row else None

    def session_cwd(self, sid: str) -> str:
        row = self.conn.execute(
            "SELECT cwd FROM sessions WHERE id=?", (sid,)
        ).fetchone()
        return row[0] if row else ""

    def append_message(self, sid: str, role: str, content: str, tool_calls=None) -> None:
        self.conn.execute(
            "INSERT INTO messages (session_id, role, content, tool_calls, created) VALUES (?,?,?,?,?)",
            (sid, role, content, json.dumps(tool_calls) if tool_calls else None, _now()),
        )
        self.conn.commit()

    def record_usage(
        self,
        sid: str,
        model: str,
        prompt: int,
        completion: int,
        cached: int,
        cost: float,
    ) -> None:
        self.conn.execute(
            "INSERT INTO usage (session_id, model, prompt_tokens, completion_tokens, cached_tokens, cost, created) "
            "VALUES (?,?,?,?,?,?,?)",
            (sid, model, prompt, completion, cached, cost, _now()),
        )
        self.conn.commit()

    def set_summary(self, sid: str, summary: str, final_text: str = "") -> None:
        self.conn.execute(
            "UPDATE sessions SET summary=?, final_text=? WHERE id=?",
            (summary, final_text, sid),
        )
        self.conn.commit()

    def get_session(self, sid: str) -> dict | None:
        row = self.conn.execute(
            "SELECT id, created, title, summary, final_text FROM sessions WHERE id=?", (sid,)
        ).fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "created": row[1],
            "title": row[2],
            "summary": row[3] or "",
            "final_text": row[4] or "",
        }

    def last_messages(self, sid: str, n: int = 5) -> list[dict]:
        rows = self.conn.execute(
            "SELECT role, content FROM messages WHERE session_id=? "
            "ORDER BY id DESC LIMIT ?",
            (sid, n),
        ).fetchall()
        return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

    def usage(self, sid: str | None = None) -> list[dict]:
        if sid:
            rows = self.conn.execute(
                "SELECT session_id, model, prompt_tokens, completion_tokens, cached_tokens, cost "
                "FROM usage WHERE session_id=? ORDER BY id",
                (sid,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT session_id, model, prompt_tokens, completion_tokens, cached_tokens, cost "
                "FROM usage ORDER BY id"
            ).fetchall()
        return [
            {
                "session_id": r[0],
                "model": r[1],
                "prompt": r[2],
                "completion": r[3],
                "cached": r[4],
                "cost": r[5] or 0.0,
            }
            for r in rows
        ]

    def sessions(self, limit: int = 20) -> list[dict]:
        rows = self.conn.execute(
            "SELECT id, created, title FROM sessions ORDER BY created DESC LIMIT ?", (limit,)
        ).fetchall()
        return [{"id": r[0], "created": r[1], "title": r[2]} for r in rows]

    def delete_session(self, sid: str) -> None:
        self.conn.execute("DELETE FROM usage WHERE session_id=?", (sid,))
        self.conn.execute("DELETE FROM messages WHERE session_id=?", (sid,))
        self.conn.execute("DELETE FROM sessions WHERE id=?", (sid,))
        self.conn.commit()
