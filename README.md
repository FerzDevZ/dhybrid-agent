# dhybrid-agent

CLI coding agent dengan hybrid routing. Tugas mekanis dikerjakan model murah, tugas penalaran dinaikkan ke model besar. Seluruh data tersimpan lokal di `~/.dhybrid/` — tidak ada server, tidak ada telemetri.

```
pip install dhybrid-agent   # atau lihat bagian Instalasi
dhybrid repl
```

- **Bahasa**: Python ≥3.12
- **Lisensi**: MIT
- **Status**: Beta (Development Status 4)

---

## Ringkasan

dhybrid-agent adalah satu program `dhybrid` yang berjalan di terminal. Anda memberi perintah, agent memutuskan sendiri langkahnya: membaca file, menjalankan perintah, mengedit kode, menjalankan test, hingga membuat Issue/PR. Setiap keputusan dicatat; setiap tool dikontrol izin.

Yang membedakan dari chatbot biasa:

- **Hybrid routing.** Satu loop agent memilih model per langkah. Operasi biasa (lari test, baca file, edit kecil) dipakai model cepat/murah; langkah "berat" (perencanaan, debug rumit, rencana arsitektur) dinaikkan ke model besar. Jika jawaban model kecil diragukan, biaya default langsung escalation.
- **Kontrol token.** Konteks lama dipadatkan (bukan dibuang), prompt caching aktif di provider yang mendukung, output tool dibatasi, cache semantik pada hasil pencarian. Semua biaya terukur lewat `/tokens`.
- **Mode plan/build.** Default `build`. Dengan `plan`, agent hanya boleh membaca — semua tool mutasi (tulis file, patch, git commit, buat Issue/PR) diblokir, dan terminal dibatasi perintah read-only.
- **Izin eksplisit.** Eskalasi ke model yang lebih besar harus Anda setujui (default `ask`). Mode NON-interaktif otomatis menolak (fail-safe).

Dokumentasi lengkap ada di [`docs/README.md`](docs/README.md).

---

## Instalasi

### One-liner (Linux/macOS)

```bash
curl -fsSL https://raw.githubusercontent.com/FerzDevZ/dhybrid-agent/main/install.sh | bash
```

Installer meng-clone repo ke `~/.dhybrid-agent`, membuat venv, memasang dependensi, lalu membuat symlink `dhybrid` di `~/.local/bin`. Variabel yang bisa disesuaikan:

| Variabel | Default | Arti |
|----------|---------|------|
| `DHYBRID_INSTALL_DIR` | `~/.dhybrid-agent` | direktori instalasi |
| `DHYBRID_BIN_DIR` | `~/.local/bin` | tempat symlink binary |
| `DHYBRID_BRANCH` | `main` | branch git |
| `DHYBRID_REPO_URL` | `https://github.com/FerzDevZ/dhybrid-agent` | sumber repo |
| `DHYBRID_SKIP_ENV=1` | — | lewati pembuatan `.env` |
| `DHYBRID_USE_UV=1` | — | gunakan `uv` untuk instalasi |

### PyPI

```bash
pip install dhybrid-agent
# atau
uv tool install dhybrid-agent
```

Wheel berisi config bawaan (`config/default.yaml` diterkapsulkan dan dibaca via `importlib.resources`), jadi instal PyPI berfungsi tanpa meng-clone repo.

### Manual (development)

```bash
git clone https://github.com/FerzDevZ/dhybrid-agent && cd dhybrid-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # isi API key
```

### Reinstal / update

```bash
dhybrid install                  # reinstal/update via installer
dhybrid install --use-uv         # pakai uv
dhybrid install --branch main    # branch spesifik
```

---

## Quickstart

```bash
dhybrid repl                     # sesi interaktif; auto-resume sesi terakhir proyek
dhybrid repl --fresh             # sesi baru, konteks lama dibuang
dhybrid run "perbaiki bug di calc.py lalu jalankan test"
dhybrid --cwd /path/proyek repl  # kerja di proyek lain
dhybrid run --json "cek repo"    # output JSON (untuk scripting/CI)
dhybrid tokens                   # token & biaya semua sesi
dhybrid resume <session_id>      # lanjutkan sesi
dhybrid doctor                   # diagnosa config, API key, toolchain
```

### Mode Plan ⇄ Build

```bash
dhybrid repl --mode plan         # baca-saja
dhybrid repl --mode build        # eksekusi penuh (default)
```

Di REPL: **Tab** saat buffer kosong menukar plan ⇄ build. Ada juga `/plan`, `/build`, `/mode`.

Model utama diganti kapan saja.

```bash
dhybrid repl --model anthropic-big
dhybrid repl --model gemini-fast
export DHYBRID_MODEL=gpt-4o      # lewat env
```

### Slash command

```
/help  /model [preset]  /tokens  /compact  /clear  /sessions
/settings  /mode  /plan  /build  /skills  /skill <nama|ls|info|rm>  /quit
```

`/skill rm <nama>` hanya menghapus skill workspace hasil auto-learn; skill bawaan tidak bisa dihapus dari sini. Auto-learn dimatikan via `skills.auto_learn: false` di config atau `DHYBRID_NO_SKILL=1`. Konteks dump untuk debug: `DHYBRID_DEBUG=1` menyimpan hasil tiap run ke `~/.dhybrid/debug/`.

---

## Fitur

### Routing & model

- Router hybrid dua layer: `fast` untuk langkah mekanis, `big` untuk penalaran.
- 21 preset provider terkirim (`config/default.yaml`), termasuk route gratis `opencode-zen-*` (9 preset, 6 bebas API key) dan `bynara-*`.
- Dialog `/settings` untuk memilih model (bisa input manual) dan meng- toggle provider hidup/mati.

### Tool (70+)

| Kelompok | Tool |
|----------|------|
| Terminal | `terminal` (shell, dijaga gate izin), `run_bg`/`poll_bg` (background job + timeout watchdog) |
| File | `read_file`, `write_file`, `apply_patch` (diff), `grep`, `find_files`, `read_document` (PDF/DOCX/XLSX/PPTX → markdown) |
| Repo | git status/diff/log, `repo_issues`, `repo_issue`, `repo_pr` (GitHub/GitLab, token env `GITHUB_TOKEN`/`GITLAB_TOKEN`) |
| Verifikasi | `run_tests` (pytest), `code_sandbox`, `read_image` |
| Web | `web_search`, `web_fetch`, `http_request` (egress allowlist) |
| Browser | `browser` (Playwright: navigate/click/type/snapshot) |
| Runtime lain | `mcp` client (server jsonrpc stdin/stdout), toolchain Go/TS/Rust/Java/C# untuk lint/compile/test |
| Memori | `memory` (FTS5 + sqlite-vec per proyek), `todo` |
| Agregator | `code_map`, `code_count`, `read_pdf`, `read_doc` |
| Power | `power_sys`, `power_data`, `power_scaffold`, `power_pdf`, `power_xlsx` |

### Skills

- ±30 skill bawaan (SKILL.md) + auto-inject sesuai konteks proyek.
- Auto-learn: skenario yang dijawab berulang diturunkan jadi skill workspace.
- Plugin/skills: `EXPORTED_SKILLS.md` di root berisi daftar skill yang diekspor.

### Sesi & memori

- Store SQLite lokal (`~/.dhybrid/`), setiap sesi direkam; `resume` dan `--fresh` berpindah antar konteks.
- **Checkpoint mid-run**: pekerjaan panjang bisa dilanjutkan dari titik terakhir (bukan dari awal).
- **Branching**: percabangan sesi untuk eksperimen.
- **Semantic memory**: pencarian memori lama via FTS5 + embedding.
- Dashboard `/tokens` = token, cache-hit, biaya per sesi.

### Keandalan

| Komponen | Perilaku |
|----------|----------|
| Health monitor | cek availability provider tiap sesi, skip model rusak |
| Auto-verify | hasil tool diverifikasi lagi secara otomatis, loop terbatas |
| Escalation chain | naikkan ke model besar bila kualitas/error; harus izin user |
| STUCK ≠ DONE | tolak label selesai tanpa bukti test/hasil verifikasi |
| Predictor | prediksi penuh-konteks / early-stop |

### Keamanan model

- `sanitize_tool_output` memblokir injeksi instruksi pada output tool.
- **Egress allowlist** untuk `http_request`.
- **Audit log JSONL** append-only `~/.dhybrid/audit/`, redaksi secret.
- **Readonly gate**: Plan Mode membekukan seluruh tool yang bisa mutasi.
- **Eskalasi wajib izin**: `workflow.escalation: ask|auto|deny` (default `ask`, non-interaktif = deny).

---

## Arsitektur

```
src/dhybrid/
├── cli.py           CLI entry (argparse, mode `repl`/`run`)
├── config.py        loading config + env override
├── mode.py          definisi PLAN/BUILD + system-prompt block
├── health.py        health monitor provider
├── agent/
│   ├── loop/        agent_loop, step_executor, state_machine, escalation_policy, nudge_controller
│   ├── router.py    hybrid router + escalasi + cooldown
│   ├── hooks.py     jalur sebelum/setelah tool, audit
│   ├── streaming.py ToolBlockFilter (menyembunyikan blok internal)
│   ├── quality.py   verif penalty & quality scoring
│   ├── auto_verify.py  verification loop berbatas
│   └── problem.py   (konteks budget dsb)
├── llm/             klien multi-provider + estimator token
├── efficiency/      budget, compaction, cache, predictor, checkpoint, lazy policies
├── security/        injection guard, egress allowlist, audit logger
├── tools/           70+ tool + registry + readonly gate
├── session/         store SQLite, memory FTS/vector, context, branch, semantic
├── skills/          loader SKILL.md + plugin + auto-learn
├── subagents/       delegasi agent terisolasi (anti-runaway)
├── eval/            harness eksekusi evaluasi
└── ui/              repl, commands, statusbar, render (prompt_toolkit + rich)
```

Diagram alur langkah: `ui` → `cli` → `loop` (ReAct) → `router` (pilih model) → `tools` (eksekusi) → guard sanitasi output → audit log → loop. Detail per modul di `docs/architecture.md`.

---

## Konfigurasi

File utama `config/default.yaml` (root adalah symlink; sumber sejati di `src/dhybrid/config/default.yaml` untuk wheel). Menyimpan: model utama, budget, preset provider, allowlist tool, `workflow.escalation`, dsb.

Preset model yang tersedia: `openai-fast/big`, `anthropic-fast/big`, `openrouter-fast/big`, `gemini-fast/big`, `groq-fast`, `deepseek-fast`, `bynara-fast/medium/big`, `opencode-zen-*` (9 preset).

Tanpa API key pun bisa jalan: default route `opencode-zen-*` gratis tersedia (6 preset bebas key).

---

## Hemat token

12 teknik terjadi secara internal. Ringkasannya:

1. Agent tidak menulis kode yang tidak diminta (lazy policies).
2. Konteks lama dipadatkan, bukan dibuang.
3. Prompt caching (cache_control) memangkas input antar-turn.
4. Router mengarahkan langkah mekanis ke model murah.
5. Ukur dampaknya: `/tokens` persesi, dan bandingkan benchmark `docs/token-efficiency.md`.

Benchmark:

```bash
python -m tests.benchmarks.run_bench        # mode hemat
python -m tests.benchmarks.run_bench --off   # kontrol tanpa teknik hemat
```

---

## Dokumentasi

Index lengkap dan peta dokumen: **[`docs/README.md`](docs/README.md)**

| Tujuan | Dokumen |
|-----|------|
| Instal langkah demi langkah | [`docs/GETTING_STARTED.md`](docs/GETTING_STARTED.md) |
| Semua perintah CLI & slash | [`docs/QUICK_REFERENCE.md`](docs/QUICK_REFERENCE.md) |
| Panduan end-to-end | [`docs/COMPLETE_GUIDE.md`](docs/COMPLETE_GUIDE.md) |
| Konfigurasi lanjutan, sesi, memori | [`docs/ADVANCED_USAGE.md`](docs/ADVANCED_USAGE.md) |
| Arsitektur & aliran data | [`docs/architecture.md`](docs/architecture.md) |
| 12 teknik hemat token | [`docs/token-efficiency.md`](docs/token-efficiency.md) |
| Detail teknis per modul | [`docs/TECHNICAL_DOCS.md`](docs/TECHNICAL_DOCS.md) |
| Multi-bahasa (toolchain) | [`docs/MULTI_LANGUAGE_GUIDE.md`](docs/MULTI_LANGUAGE_GUIDE.md) |
| Audit bug & perbaikan | [`docs/BUGS_AUDIT.md`](docs/BUGS_AUDIT.md) |
| Roadmap | [`docs/roadmap.md`](docs/roadmap.md) |
| Riwayat rilis | [`CHANGELOG.md`](CHANGELOG.md) |

---

## Pengembangan

Quality gates:

```bash
pytest -q                        # semua test
pytest -q -n auto                # paralel
pytest -q --cov=src/dhybrid      # coverage
bandit -q -r src/dhybrid -c .bandit.yml
pip-audit                        # audit dependensi
pre-commit install               # ruff otomatis sebelum commit
ruff check src tests
```

Release: tag `v*` memicu `.github/workflows/release.yml` → build wheel+sdist → trusted-publish ke PyPI → GitHub Release.

Deploy container: `Dockerfile` + `docker-compose.yml` (sandbox untuk pengecekan/preview).

---

## Lisensi

MIT — lihat `LICENSE`. Produk data 100% lokal. Repo: [github.com/FerzDevZ/dhybrid-agent](https://github.com/FerzDevZ/dhybrid-agent).