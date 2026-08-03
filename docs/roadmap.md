# Roadmap

## v0.5.1 (rilis ini)
- [x] Tier 1 paket pendukung: read_document (markitdown), REPL prompt_toolkit,
      web_fetch trafilatura, skill matching rapidfuzz
- [ ] Tier 2: ollama (model lokal), sqlite-vec (project memory), tree-sitter (AST)
- [ ] Tier 3: pytest-cov + xdist, pip-audit + bandit, pre-commit, uv

## v0.5.0 (rilis ini)
- [x] Fix parser teks: apply_patch tanpa old_string nyata tidak di-fire (+9 test text_parser)
- [x] Fix prosa model auto-fire tool: sinyal negatif niat/hedge (akan/perlu/mungkin) + boost imperatif
- [x] Fix kontaminasi auto-skill antar-run: tool_count di-reset per run
- [x] Fix jawaban ask_user: pesan biasa (push_prompt=False), tidak di-parse/di-nudge
- [x] Fix prosa model dibuang saat tool block: strip markup, prosa tetap di riwayat
- [x] Fix ask_user boros call: pause langsung setelah eksekusi tool
- [x] doctor diperluas: cek chain mati, allowlist keblokir, skill workspace sampah
- [x] /skill ls | info | rm (rm hanya skill workspace)
- [x] DHYBRID_DEBUG=1 dump konteks+hasil ke ~/.dhybrid/debug/
- [x] Failover chain saat error beruntun tanpa router
- [x] dhybrid run --json (output terstruktur untuk scripting)
- [x] Cache web_search per sesi (TTL 120 dtk)
- [x] Toggle auto-skill: config skills.auto_learn / DHYBRID_NO_SKILL=1
- [x] 5 skill baru: laravel-scaffold, free-model-survival, context-engineering, token-budget-debugging, session-hygiene (total 31)
- [x] 205 test lulus, ruff 0 error, versi sinkron 0.5.0

## v0.4.3
- [x] Fix "DONE tanpa kerja": BUILD_VERBS diperluas (kerjakan/setup/install/perbaiki/dll)
- [x] Fix "lanjutkan": warisi konteks membangun dari riwayat sesi
- [x] Fix klaim "selesai" tanpa bukti → di-nudge EVIDENCE_MSG sampai max_nudges
- [x] Fix auto-skill sampah: butuh karya nyata (file/mutasi/test) + stoplist + dedupe

## v0.4.2
- [x] Tool `ask_user` — agent tanya keputusan ke user (max 2x/sesi, non-interaktif diblokir) + golden rule #1 direvisi
- [x] Paksa skill: `/skill <nama>` + `@nama_skill` di prompt + feedback `[skill aktif: ...]`
- [x] Matching skill pintar: alias/sinonim ("crash" → debugging), skor berbobot, riwayat sesi, nama skill
- [x] 5 skill debugging/analisis baru: root-cause, performance, api, sql, concurrency (total 26)
- [x] Fix allowlist: web_search & http_request aktif di config default
- [x] Versi sinkron 0.4.2, CI green

## v0.4.1
- [x] CLI repl + one-shot run + resume
- [x] Multi-provider cloud (OpenAI/Anthropic/OpenRouter/Gemini/Groq/DeepSeek/byNara)
- [x] 12 teknik hemat token + metering
- [x] Tool: terminal, files, patch, search, git, tests, todo, memory, subagent, web, MCP
- [x] Skills + sessions + benchmark harness
- [x] CI green (ruff 0 error + pytest) via GitHub Actions
- [x] Provider toggle (enable/disable) di `/settings`
- [x] Versi sinkron (pyproject == runtime `__version__`, 0.4.1)
- [x] Tool web: `web_search` (DDG) + `http_request` (retry 429, auth redacted)
- [x] Slash-command memory di REPL (`/remember`, `/forget`, `/memories`, `/search-memory`)
- [x] Parser tool-call 5 format + dedupe + `strip_tool_block`
- [x] Validator `rm -rf` aman (blokir root sistem, `/home`, traversal)
- [x] 21 skill ter-load (11 baru: web, git, sandbox, database, memory, rag, …)
- [x] LICENSE MIT + CHANGELOG

## v0.2.0 — kekuatan
- [x] MCP tools (adaptor `tools/mcp.py` + preset `mcp_servers` di config)
- [~] Browser tool — ada `tools/web.py` (fetch HTTP); browser penuh (CDP) belum
- [x] Multi-workspace & per-project memory (auto-resume sesi per proyek + fakta memori di-inject ke konteks)
- [x] Fallback escalation yang aman (skip provider disabled / tanpa key valid)
- [x] Auto skill creation dari sesi sukses (Hermes-style) — `_auto_learn_skill` di repl, guard `auto_skill_worthwhile`, ter-test
- [ ] `dhybrid init` wizard onboarding

## v0.3.0 — jangkauan
- [ ] Gateway multi-channel (Telegram/WhatsApp)
- [ ] Dukungan model lokal (adaptor ~30 baris)
- [ ] Release binary otomatis di GitHub Actions

## Prinsip yang tidak akan berubah
1. Hemat token adalah fitur inti, bukan tambahan.
2. Local-first: data user tidak pernah wajib ke server pihak ketiga.
3. Lazy: kode terbaik adalah kode yang tidak ditulis.