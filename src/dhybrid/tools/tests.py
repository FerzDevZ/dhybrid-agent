"""Tool tests — jalankan test suite & cek status TDD."""

from __future__ import annotations

import subprocess


def run_tests(command: str = "pytest -q", path: str = ".", timeout: int = 120, max_chars: int = 8000) -> str:
    try:
        # nosec B602 — shell=True BY DESIGN: tool tests menjalankan pytest
        # dengan command yang datang dari model (hanya arg pytest, bukan shell bebas).
        proc = subprocess.run(
            command, shell=True, cwd=path, capture_output=True, text=True, timeout=timeout, check=False  # nosec B602
        )
        out = (proc.stdout or "") + (("\n[stderr]\n" + proc.stderr) if proc.stderr else "")
        if proc.returncode != 0:
            out = f"[exit {proc.returncode}]\n{out}"
    except subprocess.TimeoutExpired:
        out = f"[timeout setelah {timeout}s]"
    except Exception as e:  # noqa: BLE001
        out = f"[error] {e}"
    return out[:max_chars] + ("\n[truncated]" if len(out) > max_chars else "")


def tdd_status(path: str = ".", timeout: int = 120) -> str:
    """RED = ada test gagal, GREEN = semua test lolos, NO_TESTS = tidak ada test."""
    try:
        # nosec B602 — sama: pytest tetap, command dari model.
        proc = subprocess.run(
            "pytest -q --no-header", shell=True, cwd=path, capture_output=True, text=True, timeout=timeout, check=False  # nosec B602
        )
    except subprocess.TimeoutExpired:
        return "UNKNOWN: timeout"
    except Exception as e:  # noqa: BLE001
        return f"UNKNOWN: {e}"
    code = proc.returncode
    if code == 0:
        return "GREEN: semua test lolos"
    if code == 5:
        return "NO_TESTS: tidak ada test ditemukan"
    if code in (1, 2):
        # ekstrak ringkasan "N passed, M failed"
        for ln in (proc.stdout or "").splitlines():
            if "passed" in ln or "failed" in ln:
                return f"RED: {ln.strip()}"
        return "RED: ada test gagal"
    return f"RED: pytest exit {code}"


def register(reg, max_chars: int = 8000) -> None:
    reg.register(
        "run_tests",
        "Jalankan test suite (default pytest -q). Gunakan untuk VERIFIKASI, jangan menebak.",
        {"command": {"type": "string"}, "path": {"type": "string"}},
        lambda command="pytest -q", path=".": run_tests(command, path, max_chars=max_chars),
    )
    reg.register(
        "tdd_status",
        "Status TDD project: RED (ada test gagal) / GREEN (lolos) / NO_TESTS.",
        {"path": {"type": "string"}},
        lambda path=".": tdd_status(path),
    )
