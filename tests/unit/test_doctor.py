
from dhybrid.config import Config
from dhybrid.doctor import (
    check_config,
    check_endpoint,
    check_model_resolves,
    check_python,
    check_workspace_writable,
    key_status,
)


def test_checks_ok(tmp_path):
    cfg = Config.load("config/default.yaml")
    cfg.workspace = tmp_path
    assert check_python()[0] is True
    assert check_config(cfg)[0] is True
    assert check_model_resolves(cfg)[0] is True
    assert check_workspace_writable(cfg)[0] is True


def test_workspace_blocked_fails(tmp_path):
    cfg = Config()
    blocker = tmp_path / "block"
    blocker.write_text("x")
    cfg.workspace = blocker / "child"
    assert check_workspace_writable(cfg)[0] is False


def test_key_status_lists_providers(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    rows = key_status()
    names = [n for n, _ in rows]
    assert "OpenAI" in names and "OpenCode Zen (opsional, gratis)" in names
    openai_ok = dict(rows)["OpenAI"]
    assert openai_ok is False


def test_endpoint_ok(monkeypatch):
    import httpx

    def fake_get(url, **kw):
        return httpx.Response(200, json={"object": "list", "data": []}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    ok, msg = check_endpoint("https://x/v1")
    assert ok is True and "HTTP 200" in msg


def test_endpoint_error(monkeypatch):
    import httpx

    def fake_get(url, **kw):
        raise httpx.ConnectError("no route")

    monkeypatch.setattr(httpx, "get", fake_get)
    ok, msg = check_endpoint("https://x/v1")
    assert ok is False and "ConnectError" in msg
