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


def check_chain(cfg: Config) -> tuple[bool, str]:
    """Cek rantai eskalasi: preset chain yang bisa di-resolve vs yang mati.

    Preset yang key-nya kosong / provider tak dikenal dianggap mati — kalau
    semua mati dan model utama error, agent tidak punya jalan keluar."""
    chain = cfg.model.chain or []
    if not chain:
        return True, "chain kosong (tidak ada eskalasi)"
    from dhybrid.llm.providers import make_client
    from dhybrid.llm.registry import ModelRegistry

    reg = ModelRegistry(cfg)
    alive, dead = [], []
    for preset in chain:
        try:
            make_client(reg.resolve(preset))
            alive.append(preset)
        except (ValueError, KeyError) as e:
            dead.append(f"{preset}({e})")
    msg = f"chain {len(alive)}/{len(chain)} hidup"
    if dead:
        msg += f" — mati: {', '.join(dead)}"
    return bool(alive), msg


def check_allowlist(cfg: Config) -> tuple[bool, str]:
    """Cek allowlist tool: tool inti yang terdaftar tapi tidak diizinkan
    akan ERROR saat dipanggil — bug klasik (web_search dulu keblokir)."""
    allow = cfg.tool.get("allowlist")
    if allow is None:
        return True, "allowlist kosong (semua tool aktif)"
    core = {"terminal", "read_file", "write_file", "apply_patch", "grep",
            "find_files", "run_tests", "git_status", "git_diff", "git_commit"}
    blocked = sorted(core - set(allow))
    if blocked:
        return False, f"tool inti KEBLOKIR: {', '.join(blocked)}"
    return True, f"allowlist OK ({len(allow)} tool)"


def check_skills(cfg: Config) -> tuple[bool, str]:
    """Hitung skill bawaan vs workspace — skill sampah di workspace (yang
    di-generate otomatis dari prompt receh) bisa mengotori matching."""
    from dhybrid.skills.loader import list_skills
    from dhybrid.updater import install_dir

    repo = len(list_skills(install_dir() / "skills"))
    ws_dir = cfg.workspace / "skills"
    ws = len(list(list_skills(ws_dir)))
    msg = f"{repo} skill bawaan, {ws} skill workspace"
    if ws >= 5:
        msg += " — banyak skill workspace: cek /skill ls (mungkin sampah)"
        return False, msg
    return True, msg


def run_doctor(cfg: Config, offline: bool = False) -> int:
    """Jalankan semua cek; return exit code (0 = sehat, 1 = ada masalah)."""
    checks = [
        ("python", check_python()),
        ("config", check_config(cfg)),
        ("model", check_model_resolves(cfg)),
        ("chain", check_chain(cfg)),
        ("allowlist", check_allowlist(cfg)),
        ("skills", check_skills(cfg)),
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
