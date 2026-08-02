# Roadmap

## v0.1.0 (rilis ini)
- [x] CLI repl + one-shot run + resume
- [x] Multi-provider cloud (OpenAI/Anthropic/OpenRouter/Gemini/Groq/DeepSeek)
- [x] 12 teknik hemat token + metering
- [x] Tool: terminal, files, patch, search, git, tests, todo, memory, subagent
- [x] Skills + sessions + benchmark harness

## v0.2.0 — kekuatan
- [ ] MCP tools (dukung ekosistem MCP server)
- [ ] Browser tool (akses web untuk riset)
- [ ] Multi-workspace & per-project memory
- [ ] Auto skill creation dari sesi sukses (Hermes-style)
- [ ] `dhybrid init` wizard onboarding (OpenClaw-style)

## v0.3.0 — jangkauan
- [ ] Gateway multi-channel (Telegram/WhatsApp) ala OpenClaw
- [ ] Dukungan model lokal (bila user mau; adaptor ~30 baris)
- [ ] CI: GitHub Actions (pytest + ruff) + release binary

## Prinsip yang tidak akan berubah
1. Hemat token adalah fitur inti, bukan tambahan.
2. Local-first: data user tidak pernah wajib ke server pihak ketiga.
3. Lazy: kode terbaik adalah kode yang tidak ditulis.
