# 🦞 dhybrid-agent

CLI coding agent yang **powerful untuk coding** dan **super hemat token** — berarsitektur *hybrid*: tugas mekanis dikerjakan model murah, tugas penalaran dikerjakan model besar. Local-first (own-your-data), tanpa server.

Referensi desain: Hermes Agent (skills, memory, sessions), OpenClaw (local-first, workspace, skills), Pi (unified LLM API), Claude Code (UX REPL), Ponytail (lazy senior dev = hemat token terbesar).

## Fitur

- **Hybrid router** — klasifikasi task (heuristik + cache) → model kecil untuk grep/test/edit, model besar untuk debug/arsitektur; eskalasi otomatis saat gagal.
- **12 teknik hemat token** — lazy policies, context compaction, prompt caching (Anthropic cache_control), tool output cap, diff-based edit, semantic cache, early-stop, dsb.
- **Multi-provider cloud** — OpenAI, Anthropic, OpenRouter, Gemini, Groq, DeepSeek (satu adaptor OpenAI-compatible + adaptor Anthropic native).
- **Tool lengkap** — terminal (dengan gerbang keamanan), read/write range, apply_patch diff-minimal, grep/find, git (commit aman), pytest runner, TDD status, todo, memory jangka panjang (FTS5), subagent delegation.
- **Sesi & memori** — SQLite local di `~/.dhybrid/`, resume sesi via ringkasan, dashboard token & biaya.
- **Skills** — folder `skills/<nama>/SKILL.md`, auto-inject berdasar relevansi.

## Install

```bash
cd dhybrid-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"          # atau: uv pip install -e ".[dev]"
cp .env.example .env             # isi API key yang kamu punya
```

## Quickstart

```bash
dhybrid repl                     # sesi interaktif
dhybrid run "perbaiki bug di calc.py lalu jalankan test"
dhybrid --cwd /path/proyek repl  # kerja di proyek lain
dhybrid tokens                   # dashboard token & biaya semua sesi
dhybrid resume <session_id>      # lanjutkan sesi lama
```

### Command REPL

```
/help  /model [preset]  /tokens  /compact  /clear  /sessions  /skills  /quit
```

## Konfigurasi

`config/default.yaml` — model utama, small model (router), budget, preset 10 provider:

```bash
dhybrid repl --model anthropic-big     # model utama = Claude Sonnet
dhybrid repl --model gemini-fast       # model kecil = Gemini Flash
export DHYBRID_MODEL=gpt-4o            # atau via env
```

Preset tersedia: `openai-fast/big`, `anthropic-fast/big`, `openrouter-fast/big`, `gemini-fast/big`, `groq-fast`, `deepseek-fast`.

## Hemat Token — Cara Kerja

Lihat `docs/token-efficiency.md` untuk detail 12 teknik + cara mengukur. Inti:

1. Agent TIDAK menulis kode yang tidak diminta (lazy policies).
2. Konteks lama diringkas (compaction), bukan dihapus.
3. Prompt caching memangkas biaya input antar turn.
4. Router mengirim kerja mekanis ke model murah.
5. Semua terukur: `/tokens` menampilkan token, cache-hit, dan biaya per sesi.

## Benchmark

```bash
python -m tests.benchmarks.run_bench        # mode hemat ON
python -m tests.benchmarks.run_bench --off  # pembanding (tanpa teknik hemat)
```

Bandingkan dua laporan di `docs/benchmark-*.md` untuk melihat % penghematan nyata.

## Struktur

```
src/dhybrid/
├── llm/         client multi-provider + estimator token
├── efficiency/  budget, context (compaction), cache, lazy policies
├── agent/       loop ReAct, hybrid router, hooks, parsing
├── tools/       terminal, files, patch, search, git, tests, todo, memory, subagent
├── session/     store SQLite, memori FTS5, konteks sesi
├── skills/      loader SKILL.md + auto-inject
├── subagents/   delegasi agent terisolasi
└── ui/          repl, commands, statusline, render
```

## Lisensi

MIT. Data kamu 100% lokal (`~/.dhybrid/`) — tidak ada telemetri.
