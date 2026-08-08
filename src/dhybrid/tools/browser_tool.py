"""Tool browser — E2E web via Playwright (opsional, extra `e2e`).

Model bisa membuka halaman, klik, isi form, dan ambil snapshot teks halaman
untuk memverifikasi web yang sedang dikerjakan (mis. app Laravel lokal).
Hemat token: snapshot = teks saja (tanpa HTML/markup).

Kalau playwright/chromium belum terinstall → pesan error ramah + instruksi,
bukan crash.
"""

from __future__ import annotations

import re

_INSTALL_HINT = (
    "playwright belum siap — jalankan: "
    "pip install playwright && python3 -m playwright install chromium"
)

# state sesi: browser & page dipertahankan antar panggilan (satu tab aktif)
_LAUNCHED: dict = {"pw": None, "browser": None, "page": None}


def _require():
    try:
        from playwright.sync_api import sync_playwright

        return sync_playwright
    except ImportError as e:
        raise RuntimeError(_INSTALL_HINT) from e


def _ensure_page(sp):
    if _LAUNCHED["page"] is None:
        pw = sp().start()  # PlaywrightContextManager.start() → objek Playwright
        _LAUNCHED["pw"] = pw
        _LAUNCHED["browser"] = pw.chromium.launch(headless=True)
        _LAUNCHED["page"] = _LAUNCHED["browser"].new_page()
    return _LAUNCHED["page"]


def _text_of(page, max_chars: int = 8000) -> str:
    """Teks halaman yang bisa dibaca (bukan HTML) — cap untuk hemat token."""
    try:
        body = page.inner_text("body")
    except Exception:  # noqa: BLE001 — halaman kosong/iframe
        body = ""
    body = re.sub(r"[ \t]+", " ", body)
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    if len(body) > max_chars:
        body = body[:max_chars] + f"\n…[terpotong, {len(body)} char]"
    return body


def browser(action: str = "navigate", url: str = "", selector: str = "", text: str = "") -> str:
    """Browser headless: navigate / click / type / snapshot / close.

    action:
      navigate — buka url (wajib http/https)
      click    — klik elemen (selector CSS)
      type     — isi field (selector CSS + text)
      snapshot — ambil teks halaman saat ini
      close    — tutup browser (reset state)
    """
    try:
        sp = _require()
    except RuntimeError as e:
        return f"ERROR: {e}"

    action = (action or "navigate").strip().lower()
    try:
        if action == "close":
            if _LAUNCHED["browser"]:
                try:
                    _LAUNCHED["browser"].close()
                except Exception:  # noqa: BLE001,S110 — browser mungkin sudah mati
                    pass
                pw = _LAUNCHED.get("pw")
                if pw is not None:
                    try:
                        pw.stop()
                    except Exception:  # noqa: BLE001,S110
                        pass
                _LAUNCHED.update(pw=None, browser=None, page=None)
                return "browser ditutup"
            return "browser tidak sedang terbuka"

        if action == "navigate":
            if not url.startswith(("http://", "https://")):
                return "ERROR: url harus diawali http:// atau https://"
            page = _ensure_page(sp)
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            try:
                page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:  # noqa: BLE001,S110 — networkidle tak wajib
                pass
            return f"OK: {page.title()} — {page.url}"

        if action == "click":
            if not selector:
                return "ERROR: click butuh selector (mis. 'button#login')"
            page = _ensure_page(sp)
            page.click(selector, timeout=15000)
            return f"OK: klik {selector}"

        if action == "type":
            if not selector or not text:
                return "ERROR: type butuh selector + text"
            page = _ensure_page(sp)
            page.fill(selector, text)
            return f"OK: isi {selector}"

        if action == "snapshot":
            page = _ensure_page(sp)
            body = _text_of(page)
            return f"# {page.title()}\n{page.url}\n\n{body}" if body else f"# {page.title()}\n{page.url}"

        return f"ERROR: action tak dikenal '{action}' — pilih navigate/click/type/snapshot/close"
    except Exception as e:  # noqa: BLE001 — error playwright jadi pesan tool
        return f"ERROR browser {action}: {type(e).__name__}: {e}"


def register(reg) -> None:
    reg.register(
        "browser",
        "Browser headless (Playwright): navigate/click/type/snapshot untuk verifikasi web E2E.",
        {
            "action": {"type": "string", "required": True},
            "url": {"type": "string"},
            "selector": {"type": "string"},
            "text": {"type": "string"},
        },
        browser,
    )
