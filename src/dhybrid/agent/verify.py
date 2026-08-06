"""Verifier penyelesaian tugas — bukti NYATA (file, test), bukan janji model.

Setelah loop: berapa file dibuat di bawah cwd? test dijalankan & lolos?
git berubah? Ini mengubah 'kata model' menjadi 'fakta sistem'.
"""

from __future__ import annotations

import os
from pathlib import Path

# Dependensi / artifact — BUKAN pekerjaan user. Jangan dihitung sebagai
# "file dibuat" (mis. composer install → vendor/ bisa puluhan ribu file,
# bikin angka `files_created` tak masuk akal & menyesatkan).
IGNORED_DIRNAMES = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    ".next",
    "target",
    "logs",
    ".idea",
    ".vscode",
    # Additional common dependency/artifact directories
    "coverage",
    ".coverage",
    "htmlcov",
    ".gradle",
    ".mvn",
    "bazel-*",
    "buck-out",
    ".cache",
    ".parcel-cache",
    ".turbo",
    "out",
    "bin",
    "obj",
    "pkg",
    "pkg.mod",
    "vendor",
}


def snapshot_files(cwd: str) -> set[str]:
    """Relatif path semua file di bawah cwd (abaikan .git, __pycache__, & folder dependensi)."""
    root = Path(cwd)
    if not root.exists():
        return set()
    out: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(os.fspath(root)):
        # prune folder dependensi supaya tidak ditelusuri sama sekali (cepat + tidak mengacungkan angka)
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRNAMES]
        rel_dir = os.path.relpath(dirpath, root).replace(os.sep, "/")
        for f in filenames:
            out.add(f"{rel_dir}/{f}" if rel_dir != "." else f)
    return out


def count_created_files(before: set[str], after: set[str]) -> int:
    return len(after - before)


def tests_info(tool_events: list[dict]) -> tuple[bool | None, int]:
    """(passed, jumlah eksekusi test). Parse output run_tests/tdd_status."""
    passed: bool | None = None
    count = 0
    for ev in tool_events:
        if ev["name"] not in ("run_tests", "tdd_status"):
            continue
        count += 1
        out = str(ev.get("output", ""))
        if "failed" in out.lower() or "[exit 1]" in out or "RED" in out:
            passed = False
        elif passed is not False and ("passed" in out.lower() or "GREEN" in out or "[exit 0]" in out):
            passed = True
    return passed, count


def verify_build(cwd: str, before: set[str], after: set[str], tool_events: list[dict]) -> dict:
    """Rangkuman bukti nyata."""
    created = count_created_files(before, after)
    tests_passed, tests_count = tests_info(tool_events)
    git_changed = any(ev["name"] == "git_commit" for ev in tool_events)
    return {
        "files_created": created,
        "tests_passed": tests_passed,
        "tests_count": tests_count,
        "git_changed": git_changed,
    }
