"""dhybrid doctor — diagnosa config, key, koneksi, update."""

from __future__ import annotations

import os
import sys

from dhybrid.config import Config

OK = "✓"
FAIL = "✗"


def check_python() -> tuple[bool, str]:
    ok = sys.version_info >= (3, 12)
    return ok, f"python {sys.version.split()[0]} ({'OK' if ok else 'butuh >= 3.12'})"


def check_config(cfg: Config) -> tuple[bool, str]:
    return True, f"config OK (model default: {cfg.model.model})"


def check_model_resolves(cfg: Config) -> tuple[bool, str]:
    mc = cfg.model
    if not mc.model:
        return False, "model kosong di config"
    from dhybrid.llm.providers import make_client
    try:
        make_client(mc)
        return True, f"model OK: {mc.model} (via {mc.provider})"
    except ValueError as e:
        return False, f"provider tidak dikenal: {e}"


def check_workspace_writable(cfg: Config) -> tuple[bool, str]:
    try:
        cfg.workspace.mkdir(parents=True, exist_ok=True)
        probe = cfg.workspace / ".doctor-probe"
        probe.write_text("x")
        probe.unlink()
        return True, f"workspace writable: {cfg.workspace}"
    except OSError as e:
        return False, f"workspace tidak writable: {e}"


def key_status() -> list[tuple[str, bool]]:
    from dhybrid.ui.commands import PROVIDERS
    return [(name, bool(os.environ.get(env))) for name, env in PROVIDERS]


def check_endpoint(base_url: str, timeout: int = 5) -> tuple[bool, str]:
    import httpx
    try:
        r = httpx.get(f"{base_url}/models", timeout=timeout)
        ok = r.status_code == 200
        return ok, f"GET {base_url}/models -> HTTP {r.status_code}"
    except Exception as e:  # noqa: BLE001
        return False, f"{base_url}: {type(e).__name__}: {e}"


def check_update() -> tuple[bool, str]:
    try:
        from dhybrid.updater import update_available
        if update_available():
            return False, "update tersedia — jalankan: dhybrid self-update"
        return True, "sudah versi terbaru"
    except Exception as e:  # noqa: BLE001
        return False, f"cek update gagal: {e}"


def run_doctor(cfg: Config, offline: bool = False) -> int:
    """Jalankan semua cek; return exit code (0 = sehat, 1 = ada masalah)."""
    checks = [
        ("python", check_python()),
        ("config", check_config(cfg)),
        ("model", check_model_resolves(cfg)),
        ("workspace", check_workspace_writable(cfg)),
    ]
    if not offline and cfg.model.base_url:
        checks.append(("koneksi", check_endpoint(cfg.model.base_url)))
    checks.append(("update", check_update()))

    for label, (ok, msg) in checks:
        mark = OK if ok else FAIL
        color = "\x1b[32m" if ok else "\x1b[31m"
        reset = "\x1b[0m" if os.isatty(1) else ""
        print(f"[{color}{mark}{reset}] {label:<10} {msg}")

    print("\nAPI key:")
    for name, ok in key_status():
        mark = OK if ok else FAIL
        print(f"  {mark} {name}")

    return 0 if all(ok for ok, _ in checks) else 1
