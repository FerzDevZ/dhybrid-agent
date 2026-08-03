"""Task 3: tool sys_info — kesehatan sistem via psutil."""
from dhybrid.tools import power_sys
from dhybrid.tools.registry import ToolRegistry


def test_sys_info_basic(monkeypatch):
    calls = {}

    def fake_virtual_memory():
        calls["vm"] = True
        return type("V", (), {"percent": 42.0, "available": 1 << 30})()

    monkeypatch.setattr(power_sys.psutil, "virtual_memory", fake_virtual_memory)
    monkeypatch.setattr(power_sys.psutil, "cpu_percent", lambda *a, **k: 12.5)
    monkeypatch.setattr(power_sys.psutil, "cpu_count", lambda: 8)
    monkeypatch.setattr(
        power_sys.psutil, "disk_usage", lambda p: type("D", (), {"percent": 55.0})()
    )
    monkeypatch.setattr(power_sys.psutil, "pids", lambda: list(range(99)))
    out = power_sys._sys_info()
    assert "CPU" in out and "RAM" in out and "42" in out and "55" in out


def test_sys_info_registers(monkeypatch):
    reg = ToolRegistry()
    power_sys.register(reg, _need=lambda reg, n, m, d, p, f, **k: reg.register(n, d, p, f))
    names = {s["name"] for s in reg.specs()}
    assert "sys_info" in names
    out = reg.execute("sys_info", {})
    assert not out.startswith("ERROR")
