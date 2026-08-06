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


def _model_config_key(model_config: dict) -> str:
    """Generate a deterministic key from model config that affects output."""
    # Include all config params that affect model behavior
    relevant_keys = [
        "provider", "model", "base_url", "temperature", "max_tokens",
        "top_p", "frequency_penalty", "presence_penalty"
    ]
    config_subset = {k: model_config.get(k) for k in relevant_keys if k in model_config}
    return json.dumps(config_subset, sort_keys=True)


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
    def _key(model: str, messages: list[ChatMessage], model_config: dict | None = None) -> str:
        blob = json.dumps([m.to_api() for m in messages], sort_keys=True)
        config_key = _model_config_key(model_config) if model_config else ""
        return hashlib.sha256(f"{model}|{config_key}|{blob}".encode()).hexdigest()

    def get(self, model: str, messages: list[ChatMessage], model_config: dict | None = None) -> str | None:
        key = self._key(model, messages, model_config)
        row = self._conn.execute(
            "SELECT value, created FROM prompt_cache WHERE key=?", (key,)
        ).fetchone()
        if row and time.time() - row[1] < self.ttl:
            return row[0]
        return None

    def set(self, model: str, messages: list[ChatMessage], value: str, model_config: dict | None = None) -> None:
        key = self._key(model, messages, model_config)
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
        self._entries: list[tuple[str, str, str, str]] = []  # (model, config_key, prompt, value)

    def get(self, model: str, messages: list[ChatMessage], model_config: dict | None = None) -> str | None:
        prompt = _join(messages)
        config_key = _model_config_key(model_config) if model_config else ""
        for m, c, p, v in self._entries:
            if m == model and c == config_key:
                ratio = difflib.SequenceMatcher(None, p, prompt).ratio()
                if ratio >= self.threshold:
                    return v
        return None

    def set(self, model: str, messages: list[ChatMessage], value: str, model_config: dict | None = None) -> None:
        prompt = _join(messages)
        config_key = _model_config_key(model_config) if model_config else ""
        self._entries.append((model, config_key, prompt, value))
        if len(self._entries) > self.capacity:
            self._entries = self._entries[-self.capacity :]
