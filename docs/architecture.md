# Arsitektur dhybrid-agent

## Lapisan

```
CLI Layer      ui/: repl, commands, statusline, render (ANSI, non-tty aman)
Agent Runtime  agent/: loop ReAct, router hybrid, hooks, parsing; tools/registry
Efficiency     efficiency/: budget, context (compaction), cache, lazy policies
LLM Layer      llm/: base types, providers (OpenAICompat + Anthropic), tokens
Persistence    session/: store SQLite, memory FTS5, konteks sesi
```

## Alur Satu Turn

1. `ui/repl` menerima prompt → inject skill relevan (`skills/loader.py`).
2. `AgentLoop.run()`: router memilih client (small/big) via `classify_task` + PromptCache.
3. `ContextManager.render()` menyusun pesan: system (compiled-once + tool specs) + summary + percakapan.
4. `client.stream()` → delta di-render live; tool calls diakumulasi.
5. Tool dieksekusi via `ToolRegistry` (allowlist, cap output, gerbang keamanan terminal).
6. `TokenBudget.add(usage)` → bila soft tercapai: `compact_conversation` (model kecil) meringkas pesan tua.
7. Tool error berulang → eskalasi ke model besar (cheap-first).
8. Selesai → hooks mencatat usage ke SQLite; summary disimpan untuk resume.

## Keputusan Desain Kunci

- **Satu adaptor OpenAI-compatible** untuk OpenAI/OpenRouter/Groq/DeepSeek/Gemini — tinggal beda `base_url`. Anthropic adaptor native karena format + cache_control berbeda.
- **Tool-calling ganda**: native (OpenAI/Anthropic) + fallback blok JSON ` ```tool ` untuk model yang tidak support.
- **Kompaksi** menyimpan `summary` terpisah + `keep_recent` pesan verbatim; system prompt tidak pernah dikompaksi.
- **apply_patch** format diff minimal (`--- path` + baris `-`/`+`) — lebih hemat token daripada unified diff penuh, dengan pesan error yang memandu.
- **Local-first**: semua state di `~/.dhybrid/` (sessions.sqlite, memory.sqlite, cache.sqlite) — ala OpenClaw own-your-data.
