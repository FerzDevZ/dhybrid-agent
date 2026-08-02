"""Self-update — perbarui instalasi dari git remote."""

from __future__ import annotations

import subprocess
from pathlib import Path


def install_dir() -> Path:
    return Path(__file__).resolve().parents[2]


def _git(args: list[str]) -> str:
    proc = subprocess.run(
        ["git", "-C", str(install_dir()), *args],
        capture_output=True, text=True, timeout=60, check=False,
    )
    return (proc.stdout or "").strip()


def _git_out(args: list[str]) -> str:  # dipisah agar mudah di-mock test
    return _git(args)


def update_available() -> bool:
    try:
        _git_out(["fetch", "origin", "-q"])
        head = _git_out(["rev-parse", "HEAD"])
        remote = _git_out(["rev-parse", "origin/main"])
        return bool(head and remote and head != remote)
    except Exception:  # noqa: BLE001
        return False


def self_update() -> str:
    if not update_available():
        return "sudah versi terbaru."
    log = _git(["pull", "--ff-only", "origin", "main"])
    if not log:
        # repo install boleh di-reset (disposable); config user terpisah di ~/.dhybrid/
        log = _git(["reset", "--hard", "origin/main"])
    pip = subprocess.run(
        [str(install_dir() / ".venv" / "bin" / "pip"), "install", "-q", "-e", str(install_dir())],
        capture_output=True, text=True, timeout=180, check=False,
    )
    return f"update selesai:\n{log}\n{(pip.stdout or '').strip()}"
