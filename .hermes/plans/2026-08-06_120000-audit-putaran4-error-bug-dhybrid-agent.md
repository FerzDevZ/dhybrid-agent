# Audit Lanjutan Error & Bug — dhybrid-agent (Putaran 4)

> **Untuk Hermes:** Eksekusi dengan skill `subagent-driven-development` — subagent fresh per task + review dua tahap (spec-compliance, lalu code-quality).

**Goal:** Melanjutkan audit menyeluruh `dhybrid-agent` v0.9.6. Temukan dan perbaiki bug yang belum ter-cover putaran 1-3. Tutup celah kualitas yang tooling-nya sudah terpasang tapi tidak pernah dijalankan (coverage, bandit, pip-audit).

**Architecture:** Berlapis: (1) root-cause + fix duplikasi migrasi, (2) baseline coverage + test smoke untuk file minim-cover, (3) security scan bandit + pip-audit, (4) logging pada handler yang menelan error, (5) smoke runtime anti-junk, (6) rekap + gate. Semua perbaikan lewat TDD (RED-GREEN) + commit per task.

**Tech Stack:** Python 3.12, pytest + pytest-cov, ruff, bandit, pip-audit, MigrationManager gaya-alembic di db_migrate.py, SQLite.

---

## Konteks dan Asumsi

- Putaran 1-3 selesai dan sudah di-push (branch `main` = `origin/main`):
  - BUG-01: 6 tool terdaftar tapi tidak ada di allowlist. FIXED.
  - BUG-02: `orchestrator` dead-entry (loop generik tanpa client_factory). FIXED.
  - BUG-03: missing import `search_skills` → NameError ditelan except → selalu `[]`. FIXED.
  - DEBT-01: 68 error lint ruff → 0. FIXED.
  - Baseline test: **548 passed, 12 skipped**. `ruff check src tests` → "All checks passed!".
- **TEMUAN BARU (belum disentuh):** folder `migrations/` berisi banyak file `create_users_table` yang isinya identik, hanya beda baris `Revision` dan `Created`. Akar masalah: `MigrationManager.create_migration()` di `src/dhybrid/tools/db_migrate.py` selalu menulis file baru tanpa mengecek apakah migrasi senama sudah ada.
- Tooling keamanan sudah ada di dev-deps (`pyproject.toml`): coverage, bandit, pip-audit. Sudah terinstal di `.venv` (coverage 7.15.3, bandit 1.9.4). Belum pernah dijalankan sebagai gate.
- `cli.py` dan `efficiency/*` pernah dikoreksi pada putaran lalu tapi belum punya test dedicated (lolos hanya sebagai bagian suite).

## Pendekatan

1. Fix `MigrationManager`: jangan buat file migrasi duplikat (cek nama + konten).
2. Bersihkan file migrasi identik dari folder `migrations/`.
3. Hitung baseline coverage per file; tambahkan test smoke untuk file safety-critical yang minim cover.
4. Jalankan bandit + pip-audit; tambal temuan sahih; tandai false-positive dengan `# noqa`/`# nosec`.
5. Tambahkan `logging.exception` pada handler yang menelan error penting.
6. Ulangi smoke offline model lemah; pastikan tidak false-green.
7. Update `docs/BUGS_AUDIT.md`; jalankan semua gate; push.

## File yang Mungkin Berubah

- `src/dhybrid/tools/db_migrate.py` — dedup migrasi.
- `migrations/` — hapus file identik.
- `src/dhybrid/skills/loader.py`, `src/dhybrid/skills/marketplace.py`, `src/dhybrid/agent/loop.py` — tambah logging.
- `tests/unit/test_db_migrate.py` (baru).
- `tests/unit/test_<file>_smoke.py` (baru, untuk file minim-cover).
- `docs/BUGS_AUDIT.md` — update.
- `.pre-commit-config.yaml` — tambah hook bandit (opsional).

---

## Task 1: Root-cause analisis migrasi duplikat

**Objective:** Buktikan bahwa penyebab banyak file `create_users_table` identik adalah `create_migration()` tanpa dedup.

**Files:**
- Read: `src/dhybrid/tools/db_migrate.py` (seluruh)
- Read: contoh `migrations/20260805_192134_create_users_table.py`

**Step 1:** Probe read-only:

```bash
cd /home/firman/dhybrid-agent
ls migrations/*create_users_table* | wc -l
md5sum migrations/*create_users_table* | awk '{print $1}' | sort | uniq -c
```

Expected: banyak file dengan hash identik (kecuali baris Revision/Created).

**Step 2:** Baca `create_migration()`. Catat: `filepath.write_text(content)` dieksekusi tanpa cek file senama yang sudah ada.

**Step 3:** Dokumentasikan akar masalah di `docs/BUGS_AUDIT.md` sebagai **BUG-04**. Belum ubah logika. Commit dokumentasi.

**Expected:** Akar masalah terdokumentasi; belum ada perubahan perilaku.

---

## Task 2: TDD guard dedup di MigrationManager

**Objective:** `create_migration` tidak membuat file baru jika migrasi dengan nama yang sama sudah ada.

**Files:**
- Modify: `src/dhybrid/tools/db_migrate.py` (`create_migration`)
- Test (baru): `tests/unit/test_db_migrate.py`

**Step 1 (RED):** Tulis test:

```python
import tempfile
from pathlib import Path
from dhybrid.tools.db_migrate import MigrationManager

def test_create_migration_tidak_duplikat():
    d = tempfile.mkdtemp()
    mgr = MigrationManager(d)
    mgr.create_migration("create_users_table", "CREATE TABLE users(id SERIAL);", "")
    mgr.create_migration("create_users_table", "CREATE TABLE users(id SERIAL);", "")
    n = len(list(Path(d).glob("*.py")))
    assert n == 1, f"ada {n} file, harusnya 1"
```

Run: `.venv/bin/python -m pytest tests/unit/test_db_migrate.py -q --no-cov`
Expected: FAIL — `n == 2`.

**Step 2 (GREEN):** Ubah `create_migration`. Sebelum menulis, cek apakah sudah ada file yang memuat `up_sql` yang sama:

```python
def _has_migration(self, name: str, up_sql: str) -> bool:
    for p in self.migrations_dir.glob("*.py"):
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        if f'up_sql = """\n{up_sql}\n' in text:
            return True
    return False
```

Dalam `create_migration`: `if self._has_migration(name, up_sql): return migration` (tanpa menulis).

**Step 3:** Run test → PASS.

**Step 4:** Commit: `fix: db_migrate skip pembuatan migrasi duplikat senama`

---

## Task 3: Bersihkan duplikat migrasi

**Files:** `migrations/*.py`

**Step 1:** Kelompokkan file berdasarkan `up_sql` (bandingkan isi, bukan nama). Sisakan satu file per konten unik. Hapus sisanya dengan `git rm`.

**Step 2:** Jalankan `.venv/bin/python -m pytest -q --no-cov` — pastikan tidak ada test yang merujuk file migrasi yang dihapus.

**Step 3:** Commit: `chore: hapus N migrasi duplikat identik`

---

## Task 4: Coverage baseline per-file

**Files:** output coverage (tidak di-commit), plus test smoke baru.

**Step 1:**

```bash
.venv/bin/coverage run -m pytest -q --no-cov
.venv/bin/coverage report -m
```

**Step 2:** Identifikasi file `src/dhybrid/**` dengan coverage < 50%. Fokus pada yang safety-critical: `cli.py`, `config.py`, `llm/*`, `session/*`, `agent/loop.py`.

**Step 3:** Pilih 1-2 file penting yang minim cover. Tulis `tests/unit/test_<file>_smoke.py` dengan 3-5 assert jalur utama (import, fungsi kunci, error path). Commit.

**Step 4:** Catat hasil di `docs/BUGS_AUDIT.md` sebagai CLEAN-04 (baseline coverage).

> YAGNI: tidak mengejar 100%. Hanya buat smoke untuk file yang jalur errornya penting.

---

## Task 5: Security scan bandit + pip-audit

**Files:** `src/`, `.pre-commit-config.yaml`

**Step 1:**

```bash
.venv/bin/bandit -r src/ -f screen -q
```

Catat temuan. Filter false-positive:
- B602/B603 (shell=True): BY DESIGN untuk tool terminal/tests — sudah ada `# nosec`.
- B324 (hash): tidak relevan untuk tool ini.

**Step 2:** Untuk temuan sahih (mis. shell injection dari input user): refactor dengan argumen list (tanpa shell). Test ulang.

**Step 3:**

```bash
.venv/bin/pip-audit --format json 2>/dev/null
```

Baseline 0 bila bersih. Catat hasilnya.

**Step 4:** Tambahkan hook bandit ke `.pre-commit-config.yaml` (opsional, setelah debt lint bersih). Commit.

---

## Task 6: Logging pada error-handler yang menelan galat

**Files:** `src/dhybrid/skills/loader.py`, `src/dhybrid/skills/marketplace.py`, `src/dhybrid/agent/loop.py`

**Step 1:** Grep `except Exception` di semua file src.

**Step 2:** Untuk handler yang menelan error penting (soft-return tapi tidak terlihat): tambahkan `logger.exception(...)` atau `logger.warning(...)`. Pastikan tidak menambah noise di level debug.

**Step 3:** Jalankan ruff + suite penuh. Commit: `chore: logging exception pada handler yang menelan error`

---

## Task 7: Smoke runtime anti-junk

**Files:** `tests/unit/test_loop_stuck.py` (sudah ada), `/tmp/smoke_audit.py` (ulang)

**Step 1:** Ulangi skenario model lemah-berjanji (WeakClient). Pastikan hasil `quality == 0` dan `stopped_early == True` (tidak false-green).

**Step 2:** Bila belum ada test permanen untuk skenario ini, pindahkan ke `tests/unit/` sebagai regresi. Commit.

---

## Verifikasi Global (akhir)

```bash
cd /home/firman/dhybrid-agent
.venv/bin/python -m ruff check src tests          # All checks passed!
.venv/bin/python -m pytest -q --no-cov             # >= 548 passed, 12 skipped
.venv/bin/bandit -r src -f screen -q               # temuan sahih minimal
.venv/bin/pip-audit --format json 2>/dev/null      # bersih
```

---

## Task 8: Rekap BUGS_AUDIT.md + push

**Step 1:** Update `docs/BUGS_AUDIT.md`: tambahkan baris BUG-04 (dedup migrasi), CLEAN-04 (coverage baseline), CLEAN-05 (bandit/pip-audit).

**Step 2:** Jalankan semua gate di atas.

**Step 3:** `git push origin main`.

---

## Risiko dan Tradeoff

- Dedup migrasi mencegah pembuatan ganda; migrasi yang sudah ada (revision lama) tidak terpengaruh. Jika user ingin dua migrasi dengan nama sama tapi isi berbeda, dedup berbasis `up_sql` tetap mengizinkannya (konten berbeda = file baru).
- Coverage hanya sebagai baseline informasi, bukan gate keras.
- Bandit: `shell=True` ditandai `# nosec` karena BY DESIGN; sisanya ditargetkan 0.
- Penghapusan file migrasi hanya untuk yang benar-benar identik kontennya.

## Pertanyaan Terbuka (ajukan sebelum eksekusi)

1. Apakah `migrations/` dipakai oleh Alembic/sqlite nyata, atau hanya hasil scaffold percobaan? Jika nyata, revision lama yang sudah diaplikasi harus dijaga (dedup tidak boleh membuang identitas).
2. Apakah perlu mengejar coverage minimum untuk `cli.py` / `llm/*` / `tools/*`? (opsional, prioritas user)
3. Bandit strictness: izinkan `shell=True` (tool terminal/pytest), atau ingin lebih ketat?
4. Ada secret/API key yang perlu diverifikasi tidak bocor ke git sebelum push?

---

Plan disimpan di: `.hermes/plans/2026-08-06_120000-audit-putaran4-error-bug-dhybrid-agent.md`