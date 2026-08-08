"""AutoVerify — setelah agent klaim selesai, JALANKAN test nyata untuk bukti.

Cara kerja (tidak memanggil LLM):
1. Dari `new_files`, identifikasi tipe project (pyproject.toml, package.json,
   Cargo.toml, go.mod, pom.xml, build.gradle, *.csproj/Makefile).
2. Pilih perintah test "paling ringkas" yang cepat (mis. `pytest --collect-only -q`
   dulu → kalo ada test, `pytest -x --tb=short -q`), dengan timeout.
3. Jalankan via subprocess, tangkap stdout/stderr + exit code.
4. Return `VerificationReport` = {ran?, passed?, runner, cmd, log tail}.
5. AgentLoop: jalankan tepat sebelum finalisasi (sekali per run).
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class VerificationReport:
    ran: bool = False
    passed: bool | None = None
    runner: str | None = None
    command: str | None = None
    exit_code: int | None = None
    log_tail: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def evidence(self) -> bool:
        return self.ran and self.passed is True

    def summarize(self) -> str:
        if not self.ran:
            return "auto-verify: tidak ada project/test terdeteksi"
        status = "LULUS" if self.passed else ("GAGAL" if self.passed is False else "Tidak ada test")
        return f"auto-verify [{self.runner}] '{self.command}' {status} (exit={self.exit_code})"


def detect_runner(cwd: str, new_files: set[str]) -> tuple[str | None, list[str]]:
    """Deteksi (runner, command_list) dari marker file workspace atau new_files.

    Command diusahakan CEPAT dan non-invasif: prefer collection-only kalau
    tidak ada test sebelumnya. Kalau user punya konvensi pake pytest vitest
    dll, perintah ini tidak install dependency.
    """
    root = Path(cwd)
    has = lambda f: (root / f).exists() or f in new_files
    new_ext = {Path(n).suffix.lstrip(".") for n in new_files}
    new_ext.discard("")

    py_hints = {"py"} & new_ext or has("pyproject.toml") or has("pytest.ini") or has("setup.cfg")
    if py_hints or has("conftest.py"):
        return "pytest", [
            sys.executable, "-m", "pytest",
            "-x", "--tb=short", "-q", "--no-header", "--cache-clear",
        ]

    if has("package.json"):
        return "npm_test", ["npm", "test", "--silent", "--", "--run"]

    if has("Cargo.toml"):
        return "cargo_test", ["cargo", "test", "--no-run", "--quiet"]

    if has("go.mod") or {"go"} & new_ext:
        return "go_test", ["go", "test", "./...", "-count=1", "-timeout=30s", "-short"]

    if has("pom.xml"):
        return "mvn_test", ["mvn", "-q", "test", "-o", "-DskipTests=false"]
    if has("build.gradle") or has("build.gradle.kts"):
        return "gradle_test", ["gradle", "test", "--quiet", "--offline"]

    cs_hints = {"cs"} & new_ext or has("*.csproj")
    if cs_hints or any(str(p).endswith(".csproj") for p in root.glob("*.csproj")):
        return "dotnet_test", ["dotnet", "test", "--no-restore", "--nologo", "-v", "q"]

    # Makefile tanpa spesifik tool — coba `make test`
    if has("Makefile"):
        return "make_test", ["make", "--quiet", "test"]
    return None, []


def _truncate(text: str, lines: int = 12) -> list[str]:
    out = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    if len(out) <= lines:
        return out
    return ["…"] + out[-lines:]


def run_verification(
    cwd: str,
    new_files: set[str],
    timeout_s: int = 60,
) -> VerificationReport:
    """Jalankan 1 test command ringkas; non-blocking via timeout. Aman: tidak
    pernah error, selalu return VerificationReport."""
    rep = VerificationReport()
    runner, cmd = detect_runner(cwd, new_files)
    if runner is None or not cmd:
        return rep
    rep.runner = runner
    rep.command = " ".join(cmd)
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            env={**os.environ, "CI": "true"},
            check=False,
        )
    except FileNotFoundError as e:
        rep.ran = False
        rep.error = f"command not found: {e}"
        return rep
    except subprocess.TimeoutExpired as e:
        rep.ran = True
        rep.passed = False
        rep.exit_code = -1
        rep.log_tail = _truncate((e.stdout or "") + (e.stderr or ""))
        rep.error = "timeout"
        return rep

    rep.ran = True
    rep.exit_code = proc.returncode
    combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
    rep.log_tail = _truncate(combined)
    low = combined.lower()
    if proc.returncode == 0 and ("no tests ran" not in low and "0 passed" not in low):
        rep.passed = True
    elif "no tests ran" in low or "0 passed" in low or "collected 0 items" in low:
        rep.passed = None  # tidak ada test ditemukan
    else:
        rep.passed = False
    return rep
