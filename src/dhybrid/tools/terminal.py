"""Tool terminal — jalankan perintah shell dengan timeout, cap output,
dan gerbang keamanan untuk perintah berbahaya."""

from __future__ import annotations

import subprocess

from dhybrid.tools.security import is_dangerous

# Callback konfirmasi — di-set oleh UI (repl). None = tolak (default aman).
confirm_fn: callable | None = None  # type: ignore[assignment]


def run_command(command: str, timeout: int = 60, max_chars: int = 8000) -> str:
    if not command or not command.strip():
        return "ERROR: command kosong — tidak ada yang dijalankan."
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
