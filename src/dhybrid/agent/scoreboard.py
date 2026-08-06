"""Scoreboard kualitas model — belajar dari pemakaian nyata.

Setiap sesi mencatat skor kualitas per model → rata-rata bergerak.
`best_available(presets)` memilih preset terbaik yang tersedia.
Routing default 'auto' memakai ini: model apa pun yang terpasang → hasil
terbaik yang pernah diukur di mesin ini.

Thread-safe: SQLite WAL mode + threading lock untuk concurrent access.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path


class Scoreboard:
    def __init__(self, db_path: Path | None = None):
        self.db_path = Path(db_path or Path.home() / ".dhybrid" / "scoreboard.sqlite")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        # Enable WAL mode for better concurrent access
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=5000")
        self._lock = threading.Lock()
        self.conn.execute(
            """CREATE TABLE IF NOT EXISTS scores (
                preset TEXT PRIMARY KEY,
                score REAL,
                samples INTEGER,
                updated TEXT)"""
        )

    def record(self, preset: str, score: int) -> None:
        """Rata-rata bergerak: new = (old*samples + score) / (samples+1)."""
        import datetime

        now = datetime.datetime.now(datetime.UTC).isoformat()
        with self._lock:
            row = self.conn.execute("SELECT score, samples FROM scores WHERE preset=?", (preset,)).fetchone()
            if row:
                old, samples = row
                new_score = (old * samples + score) / (samples + 1)
                self.conn.execute(
                    "UPDATE scores SET score=?, samples=?, updated=? WHERE preset=?",
                    (new_score, samples + 1, now, preset),
                )
            else:
                self.conn.execute(
                    "INSERT INTO scores VALUES (?,?,?,?)",
                    (preset, float(score), 1, now),
                )
            self.conn.commit()

    def best_available(self, presets: list[str]) -> str | None:
        """Preset dengan skor tertinggi dari daftar yang tersedia (dan pernah diukur)."""
        if not presets:
            return None
        with self._lock:
            rows = self.conn.execute("SELECT preset, score FROM scores").fetchall()
            by_name = {r[0]: r[1] for r in rows}
            candidates = [(p, by_name[p]) for p in presets if p in by_name]
            if not candidates:
                return None
            candidates.sort(key=lambda x: -x[1])
            return candidates[0][0]

    def table(self, limit: int = 15) -> list[tuple[str, float, int]]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT preset, score, samples FROM scores ORDER BY score DESC LIMIT ?", (limit,)
            ).fetchall()
            return [(r[0], round(r[1], 1), r[2]) for r in rows]
    
    def close(self) -> None:
        """Close database connection."""
        self.conn.close()
