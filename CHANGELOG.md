# Changelog

Semua perubahan penting dhybrid-agent dicatat di sini.
Format mengikuti [Keep a Changelog](https://keepachangelog.com/id-ID/1.1.0/),
versi mengikuti [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Plan Mode / Build Mode (keamanan + workflow)

- **Mode kerja `plan`/`build`** (default di `config/default.yaml`):
  - `plan` = observasi saja: terminal dibatasi perintah read-only
    (`ls cat grep strings watch` dst, tanpa metachar shell), tool mutasi
    (write_file, apply_patch, git_commit, repo_issue, repo_pr, dll) diblokir.
  - `build` = eksekusi penuh + alur Issue/PR.
- **Shortcut Tab** di REPL: ganti plan ⇄ build (buffer kosong); saat mengetik
  Tab tetap autocomplete.
- **Slash command** `/plan`, `/build`, `/mode`, dan flag CLI `--mode plan|build`.
- **Tool repo** baru: `repo_issues` (list read-only), `repo_issue` (buat Issue),
  `repo_pr` (buat PR/MR) untuk GitHub/GitLab (token env
  `GITHUB_TOKEN`/`GITLAB_TOKEN`).
- **Eskalasi wajib izin user**: sebelum model di-upgrade (kualitas/error/tool-error)
  REPL bertanya `y/N`. Tolak = lanjut model sama. Non-interaktif = tolak
  (fail-safe); `workflow.escalation: auto` untuk otomatis.
- Instructi mode disuntik ke system prompt via `dhybrid.mode`.

### Distribusi PyPI & semver

- **Wheel standalone** — `config/default.yaml` kini terkemas di dalam paket
  (`src/dhybrid/config/default.yaml`, dibaca via `importlib.resources`);
  `pip install dhybrid-agent` berfungsi tanpa file repo.
- **Metadata PyPI** — `[project.urls]`, keywords, classifiers di `pyproject.toml`.
- **Workflow rilis** (`.github/workflows/release.yml`) — tag `v*` → validasi
  versi vs tag → build wheel+sdist (`python -m build`) → publish PyPI (trusted
  publishing) → GitHub Release dengan artifact.

## [0.9.6] - 2026-08-04

### Reliability Power-up: Retry + Redis Persistence + MIME Media
Tingkatkan reliability & observability: retry cerdas, state persistence cross-session via Redis, serta MIME detection audio/video.

- **Tenacity retry** (`llm/providers.py`) — exponential backoff pada provider HTTP (Anthropic/OpenAICompat), increment `api_errors` counter saat retry failure.
- **Redis persistence** (`session/store.py`) — `RedisStore` layer dengan fallback graceful ke SQLite, cross-instance state sync untuk subagent.
- **MIME media detection** (`tools/vision.py`) — `_is_media_bytes` detect audio/video via python-magic, plus `_is_image_bytes` legacy wrapper.
- **Prometheus exporter** (`efficiency/prometheus_exporter.py`) — export metrics ke text exposition format.

### Files baru
- `src/dhybrid/efficiency/metrics.py`, `tokenizer.py`, `prometheus_exporter.py`
- `src/dhybrid/utils/log.py`, `async_io.py`
- `scripts/smoke_095.py`, `tests/integration/test_095_features.py`
- `tests/unit/test_metrics.py`, `test_tokenizer.py`, `test_session_checkpoint.py`, `test_repl_rich.py`, `test_log.py`, `test_async_io.py`, `test_prometheus_exporter.py`, `test_retry_providers.py`, `test_redis_store.py`, `test_vision_mime.py`

### Validation
- 425 test lulus, coverage 71.83% (≥65%).
- ruff 0, smoke 0.9.6 OK.

---

## [0.9.5] - 2026-08-04

### Power-up: observability, state persistence + unified LLM routing
Elevasi dhybrid-agent dari CLI hemat token ke agen AI modular tingkat lanjut.
- **Metrics module** (`efficiency/metrics.py`) — Counter + Histogram + Registry
  in-memory (8 counter standar: tokens_*, api_calls/errors, turn_latency_ms, cost).
- **Token counting akurat** (`efficiency/tokenizer.py`) — tiktoken per-model +
  heuristic fallback untuk Claude/unknown, cache per-encoding, api_errors tracking.
- **Session checkpoint** (`session/store.py`) — persist state counters (run_count,
  fallback_uses, qa_history, skill_candidates) ke SQLite → resume turn & multi-session.
- **Litellm routing** (`llm/litellm_client.py`) — provider utama via `make_client`
  (openai/anthropic/litellm), 100+ provider via litellem.
- **Rich UI** (`ui/rich_ui.py`) — banner DONE panel + spinner progress di run_agent.
- **Structured logging** (`utils/log.py`) — JSON/text hybrid, machine-readable.
- **Async I/O** (`utils/async_io.py`) — aiofiles wrapper, sync fallback.
- **Prometheus exporter** (`efficiency/prometheus_exporter.py`) — export metrics
  ke text exposition format (/metrics endpoint).

### Files baru
- `src/dhybrid/efficiency/metrics.py`, `tokenizer.py`, `prometheus_exporter.py`
- `src/dhybrid/utils/log.py`, `async_io.py`
- `scripts/smoke_095.py`, `tests/integration/test_095_features.py`
- 5x `tests/unit/test_metrics.py`, `test_tokenizer.py`, `test_session_checkpoint.py`,
  `test_repl_rich.py`, `test_log.py`, `test_async_io.py`, `test_prometheus_exporter.py`

### Validation
- 368 test lulus (361 existing + 7 baru), coverage 72% (≥65%).
- ruff 0, smoke_095.py OK.

---

## [0.9.0] - 2026-08-03

### Power-up pip packages (extra `power`) — 5 tool baru + MIME detect

Tool baru berbasis package populer, semuanya **soft-register**: kalau
package belum terpasang, tool tidak merusak startup & dipanggil → pesan
install ramah (`pip install -e '.[power]'`). Allowlist default 31 → **36**.
- `sys_info` (psutil) — CPU/RAM/disk/proses: cek kesehatan sistem.
- `scaffold` (jinja2) — generate banyak file dari template, render variabel,
  aman anti path-traversal (symlink keluar dir diblokir).
- `data_query` (duckdb) — SQL **read-only** langsung ke CSV/JSONL/Parquet;
  query tulis (CREATE/INSERT/DROP/dst) diblokir di level kode, hasil dipotong.
- `pdf_ops` (pypdf) — merge beberapa PDF jadi satu.
- `xlsx_edit` (openpyxl) — edit cell di salinan, file asli aman.
- MIME detect gambar (python-magic + magic bytes) → `read_image` + `/pasteshot`.

### Observability & cost
- `litellm` jadi provider utama (100+ provider, 1 interface).
- Token counting akurat via `tiktoken` (ganti heuristic `len/4`).
- Structured logging JSON/text (`utils/log.py`).
- Metrics Prometheus-style (`efficiency/metrics.py`).

### Session & skills
- Checkpoint state ke SQLite (`session/store.py`) — resume turn + multi-session.
- Auto-skill Q&A berulang (rapidfuzz token_set_ratio ≥75%).
- Skill digest akhir sesi (run_count ≥5, kandidat bernomor).
- Skill lint (frontmatter rusak di-skip).

### Files baru
- `src/dhybrid/efficiency/metrics.py`, `tokenizer.py`, `prometheus_exporter.py`
- `src/dhybrid/utils/log.py`, `async_io.py`
- `scripts/smoke_095.py`, `tests/integration/test_095_features.py`
- 10x `tests/unit/test_*.py` baru

### Validation
- 361 test lulus, coverage ~70% (≥65%).
- ruff 0, smoke_095.py OK.

---

## [0.8.2] - 2026-08-02

### STUCK fix + quality enforcement
- **Single quality measure**: `_measure_output` menggantikan `_finalize_response` di SEMUA jalur berhenti (max_steps, error, user cancel, success).
- **STUCK label**: jika build/ops tanpa file ditulis → banner `STUCK` (bukan `DONE`), tag `⤴` untuk escalation count.
- **Quality gate**: 0 file written + score < 50 → `STUCK`.

### Breeze installer fix
- Hapus `composer require` dari docs (breeze gagal tanpa --dev).
- Tambah `ask_user` untuk Breeze confirm (stack Blade/React + dark/light).

### Escalation chain
- Config `escalation_chain` preset models untuk quality-based fallback.

### Validation
- 315 test lulus, coverage 68.84%.
- ruff 0.

---

## [0.8.1] - 2026-08-01

### Clarify AI + fallback bervariasi
- AI-generated clarify question (natural, selalu bervariasi).
- Fallback pool 3 template bervariasi (bukan statis).
- Auto-clarify hanya 1x/turn (`clarify_just_answered` guard).

### Skill system hardening
- Skill digest: run_count ≥5, kandidat skill ditampilkan akhir sesi (Enter/nomor/0).
- Auto-skill update: session baru lebih lengkap → update skill lama (auto-only).
- Skill lint: frontmatter rusak di-skip tanpa crash.

### Validation
- 298 test lulus.

---

## [0.8.0] - 2026-07-31

### Initial release — token-efficient hybrid CLI agent
- Loop dengan soft budget (compact @ 60k, hard @ 120k tokens).
- Tool registry: terminal, files, patch, search, git, tests, todo, web, documents, code_map, project_memory, soft, subagents.
- Vision: `read_image` + `/pasteshot` (byNara + OCR lokal).
- Skills: soft-register, auto-inject, disable via config.
- Config YAML + env override.
- Breeze installer: `curl ... | bash` → auto venv + deps.

### Validation
- 245 test lulus.