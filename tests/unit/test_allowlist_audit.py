"""Audit 2026-08-06: regresi gating allowlist (pitfall #2).

Memastikan:
1. Setiap tool yang terdaftar di registry build_tools HARUS ada di allowlist
   config/default.yaml -> kalau tidak, agent tak bisa memanggilnya sementara test hijau.
2. Tool `orchestrator` hanya muncul bila client_factory tersedia (bukan dead-entry).
"""
from dhybrid.config import Config
from dhybrid.tools import build_tools


def test_semua_tool_terdaftar_harus_di_allowlist():
    """Tool yang terdaftar di registry TIDAK boleh absen dari allowlist."""
    cfg = Config.load("config/default.yaml")
    reg = build_tools(cfg, client_factory=lambda *a, **k: None)
    allow = set(cfg.tool.get("allowlist", []))
    registered = set(reg._tools.keys())

    missing = sorted(registered - allow)
    assert not missing, (
        "Tool terdaftar tapi absen dari allowlist (agent tak bisa memanggil): "
        f"{missing}"
    )


def test_tool_tambahan_new_fix_di_allowlist():
    """Tool yang baru ditambahkan harus eksplisit di allowlist default."""
    cfg = Config.load("config/default.yaml")
    allow = set(cfg.tool.get("allowlist", []))
    for n in ("todo_clear", "cargo_outdated",
              "episodic_remember", "episodic_recall",
              "episodic_recent", "episodic_forget"):
        assert n in allow, f"{n} tidak ada di allowlist"


def test_orchestrator_hadir_hanya_jika_client_factory():
    """orchestrator TIDAK boleh jadi dead-entry saat client_factory tersedia."""
    cfg = Config.load("config/default.yaml")

    rg_no = build_tools(cfg)
    assert "orchestrator" not in rg_no._tools, "tanpa client_factory tak perlu"

    rg_yes = build_tools(cfg, client_factory=lambda *a, **k: None)
    assert "orchestrator" in rg_yes._tools, "dengan client_factory harus terdaftar"