"""MemoryStore — memori jangka panjang (KV + FTS5, gaya engram)."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path


class MemoryStore:
    def __init__(self, db_path: Path | None = None):
        self.db_path = Path(db_path or Path.home() / ".dhybrid" / "memory.sqlite")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS memory (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated TEXT
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(key, value);
            """
        )

    def remember(self, key: str, value: str) -> str:
        now = datetime.now(UTC).isoformat()
        self.conn.execute(
            "INSERT OR REPLACE INTO memory VALUES (?,?,?)", (key, value, now)
        )
        self.conn.execute("DELETE FROM memory_fts WHERE key=?", (key,))
        self.conn.execute("INSERT INTO memory_fts (key, value) VALUES (?,?)", (key, value))
        self.conn.commit()
        return f"OK: disimpan ({key})"

    def recall(self, key: str) -> str:
        row = self.conn.execute(
            "SELECT value FROM memory WHERE key=?", (key,)
        ).fetchone()
        return row[0] if row else f"(tidak ada memori untuk {key!r})"

    def search(self, query: str, limit: int = 5) -> str:
        try:
            rows = self.conn.execute(
                "SELECT key, value FROM memory_fts WHERE memory_fts MATCH ? LIMIT ?",
                (query, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            return "(query FTS tidak valid)"
        if not rows:
            return "(tidak ada memori cocok)"
        return "\n".join(f"[{k}] {v[:200]}" for k, v in rows)

    def recent(self, limit: int = 8) -> str:
        """Fakta memori terbaru (untuk di-inject ke system prompt saat sesi mulai)."""
        rows = self.conn.execute(
            "SELECT key, value FROM memory ORDER BY updated DESC LIMIT ?",
            (limit,),
        ).fetchall()
        if not rows:
            return ""
        return "\n".join(f"• {key}: {value[:220]}" for key, value in rows)

    def forget(self, key: str) -> str:
        self.conn.execute("DELETE FROM memory WHERE key=?", (key,))
        self.conn.execute("DELETE FROM memory_fts WHERE key=?", (key,))
        self.conn.commit()
        return f"OK: dihapus ({key})"
