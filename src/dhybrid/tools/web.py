"""Tool web — fetch halaman web hemat token (ekstrak teks, bukan HTML mentah)."""

from __future__ import annotations

import re
import urllib.request
from html.parser import HTMLParser

TEXT_TAGS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "pre", "code", "td", "th", "blockquote"}


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0
        self._title = ""

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self._skip += 1
        if tag == "title" and not self._title:
            self._title = ""

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self._skip:
            self._skip -= 1
        if tag in TEXT_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if self._skip:
            return
        if self.parts and self.parts[-1].endswith("\n"):
            self.parts.append(data.strip())
        else:
            self.parts.append(data.strip())


def web_fetch(url: str, max_chars: int = 6000, timeout: int = 15) -> str:
    """Fetch URL → teks bersih (tanpa markup). Cap output untuk hemat token."""
    if not url.startswith(("http://", "https://")):
        return f"ERROR: URL harus http/https: {url}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "dhybrid-agent/0.3"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read(200_000)  # batas 200KB
            ctype = r.headers.get("Content-Type", "")
            enc = "utf-8"
            m = re.search(r"charset=([\w-]+)", ctype)
            if m:
                enc = m.group(1)
            html = raw.decode(enc, errors="replace")
    except Exception as e:  # noqa: BLE001
        return f"ERROR fetch {url}: {type(e).__name__}: {e}"

    parser = _TextExtractor()
    try:
        parser.feed(html)
    except Exception:  # noqa: BLE001, S110
        pass
    title = parser._title.strip() if parser._title else url
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(p for p in parser.parts if p)).strip()
    if not text:
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s{2,}", " ", text).strip()
    out = f"# {title}\n\n{text}"
    return out[:max_chars] + ("\n[truncated]" if len(out) > max_chars else "")


def register(reg, max_chars: int = 8000) -> None:
    reg.register(
        "web_fetch",
        "Ambil teks halaman web (riset/docs) — HTML dibersihkan, output di-cap.",
        {"url": {"type": "string"}, "max_chars": {"type": "integer"}},
        lambda url, max_chars=6000: web_fetch(url, max_chars=max_chars),
    )
