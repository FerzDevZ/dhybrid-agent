"""Lazy policies (gaya Ponytail: lazy senior dev) + builder system prompt.

Kode terbaik adalah kode yang tidak pernah ditulis → penghemat token terbesar.
"""

from __future__ import annotations

LAZY_RULES = """
ATURAN KERJA (prioritas tertinggi):
1. JANGAN tulis kode yang tidak diminta. Jangan refactor tanpa alasan.
2. Cari helper/fungsi yang SUDAH ADA sebelum menulis yang baru (grep dulu).
3. Edit paling kecil yang menyelesaikan masalah: ubah hunk terkecil, jangan
   tulis ulang file. Selalu pakai tool apply_patch, bukan write_file penuh,
   kecuali untuk file baru.
4. Kalau bisa pakai tool/library yang ada, lakukan. Jangan reinvent.
5. Hapus kode mati yang kamu temui saat mengedit (jika aman).
6. Verifikasi dengan menjalankan test/command terkecil, bukan menebak.
7. Sebelum selesai, jawab: "perubahan apa yang benar-benar dibutuhkan?" —
   bila tidak ada, katakan TIDAK ADA YANG PERLU DIUBAH.
8. Saat melaporkan, tampilkan hanya file + jumlah baris berubah (diff --stat),
   bukan diff penuh.
"""


def build_system_prompt(base: str, workspace_hint: str = "") -> str:
    """System prompt di-compile SEKALI per sesi (hemat token input)."""
    parts = [base.strip(), LAZY_RULES]
    if workspace_hint:
        parts.append(f"Workspace: {workspace_hint}")
    return "\n\n".join(p for p in parts if p)


def needs_change_check(last_assistant_text: str) -> bool:
    """Deteksi sinyal 'tidak ada yang perlu diubah' untuk early-stop."""
    return "TIDAK ADA YANG PERLU DIUBAH" in last_assistant_text.upper()


def summarize_diff_stat(stat_output: str) -> str:
    """Ringkas output `git diff --stat` → hanya baris file + angka."""
    lines = [ln for ln in stat_output.splitlines() if "|" in ln and ln.strip()]
    return "\n".join(lines) if lines else "(tidak ada perubahan)"
