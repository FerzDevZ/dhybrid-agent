"""Kualitas output — heuristik murni (tanpa LLM) untuk keputusan escalation.

Deteksi:
- Refusal / menolak kerja
- Bertanya kembali padahal diminta buat
- Bingung / "mau yang mana"
- Diam (jawaban kosong)

Skor 0-100. Dipakai untuk eskalasi otomatis ke model berikutnya di chain.
"""
from __future__ import annotations

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

    Prinsip: bukti EKSEKUSI NYATA (tools_used, files_created) lebih penting
    daripada pola teks. Model bahasa Indonesia alami sering menulis "apakah
    kamu", "saya akan buat", "bisakah Anda" — itu SOPAN, bukan bingung/menolak.
    Jangan hukum kata-kata natural; hukum hanya bila TIDAK ada kerja nyata.

    Heuristik murni — tanpa biaya LLM.
    """
    t = (text or "").strip()
    low = t.lower()

    if not t and tools_used == 0:
        return 0  # diam total + tidak ada kerja

    score = 50

    # --- Penalti teks: hanya berlaku jika TIDAK ada bukti eksekusi ---
    # (kalau tool jalan & file dibuat, kata-kata natural tidak dihukum)
    if tools_used == 0:
        if any(h in low for h in REFUSAL_HINTS):
            score -= 40  # menolak kerja
        if any(h in low for h in CONFUSED_HINTS):
            score -= 25  # bingung / minta klarifikasi tanpa kerja
        if any(h in low for h in PROMISE_HINTS):
            score -= 15  # berjanji tanpa eksekusi

    # --- Penalti build (hanya bila tidak ada eksplor/eksekusi) ---
    if is_build and tools_used == 0 and files_created == 0:
        score -= 35
    if is_build and files_created == 0 and tools_used > 0:
        score -= 10  # kerja tapi belum ada file nyata

    # --- Bonus eksekusi nyata (dominan) ---
    score += min(tools_used, 10)  # +0..10 untuk tool dipakai
    if files_created > 0:
        score += min(files_created * 10, 30)  # max +30 untuk file
        # task yang menghasilkan file nyata minimal "cukup" — jangan jatuh < 60
        score = max(score, 60)
    if tests_passed is True:
        score += 20
    elif tests_passed is False:
        score -= 15
    if len(t) > 300:
        score += 10
    elif len(t) < 60 and is_build and tools_used == 0:
        score -= 15  # pendek + tidak kerja → buruk

    return max(0, min(100, score))
