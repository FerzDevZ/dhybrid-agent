import http.server
import sys
import threading
from pathlib import Path

from dhybrid.tools.registry import ToolRegistry
from dhybrid.tools.web import web_fetch


def _serve(tmp_path):
    (tmp_path / "index.html").write_text(
        "<html><head><title>Halaman Test</title></head><body>"
        "<h1>Judul</h1><p>Ini <b>teks penting</b> untuk diuji.</p>"
        "<script>alert('skip');</script></body></html>"
    )
    handler = lambda *a, **kw: http.server.SimpleHTTPRequestHandler(*a, directory=str(tmp_path), **kw)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv


def test_web_fetch_clean_text(tmp_path):
    srv = _serve(tmp_path)
    try:
        port = srv.server_address[1]
        out = web_fetch(f"http://127.0.0.1:{port}/index.html")
    finally:
        srv.shutdown()
    assert "Halaman Test" in out          # title
    assert "Judul" in out
    assert "teks penting" in out
    assert "<script>" not in out          # markup dibuang
    assert "alert" not in out


def test_web_fetch_invalid_url():
    out = web_fetch("ftp://x")
    assert "ERROR" in out


def test_web_fetch_timeout_cap(tmp_path):
    srv = _serve(tmp_path)
    try:
        port = srv.server_address[1]
        out = web_fetch(f"http://127.0.0.1:{port}/index.html", max_chars=30)
    finally:
        srv.shutdown()
    assert "truncated" in out


def test_mcp_tools_registered():
    """Fake MCP server (stdio) → tool mcp_* muncul di registry & bisa dipanggil."""
    from dhybrid.tools.mcp import register

    reg = ToolRegistry(allowlist=None)  # allowlist kosong = semua boleh
    servers = [{"name": "fake", "command": sys.executable, "args": [str(Path(__file__).parent / "fake_mcp_server.py")]}]
    register(reg, servers=servers)
    names = [s["name"] for s in reg.specs()]
    assert "mcp_fake_echo" in names
    out = reg.execute("mcp_fake_echo", {"text": "halo"})
    assert out == "echo:halo"
