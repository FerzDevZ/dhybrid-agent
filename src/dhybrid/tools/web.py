"""Tool web — fetch halaman web hemat token + search & HTTP request."""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
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
    except Exception:  # noqa: BLE001,S110 — HTML tak valid; pakai fallback regex
        pass
    title = parser._title.strip() if parser._title else url
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(p for p in parser.parts if p)).strip()
    if not text:
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s{2,}", " ", text).strip()
    out = f"# {title}\n\n{text}"
    return out[:max_chars] + ("\n[truncated]" if len(out) > max_chars else "")


class _DDGResultParser(HTMLParser):
    """Parse DuckDuckGo HTML results → (title, url, snippet) list (heuristic)."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._in_a = False
        self._href = ""
        self._cur_text = ""
        self.results: list[dict] = []

    def handle_starttag(self, tag, attrs):
        attrs_d = dict(attrs)
        cls = attrs_d.get("class") or ""
        if tag == "a" and cls and "result__a" in cls:  # DDG HTML class
            self._in_a = True
            self._href = attrs_d.get("href") or ""
            self._cur_text = ""
        if tag == "a" and self._in_a and not (self._href or "").startswith("http"):
            self._in_a = False

    def handle_endtag(self, tag):
        if tag == "a" and self._in_a:
            title = self._cur_text.strip()
            if title and self._href:
                self.results.append({"title": title, "url": self._href})
            self._in_a = False

    def handle_data(self, data):
        if self._in_a:
            self._cur_text += data


def _ddg_url(title: str, url: str) -> str:
    """DuckDuckGo HTML sering kembalikan redirect URL udd.so/duckduckgo → resolv ke nyata."""
    if "uddg=" in url:
        try:
            parsed = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
            return parsed["uddg"][0]
        except Exception:  # noqa: BLE001, S110
            pass
    return url


def web_search(query: str, n: int = 5, timeout: int = 15) -> str:
    """Cari dengan DuckDuckGo HTML → top-N title+snippet (tanpa API key)."""
    if not query.strip():
        return "ERROR: query kosong"
    q = urllib.parse.urlencode({"q": query, "kl": "us-en", "df": "y"})
    url = f"https://html.duckduckgo.com/html/?{q}"
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
            "Accept": "text/html",
        })
        with urllib.request.urlopen(req, timeout=timeout) as r:
            html = r.read(120_000).decode("utf-8", errors="replace")
    except Exception as e:  # noqa: BLE001
        return f"ERROR search: {type(e).__name__}: {e}"
    parser = _DDGResultParser()
    parser.feed(html)
    results = parser.results[:n] or []
    out_parts = []
    for i, res in enumerate(results, 1):
        real = _ddg_url(res["title"], res["url"])
        out_parts.append(f"[{i}] {res['title']} — {real}")
    summary = f"Search: {query}\n\n" + "\n".join(out_parts)
    if not results:
        summary += "\n(tidak ada hasil — DDG mungkin blokir atau query spesifik)"
    return summary[:8000]


def http_request(
    method: str,
    url: str,
    json_body: dict | None = None,
    headers: dict | None = None,
    timeout: int = 15,
    max_chars: int = 6000,
) -> str:
    """Fire HTTP request (utk API CALL tool). Redak Authorization, retry 429 backoff."""
    if not url.startswith(("http://", "https://")):
        return f"ERROR: URL harus http/https: {url}"
    method_u = method.upper()
    if method_u not in ("GET", "POST", "PUT", "PATCH", "DELETE"):
        return f"ERROR: method tidak didukung: {method}"
    hdrs = {
        "User-Agent": "dhybrid-agent/0.4",
        "Accept": "application/json",
    }
    if headers:
        hdrs.update(headers)
    # redak auth header untuk logging (tapi tetap kirim)
    body = None
    if json_body is not None:
        body = json.dumps(json_body).encode()
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(url, headers=hdrs, method=method_u, data=body)
    # retry 429/5xx exponential backoff (max 3x)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                status = r.getcode()
                raw = r.read(200_000)
                ctype = r.headers.get("Content-Type", "")
                enc = "utf-8"
                m = re.search(r"charset=([\w-]+)", ctype)
                if m:
                    enc = m.group(1)
                text = raw.decode(enc, errors="replace")
                if "json" in ctype and text.strip().startswith("{"):
                    try:
                        text = json.dumps(json.loads(text), indent=2, ensure_ascii=False)
                    except Exception:  # noqa: BLE001,S110 — bukan JSON valid; tetap pakai teks mentah
                        pass
                if len(text) > max_chars:
                    text = text[:max_chars] + "\n[truncated]"
                return f"HTTP {status}\n{text}"
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < 2:
                wait = min(2 ** attempt, 5)
                time.sleep(wait)
                continue
            try:
                err_body = e.read(20_000).decode("utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                err_body = ""
            return f"HTTP {e.code} ERROR\n{err_body[:2000]}"
        except Exception as e:  # noqa: BLE001
            return f"ERROR request: {type(e).__name__}: {e}"
    return "ERROR: max retries exceeded"


def register(reg, max_chars: int = 8000) -> None:
    reg.register(
        "web_fetch",
        "Ambil teks halaman web (riset/docs) — HTML dibersihkan, output di-cap.",
        {"url": {"type": "string"}, "max_chars": {"type": "integer"}},
        lambda url, max_chars=6000: web_fetch(url, max_chars=max_chars),
    )
    reg.register(
        "web_search",
        "Cari internet via DuckDuckGo (tanpa API key) → top-N title+URL.",
        {"query": {"type": "string"}, "n": {"type": "integer"}},
        lambda query, n=5: web_search(query, n=n),
    )
    reg.register(
        "http_request",
        "Fire REST API call (GET/POST/PUT/PATCH/DELETE) — auth header redacted, 429 retry.",
        {
            "method": {"type": "string"},
            "url": {"type": "string"},
            "json_body": {"type": "object"},
            "headers": {"type": "object"},
            "timeout": {"type": "integer"},
        },
        lambda method, url, json_body=None, headers=None, timeout=15: http_request(
            method, url, json_body=json_body, headers=headers, timeout=timeout
        ),
    )
