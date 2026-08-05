# Rencana: Studi Full Source Code dhybrid-agent

## Ringkasan

Mempelajari seluruh source code proyek `dhybrid-agent` (CLI coding agent Python, v0.9.6)
secara menyeluruh, lalu **menyampaikan hasil studi langsung di chat** — tanpa membuat
file dokumentasi apa pun (sesuai keputusan user).

Tingkat detail: **per modul + fungsi kunci** — setiap file dijelaskan tujuan, API publik,
hubungan antar modul, alur eksekusi utama, serta catatan bug/kualitas yang ditemukan.

## Analisis Kondisi Saat Ini

Fase eksplorasi sudah selesai. Yang telah dibaca & dipahami:

1. **Top-level & config**: `pyproject.toml`, `README.md`, `config/default.yaml`,
   `src/dhybrid/{cli,config,__main__,dotenv}.py`, `docs/architecture.md`,
   `.github/workflows/ci.yml`, `.pre-commit-config.yaml`, `.bandit.yml`,
   `CHANGELOG.md`, `install.sh`, `scripts/*` (smoke & completion).
2. **LLM layer** (`src/dhybrid/llm/`): base, providers, litellm_client, registry, tokens.
3. **Efficiency layer** (`src/dhybrid/efficiency/`): budget, cache, compress, context,
   lazy, metrics, tokenizer, prometheus_exporter.
4. **Agent layer** (`src/dhybrid/agent/`): loop, router, intent, hooks, messages,
   parsing, quality, scoreboard, streaming, text_parser, verify.
5. **Tools layer** (`src/dhybrid/tools/`): registry, build_tools (`__init__`),
   security, validate, terminal, files, patch, search, git, tests, todo, web,
   documents, code_map, memory, project_memory, mcp, subagents, ask, clarify,
   browser_tool, vision, soft + 5 power tool.
6. **Session layer** (`src/dhybrid/session/`): context, memory, store (RedisStore), userconfig.
7. **Skills** (`src/dhybrid/skills/loader.py`), **Subagents** (`delegate.py`),
   **UI** (`repl.py`, `commands.py`, `render.py`, `rich_ui.py`, `status.py`),
   **Utils** (`async_io.py`, `log.py`), plus `doctor.py` dan `updater.py`.

### Temuan penting dari eksplorasi

- Arsitektur berlapis: CLI → agent runtime → efficiency → LLM → persistence, local-first SQLite di `~/.dhybrid/`.
- Jantung sistem: `AgentLoop` (ReAct) dengan 12 teknik hemat token, escalation chain
  (bynara-big → openrouter-big → anthropic-big), retry transient, live-verify, self-critique.
- **Bug nyata**: `browser_tool.register` argumen tertukar (fn vs description) → tool browser selalu gagal.
- **Bug regex** di `quality.py:68` (`\?\\s*$`): penalti "bertanya saat build" hampir tidak pernah terpicu.
- **Bug kecil**: judul selalu kosong di parser internal `web.py`; `_DEFAULT_PROMPT` duplikat di `vision.py`;
  `estimate_messages` (`llm/tokens.py`) rawan `TypeError` untuk konten multimodal.
- **Kode mati**: `_FACT_PATTERNS`/`is_known` (efficiency/context), `MessageStore` (agent/messages),
  `status.py` (diimpor `# noqa`).
- **Kebersihan layering**: `llm/registry.py` mengimpor dari `ui/commands.py` (UI diintip lapisan LLM).
- Inkonsistensi kecil: `todo_clear` tidak ada di allowlist, `updater.py` hardcode branch `main`.

## Keluaran yang Diusulkan (Deliverable)

Satu ringkasan komprehensif di chat (bukan file), terstruktur sebagai berikut:

1. **Gambaran proyek** — apa itu dhybrid-agent, versi, struktur folder, dependensi utama.
2. **Arsitektur & alur satu turn** — lapisan + langkah 1-8 dari prompt user sampai penyimpanan sesi.
3. **Katalog per modul + fungsi kunci** — diorganisir per lapisan:
   - LLM, Efficiency, Agent, Tools (kelompokkan per kategori tool),
     Session, Skills, Subagents, UI, Utils, Top-level.
   - Untuk setiap file: tujuan, 1-3 API publik utama, hubungan dengan modul lain.
4. **Mekanisme hemat token** — 12 teknik + di file mana diimplementasikan.
5. **Catatan kualitas / bug / kode mati / inkonsistensi** — daftar temuan yang bisa
   ditindaklanjuti (opsional jadi tugas perbaikan berikutnya).
6. **Peta untuk pengembangan selanjutnya** — di mana meletakkan fitur baru,
   file mana yang paling sering disentuh.

## Asumsi & Keputusan

- Keluaran hanya di chat; tidak ada file dokumentasi yang dibuat.
- Bahasa ringkasan: Indonesia (sesuai bahasa user).
- Tidak ada perubahan kode — murni studi/analisis.
- Referensi kode memakai tautan clickable `file:///` ke file sumber.

## Verifikasi

- Ringkasan disusun berdasarkan pembacaan nyata semua file (sudah dilakukan fase eksplorasi),
  setiap klaim dikaitkan ke file/lokasi spesifik.
- Tidak ada tool lain yang dijalankan; tidak ada file yang diedit.
