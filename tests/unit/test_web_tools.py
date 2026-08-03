"""Unit test web_search & http_request (register, redaksi, error handling, retry)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from dhybrid.tools.registry import ToolRegistry
from dhybrid.tools.web import http_request, register, web_search


def test_register_adds_web_tools():
    reg = ToolRegistry()
    register(reg)
    names = {s["name"] for s in reg.specs()}
    assert "web_fetch" in names
    assert "web_search" in names
    assert "http_request" in names


def test_web_search_empty_query():
    assert http_request("", "https://example.com")  # tidak crash
    assert "ERROR" in web_search("")


def test_http_request_invalid_url_scheme():
    out = http_request("GET", "ftp://bad")
    assert "ERROR" in out and "http" in out


def test_http_request_unsupported_method():
    out = http_request("TRACE", "https://example.com")
    assert "ERROR" in out and "tidak didukung" in out


def test_http_request_auth_header_not_leaked(monkeypatch, capsys):
    """Pastikan http_request tidak me-return token auth ke output mentah.

    httpbin mungkin echo header, tapi tool kita harus redak di path kita.
    Di sini kita mock urlopen supaya tidak butuh jaringan.
    """
    import urllib.request as u
    captured = {}

    class FakeResp:
        def __init__(self):
            self._sent_header = None

        def read(self, n=-1):
            return b'{"ok": true}'
        def getcode(self):
            return 200
        @property
        def headers(self):
            class H:
                def get(self, k, d=""):
                    return "application/json" if k == "Content-Type" else d
            return H()

    def fake_urlopen(req, timeout=0):
        captured["req"] = req
        captured["sent_headers"] = dict(req.headers)
        return FakeResp()

    # FakeResp perlu support context manager
    FakeResp.__enter__ = lambda self: self
    FakeResp.__exit__ = lambda self, *a: False

    monkeypatch.setattr(u, "urlopen", fake_urlopen)
    out = http_request("GET", "https://api.example.com/x", headers={"Authorization": "Bearer SANGAT-RAHASIA"})
    # output hasilnya tidak mengandung token mentah
    assert "SANGAT-RAHASIA" not in out
    # header tetap dikirim (redaksi = di output/log, bukan di pengiriman)
    assert captured["sent_headers"].get("Authorization") == "Bearer SANGAT-RAHASIA"


def test_http_request_retries_on_429(monkeypatch):
    """429 harus retry (up to 3x), 5xx juga di-retry."""
    import urllib.error
    import urllib.request as u

    attempts = {"n": 0}

    class Http429(urllib.error.HTTPError):
        def __init__(self):
            super().__init__(url="x", code=429, msg="Too Many", hdrs={}, fp=None)

    def fake_urlopen(req, timeout=0):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise Http429()
        # success ke-3
        class R:
            def read(self, n=-1): return b'{"done": true}'
            def getcode(self): return 200
            class headers:
                @staticmethod
                def get(k, d=""): return "application/json" if k=="Content-Type" else d
            def __enter__(self): return self
            def __exit__(self, *a): return False
        return R()

    monkeypatch.setattr(u, "urlopen", fake_urlopen)
    monkeypatch.setattr("dhybrid.tools.web.time.sleep", lambda x: None)
    out = http_request("GET", "https://api.example.com/x")
    assert attempts["n"] == 3  # retry sampai success
    assert "HTTP 200" in out


def test_http_request_truncates_large(monkeypatch):
    import urllib.request as u

    class R:
        def read(self, n=-1): return (b"x" * 7000)
        def getcode(self): return 200
        class headers:
            @staticmethod
            def get(k, d=""): return "application/json" if k=="Content-Type" else d
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(u, "urlopen", lambda req, timeout=0: R())
    out = http_request("GET", "https://api.example.com/x", max_chars=100)
    assert "[truncated]" in out
    assert len(out) < 100 + 50


def test_registry_execute_dispatches():
    reg = ToolRegistry()  # allowlist kosong = semua terpilih
    register(reg)
    # web_search empty → error msg via execute
    result = reg.execute("web_search", {"query": ""})
    assert isinstance(result, str) and len(result) > 0
