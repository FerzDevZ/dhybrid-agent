# Audit & Pencarian Bug dhybrid-agent — Implementation Plan

> **Untuk Hermes:** implementasi lewat `subagent-driven-development`, task-by-task, dengan dua-tahap review (spesifikasi lalu kualitas). Kernel audit = perintah eksak + bukti keluaran nyata, bukan asumsi.

**Goal:** Menemukan semua bug, error, kode curiga, dan inkonsistensi pada codebase `dhybrid-agent` (versi 0.9.6), memverifikasi mana yang sungguhan, lalu memperbaikinya dengan TDD dan commit+push.

**Architecture:** Audit 4-lapis — (1) baseline (test+lint hijau?), (2) scan statis pola bug, (3) re-check regresi `pitfall` historis ke file konkret, (4) analisis runtime (`dhybrid doctor`, smoke session, tangkap traceback). Tiap temuan divalidasi dulu (bukan sekadar curiga) → baru perbaikan TDD + regression test. Prinsip DRY/YAGNI: kolom rekap di `docs/BUG_AUDIT.md`, tidak menambah fitur di luar scope.

**Tech Stack:** Python 3.12, pytest, ruff 0.16.1 (di `.venv`), venv wajib (`.venv/bin/python`); SQLite; source di `src/dhybrid/`, test di `tests/`, config di `config/default.yaml`.

---

## Lingkup & Aturan

- **VERIFY WAJIB pakai venv** (system python3 tak punya pytest):
  ```bash
  cd /home/firman/dhybrid-agent
  .venv/bin/python -m pytest -q
  .venv/bin/python -m ruff check src tests
  ```
- **Bahasa**: komentar/test/commit = Bahasa Indonesia, prefix konvensional (`fix:`/`chore:`).
- **Jangan** menyeret proyek sibling (`~/ppj/auth-app`); "push" = repo ini saja.
- **Smoke script** tulis ke `/tmp/*.py` dulu (terminal guard memblok heredoc), jalankan `.venv/bin/python /tmp/...`.
- **Git state saat mulai**: bukan kosong — ada 13 file `migrations/2026...create_users_table.py` untracked (duplikat, revision beda) + `.trae/documents/...`. **JANGAN di-commit** (keputusan user sebelumnya: ignore). Audit tidak menyentuh `migrations/` kecuali ditemukan bug nyata di sana.

---

## Fase 0 — Baseline: Berapa tingkat kesehatan saat ini?

**Tujuan:** tahu titik awal — suite hijau? lint bersih? versi sink? bersih git dari junk?

### Task 0.1: Jalankan seluruh suite test
**Step 1:** `cd /home/firman/dhybrid-agent && .venv/bin/python -m pytest -q 2>&1 | tail -30`
**Expected:** lihat jumlah `passed/failed/errors`. Catat ANY failed/error → inilah bug nyata pertama. Simpan ringkasan ke papan hasil.
**Step 2:** kalau ada fail, catat nama test + file + traceback ke `.hermes/plans/` (temp) untuk di-fix Fase 6.

### Task 0.2: Jalankan ruff (lint + pola)
**Step 1:** `.venv/bin/python -m ruff check src tests`
**Expected:** "All checks passed!" (0). Kalau ada `F401/F811/BLE001` dll → catat.
**Step 2:** `.venv/bin/python -m ruff check src tests --output-format=concise | wc -l` → buat daftar jumlah per kode.

### Task 0.3: Sinkron versi & state git
**Step 1:** `grep -m1 '^version' pyproject.toml` vs `grep -m1 '__version__' src/dhybrid/__init__.py` — kedua harus `0.9.6`. Tidak sinkron = bug.
**Step 2:** `git status --short` — konfirmasi file untracked (13 migration + .trae) TETAP di luar commit.
**Step 3:** `git ls-files | grep -E '(__pycache__|egg-info|\\.env$)'` — harus kosong (junk ter-commit?).
**Expected:** versi sinkron, tidak ada junk ter-tracked.

---

## FASE 1 — Scan statis pola bug umum

**Tujuan: temukan calon bug dengan grep presisi, lalu verifikasi tiap calon di Fase 5.**

### Task 1.1: Handler exception yang menelan error
**Step 1 (grep):**
```
.venv/bin/python -m ruff check src --select BLE,TRY,PERF,SIM 2>/dev/null
```
juga scan manual:
`.venv/bin/python - <<'PY'` tidak; pakai `grep` lewat search_files:
- `grep -rn "except:" src/` → bare except (mematikan segala error)
- `grep -rn "except Exception" src/` → blind handler (BLE001)
- `grep -rn "except.*:\s*pass\|except .*: *pass" src/` → telan silent
**Expected (hit):** daftar lokasi `path:line`. Verifikasi tiap: apakah pad `except` menelan error penting?
**Catatan:** jangan jagoan — banyak `# noqa: BLE001` adalah INTENCIONAL (soft-register, pitfall 2; clari AI fallback, pitfall 25). Core: yang MENYEBABKAN salah-ozon.

### Task 1.2: Tanda TODO/FIXME/laziness & risky code
**Step 1:** `grep -rniE "TODO|FIXME|XXX|HACK|KITA\|not implemented|NotImplemented" src/`
**Step 2:** `grep -rn "= \[\]\s*\$/= {}|.append(" src/` → mutable default arg? verifikasi manual `def fn(x=[]):`.
**Step 3:** `grep -rn "eval(\|exec(\|subprocess.*shell=True\|shell=True" src/` → titik injeksi (lihat Fase 5).
**Expected:** daftar kandidat; yang krusial divalidasi di Fase 2–5.

### Task 1.3: Calon masalah antrian/state global
**Step 1:** `grep -rn "^[_A-Z0-9]* = *\[\]\|^[_A-Z0-9]* = *{}\|REGISTRY\|_items" src/dhybrid/efficiency/prometheus_exporter.py src/dhybrid/agent/*.py src/dhybrid/tools/*.py` → state mutabel global (pitfall #46 prometheus, #10 tool_count). Devia terhadap per-run reset.

---

## Fase 2 — Re-check regresi pitfall historis

**Tujuan: memverifikasi bug yang pernah terjadi TIDAK kembali (regression hunt). Map ke file konkret + test regresi.**

### Task 2.1: Auto-resume ordering (store)
**Baca:** `src/dhybrid/session/store.py` sekitar `recent()`/query "record terakhir" & insert baru. Pola salah: insert row baru SEBELUM query terakhir → problem shadow.
**Verify:** pastikan urutan = lookup_dulu → insert_belakang. Kalau salah → catat.
**Reference:** `references/auto-resume-order-bug.md`.

### Task 2.2: Tool registry arg order (vision & lain)
**Baca:** `src/dhybrid/tools/vision.py` + semua modul yang panggil `reg.register(name, fn, params, desc)`. Pola salah: `fn`↔`desc` tertukar → TypeError saat eksekusi.
**Baca:** `src/dhybrid/tools/registry.py:ToolSpec` — signature positional (nama, deskripsi, params, fn).
**Verify:** untuk tiap modul tool, `reg.execute(NAME, {valid_args})` HARUS run tanpa TypeError (pattern test pitfall #1). Cara: jalankan satu test-file terkait (mis. `tests/unit/test_vision_mime.py`).

### Task 2.3: Allowlist gating (`build_tools` vs config)
**Buku kunci:** Modul baru terdaftar di `build_tools` (`src/dhybrid/tools/__init__.py`) TAPI absen dari `config/default.yaml` allowlist → agent gagal memanggil sementara test hijau.
**Verify:** jalankan scan set-ekspansi:
```bash
.venv/bin/python -c "from dhybrid.tools import build_tools; print(sorted(t.__name__ ...))"
```
dan bandingkan dengan nama di `grep -A200 'allowlist' config/default.yaml`. Buka `doctor.check_allowlist` (Fase 4). Aturan: uint test yang memanggil tool via registry (bukan langsung) agar tak lolos false-green.

### Task 2.4: Intent/nudge/early-stop yang bocor (loop.py)
**Baca:** `src/dhybrid/agent/loop.py` + `agent/quality.py` + `agent/verify.py`:
- `.is_build` gate loop protections (BUILD_VERBS)
- `_expresses_intent()` & INTENT_HINTS
- intent budget `×2` bila `escalation_chain` kosong; `nudges=0` saat tool jalan; satu `hard_nudged` terakhir.
- `_measure_output` dipakai di KEDUA cabang (early-stop & post-loop) → `stopped_early` jujur.
**Verify:** `.venv/bin/python -m pytest tests/unit/test_loop_stuck.py tests/e2e/test_agent_loop.py -q` paling tidak semua green.

### Task 2.5: REPL guard & markup rusak (regression)
**Baca:** `src/dhybrid/ui/repl.py` cara loop `_run_one` (guard `_clarify_done_this_turn`, `_ask_done_this_turn`); `src/dhybrid/agent/text_parser.py` (pasang `BROKEN_MARKUP_RE` sebelum NL pass).
**Verify:** `.venv/bin/python -m pytest tests/unit/test_text_parser.py tests/unit/test_repl_clarify.py tests/unit/test_repl_skills_feedback.py -q` green.

---

## Fase 3 — Konsistensi tool/registri + doctor

### Task 3.1: Semua tool yang terdaftar harus allowlist; sebaliknya
**Step 1:** Jalankan `dhybrid doctor` (Fase 3.2) — `check_allowlist` flags tool inti yang keblok, `check_chain` daftar preset chain mati.
**Step 2:** panggil tiap tool via `ToolRegistry.execute(name, minimal args)` di test ad-hoc `/tmp/tools_probe.py`, assert bukan `"tidak diizinkan (allowlist)"` untuk name di allowlist, dan AssertError friendly utk name soft. Kelola deps opsional (power extra) → harap menghasil pesan install ramah, BUKAN crash.

### Task 3.2: Extra & dependency map (pyproject)
**Step 1:** `grep -nE 'dependencies|optional-dependencies|markitdown|tenacity|redis|e2e|vision|power' pyproject.toml`
- `markitdown` HARUS punya extras `[pdf,docx,pptx,xlsx]` (pitfall #14)
- `tenacity>=9.0` ada (pitfall #29)
- `redis`, `semsearch/FAISS/sentence-transformers` — ingat user VETO `torch/sentence-transformers/chromadb`. Kalau `semantic_search.py`/`episodic_memory.py` mensyaratkan sentence-transformers → VERIFIKASI kalau jadi optional & skip-gracefully (test jaringan tersedia skip).
**Step 2:** kalau ada dependensi "keras" yang wajib `torch/transformers` di jalur import top-level → DILARANG (user veto) → catat bug.

### Task 3.3: `dhybrid doctor` end-to-end
**Step 1 (di dev venv):** `.venv/bin/python -m dhybrid doctor`  (atau `dhybrid doctor` dari biner venv)
**Expected:** tak ada panic; catat semua warning `check_*`.
**Step 2:** `.venv/bin/python -m dhybrid --version` → harus `0.9.6` (bukan crash/ansi).

---

## Fase 4 — Analisis runtime: smoke session & tangkap traceback nyata

**Tujuan: temukan error yang hanya muncul saat LIVE (API, streaming, parse model bebas) yang lewat dari unit test.**

### Task 4.1: Smoke run minimal (tanpa jaringan)
Tulis `/tmp/smoke_audit.py` (via write_file), jalankan `.venv/bin/python /tmp/smoke_audit.py`:
- load `SessionContext` dengan config bersih & `clarify.ai:false`
- jalankan `AgentLoop.run("kerjakan X")` dengan model prilaku bertingkah (free-model) → pastikan tidak ada `TypeError`/`AttributeError` di jalur `loop -> _measure_output -> verify_build`.
**Expected:** tidak panic; kalau panic → catat traceback FULL untuk Fase 6.

### Task 4.2: Tangkap traceback saat `/pasteshot`, `read_image`, `web_fetch`
**Unit re-check:** `.venv/bin/python -m pytest tests/unit/test_vision_mime.py tests/unit/test_web_tools.py tests/unit/test_documents.py -q`
green dulu, lalu smoke terpisah untuk X11/vision hanya jika user punya display & clipboard (opsional — jika dulu runtime tak tersedia, tandai "tidak dapat ditest lokal").

### Task 4.3: Cek jalur Redis & retry (0.9.6) tanpa server Redis
**Baca:** `src/dhybrid/session/store.py` (`RedisStore`), `src/dhybrid/llm/providers.py` (`@retry`).
**Verify:** jalankan `tests/unit/test_redis_store.py` & `test_retry_providers.py` → green; `REDIS_AVAILABLE=False` path → kerja murni SQLite, no crash.

---

## Fase 5 — Audit keamanan singkat

### Task 5.1: Injeksi shell / traversal path
**Baca & scan:**
- `src/dhybrid/tools/terminal.py` — `subprocess` dengan arg list (NO `shell=True`), reject perintah kosong (`pitfall #19`).
- `src/dhybrid/tools/power_scaffold.py` — path traversal (`..`) guard (pitfall "anti-traversal" README).
- `src/dhybrid/tools/files.py` — path allowlist/rep.
- `src/dhybrid/tools/security.py` sudah ada? gunakan untuk verify pattern.
- `grep -rn "shell=True\|os.system\|meta_command\|f'...{...}'" src/` — selidiki bentuk interpstring ke subprocess.
**Verify:** `tests/unit/test_security.py`, `test_power_scaffold.py` green. Jika ada `shell=True` tak ternetral, catat sebagai temuan.

### Task 5.2: Secret/files sensitif di registry
`grep -rniE 'password|api_key|secret|token' src/ | grep -v test` → pastikan tak ada hardcode secret; semua key via env (read dari `~/.env`/provider).

---

## Fase 6 — Rekap & Perbaikan (TDD untuk bug nyata)

### Task 6.1: Tabel rekap ke `docs/BUGS_AUDIT.md` (baru)
Buat tabel: ID | Lokasi file:line | Jenis | Biz-bukti (command output) | Status (DIAGNOSA/PERBAIKAN/WONTFIX). Commit awal: `chore: pertanda tabel bug audit`.

### Task 6.2–6.N: Fix tiap bug TERKONFIRMASI dengan TDD
Utk setiap bug (identifikasi dari Fase 0–5):
**Step 1:** tulis/pastikan test gagal dulu (RED).
```python
def test_<bug_contoh>():
    ...
```
**Run expected:** FAIL.
**Step 2:** perbaiki minimal di file sumber.
**Run expected:** PASS (file target).
**Step 3:** jalankan set test yang mengandung file itu + `ruff check src tests` → hijau, 0 lint error.
**Step 4:** commit `fix: <inti masalah> (<contoh singkat>)` + verifikator.
**Dan setelah semua:** suite PENUH hijau → `.venv/bin/python -m pytest -q` penanda penanda sepenuhnya → git add → commit rekap → `git push origin main`.

### Task 6.x: Batas aturan
- BUG VALID, bisa fix ringan → fix.
- BUG yang dilarang user (mis, menambah dep torch) → ditandai WONTFIX di rekap.
- Temuan yang TERNYATA false-positive (diak ulang dirac) → tutup di rekap dengan alasan, TIDAK di-fix.
- Berhenti setelah ±3 percobaan fix pada file yang sama → tanya user, jangan loop.

---

## File yang kemungkinan berubah
- Baru: `docs/BUGS_AUDIT.md`
- Terpengaruh (tergantung temuan): `src/dhybrid/session/store.py`, `src/dhybrid/agent/loop.py`, `src/dhybrid/agent/text_parser.py`, `src/dhybrid/tools/*.py`, `src/dhybrid/session/store.py`, `config/default.yaml`, dsb — **HANYA bila bug terverifikasi**.
- Tidak disentuh: `migrations/`, `.trae/`.

## Verifikasi akhir (gates)
```bash
cd /home/firman/dhybrid-agent
.venv/bin/python -m pytest -q                       # ALL green (baseline number ±0, no new fail)
.venv/bin/python -m ruff check src tests            # "All checks passed!" 0 errors
git status --short                                  # clean (kecuali untracked migrations/.trae yg sengaja dibiarkan)
git log --oneline -3                                # bukti push
git status -sb | head -1                            # ## main...origin/main (sinkron)
```

## Risiko & tradeoff
- **False-positive grep → buang waktu**: setiap calon DIVALIDASI (jalankan code/repro) sebelum di-fix; prininfo perbedaan "inti historique" vs "intended soft" (noqa BLE/SIM di banyak file itu sengaja).
- **Regression dari "fix"**: hanya fix bila suite hijau sebelumnya; setiap fix pakai TDD. Kalau baseline sudah ada FAIL/hi — FIX baseline dulu sebelum yang lain.
- **Feature bukan bug**: .gitignore/trailing promotion docs dll tidak termasuk → di luar audienc.

## Pertanyaan terbuka
1. Baseline suite ternyata SUDAH punya fail sebelum audit — prioritas (fix fail dulu / catat dulu)? (default: fix dulu).
2. Audit runtime memerlukan display X11/key live untuk /pasteshot & web — apakah environment ini supports? (default: tandai "tidak dapat lokal", jangan block).
3. Kalau ditemukan bug di `migrations/` (13 file duplikat) — user sebelumnya ingin mereka TETAP tidak di-commit. Fix di sana tetap dilarang; ditulis di rekap sebagai item pembersihan terpisah.