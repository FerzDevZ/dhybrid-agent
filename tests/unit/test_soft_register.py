"""Task 1: infrastruktur soft-register tool power (dependency opsional).

- dep tidak terpasang → tool terdaftar sebagai stub dengan pesan install ramah
- dep terpasang → fn sungguhan dipakai
- modul tool yang belum ada → di-skip tanpa crash
"""
from dhybrid.tools import soft
from dhybrid.tools.registry import ToolRegistry


def test_import_any_returns_none_when_missing():
    assert soft._import_any(["mod.tidak.ada"]) is None


def test_import_any_returns_module_when_present():
    assert soft._import_any(["os", "mod.tidak.ada"]) is not None


def test_need_registers_friendly_stub_when_dep_missing(monkeypatch):
    reg = ToolRegistry()
    monkeypatch.setattr(soft, "_import_any", lambda mods: None)
    soft._need(reg, "data_query", ["duckdb"], "SQL read-only", {}, lambda: "real")
    out = reg.execute("data_query", {"sql": "SELECT 1"})
    assert "duckdb" in out and "pip install" in out


def test_need_registers_real_fn_when_dep_present(monkeypatch):
    reg = ToolRegistry()
    monkeypatch.setattr(soft, "_import_any", lambda mods: object())
    soft._need(reg, "sys_info", ["psutil"], "kesehatan sistem", {}, lambda: "OK real")
    assert reg.execute("sys_info", {}) == "OK real"


def test_register_does_not_crash_without_power_modules():
    # bila modul power_* belum ada, register() harus diam-diam melewatinya
    reg = ToolRegistry()
    soft.register(reg)
    assert isinstance({s["name"] for s in reg.specs()}, set)
