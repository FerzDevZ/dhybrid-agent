"""Tool search — grep & find_files dengan cap hasil."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def grep(pattern: str, path: str = ".", max_results: int = 200, max_chars: int = 8000) -> str:
    p = Path(path)
    if not p.exists():
        return f"ERROR: path tidak ada: {path}"
    cmd: list[str]
    if shutil.which("rg"):
        cmd = ["rg", "-n", "--no-heading", pattern, str(p)]
    else:
        cmd = ["grep", "-rn", "--color=never", pattern, str(p)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
    except subprocess.TimeoutExpired:
        return "[timeout]"
    lines = (proc.stdout or "").splitlines()[:max_results]
    out = "\n".join(lines) if lines else "(tidak ada hasil)"
    return out[:max_chars] + ("\n[truncated]" if len(out) > max_chars else "")


def find_files(glob: str, path: str = ".", max_results: int = 100, max_chars: int = 8000) -> str:
    p = Path(path)
    if not p.exists():
        return f"ERROR: path tidak ada: {path}"
    try:
        hits = [str(f) for f in p.rglob(glob)][:max_results]
    except OSError as e:
        return f"ERROR: {e}"
    out = "\n".join(hits) if hits else "(tidak ada file cocok)"
    return out[:max_chars]


def register(reg, max_chars: int = 8000) -> None:
    reg.register(
        "grep",
        "Cari teks/regex di dalam file. WAJIB dicoba SEBELUM menulis helper baru.",
        {"pattern": {"type": "string"}, "path": {"type": "string"}},
        lambda pattern, path=".": grep(pattern, path, max_chars=max_chars),
    )
    reg.register(
        "find_files",
        "Cari file berdasarkan glob (contoh: '*.py').",
        {"glob": {"type": "string"}, "path": {"type": "string"}},
        lambda glob, path=".": find_files(glob, path, max_chars=max_chars),
    )
