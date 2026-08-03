"""MemoryStore — memori jangka panjang (KV + FTS5, gaya engram)."""

from __future__ import annotations

import re
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

    @staticmethod
    def _fts_terms(context: str) -> list[str]:
        """Token alfanumerik dari teks konteks (cwd/path) untuk query FTS aman."""
        return list(dict.fromkeys(re.findall(r"[A-Za-z0-9_]{2,}", context or "")))

    def digest(self, context: str = "", limit: int = 8) -> str:
        """Fakta paling RELEVAN utk di-inject di awal sesi, bukan sekadar 'terbaru'.

        Prioritas: (1) cari berdasar konteks (basename cwd/topik proyek) via FTS,
        (2) isi sisa slot dgn fakta terbaru bila terlalu sedikit yang cocok.
        Fallback ke `recent()` bila FTS tak valid / tidak ada cocok.
        """
        seen: dict[str, str] = {}
        terms = self._fts_terms(context)
        if terms:
            query = " OR ".join(f'"{t}"' for t in terms[:12])
            try:
                rows = self.conn.execute(
                    "SELECT key, value FROM memory_fts WHERE memory_fts MATCH ? LIMIT ?",
                    (query, max(limit, 1)),
                ).fetchall()
                for k, v in rows:
                    seen.setdefault(k, v)
            except sqlite3.OperationalError:
                seen = {}
        if len(seen) < limit:
            # isi sisa dengan fakta terbaru (bukan menimpa yg sudah relevan)
            rows = self.conn.execute(
                "SELECT key, value FROM memory ORDER BY updated DESC LIMIT ?",
                (limit,),
            ).fetchall()
            for k, v in rows:
                seen.setdefault(k, v)
        if not seen:
            return ""
        return "\n".join(f"• {key}: {value[:220]}" for key, value in list(seen.items())[:limit])

    def forget(self, key: str) -> str:
        self.conn.execute("DELETE FROM memory WHERE key=?", (key,))
        self.conn.execute("DELETE FROM memory_fts WHERE key=?", (key,))
        self.conn.commit()
        return f"OK: dihapus ({key})"
