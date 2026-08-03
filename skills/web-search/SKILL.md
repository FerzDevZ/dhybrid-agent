---
name: web-search
description: Real-time internet search, read articles & cite official sources (web-search + web-scraping)
---

# Web Search / Browsing Skill

Enables real-time information lookup, article reading, and source-backed answers —
not from model training data.

## Tools available (see `src/dhybrid/tools/web.py` + browser tool)

| Tool | Purpose |
|------|---------|
| `web_search` | DuckDuckGo HTML search → top-N result URLs + snippets. |
| `web_extract` | Fetch URL → readable text (strips nav/ads), plain markdown. |
| `browser_navigate` / `browser_click` / `browser_type` | Drive interactive pages (forms, JS) via CDP-backed browser. |
| *(future)* `serpapi`/`google` | Structured search when DDG is blocked. |

## Policies

1. **Question first** — always `web_search` before `web_extract`. One query per
   result-block (avoid flooding). If 0 good results → broaden query once, else bail.
2. **Extract + synthesize** — read 2-4 authoritative sources; don't dump raw text.
   Summarize in own words + cite `[n]` source.
3. **Source quality filter** — trust `.gov/.edu/.org` > news > forums > social.
   Skip results from link-farms / parked domains.
4. **Citation** — every factual claim → `[1]` etc. matching a real URL shown at reply end.
5. **No scraping paywalled content** — if paywall/403, note it; never bypass.

## Commands (REPL)

- `/web search <query>` — run a search, show 3 top URLs + snippet.
- `/web read <url>` — fetch + extract readable text (capped at ~8k chars).
- `/web answer "<question>"` — full search → read → synthesize with citations.
- `/web status` — show search provider used (DDG / SerpAPI / browser).

## Recommended flow for `dhybrid run "<q>"`

```
1. web_search(q, n=4)                # 1 search
2. for url in top2: web_extract(url)
3. llm.synthesize(system="answer from these passages, cite [n] sources")
4. append: Sources:\n- [1] url1\n- [2] url2
```

## Lazy pattern (token savings)

- If the question is answerable by existing context (file/grep), skip search entirely.
- If a prior `web_search` for same query exists in session, reuse (cache ~5 min,
  keyed by normalized query string — store via `memory` or a `/cache`).
- Truncate extracted articles to first 200 lines before synthesize (long tail
  rarely changes the answer & burns budget).

## Trigger keywords

"apa", "kapan", "apa artinya", "definisi", "berapa harga", "harga terbaru",
"berita", "update", "tutorial", "cara pakai", "referensi", "bukti", "cari di internet",
plus any domain ending in `.sh/.py/.dev/.md` → prefer raw file fetch over HTML.

## Verification

- [ ] `/web search` returns real URLs (not placeholder) for 3 different queries.
- [ ] `/web read <url>` strips nav/ads; output starts with the article heading.
- [ ] `/web answer` cites `[n]` URLs that actually back each claim.
- [ ] no paywalled body is extracted (403 → note + bail).
- [ ] search cache reused within same session (no 2nd identical request).
