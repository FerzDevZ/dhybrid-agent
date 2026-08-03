"""Task 2: extra `power` — wiring build_tools + allowlist default 36."""
from dhybrid.config import Config
from dhybrid.tools import build_tools

POWER_TOOLS = ("sys_info", "scaffold", "data_query", "pdf_ops", "xlsx_edit")


def test_allowlist_default_memuat_tool_power():
    cfg = Config.load("config/default.yaml")
    allow = cfg.tool.get("allowlist", [])
    for n in POWER_TOOLS:
        assert n in allow, f"{n} tidak ada di allowlist default"


def test_build_tools_memanggil_soft_register(tmp_path, monkeypatch):
    calls = []

    from dhybrid.tools import soft

    monkeypatch.setattr(soft, "register", lambda reg, max_chars=8000: calls.append("soft"))
    cfg = Config.load("config/default.yaml")
    cfg.workspace = tmp_path
    reg = build_tools(cfg)
    assert calls == ["soft"]
    assert reg.allowlist  # allowlist terpasang
