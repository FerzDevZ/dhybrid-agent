"""Tool terminal — jalankan perintah shell dengan timeout, cap output,
dan gerbang keamanan untuk perintah berbahaya + mode read-only."""

from __future__ import annotations

import re
import shlex
import subprocess

from dhybrid.tools.security import is_dangerous

# Callback konfirmasi — di-set oleh UI (repl). None = tolak (default aman).
confirm_fn: callable | None = None  # type: ignore[assignment]
# Mode read-only (Plan Mode) — di-set UI. True = hanya perintah observasi.
readonly: bool = False

# Binary yang diizinkan di Plan Mode (observasi saja). Toolchain biner lain
# (npm, cargo, pytest, dsb) MUTASI lingkungan → tidak diizinkan.
READONLY_BIN = frozenset({
    "ls", "cat", "grep", "rg", "find", "strings", "watch", "head", "tail",
    "wc", "file", "stat", "which", "whoami", "date", "env", "git", "pwd",
    "printf", "du", "df", "ps", "top", "free",
})
_GIT_RO_SUBS = frozenset({
    "status", "diff", "log", "show", "branch", "remote", "config",
    "ls-files", "ls-tree", "rev-parse", "grep", "blame",
})
# Metachar shell: redirection, pipa, AND/OR, substitution, group — memungkinkan
# efek samping → dilarang di Plan Mode.
_METACHAR = re.compile(r"[;&|`><()]|\$\{|\$\(")


def is_readonly_command(command: str) -> bool:
    """True bila perintah aman untuk Plan Mode (observasi, tanpa efek samping).

    Allowlist binary read-only + tanpa metachar shell; `git` hanya subcommand
    yang memang read-only (status/diff/log/show/branch/remote/…).
    """
    if not command or not command.strip():
        return False
    if _METACHAR.search(command):
        return False
    try:
        tokens = shlex.split(command)
    except ValueError:
        return False
    if not tokens:
        return False
    # `watch` mengulang perintah di belakangnya — binary utama harus read-only.
    if tokens[0] == "watch":
        bins = [t for t in tokens[1:] if t and not t.startswith("-")]
        return bool(bins) and bins[0] in READONLY_BIN
    if tokens[0] == "git":
        return len(tokens) > 1 and tokens[1] in _GIT_RO_SUBS
    return tokens[0] in READONLY_BIN


def run_command(command: str, timeout: int = 60, max_chars: int = 8000) -> str:
    if not command or not command.strip():
        return "ERROR: command kosong — tidak ada yang dijalankan."
    if readonly and not is_readonly_command(command):
        return (
            "ERROR: Plan Mode — perintah ini mutasi/diluar observasi, diblokir. "
            "Gunakan perintah read-only (ls, cat, grep, strings, watch, git status/log/diff). "
            "Ganti ke Build Mode (Tab) untuk menjalankan."
        )
    if is_dangerous(command):
        if confirm_fn is None:
            return "ERROR: perintah terdeteksi berbahaya dan mode konfirmasi non-aktif — ditolak."
        ok = confirm_fn(command)
        if not ok:
            return "ERROR: perintah ditolak user."
    try:
        # shell=True BY DESIGN: tool terminal memang menjalankan shell;
        # sudah dijaga gerbang is_dangerous + confirm_fn di atas.
        proc = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=timeout, check=False  # nosec B602
        )
        out = (proc.stdout or "")
        if proc.stderr:
            out += f"\n[stderr]\n{proc.stderr}"
        if proc.returncode != 0:
            out = f"[exit {proc.returncode}]\n{out}"
    except subprocess.TimeoutExpired:
        out = f"[timeout setelah {timeout}s]"
    except Exception as e:  # noqa: BLE001
        out = f"[error] {e}"
    return out[:max_chars] + ("\n[truncated]" if len(out) > max_chars else "")


def register(reg, max_chars: int = 8000) -> None:
    reg.register(
        "terminal",
        "Jalankan perintah shell (lebih baik read-only dulu: ls, git status, pytest). Perintah berbahaya butuh konfirmasi.",
        {"command": {"type": "string"}, "timeout": {"type": "integer"}},
        lambda command, timeout=60: run_command(command, timeout=timeout, max_chars=max_chars),
    )
