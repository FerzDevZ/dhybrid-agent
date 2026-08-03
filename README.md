# 🦞 dhybrid-agent

![CI](https://github.com/FerzDevZ/dhybrid-agent/actions/workflows/ci.yml/badge.svg)

CLI coding agent yang **powerful untuk coding** dan **super hemat token** — berarsitektur *hybrid*: tugas mekanis dikerjakan model murah, tugas penalaran dikerjakan model besar. Local-first (own-your-data), tanpa server.

Referensi desain: Hermes Agent (skills, memory, sessions), OpenClaw (local-first, workspace, skills), Pi (unified LLM API), Claude Code (UX REPL), Ponytail (lazy senior dev = hemat token terbesar).

## Fitur

- **Satu model, pilih bebas** — satu model utama yang bisa diganti kapan saja (preset / manual) via `/settings`; router hybrid kecil/besar tetap tersedia sebagai opsi config `small_model`.
- **12 teknik hemat token** — lazy policies, context compaction, prompt caching (Anthropic cache_control), tool output cap, diff-based edit, semantic cache, early-stop, dsb.
- **Multi-provider cloud** — OpenAI, Anthropic, OpenRouter, Gemini, Groq, DeepSeek, byNara (satu adaptor OpenAI-compatible + adaptor Anthropic native), plus route gratis opencode-zen & byNara.
- **Tool lengkap** — terminal (dengan gerbang keamanan), read/write range, apply_patch diff-minimal, grep/find, git (commit aman), pytest runner, TDD status, todo, memory jangka panjang (FTS5), subagent delegation, web (web_search + http_request), dan `ask_user` (agent boleh tanya keputusan ke user di tengah kerja — guardrail maks 2x/sesi, non-interaktif diblokir).
- **Tool analisis & E2E baru (v0.6.0)** — `code_map` (struktur fungsi/class per file via tree-sitter AST, hemat token), `mem_index`/`mem_search`/`mem_reset` (memory kode proyek via sqlite-vec, pencarian vektor char n-gram), dan `browser` (Playwright headless: navigate/click/type/snapshot untuk verifikasi web E2E).
- **Auto-skill wajib + clarify cerdas (v0.8.x)** — setiap prompt otomatis memicu skill; bila tak ada skill khusus yang cocok, skill umum `general` dipakai (fallback, bisa dimatikan via `skills.fallback: null`) dengan feedback transparan `[skill aktif: general (fallback)]`. Prompt ambigu (mis. "buat web login register" tanpa stack) ditanya lewat pilihan bernomor SEBELUM agent bekerja — pertanyaannya **digenerate AI** (natural, selalu bervariasi; fallback template pool lokal saat offline, `clarify.ai: false` untuk mematikan). Jawab dengan angka, teks bebas, atau Enter/"Lanjutkan" = default; deteksi project cwd otomatis (composer.json → PHP/Laravel, next.config → Next.js, pubspec.yaml → Flutter, dll); keputusan masuk konteks sebagai `[keputusan user]`. Tool baru `clarify` (allowlist 31) — agent bisa tanya pilihan bernomor di tengah kerja (guardrail 3x/sesi, terpisah dari `ask_user` 2x/sesi). Matikan total via `clarify.enabled: false`.
- **Agent bisa MELIHAT & menerima paste apa pun (v0.7.x)** — `read_image` membacakan gambar/screenshot (vision LLM byNara; fallback OCR lokal tanpa API key via rapidocr-onnxruntime); `/shot` screenshot layar ke `~/.dhybrid/captures/`; `/pasteshot` mengambil GAMBAR dari clipboard (Shift+PrtSc → langsung dibaca, jalur terdekat dari paste gambar); `/paste` menyimpan teks tempel ke `~/.dhybrid/pastes/` dan langsung masuk konteks agent.
- **Tidak berhenti prematur saat membangun** — agent menolak melabeli "DONE" bila target membangun masih bertanya/menawarkan pilihan; otomatis naik ke model lebih kuat (escalation chain) atau disodorkan default lalu lanjut, dan tidak berhenti sebelum ada bukti nyata. Bukti penyelesaian dihitung dari file yang benar-benar dibuat (folder dependensi seperti `vendor/`, `node_modules/` diabaikan supaya angkanya akurat — bukan puluhan ribu file palsu).
- **Sesi & memori** — SQLite local di `~/.dhybrid/`, resume sesi via ringkasan, dashboard token & biaya. `dhybrid repl` otomatis meneruskan sesi terakhir di proyek yang sama: `cwd` dinormalisasi (relatif vs absolut dianggap proyek sama), konteks & judul sesi lama dimuat ulang dan ditampilkan di banner (tanpa baris sesi 'yatim'); fakta memori jangka panjang yang **relevan dengan proyek/cwd** di-inject ke awal sesi (bukan sekadar 'yang terbaru').
- **Skills** — folder `skills/<nama>/SKILL.md`, auto-inject berdasar relevansi: kata kunci prompt + sinonim/alias ("crash" → skill debugging) + riwayat sesi, dengan skor berbobot (kata langka lebih kuat) dan feedback `[skill aktif: ...]`. Paksa skill via `/skill <nama>` (tiap prompt) atau `@nama_skill` di prompt.

## Install

### One-liner (disarankan)

```bash
curl -fsSL https://raw.githubusercontent.com/FerzDevZ/dhybrid-agent/main/install.sh | bash
```

Installer: clone repo ke `~/.dhybrid-agent`, buat venv, pasang dependensi,
buat symlink `~/.local/bin/dhybrid`, dan siapkan `.env` dari `.env.example`.
Lalu isi API key dan jalankan `dhybrid repl` (buka terminal baru).

Variabel opsional: `DHYBRID_INSTALL_DIR`, `DHYBRID_BIN_DIR`, `DHYBRID_BRANCH`,
`DHYBRID_REPO_URL`, `DHYBRID_SKIP_ENV=1` (lewati pembuatan .env).

### Manual

```bash
cd dhybrid-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"          # atau (lebih cepat): uv pip install -e ".[dev]"
cp .env.example .env             # isi API key yang kamu punya
```

### Quality gates (dev)

```bash
pytest -q                        # semua test
pytest -q -n auto                # lebih cepat (pytest-xdist, paralel)
pytest -q --cov=src/dhybrid      # laporan coverage
bandit -q -r src/dhybrid -c .bandit.yml   # static security scan
pip-audit                        # cek kerentanan dependensi
pre-commit install               # ruff lint otomatis sebelum tiap commit
```

## Quickstart

```bash
dhybrid repl                     # sesi interaktif — auto-resume sesi terakhir proyek ini
dhybrid repl --fresh             # mulai sesi BARU (lewat konteks lama)
dhybrid run "perbaiki bug di calc.py lalu jalankan test"
dhybrid --cwd /path/proyek repl  # kerja di proyek lain
dhybrid tokens                   # dashboard token & biaya semua sesi
dhybrid resume <session_id>      # lanjutkan sesi lama
dhybrid run --json "cek repo"    # output JSON terstruktur (scripting/CI)
dhybrid doctor                   # diagnosa config, key, chain, allowlist, skill
```

### Baca dokumen kantor

```
read_document path/laporan.pdf   # PDF/DOCX/XLSX/PPTX/HTML → markdown
                                 # (via markitdown; dulu cuma file teks)
```

### Command REPL

```
/help  /model [preset]  /tokens  /compact  /clear  /sessions  /skills  /skill <nama|ls|info|rm>  /quit
```

`/skill rm <nama>` hanya menghapus skill workspace (hasil auto-learn); skill
bawaan ditolak. Auto-skill bisa dimatikan: `skills.auto_learn: false` di config
atau `DHYBRID_NO_SKILL=1`. Debug: `DHYBRID_DEBUG=1` menyimpan dump konteks &
hasil tiap run ke `~/.dhybrid/debug/`.

## Konfigurasi

`config/default.yaml` — model utama, budget, preset provider:

```bash
dhybrid repl --model anthropic-big     # model utama = Claude Sonnet
dhybrid repl --model gemini-fast       # model kecil = Gemini Flash
export DHYBRID_MODEL=gpt-4o            # atau via env
```

Preset tersedia (21): `openai-fast/big`, `anthropic-fast/big`, `openrouter-fast/big`, `gemini-fast/big`, `groq-fast`, `deepseek-fast`, `bynara-fast/medium/big` (route `https://router.bynara.id/v1`), dan `opencode-zen-*` (9 preset route https://opencode.ai/zen/v1 — 6 di antaranya **gratis tanpa API key**: fast/big/codex/nemotron/laguna/ling/mimo/north, model `*-free`).

**Default model = Gemini** (`gemini-flash-latest`, via `/v1beta/openai`). Tanpa key Gemini, dhybrid jalan sebagai chatbot hanya dengan provider yang punya key; pilih model kapan saja via `/settings` (bisa input manual) atau `dhybrid --model <preset>`.

**Provider toggle** — hidup/matikan provider lewat `/settings` (opsi 5). Provider yang dinonaktifkan tidak akan dipakai sebagai model utama maupun di escalation chain.

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
