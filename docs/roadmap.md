# Roadmap

## v0.1.0 (rilis ini)
- [x] CLI repl + one-shot run + resume
- [x] Multi-provider cloud (OpenAI/Anthropic/OpenRouter/Gemini/Groq/DeepSeek/byNara)
- [x] 12 teknik hemat token + metering
- [x] Tool: terminal, files, patch, search, git, tests, todo, memory, subagent, web, MCP
- [x] Skills + sessions + benchmark harness
- [x] CI green (ruff 0 error + pytest) via GitHub Actions
- [x] Provider toggle (enable/disable) di `/settings`
- [x] Versi sinkron (pyproject == runtime `__version__`, 0.4.1)

## v0.2.0 — kekuatan
- [x] MCP tools (adaptor `tools/mcp.py` + preset `mcp_servers` di config)
- [~] Browser tool — ada `tools/web.py` (fetch HTTP); browser penuh (CDP) belum
- [ ] Multi-workspace & per-project memory
- [ ] Auto skill creation dari sesi sukses (Hermes-style)
- [ ] `dhybrid init` wizard onboarding
- [ ] Fallback escalation yang aman (skip provider disabled / tanpa key valid)

## v0.3.0 — jangkauan
- [ ] Gateway multi-channel (Telegram/WhatsApp)
- [ ] Dukungan model lokal (adaptor ~30 baris)
- [ ] Release binary otomatis di GitHub Actions

## Prinsip yang tidak akan berubah
1. Hemat token adalah fitur inti, bukan tambahan.
2. Local-first: data user tidak pernah wajib ke server pihak ketiga.
3. Lazy: kode terbaik adalah kode yang tidak ditulis.