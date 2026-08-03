"""Test tool browser (Playwright) — E2E web terhadap server HTTP lokal.

Skip otomatis bila playwright/chromium tidak tersedia (extra `e2e`)."""

import http.server
import threading

import pytest

pytest.importorskip("playwright")

from dhybrid.tools.browser_tool import browser

HTML = """<!doctype html><html><head><title>Test Page</title></head><body>
<h1>Judul Halaman</h1>
<form><input id="nama" placeholder="nama"><button id="tombol" type="button">Kirim</button></form>
<p id="hasil">placeholder</p>
<script>
document.getElementById("tombol").addEventListener("click", () => {
  document.getElementById("hasil").textContent =
    "diklik: " + document.getElementById("nama").value;
});
</script>
</body></html>"""


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = HTML.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


@pytest.fixture(scope="module")
def chromium_ok():
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            p.chromium.launch(headless=True).close()
    except Exception:  # noqa: BLE001
        pytest.skip("chromium belum terinstall (python3 -m playwright install chromium)")
    return True


@pytest.fixture(scope="module")
def srv():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    browser("close")  # bersihkan state browser sesi


def test_browser_navigate_snapshot(srv, chromium_ok):
    out = browser("navigate", url=srv + "/")
    assert out.startswith("OK: Test Page"), out
    snap = browser("snapshot")
    assert "Judul Halaman" in snap
    assert "Test Page" in snap


def test_browser_click_type_flow(srv, chromium_ok):
    browser("navigate", url=srv + "/")
    assert "OK: isi" in browser("type", selector="#nama", text="Budi")
    assert "OK: klik" in browser("click", selector="#tombol")
    snap = browser("snapshot")
    assert "diklik: Budi" in snap


def test_browser_close_idempotent(srv, chromium_ok):
    assert "ditutup" in browser("close")
    assert "tidak sedang terbuka" in browser("close")


def test_browser_rejects_bad_url(chromium_ok):
    out = browser("navigate", url="ftp://x")
    assert "ERROR" in out


def test_browser_unknown_action(chromium_ok):
    assert "tak dikenal" in browser(action="hack", url="x")
