"""Kualitas output — heuristik murni (tanpa LLM) untuk keputusan escalation.

Semua model dinilai dengan ukuran yang sama → output merata: model lemah
otomatis dibantu model berikutnya di chain.
"""

from __future__ import annotations

import re

REFUSAL_HINTS = (
    "tidak bisa", "tidak dapat", "tidak punya akses", "cannot", "can't",
    "belum bisa", "tidak tersedia", "tidak memiliki akses", "tidak sanggup",
    "saya tidak bisa", "tidak akan bisa",
)


def score_output(
    text: str,
    *,
    is_build: bool = False,
    tools_used: int = 0,
    files_created: int = 0,
    tests_passed: bool | None = None,
) -> int:
    """Skor 0-100. Dipakai untuk keputusan escalate antar model."""
    t = (text or "").strip()
    if not t:
        return 0  # diam → gagal total
    score = 50
    low = t.lower()
    if any(h in low for h in REFUSAL_HINTS):
        score -= 40  # menolak kerja
    if is_build and re.search(r"\?\s*$", t):
        score -= 30  # balik bertanya saat diminta buat
    if is_build and files_created == 0:
        score -= 25  # diminta buat tapi tidak ada file nyata
    if tests_passed is True:
        score += 20
    elif tests_passed is False:
        score -= 15
    if len(t) > 300:
        score += 10  # jawaban substansial
    elif len(t) < 60 and is_build:
        score -= 15  # terlalu pendek untuk tugas membangun
    return max(0, min(100, score))
