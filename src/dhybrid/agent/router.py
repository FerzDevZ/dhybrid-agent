"""Hybrid router — inti "dhybrid": model kecil utk tugas mekanis, besar utk penalaran.

Klasifikasi memakai heuristik murah (tanpa biaya LLM) dan hasilnya di-cache
(PromptCache) supaya konsisten + hemat.
"""

from __future__ import annotations

import re

from dhybrid.efficiency.cache import PromptCache
from dhybrid.llm.base import ChatMessage, LLMClient

MECHANICAL_HINTS = [
    r"\b(grep|find|search|list|show|cat|head|tail|status|ls)\b",
    r"\b(run|execute|test|pytest|format|rename|move|copy|delete)\b",
    r"\b(add\s+(type|log|print|comment|field))\b",
    r"\b(cara\s+(pakai|gunakan)|help|bantuan)\b",
]
REASONING_HINTS = [
    r"\b(design|architecture|arsitektur|refactor|optimize|debug|why|explain)\b",
    r"\b(rewrite|migrate|parallel|async|performance|security|bug|crash|race)\b",
    r"\b(redesign|analisa|analisis|desain)\b",
]


def classify_task(prompt: str) -> str:
    """'small' = mekanis (model murah cukup), 'big' = butuh penalaran."""
    low = prompt.lower()
    if any(re.search(p, low) for p in REASONING_HINTS):
        return "big"
    if any(re.search(p, low) for p in MECHANICAL_HINTS):
        return "small"
    return "small" if len(prompt) < 200 else "big"


class HybridRouter:
    """route(prompt) -> LLMClient. force="big" untuk eskalasi saat gagal."""

    def __init__(
        self,
        big_client: LLMClient,
        small_client: LLMClient,
        cache: PromptCache | None = None,
    ):
        self.big = big_client
        self.small = small_client
        self.cache = cache
        self.stats: dict[str, int] = {"small": 0, "big": 0}
        self._last_class: str = "small"

    def _classify_cached(self, prompt: str) -> str:
        if self.cache:
            msgs = [ChatMessage(role="user", content=prompt)]
            hit = self.cache.get("classifier", msgs)
            if hit in ("small", "big"):
                return hit
            cls = classify_task(prompt)
            self.cache.set("classifier", msgs, cls)
            return cls
        return classify_task(prompt)

    def route(self, prompt: str, force: str | None = None) -> LLMClient:
        cls = force or self._classify_cached(prompt)
        self._last_class = cls
        self.stats[cls] += 1
        return self.small if cls == "small" else self.big

    @property
    def last_class(self) -> str:
        return self._last_class
