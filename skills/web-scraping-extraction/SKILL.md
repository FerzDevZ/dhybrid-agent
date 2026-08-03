---
name: web-scraping-extraction
description: Extract structured data from web pages via curl + CSS selectors (scraping, price/news monitoring)
---

# Web Scraping / Extraction Skill

Extract structured data (price, headline, table rows, JSON-LD) from specific pages
for price monitoring, news tracking, or data collection. Uses `curl` + CSS-selector
extraction (no headless browser needed for static pages).

## Mechanism (see `src/dhybrid/tools/search.py` + `web_extract` in `src/dhybrid/tools/web.py`)

- **Static first** — `curl -sL --compressed -A "<UA>" <url>` → parse HTML.
- **Selector extraction** — `python -c "..."` or `execute_code` with `selectolax`/`lxml`
  to pull `soup.select(<css>)` → list of text/attrs.
- **Structured output** — emit JSON list, one item per match (capped 200 items).
- **Fallback** — if JS-render needed (no static HTML), route to `browser_navigate`/`web_extract`
  (CDP) and snapshot after load.

## Policies

1. **Respect robots.txt** — `curl -s https://site/robots.txt` dulu; skip jika `Disallow`
   melarang. Jangan scrape endpoint yang dilarang.
2. **Rate limit soft per-host** — 2 req/s default; sleep between requests.
3. **No login bypass** — hanya scrape publik; jika butuh auth, gunakan cookie env
   (`SCRAPE_COOKIE`) yang diset user secara eksplisit.
4. **User-Agent real** — kirim UA browser wajar; jangan `curl/*` default (discriminatory).
5. **Output structured, not raw HTML** — selalu ekstrak ke list of dict / CSV, jangan
   kirim HTML mentah ke model (boros token).

## Commands (REPL / tool)

- `/scrape url <url> "<css_selector>"` — extract text of matching elements → JSON.
- `/scrape table <url> [<table_selector>]` — parse `<table>` ke list of dict (header row keys).
- `/scrape json <url>` — cari dan parse `<script type="application/ld+json">` → dict.
- `/scrape monitor <url> "<selector>" --every 1h` — schedule re-scrape (cronjob).
- `/scrape to csv/json <url> "<selector>"` — save hasil ke file (via `write_file`).

## Recommended selectors (contoh)

- Harga: `.price`, `[itemprop=price]`, `#priceblock_ourprice`
- Headline: `h1`, `.title`, `[class*=headline]`
- Tabel: `table tr` (header → `th`, row → `td`)
- JSON-LD: `script[type="application/ld+json"]`

## Lazy pattern (token savings)

- Cache hasil scrape 10 min keyed by `(url, selector, modified-since header)` —
  reuse, note `[cached]`. Untuk price monitoring, cek `Last-Modified`/`ETag` dulu
  sebelum re-download.
- Truncate hasil ke 50 item / 4KB; `[full]` on demand.
- Jika `selectolax` tidak install → fallback `regex` sederhana (kurang robust, catat warning).

## Trigger

User sebut: "scrape", "ambil harga", "monitoring harga", "parsing tabel",
"ekstrak dari url", "news scraper", "<url>" langsung, class CSS seperti
".price", "table#".

## Verification

- [ ] `/scrape url <url> "h1"` → list string (bukan HTML mentah).
- [ ] `/scrape table <url>` → list of dict (key=header).
- [ ] `/scrape json <url>` → dict parsed (atau pesan "no JSON-LD found").
- [ ] robots.txt dicek; `Disallow`-disallow host dilewati.
- [ ] hasil dipotong 50 item/4KB; cache reusable selama 10 min.
