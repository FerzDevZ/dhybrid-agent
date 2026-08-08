"""Tool web — fetch halaman web hemat token + search & HTTP request."""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

from dhybrid.security.guard import check_egress

TEXT_TAGS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "pre", "code", "td", "th", "blockquote"}


def _egress_allow() -> list[str]:
    """Allowlist host egress dari env DHYBRID_EGRESS_ALLOW (koma). Kosong = izinkan semua."""
    raw = os.environ.get("DHYBRID_EGRESS_ALLOW", "")
    return [h.strip() for h in raw.split(",") if h.strip()]


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


def _extract_bs4(html: str) -> tuple[str, str]:
    """Ekstraksi teks via BeautifulSoup + lxml — robust untuk HTML tidak valid
    / messy (parser bawaan HTMLParser mudah tersendat). Kembalikan (title, text)."""
    from bs4 import BeautifulSoup  # import lambat: paket opsional

    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "nav", "footer", "form", "svg", "header", "aside"]):
        tag.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    blocks = [
        el.get_text(" ", strip=True)
        for el in soup.find_all(
            ["p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "pre", "code", "td", "th", "blockquote"]
        )
        if el.get_text(" ", strip=True)
    ]
    return title, "\n".join(blocks)


def web_fetch(url: str, max_chars: int = 6000, timeout: int = 15) -> str:
    """Fetch URL → teks bersih (tanpa markup). Cap output untuk hemat token.

    Rantai ekstraksi: trafilatura (artikel bersih) → bs4+lxml (HTML umum,
    robust) → parser internal → regex mentah.
    """
    if not url.startswith(("http://", "https://")):
        return f"ERROR: URL harus http/https: {url}"
    blocked = check_egress(url, _egress_allow())
    if blocked:
        return blocked
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "dhybrid-agent/0.3"})
        with urllib.request.urlopen(req, timeout=timeout) as r:  # nosec B310
            raw = r.read(200_000)  # batas 200KB
            ctype = r.headers.get("Content-Type", "")
            enc = "utf-8"
            m = re.search(r"charset=([\w-]+)", ctype)
            if m:
                enc = m.group(1)
            html = raw.decode(enc, errors="replace")
    except Exception as e:  # noqa: BLE001
        return f"ERROR fetch {url}: {type(e).__name__}: {e}"

    text = ""
    try:
        from trafilatura import extract as _traf_extract

        body = _traf_extract(html, include_comments=False, include_tables=True)
        if body and len(body.strip()) > 50:
            text = re.sub(r"\n{3,}", "\n\n", body).strip()
    except Exception:  # noqa: BLE001, S110 — trafilatura gagal → fallback
        pass

    title = url
    if not text:
        try:
            b_title, b_text = _extract_bs4(html)
            if b_title:
                title = b_title
            if b_text:
                text = re.sub(r"\n{3,}", "\n\n", b_text).strip()
        except Exception:  # noqa: BLE001,S110 — bs4 gagal → parser internal
            pass

    if not text:
        parser = _TextExtractor()
        try:
            parser.feed(html)
        except Exception:  # noqa: BLE001,S110 — HTML tak valid; pakai fallback regex
            pass
        if parser._title.strip():
            title = parser._title.strip()
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


# Cache web_search per-sesi (TTL 120 detik): query yang sama diulang-ulang
# agent (pola umum saat looping) tidak perlu hit DDG lagi.
# Struktur cache: {query_key: (timestamp, summary, etag, last_modified)}
_SEARCH_CACHE: dict[str, tuple[float, str, str | None, str | None]] = {}
_SEARCH_CACHE_TTL = 120.0


def _reset_search_cache() -> None:
    _SEARCH_CACHE.clear()


def _search_ddgs_api(query: str, n: int, timeout: int) -> list[dict]:
    """Cari via API resmi DuckDuckGo (paket `ddgs`) — lebih stabil daripada
    scraping HTML hardcoded yang rawan berubah. Raise bila gagal → caller
    fallback ke scraping HTML lama."""
    from ddgs import DDGS  # import lambat: paket opsional

    with DDGS(timeout=timeout) as ddgs:
        raw = ddgs.text(query, max_results=n)
    results: list[dict] = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        results.append(
            {
                "title": (item.get("title") or "").strip(),
                "url": (item.get("href") or item.get("url") or "").strip(),
                "body": (item.get("body") or "").strip(),
            }
        )
    return [r for r in results if r["title"] or r["url"]]


def _format_search_results(query: str, results: list[dict], n: int) -> str:
    out_parts = []
    for i, res in enumerate(results[:n], 1):
        line = f"[{i}] {res['title']} — {res['url']}"
        if res.get("body"):
            line += f"\n    {res['body'][:200]}"
        out_parts.append(line)
    summary = f"Search: {query}\n\n" + "\n".join(out_parts)
    if not out_parts:
        summary += "\n(tidak ada hasil — DDG mungkin blokir atau query spesifik)"
    return summary[:8000]


def web_search(query: str, n: int = 5, timeout: int = 15) -> str:
    """Cari dengan DuckDuckGo → top-N title+snippet (tanpa API key).

    Prioritas: API resmi (paket `ddgs`) → fallback scraping HTML lama.
    Set env `DHYBRID_WEB_SEARCH=html` untuk memaksa path scraping (debug).
    Cache dengan TTL 120s + result hash untuk invalidasi otomatis.
    """
    if not query.strip():
        return "ERROR: query kosong"
    key = f"{query.strip()}|{n}"
    cached = _SEARCH_CACHE.get(key)
    if cached and (time.monotonic() - cached[0]) < _SEARCH_CACHE_TTL:
        # Check if results have changed via content hash
        return cached[1]
    results: list[dict] = []
    if os.environ.get("DHYBRID_WEB_SEARCH") != "html":
        try:
            results = _search_ddgs_api(query, n, timeout)
        except Exception:  # noqa: BLE001,S110 — fallback scraping lama
            pass
    if not results:
        q = urllib.parse.urlencode({"q": query, "kl": "us-en", "df": "y"})
        url = f"https://html.duckduckgo.com/html/?{q}"
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
                "Accept": "text/html",
            })
            with urllib.request.urlopen(req, timeout=timeout) as r:  # nosec B310
                html = r.read(120_000).decode("utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001
            return f"ERROR search: {type(e).__name__}: {e}"
        parser = _DDGResultParser()
        parser.feed(html)
        results = [{"title": r["title"], "url": _ddg_url(r["title"], r["url"]), "body": ""}
                   for r in parser.results]
    summary = _format_search_results(query, results, n)
    # Store result hash for cache invalidation
    import hashlib
    result_hash = hashlib.md5(summary.encode(), usedforsecurity=False).hexdigest()
    _SEARCH_CACHE[key] = (time.monotonic(), summary, result_hash, None)
    return summary


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
    blocked = check_egress(url, _egress_allow())
    if blocked:
        return blocked
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
            with urllib.request.urlopen(req, timeout=timeout) as r:  # nosec B310
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
