"""Estimator token cepat — untuk budget & keputusan compaction (bukan billing)."""

from __future__ import annotations

from dhybrid.llm.base import ChatMessage


def estimate_tokens(text: str) -> int:
    """Estimasi cepat: ~4 char/token teks, ~3.2 char/token untuk teks padat kode."""
    if not text:
        return 0
    code_heavy = sum(1 for c in text if c in " \t\n{}();=#\"'") / max(len(text), 1)
    ratio = 3.2 if code_heavy > 0.15 else 4.0
    return max(1, int(len(text) / ratio))


def estimate_messages(messages: list[ChatMessage]) -> int:
    return sum(estimate_tokens(m.content) for m in messages) + 4 * len(messages)
