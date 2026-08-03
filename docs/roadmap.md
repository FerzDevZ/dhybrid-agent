# Roadmap

## v0.4.2 (rilis ini)
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