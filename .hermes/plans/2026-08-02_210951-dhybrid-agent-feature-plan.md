# dhybrid-agent — Rencana Fitur Lengkap (v0.3.0 → v1.0)

> **Untuk Hermes:** gunakan skill `subagent-driven-development` untuk mengimplementasikan plan ini task-by-task.

**Goal:** Peta jalan fitur lengkap dhybrid-agent dari v0.2.0 (rilis sekarang) menuju v1.0 — stabil, powerful, mudah dipakai, hemat token, dan siap dipakai publik.

**Architecture:** 3 lapis yang sudah ada (LLM layer → Efficiency core → Agent runtime) ditambah lapisan baru: *Ops* (doctor, self-update, persistence), *Integrasi* (MCP, browser, gateway), dan *Distribusi* (CI, release, completion). Semua tetap local-first.

**Tech Stack:** Python 3.12, stdlib-first (argparse, sqlite3, dataclasses), httpx + pyyaml. Tambahan minimal: `prompt_toolkit` (REPL richer, opsional), GitHub Actions (CI), websockets (gateway, v0.5).

---

## 1. Status Saat Ini (v0.2.0 — sudah live di GitHub)

**Sudah ada & teruji (81 test hijau):**
- CLI: `dhybrid` (bare) → banner + menu `/`; `run`/`repl`/`tokens`/`resume`/`sessions`/`skills`; opsi global `--model/--cwd/--yes`
- Satu model utama, pilih bebas: preset / `provider:model` / manual di route aktif (`/settings`, `/model`, `/key`)
- 13 provider preset (OpenAI, Anthropic, OpenRouter, Gemini, Groq, DeepSeek + 8 route opencode zen, 6 gratis)
- Default = zen `deepseek-v4-flash-free` — jalan TANPA API key; metering token (stream_options.include_usage)
- Mode tool loop GANDA: native (OpenAI/Anthropic) + teks fallback (` ```tool `) — kompatibel model tanpa tool-calling (zen)
- 12 teknik hemat token: lazy policies, compaction, prompt caching, budget, early-stop, cache, resume-by-summary, dsb.
- Tool: terminal (gerbang keamanan), files (range-read), apply_patch, grep/find, git, pytest/TDD, todo, memory FTS5, subagent
- Persistence: SQLite (sessions/messages/usage), memory jangka panjang, resume via ringkasan
- Skills (`skills/<nama>/SKILL.md`, auto-inject relevansi), benchmark harness, installer one-liner, docs
- GitHub: repo public, release v0.2.0, tag main

**Kelemahan yang diketahui (dasar prioritas v0.3.0):**
1. Pilihan model TIDAK persisten (per sesi saja)
2. Tidak ada `doctor`/diagnosa; error API hanya tampil mentah
3. Tidak ada self-update — user harus jalankan ulang installer manual
4. Tidak ada CI — regresi hanya ketahuan manual
5. REPL pakai `input()` polos — tanpa history/arrow keys

---

## 2. Visi & Prinsip Desain

- **Hemat token adalah fitur inti** — setiap fitur baru harus punya biaya token yang terukur.
- **Local-first** — data user tidak pernah wajib ke server pihak ketiga.
- **Satu perintah, menu lengkap** — `dhybrid` langsung usable; `/settings` satu pintu.
- **Lazy** — kode terbaik adalah kode yang tidak ditulis (YAGNI tetap berlaku untuk fitur).
- **Gratis dulu** — route zen gratis jadi jalur default; fitur berbayar opsional.
- Setiap fitur: TDD, commit kecil, verifikasi live (zen gratis sebagai jalur test tanpa key).

---

## 3. Peta Jalan

| Versi | Tema | Fitur |
|---|---|---|
| **v0.3.0** | Praktis & Stabil | F1 model persisten · F2 doctor · F3 self-update · F4 CI · F5 shell completion · F6 release otomatis |
| **v0.4.0** | Power | F7 MCP tools · F8 browser tool · F9 auto-skill · F10 multi-workspace + per-project memory |
| **v0.5.0** | Jangkauan | F11 gateway multi-channel · F12 model lokal opsional · F13 plugin API |
| **v1.0** | Rilis | Hardening, benchmark publik, docs lengkap, release final |

Prioritas user (dari sesi): F1+F2+F3 dulu (tiga fitur praktis), lalu F4+F5.

---

## 4. v0.3.0 — Praktis & Stabil

### F1: Pilihan Model Persisten

**Objective:** Pilihan model (dan provider) tersimpan di `~/.dhybrid/config.yaml` — bertahan setelah restart, tanpa edit manual YAML.

**Files:**
- Modify: `src/dhybrid/session/context.py` (set_model/set_small_model → tulis ke user config)
- Create: `src/dhybrid/session/userconfig.py` (load/save user override YAML)
- Modify: `src/dhybrid/config.py` (merge user config setelah default)
- Test: `tests/unit/test_userconfig.py`

**Task F1.1: UserConfig loader/saver**
```python
# src/dhybrid/session/userconfig.py
from pathlib import Path
import yaml

def user_config_path() -> Path:
    return Path.home() / ".dhybrid" / "config.yaml"

def load_user_config() -> dict:
    p = user_config_path()
    return yaml.safe_load(p.read_text()) if p.exists() else {}

def save_model_choice(model_cfg) -> None:
    p = user_config_path(); p.parent.mkdir(parents=True, exist_ok=True)
    data = load_user_config()
    data["model"] = {"provider": model_cfg.provider, "model": model_cfg.model,
                     "base_url": model_cfg.base_url, "api_key_env": model_cfg.api_key_env}
    p.write_text(yaml.safe_dump(data, sort_keys=False))
```
- Test: simpan → load → nilai cocok; file tidak ada → `{}`.
- Run: `pytest tests/unit/test_userconfig.py -v` → RED → implement → GREEN → commit `feat: user config persistence`.

**Task F1.2: Merge ke Config.load**
- `Config.load()`: setelah default, baca `~/.dhybrid/config.yaml`; blok `model:` menimpa default (bukan presets).
- Test: tulis user config dengan model lain → `Config.load()` memakainya; tanpa file → default zen.
- Commit: `feat: config load merge user overrides`.

**Task F1.3: Wire ke /settings & /model**
- `ctx.set_model()` dan `set_small_model()` memanggil `save_model_choice()`.
- Output ditambah catatan: `(tersimpan permanen)`.
- Test: `test_settings.py` tambah — set_model menulis file (tmp HOME via monkeypatch `user_config_path`).
- Verifikasi live: `dhybrid --model openrouter-big` → restart `dhybrid` → menu tetap openrouter-big.
- Commit: `feat: pilihan model persisten`.

### F2: `dhybrid doctor`

**Objective:** Diagnosa sekali jalan: config, API key per provider, koneksi ke endpoint, versi vs remote, health tool.

**Files:**
- Create: `src/dhybrid/doctor.py`
- Modify: `src/dhybrid/cli.py` (subcommand `doctor`)
- Test: `tests/unit/test_doctor.py`, `tests/e2e/test_cli_smoke.py`

**Task F2.1: Checker statis (tanpa network)**
- Cek: config loadable; model aktif ter-resolve; tiap preset punya base_url valid; API key ada/tidak per provider; workspace writable; sqlite db writable; python ≥ 3.12.
- Output format: `[✓]/[✗] label — detail` (non-tty aman).
- Test: setiap checker fungsi murni `check_x(cfg) -> (bool, str)`.

**Task F2.2: Checker network (opsional, timeout 5s/provider)**
- `GET {base_url}/models` (OpenAI-compat) / `GET {base_url}/models` (Anthropic `/v1/models`) → status.
- Flag `--offline` untuk skip network.
- Test: mock httpx (monkeypatch `_post`/httpx.post) → 200/401/timeout → label benar.

**Task F2.3: Update check**
- `git -C <install_dir> fetch` + banding `HEAD` vs `origin/main` → "update tersedia: vX (jalankan dhybrid self-update)".
- Test: mock subprocess return.

**Task F2.4: CLI wiring + exit code**
- `dhybrid doctor [--offline]` → exit 0 jika semua OK, 1 jika ada ✗.
- Commit: `feat: dhybrid doctor`.

### F3: Self-Update

**Objective:** `dhybrid self-update` memperbarui instalasi (git pull + pip install -e) dan notifikasi update saat buka.

**Files:**
- Create: `src/dhybrid/updater.py`
- Modify: `src/dhybrid/cli.py`, `src/dhybrid/ui/repl.py` (notifikasi welcome)

**Task F3.1: updater core**
```python
# src/dhybrid/updater.py
def update_available() -> bool:      # fetch + banding HEAD vs origin/main
def self_update() -> str:            # git pull --ff-only + pip install -e + return log
def current_version() -> str         # git describe --tags --always
```
- Test: mock subprocess → update_available True/False; self_update memanggil urutan perintah benar.

**Task F3.2: CLI + notifikasi**
- `dhybrid self-update` → jalankan, tampilkan log, versi baru.
- Welcome menu: jika `update_available()` → baris kuning "⚠ update tersedia — ketik /update" (cek sekali per hari via file timestamp cache).
- Test smoke: `dhybrid self-update` exit 0 (di repo dev = "sudah terbaru").
- Commit: `feat: self-update + notifikasi`.

### F4: GitHub Actions CI

**Objective:** pytest + ruff otomatis tiap push/PR; artefak release otomatis saat tag.

**Files:**
- Create: `.github/workflows/ci.yml`

**Task F4.1: Workflow CI**
```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "3.12"}
      - run: pip install -e ".[dev]"
      - run: ruff check src tests
      - run: pytest -q
```
- Verifikasi: push → badge hijau di README (`![CI](https://github.com/FerzDevZ/dhybrid-agent/actions/workflows/ci.yml/badge.svg)`).
- Commit: `ci: github actions (pytest + ruff)`.

**Task F4.2 (opsional): Release otomatis**
- Workflow `release.yml` on tag `v*`: buat GitHub Release dari release-notes template + lampirkan `install.sh` checksum.
- Commit: `ci: auto release on tag`.

### F5: Shell Completion

**Objective:** Tab-completion bash/zsh untuk `dhybrid` (subcommand + preset + flag).

**Files:**
- Create: `scripts/completions.bash`, `scripts/completions.zsh`
- Modify: `install.sh` (source completion bila shell terdeteksi), `src/dhybrid/cli.py` (`--completion` print skrip)

**Task F5.1: Skrip completion**
- Subcommand: `repl run tokens resume sessions skills doctor self-update`; flag: `--model --cwd --config --yes`; preset: `complete -W "$(dhybrid --list-presets 2>/dev/null)"` — tambah `dhybrid --list-presets` ke cli.
- Test: bash -n / zsh -n syntax; manual: `dhybrid <TAB>`.

**Task F5.2: Installer wiring**
- `install.sh`: deteksi `$SHELL`; bash → `.bashrc` source `$INSTALL_DIR/scripts/completions.bash` (guard marker).
- Commit: `feat: shell completion`.

### F6: Polish REPL (bonus kecil)

**Objective:** History + arrow keys + Ctrl-C friendly, tanpa dependensi berat.

**Files:**
- Modify: `src/dhybrid/ui/repl.py`

**Task F6.1:** gunakan `readline` (stdlib) bila tersedia: `readline.read_history_file(~/.dhybrid/history)` + save on exit. Fallback `input()` bila readline tidak ada.
- Test: manual — ketik, panah atas, history tersimpan antar sesi.
- Commit: `feat: repl history`.

---

## 5. v0.4.0 — Power

### F7: MCP Tools (Model Context Protocol)

**Objective:** Dukung MCP server eksternal (stdio) sebagai tool tambahan — akses ekosistem MCP.

**Files:**
- Create: `src/dhybrid/tools/mcp.py`, `src/dhybrid/mcp/client.py` (stdio transport, JSON-RPC)
- Config: `tool.mcp_servers: [{name, command, args, env}]` di default.yaml + user config

**Task F7.1: Client stdio MCP**
- Spawn `command`, handshake `initialize`, `tools/list`, `tools/call` — timeout 30s, cap output 8k.
- Test: fake MCP server script (stdio echo) di test — list/call berhasil.

**Task F7.2: Registry wiring**
- `build_tools()` menambah tool `mcp_<name>_<tool>` per server terdaftar; allowlist tetap berlaku.
- Test: config 1 server fake → specs() berisi tool MCP.

**Task F7.3: Keamanan**
- Server hanya dari config eksplisit (bukan prompt); output di-cap; proses di-kill saat sesi tutup.
- Commit: `feat: MCP tools`.

### F8: Browser Tool

**Objective:** Agent bisa fetch halaman web (riset, docs) dengan hemat token (extract teks, bukan HTML mentah).

**Files:**
- Create: `src/dhybrid/tools/web.py`
- Deps: stdlib `urllib` (atau httpx yang sudah ada); parsing: regex-based text extraction (tanpa bs4 — hemat deps) atau `html.parser` stdlib.

**Task F8.1: `web_fetch(url, max_chars=6000)`**
- GET dengan UA, timeout 15s; ekstrak `<title>` + teks dari tag `<p>/<h1-h6>/<li>/<pre>` via `html.parser`; strip markup; cap.
- Test: file:// local HTML di tmp → teks bersih; URL tak valid → pesan error.

**Task F8.2: `web_search(query, max_results=5)` (opsional)**
- Via endpoint gratis (mis. DuckDuckGo lite scrape) — cap; catatan: bisa berubah, jadikan opsional di allowlist default.
- Commit: `feat: browser/web tool`.

### F9: Auto-Skill Creation

**Objective:** Sesi sukses → skill baru otomatis (pola Hermes: "simpan sebagai skill?").

**Files:**
- Modify: `src/dhybrid/ui/repl.py`, `src/dhybrid/skills/loader.py`

**Task F9.1:** setelah task coding selesai & user puas (konfirmasi `y/N`), agent diminta buat `skills/<nama>/SKILL.md` (frontmatter + langkah) dari sesi; simpan ke `~/.dhybrid/skills/`.
- Test: fungsi `skill_from_session(messages, dir)` → SKILL.md valid (parse ulang via loader).
- Commit: `feat: auto-skill creation`.

### F10: Multi-Workspace & Per-Project Memory

**Objective:** Memori & sesi terpisah per proyek (`~/.dhybrid/projects/<hash-cwd>/`).

**Files:**
- Modify: `src/dhybrid/session/context.py`, `src/dhybrid/session/memory.py`

**Task F10.1:** `workspace` default mengikuti cwd project (hash path) untuk memory.sqlite; sesi tetap global.
- Test: dua cwd berbeda → memory terpisah.
- Commit: `feat: per-project memory`.

---

## 6. v0.5.0 — Jangkauan

### F11: Gateway Multi-Channel (ala OpenClaw)

**Objective:** Satu daemon `dhybrid gateway` melayani channel (Telegram, WhatsApp, Discord) dengan sesi per chat.

**Files:**
- Create: `src/dhybrid/gateway/` (server + adapter), `src/dhybrid/cli.py` subcommand `gateway`
- Deps: `websockets` / httpx long-poll (Telegram Bot API tanpa dep baru)

**Task F11.1:** Gateway inti — daemon, sesi per chat_id, antrian pesan, timeout.
**Task F11.2:** Adapter Telegram (paling mudah; token bot) — polling updates.
**Task F11.3:** Kontrol: `gateway start/stop/status`, autentikasi pairing (kode).
- Verifikasi live: bot Telegram menjawab prompt → jawaban agent.
- Commit: `feat: gateway telegram`.

### F12: Model Lokal Opsional (Ollama)

**Objective:** Adaptor `/api/chat` ~30 baris, opsional (user yang memilih). Dulu di-skip atas permintaan user — sekarang jadi opsi config, bukan default.

**Files:**
- Modify: `src/dhybrid/llm/providers.py` (OllamaClient), `make_client` tambah `ollama`
- Test: mock HTTP `{"message":{"content":...},"done":true}` → parse benar.
- Commit: `feat: optional local model (ollama)`.

### F13: Plugin API

**Objective:** Tool/command dari folder `~/.dhybrid/plugins/<nama>/` (Python entry: `register(reg, ctx)`), tanpa fork.

**Files:**
- Create: `src/dhybrid/plugins.py` (loader + sandbox ringan)
- Test: plugin dummy di tmp → tool terdaftar.
- Commit: `feat: plugin api`.

---

## 7. v1.0 — Rilis

**Task R1: Hardening**
- Review keamanan: shell injection (sudah shell=True — perketat dengan `shlex` + allowlist command), path traversal di read_file/write_file/patch, batas ukuran file, timeout semua tool.
- Fuzz-lite: patch parser dengan kasus tepi (patch kosong, konteks ganda, unicode).
- Test: `tests/unit/test_security.py` (traversal `../`, command injection `; rm`, file raksasa).

**Task R2: Benchmark publik**
- Jalankan `run_bench` ON vs OFF di 5 task; tulis `docs/benchmark-v1.md` dengan angka nyata (token, biaya, cache-hit, routing).
- Target: task kecil ≤ 40k token; biaya ≥ 50% lebih hemat vs tanpa teknik.

**Task R3: Docs lengkap**
- `docs/user-guide.md` (skenario nyata), `docs/architecture.md` (perbarui), CHANGELOG.md, LICENSE MIT, README badges (CI, version, license).
- `docs/roadmap.md` dihapus → diganti CHANGELOG + rilis.

**Task R4: Release v1.0.0**
- Tag `v1.0.0` + GitHub Release + verifikasi one-liner install dari tag.

---

## 8. Prioritas & Estimasi

| # | Fitur | Effort | Nilai | Urutan |
|---|---|---|---|---|
| F1 | Model persisten | S (1-2 jam) | Tinggi (UX) | 1 |
| F2 | doctor | S-M | Tinggi (debug) | 2 |
| F3 | self-update | S | Tinggi (ops) | 3 |
| F4 | CI | S | Sedang (kualitas) | 4 |
| F5 | completion | S | Sedang (UX) | 5 |
| F6 | repl history | XS | Sedang (UX) | 6 |
| F7 | MCP | M | Tinggi (ekosistem) | v0.4 |
| F8 | browser | M | Sedang | v0.4 |
| F9 | auto-skill | M | Sedang | v0.4 |
| F10 | per-project memory | S | Sedang | v0.4 |
| F11 | gateway | L | Tinggi (jangkauan) | v0.5 |
| F12 | ollama opsional | XS | Rendah | v0.5 |
| F13 | plugin API | M | Sedang | v0.5 |

Estimasi total v0.3.0: ±1 hari kerja (TDD + verifikasi live per fitur).

## 9. Risiko & Tradeoff

- **F1 (persisten):** user config bisa konflik dengan default saat preset berubah → merge hanya blok yang dikenal; unknown key dipertahankan.
- **F2 (doctor network):** cek network lambat/blocked → selalu `--offline` default? Tradeoff: offline default (cepat, aman), network via `--net`.
- **F3 (self-update):** `git pull` bisa konflik dengan perubahan lokal di repo install → pakai `reset --hard origin/main` (repo install = disposable) + backup config user terpisah (sudah terpisah di ~/.dhybrid/).
- **F7 (MCP):** MCP server bisa berbahaya (akses file) → hanya dari config eksplisit, allowlist tetap, dokumentasi risiko.
- **F8 (browser):** scraping situs berubah-ubah → web_search via lite scraper rawan; jadikan opsional + allowlist non-default.
- **F11 (gateway):** eksposur jaringan → pairing code + allowlist pengguna (pola OpenClaw), dokumentasi keamanan.
- **Keamanan umum:** shell=True tetap dipakai → v1.0 hardening wajib sebelum rilis publik luas.

## 10. Metrik Sukses (definisi selesai)

- **F1:** pilih model → restart → model bertahan (tanpa flag CLI).
- **F2:** `dhybrid doctor` di mesin sehat → semua ✓ exit 0; di mesin rusak → ✗ jelas + petunjuk.
- **F3:** `dhybrid self-update` dari versi lama → versi baru dalam 1 perintah.
- **F4:** setiap push → badge CI hijau; PR yang rusak tertahan.
- **F5:** `dhybrid <TAB><TAB>` menampilkan subcommand + preset.
- **F7:** 1 MCP server dummy → tool muncul & bisa dipanggil.
- **F8:** `web_fetch(url)` mengembalikan teks bersih ≤ 6k chars, tanpa markup.
- **F9:** sesi coding sukses → SKILL.md valid tersimpan.
- **F11:** bot Telegram membalas prompt dengan jawaban agent.
- **R1:** test keamanan (traversal, injection) lulus.
- **R2:** laporan benchmark dengan angka nyata; target token/biaya tercapai.

---

*Disusun 2026-08-02 dari kondisi repo: HEAD c1bc218 (v0.2.0 + fix tool mode teks), 46 modul, 2.994 baris, 81 test hijau.*
