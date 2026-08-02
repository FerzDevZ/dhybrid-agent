"""Kualitas output — heuristik murni (tanpa LLM) untuk keputusan escalation.

Deteksi:
- Refusal / menolak kerja
- Bertanya kembali padahal diminta buat
- Bingung / "mau yang mana"
- Diam (jawaban kosong)

Skor 0-100. Dipakai untuk eskalasi otomatis ke model berikutnya di chain.
"""
from __future__ import annotations

import re

# Model menolak / membatalkan — sangat buruk untuk task membangun
REFUSAL_HINTS = (
    "tidak bisa", "tidak dapat", "tidak punya akses", "cannot", "can't",
    "belum bisa", "tidak tersedia", "tidak memiliki akses", "tidak sanggup",
    "saya tidak bisa", "tidak akan bisa", "maaf", "maafkan",
    "hanya bisa", "terbatas pada", "tidak dapat membantu",
)

# Model bingung / minta klarifikasi padahal sudah jelas
CONFUSED_HINTS = (
    "mau yang mana", "pilih", "bagaimana sebaiknya", "bisa jelaskan",
    "untuk memastikan", "agar saya yakin", "jika memungkinkan",
    "saya tidak yakin", "butuh klarifikasi", "perlu informasi",
    "silakan beri tahu saya", "bisakah Anda", "apakah kamu",
    "boleh tanya", "mungkin kita", "kita bisa", "saya usulkan",
)

# Model berjanji tanpa eksekusi (over-promise, under-deliver)
PROMISE_HINTS = (
    "akan saya buat", "saya akan membuatkan", "nanti akan", "akan kuselesaikan",
    "saya akan coba", "mungkin bisa", "semoga bisa",
)


def score_output(
    text: str,
    *,
    is_build: bool = False,
    tools_used: int = 0,
    files_created: int = 0,
    tests_passed: bool | None = None,
) -> int:
    """Skor 0-100. Dipakai untuk keputusan escalate antar model.

    Heuristik murni — tanpa biaya LLM.
    """
    t = (text or "").strip()
    low = t.lower()

    if not t:
        return 0  # diam → gagal total

    score = 50

    # --- Penalti kualitas ---
    if any(h in low for h in REFUSAL_HINTS):
        score -= 40  # menolak kerja
    if any(h in low for h in CONFUSED_HINTS):
        score -= 25  # bingung / minta klarifikasi
    if any(h in low for h in PROMISE_HINTS):
        score -= 15  # berjanji tanpa eksekusi

    # --- Penalti build ---
    if is_build and re.search(r"\?\\s*$", t):
        score -= 30  # bertanya saat diminta buat
    if is_build and files_created == 0 and tools_used == 0:
        score -= 35  # diminta buat tapi tidak ada eksplor/eksekusi
    if is_build and files_created == 0:
        score -= 20  # diminta buat tapi tidak ada file nyata

    # --- Bonus ---
    if files_created > 0:
        score += min(files_created * 10, 30)  # max +30 untuk file
    if tests_passed is True:
        score += 20
    elif tests_passed is False:
        score -= 15
    if len(t) > 300:
        score += 10  # jawaban substantional
    elif len(t) < 60 and is_build:
        score -= 15  # terlalu pendek untuk tugas membangun

    # --- Escalation threshold hint ---
    # Bila score < 30 → HARUS escalate ke model berikutnya
    # Bila score < 50 → pertimbangkan escalate

    return max(0, min(100, score))
