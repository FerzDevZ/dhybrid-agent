# Changelog

Semua perubahan penting dhybrid-agent dicatat di sini.
Format mengikuti [Keep a Changelog](https://keepachangelog.com/id-ID/1.1.0/),
versi mengikuti [Semantic Versioning](https://semver.org/).

## [0.4.2] - 2026-08-03

### Ditambahkan
- Tool `ask_user(prompt, options)` — agent boleh tanya keputusan ke user di
  tengah loop; guardrail: maks 2x/sesi, diblokir di mode non-interaktif
  (`dhybrid run` — agent harus pilih default sendiri). Golden rule #1 direvisi:
  "eksekusi dulu; tanya hanya via ask_user bila pilihan berdampak besar".
- Paksa skill: `/skill <nama>` (berlaku tiap prompt) dan `@nama_skill` di prompt;
  feedback `[skill aktif: ...]` ditampilkan setelah tiap prompt.
- Matching skill lebih pintar: sinonim/alias ("crash" → debugging), skor
  berbobot (kata langka lebih kuat), cocok dengan riwayat sesi, nama skill
  ikut dihitung.
- 5 skill debugging/analisis baru: root-cause-analysis, performance-profiling,
  api-debugging, sql-query-optimization, concurrency-debugging (total 26).
- Fix: `web_search` & `http_request` ternyata tidak ada di default allowlist
  config — sekarang aktif.

### Diperbaiki
- Import tak terpakai + urutan import (ruff bersih).

## [0.4.1] - 2026-08-03

### Ditambahkan
- Tool `web_search` (DuckDuckGo, tanpa API key) & `http_request` (REST generik,
  Authorization tidak bocor ke output, retry 429/5xx dengan backoff) di
  `tools/web.py`.
- 4 slash-command memory di REPL: `/remember`, `/forget`, `/memories`,
  `/search-memory`.
- Parser tool-call mendukung 5 format (bare JSON, index alias, array,
  tag `<function=..>`, tag `arg_key`/`arg_value`) + dedupe + `strip_tool_block`.
- Validator `rm -rf` memblokir target root sistem, `/home`, dan traversal;
  target spesifik dalam workspace tetap lewat konfirmasi user.
- 11 skill baru: web-search, web-github, gitlab-lazy, code-sandbox,
  database-query, api-http-request, web-scraping-extraction, skills-sh,
  memory-persistence, notion-trello-jira, customer-support-rag.
- LICENSE MIT + field `license` di pyproject.

### Diperbaiki
- Escaping test parsing; `test_parsing.py` 12/12 lulus.
- 2 temuan ruff di `security.py` (blind except, SIM103).

## [0.4.0] - 2026-08-02

### Ditambahkan
- Parse tool-call format `<function=..>` + `arg_key`/`arg_value`.
- Retry 429 dengan backoff, progress live, injeksi known-facts.
- Auto-resume sesi per-proyek + injeksi memori jangka panjang relevan ke
  konteks awal sesi.
- Provider toggle di `/settings`; escalation skip provider disabled/401.

### Diperbaiki
- Agent selalu memberi respons (tidak terserap format tool-call).
- Agent tidak berhenti prematur saat membangun (bukti file nyata, folder
  dependensi diabaikan).
- Sinkronisasi versi pyproject ↔ runtime `__version__` (0.4.1).

## [0.1.0] - 2026-07-31

### Ditambahkan
- CLI repl + one-shot run + resume.
- Multi-provider cloud (OpenAI/Anthropic/OpenRouter/Gemini/Groq/DeepSeek/byNara).
- 12 teknik hemat token + metering (`/tokens`).
- Tool: terminal (gerbang keamanan), files, patch, search, git, tests, todo,
  memory (FTS5), subagent, MCP.
- Skills + sessions + benchmark harness.
- CI green (ruff + pytest) via GitHub Actions.
