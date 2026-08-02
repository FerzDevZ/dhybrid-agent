"""Cache hemat token: PromptCache (exact) + SemanticCache (fuzzy).

PromptCache: respons deterministik (klasifikasi routing, kompaksi, dsb)
di-cache di SQLite dengan TTL. SemanticCache: fallback fuzzy via difflib
untuk prompt yang mirip tapi tidak identik.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import sqlite3
import time
from pathlib import Path

from dhybrid.llm.base import ChatMessage


def _join(messages: list[ChatMessage]) -> str:
    return "\n".join(f"{m.role}: {m.content}" for m in messages)


class PromptCache:
    def __init__(self, db_path: Path | None = None, ttl: int = 3600):
        self.db_path = Path(db_path or Path.home() / ".dhybrid" / "cache.sqlite")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl
        self._conn = sqlite3.connect(self.db_path)
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS prompt_cache (
                key TEXT PRIMARY KEY, value TEXT, created REAL)"""
        )

    @staticmethod
    def _key(model: str, messages: list[ChatMessage]) -> str:
        blob = json.dumps([m.to_api() for m in messages], sort_keys=True)
        return hashlib.sha256(f"{model}|{blob}".encode()).hexdigest()

    def get(self, model: str, messages: list[ChatMessage]) -> str | None:
        key = self._key(model, messages)
        row = self._conn.execute(
            "SELECT value, created FROM prompt_cache WHERE key=?", (key,)
        ).fetchone()
        if row and time.time() - row[1] < self.ttl:
            return row[0]
        return None

    def set(self, model: str, messages: list[ChatMessage], value: str) -> None:
        key = self._key(model, messages)
        self._conn.execute(
            "INSERT OR REPLACE INTO prompt_cache VALUES (?,?,?)",
            (key, value, time.time()),
        )
        self._conn.commit()


class SemanticCache:
    """Cache fuzzy in-memory: hit bila similarity >= threshold (default 0.95)."""

    def __init__(self, threshold: float = 0.95, capacity: int = 100):
        self.threshold = threshold
        self.capacity = capacity
        self._entries: list[tuple[str, str, str]] = []  # (model, prompt, value)

    def get(self, model: str, messages: list[ChatMessage]) -> str | None:
        prompt = _join(messages)
        for m, p, v in self._entries:
            if m == model:
                ratio = difflib.SequenceMatcher(None, p, prompt).ratio()
                if ratio >= self.threshold:
                    return v
        return None

    def set(self, model: str, messages: list[ChatMessage], value: str) -> None:
        self._entries.append((model, _join(messages), value))
        if len(self._entries) > self.capacity:
            self._entries = self._entries[-self.capacity :]
