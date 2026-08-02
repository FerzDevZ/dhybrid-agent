"""Tool git — status, diff, commit dengan preview, log. Semua output di-cap."""

from __future__ import annotations

import subprocess

from dhybrid.efficiency.lazy import summarize_diff_stat


def _git(args: list[str], cwd: str = ".", timeout: int = 30) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False
        )
        out = (proc.stdout or "") + (("\n[stderr]\n" + proc.stderr) if proc.stderr else "")
        return proc.returncode, out
    except FileNotFoundError:
        return 127, "git tidak terpasang"
    except subprocess.TimeoutExpired:
        return -1, "[timeout]"


def git_status(cwd: str = ".", max_chars: int = 4000) -> str:
    code, out = _git(["status", "--short"], cwd)
    if code != 0:
        return f"ERROR: bukan repo git atau git error:\n{out[:max_chars]}"
    return out[:max_chars] or "(working tree bersih)"


def git_diff(cwd: str = ".", stat: bool = True, max_chars: int = 4000) -> str:
    args = ["diff", "--stat"] if stat else ["diff"]
    code, out = _git(args, cwd)
    if code != 0:
        return f"ERROR:\n{out[:max_chars]}"
    if stat:
        out = summarize_diff_stat(out)
    return out[:max_chars] or "(tidak ada perubahan)"


def git_commit_preview(cwd: str = ".") -> str:
    """Diff yang AKAN di-commit (staged + unstaged digabung via diff HEAD)."""
    code, out = _git(["diff", "HEAD", "--stat"], cwd)
    if code != 0:
        return "ERROR: bukan repo git"
    return summarize_diff_stat(out) or "(tidak ada perubahan untuk di-commit)"


def git_commit(message: str, cwd: str = ".", files: str | None = None) -> str:
    if not message.strip():
        return "ERROR: pesan commit kosong"
    preview_code, preview = _git(["diff", "HEAD", "--stat"], cwd)
    if preview_code != 0:
        return "ERROR: bukan repo git"
    if not preview.strip():
        return "ERROR: tidak ada perubahan untuk di-commit (working tree bersih)"
    if files:
        code, out = _git(["add", *files.split()], cwd)
        if code != 0:
            return f"ERROR add:\n{out[:2000]}"
    else:
        code, out = _git(["add", "-A"], cwd)
        if code != 0:
            return f"ERROR add:\n{out[:2000]}"
    code, out = _git(["commit", "-m", message], cwd)
    if code != 0:
        return f"ERROR commit:\n{out[:2000]}"
    return out.strip()


def git_log(n: int = 5, cwd: str = ".", max_chars: int = 2000) -> str:
    code, out = _git(["log", "--oneline", f"-{n}"], cwd)
    if code != 0:
        return "ERROR: bukan repo git"
    return out[:max_chars] or "(belum ada commit)"


def register(reg, max_chars: int = 8000) -> None:
    reg.register("git_status", "Status repo git (short).", {"cwd": {"type": "string"}},
                 lambda cwd=".": git_status(cwd))
    reg.register("git_diff", "Ringkasan diff (stat) — file + jumlah baris berubah.",
                 {"cwd": {"type": "string"}}, lambda cwd=".": git_diff(cwd))
    reg.register("git_commit", "Commit SEMUA perubahan dengan pesan (menolak bila working tree bersih).",
                 {"message": {"type": "string"}, "cwd": {"type": "string"}},
                 lambda message, cwd=".": git_commit(message, cwd))
    reg.register("git_log", "Log commit terakhir.", {"n": {"type": "integer"}, "cwd": {"type": "string"}},
                 lambda n=5, cwd=".": git_log(n, cwd))
