"""Hybrid router — inti "dhybrid": model kecil utk tugas mekanis, besar utk penalaran.

Klasifikasi memakai heuristik murah (tanpa biaya LLM) + estimasi kompleksitas
prompt, hasilnya di-cache (PromptCache) supaya konsisten + hemat.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from dhybrid.efficiency.cache import PromptCache
from dhybrid.llm.base import ChatMessage, LLMClient

MECHANICAL_HINTS = [
    r"\b(grep|find|search|list|show|cat|head|tail|status|ls)\b",
    r"\b(run|execute|test|pytest|format|rename|move|copy|delete)\b",
    r"\b(add\s+(type|log|print|comment|field))\b",
    r"\b(cara\s+(pakai|gunakan)|help|bantuan)\b",
    r"\b(jalankan|cek|lihat|tampilkan|buat file)\b",
]
REASONING_HINTS = [
    r"\b(design|architecture|arsitektur|refactor|optimize|debug|why|explain)\b",
    r"\b(rewrite|migrate|parallel|async|performance|security|bug|crash|race)\b",
    r"\b(redesign|analisa|analisis|desain)\b",
    r"\b(perbaiki|optimalkan|arsitektur|sekaligus|pendekatan|strategi)\b",
]
BUILD_VERBS_ROUTER = {
    "buat", "buatkan", "bikin", "buatin", "tambahkan", "tambah", "create",
    "make", "implement", "implementasikan", "bangun", "kerjakan", "setup",
    "set-up", "install", "scaffold", "generate", "tuliskan", "perbaiki",
    "fix", "refactor", "selesaikan", "deploy", "migrate",
}
COMPLEXITY_TRIGGERS = {
    "auth", "login", "register", "oauth", "jwt", "database", "db", "migration",
    "api", "endpoint", "rest", "websocket", "async", "concurrency", "cache",
    "redis", "docker", "kubernetes", "deploy", "ci", "cd", "microservice",
    "monolith", "logging", "analytics", "payment", "stripe",
    "arsitektur", "desain sistem", "koneksi", "realtime", "scalable",
}

# Alias: nama yang dipakai di estimate_complexity
COMPLEXITY_HINTS = COMPLEXITY_TRIGGERS


def classify_task(prompt: str) -> str:
    """'small' = mekanis (model murah cukup), 'big' = butuh penalaran."""
    low = prompt.lower()
    if any(re.search(p, low) for p in REASONING_HINTS):
        return "big"
    if any(re.search(p, low) for p in MECHANICAL_HINTS):
        return "small"
    return "small" if len(prompt) < 200 else "big"


def estimate_complexity(prompt: str) -> int:
    """Skor kompleksitas 0-10 untuk estimasi biaya/token.

    Basis: panjang prompt + jumlah domain-critical keyword. Semakin tinggi,
    semakin layak dipakai model besar (lebih mahal tapi lebih akurat).
    """
    low = (prompt or "").lower()
    score = 0
    if len(prompt) >= 400:
        score += 3
    elif len(prompt) >= 200:
        score += 2
    elif len(prompt) >= 80:
        score += 1
    # keyword kompleksitas menambah bobot
    hits = sum(1 for h in COMPLEXITY_HINTS if h in low)
    score += min(hits, 4)  # max +4
    is_build = any(v in low for v in BUILD_VERBS_ROUTER)
    if is_build:
        score += 1  # build task biasanya butuh lebih banyak langkah
    return max(0, min(10, score))


@dataclass
class RouterConfig:
    """Kebijakan routing dinamis (cost/quality-aware)."""
    cost_weight: float = 0.3
    quality_weight: float = 0.5
    latency_weight: float = 0.2
    small_cost_unit: float = 0.001   # relatif
    big_cost_unit: float = 0.01
    big_threshold: float = 0.40     # complexity relatif → pakai big
    model_costs: dict = field(default_factory=dict)
    model_quality: dict = field(default_factory=dict)


class HybridRouter:
    """route(prompt) -> LLMClient. force="big" untuk eskalasi saat gagal."""

    def __init__(
        self,
        big_client: LLMClient,
        small_client: LLMClient,
        cache: PromptCache | None = None,
        config: RouterConfig | None = None,
    ):
        self.big = big_client
        self.small = small_client
        self.cache = cache
        self.config = config or RouterConfig()
        self.stats: dict[str, int] = {"small": 0, "big": 0}
        self._last_class: str = "small"

    def _classify_cached(self, prompt: str) -> str:
        if self.cache:
            msgs = [ChatMessage(role="user", content=prompt)]
            model_config = {
                "model": getattr(self.big, "model", "unknown"),
                "provider": getattr(self.big, "provider", "unknown"),
                "temperature": getattr(self.big, "temperature", 0.2),
            }
            hit = self.cache.get("classifier", msgs, model_config)
            if hit in ("small", "big"):
                return hit
            cls = self._classify(prompt)
            self.cache.set("classifier", msgs, cls, model_config)
            return cls
        return self._classify(prompt)

    def _complexity_rel(self, prompt: str) -> float:
        """Relatif kompleksitas 0.0..1.0 untuk keputusan cost/quality."""
        return estimate_complexity(prompt) / 10.0

    def _classify(self, prompt: str) -> str:
        """Routing cost/quality-aware:
        - hint penalaran → selalu big (akurasi kritis)
        - hint mekanis → selalu small (hemat)
        - kalau generik/long → big HANYA BILA kompleksitas cukup (tidak
          boros untuk prompt panjang tapi dangkal)."""
        low = prompt.lower()
        if any(re.search(p, low) for p in REASONING_HINTS):
            return "big"
        if any(re.search(p, low) for p in MECHANICAL_HINTS):
            return "small"
        rel = self._complexity_rel(prompt)
        if rel >= self.config.big_threshold:
            return "big"
        return "small"

    def route(self, prompt: str, force: str | None = None) -> LLMClient:
        cls = force or self._classify_cached(prompt)
        self._last_class = cls
        self.stats[cls] += 1
        return self.small if cls == "small" else self.big

    @property
    def last_class(self) -> str:
        return self._last_class
