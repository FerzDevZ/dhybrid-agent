"""SessionStore — SQLite local-first + optional Redis persistence.

Tabel: sessions, messages, usage. Semua data lokal, tanpa server.
Redis layer: optional cross-instance state sync (fallback ke SQLite).
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

try:
    import redis  # type: ignore

    REDIS_AVAILABLE = True
    RedisError = redis.RedisError
except ImportError:  # pragma: no cover
    redis = None  # type: ignore
    REDIS_AVAILABLE = False

    class RedisError(Exception):
        """Fallback RedisError when redis is not available."""

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    created TEXT,
    title TEXT,
    summary TEXT,
    final_text TEXT,
    cwd TEXT
);
CREATE TABLE IF NOT EXISTS session_state (
    session_id TEXT PRIMARY KEY,
    state TEXT,
    updated TEXT,
    FOREIGN KEY(session_id) REFERENCES sessions(id)
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
            "SELECT id, created, title, summary, final_text, cwd FROM sessions WHERE id=?", (sid,)
        ).fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "created": row[1],
            "title": row[2],
            "summary": row[3] or "",
            "final_text": row[4] or "",
            "cwd": row[5] or "",
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
        self.conn.execute("DELETE FROM session_state WHERE session_id=?", (sid,))
        self.conn.execute("DELETE FROM sessions WHERE id=?", (sid,))
        self.conn.commit()

    # ---- checkpoint: persist state counters (run_count, fallback_uses, …) ----
    def save_checkpoint(self, sid: str, state: dict) -> None:
        self.conn.execute(
            "INSERT INTO session_state (session_id, state, updated) "
            "VALUES (?,?,?) "
            "ON CONFLICT(session_id) DO UPDATE SET state=excluded.state, updated=excluded.updated",
            (sid, json.dumps(state), _now()),
        )
        self.conn.commit()

    def load_checkpoint(self, sid: str) -> dict | None:
        row = self.conn.execute(
            "SELECT state FROM session_state WHERE session_id=?",
            (sid,),
        ).fetchone()
        return json.loads(row[0]) if row else None


class RedisStore(SessionStore):
    """SessionStore with optional Redis persistence for cross-instance state sync.

    Falls back to SQLite when Redis is unavailable or errors occur.
    """

    def __init__(
        self,
        db_path: Path | None = None,
        redis_client=None,
        redis_url: str | None = None,
    ):
        # Initialize SQLite first
        super().__init__(db_path)
        self.redis = redis_client

        if redis_client is None and REDIS_AVAILABLE and redis_url:
            try:
                self.redis = redis.from_url(redis_url)
                # Test connection
                self.redis.ping()
            except RedisError:
                self.redis = None

    def _redis_key(self, sid: str) -> str:
        return f"sess:{sid}:state"

    def save_checkpoint(self, sid: str, state: dict) -> None:
        # Always save to SQLite first
        super().save_checkpoint(sid, state)

        # Then try Redis
        if self.redis is not None:
            try:
                self.redis.set(self._redis_key(sid), json.dumps(state))
            except RedisError:
                pass  # Fail silently, SQLite has the data

    def load_checkpoint(self, sid: str) -> dict | None:
        # Try Redis first
        if self.redis is not None:
            try:
                data = self.redis.get(self._redis_key(sid))
                if data:
                    return json.loads(data)
            except RedisError:
                pass

        # Fallback to SQLite
        return super().load_checkpoint(sid)

    def append_message(self, sid: str, role: str, content: str, tool_calls=None) -> None:
        super().append_message(sid, role, content, tool_calls)
        if self.redis is not None:
            try:
                # Optionally sync message to Redis for cross-instance access
                key = f"sess:{sid}:messages"
                self.redis.lpush(key, json.dumps({"role": role, "content": content, "created": _now()}))
                self.redis.ltrim(key, 0, 99)  # Keep last 100
            except RedisError:
                pass