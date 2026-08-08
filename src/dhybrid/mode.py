"""Mode kerja agent: Plan (observasi) ⇄ Build (eksekusi + Issue/PR).

`apply_mode` menyinkronkan state mode ke sesi (ctx) + gerbang tool:
- ctx.tools.readonly  → blok tool mutasi di registry
- dhybrid.tools.terminal.readonly → batasi terminal ke perintah observasi

`mode_system_block` menghasilkan tambahan instruksi system prompt per mode.
"""

from __future__ import annotations

PLAN = "plan"
BUILD = "build"
MODES = (BUILD, PLAN)

MODE_LABEL = {BUILD: "BUILD", PLAN: "PLAN"}


def _workflow(cfg) -> dict:
    return getattr(cfg, "workflow", {}) or {}


def apply_mode(ctx, mode: str | None = None) -> str:
    """Set ctx.mode (default dari cfg), kunci gerbang tool sesuai mode.

    Return mode aktif.
    """
    if mode not in MODES:
        mode = getattr(getattr(ctx, "cfg", None), "mode", BUILD)
        if mode not in MODES:
            mode = BUILD
    ctx.mode = mode
    if getattr(ctx, "tools", None) is not None:
        ctx.tools.readonly = mode == PLAN
    from dhybrid.tools import terminal as _terminal

    _terminal.readonly = mode == PLAN
    return mode


def mode_system_block(mode: str, cfg: dict | None = None) -> str:
    """Blok instruksi system prompt sesuai mode."""
    workflow = cfg or {}
    if mode == PLAN:
        return (
            "MODE PLAN: hanya observasi. TOOL MUTASI DIBLOKIR SISTEM "
            "(write_file, apply_patch, git_commit, repo_issue, repo_pr, dll). "
            "Terminal hanya perintah read-only (ls, cat, grep, strings, watch, "
            "git status/log/diff). JANGAN mengubah file apa pun. Tugaskan: "
            "teliti, catat temuan, lalu sampaikan rencana eksekusi yang akan "
            "dikerjakan user di Mode Build."
        )
    parts = [
        "MODE BUILD: eksekusi penuh diizinkan. Kebijakan kerja:"
    ]
    if workflow.get("auto_issue", True):
        parts.append(
            " 1) pastikan pekerjaan ini tercatat sebagai Issue: cek repo_issues, "
            "tambahkan task lewat repo_issue bila belum ada;"
        )
    parts.append(" 2) kerjakan task; 3) verifikasi (test/build); 4) commit perubahannya;")
    if workflow.get("auto_pr", True):
        parts.append(" 5) buat PR/MR via repo_pr; 6) lapor hasilnya.")
    else:
        parts.append(" 5) lapor hasil; jangan buat PR tanpa diminta.")
    return "".join(parts)