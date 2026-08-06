# BUGS_AUDIT — dhybrid-agent v0.9.6

> Rekap audit menyeluruh error & bug (plan: `.hermes/plans/2026-08-06_101500-audit-lanjutan-error-bug-dhybrid-agent.md` dan putaran 4 `.hermes/plans/2026-08-06_120000-audit-putaran4-error-bug-dhybrid-agent.md`).
> Status: DIAGNOSA / PERBAIKAN / WONTFIX / FALSE-POSITIVE.
> Audit sebelumnya: `.hermes/plans/2026-08-06_090000-audit-bug-dhybrid-agent.md`.

## Hasil akhir (gates)

- **Test:** `.venv/bin/python -m pytest -q --no-cov` → **556 passed, 12 skipped** (baseline 545 + 11 baru: 3 BUG-03 + 3 BUG-04 + 1 anti-junk + 1 BUG-01 allowlist + 3 lainnya).
- **Lint:** `.venv/bin/python -m ruff check src tests` → **"All checks passed!"** (debt 68 → 0, bertahan).
- **Security:** `bandit -c pyproject.toml -r src/` → **0 temuan** (62 → 0); `pip-audit` → **0 vulnerabilities**.
- **Coverage:** baseline total **82%**; `tools/files.py` naik **19% → 94%** (jalur baca/tulis/traversal).
- **Pre-commit hook ruff kini pass** (sebelumnya selalu gagal oleh debt lint → semua commit terpaksa `--no-verify`).
- **Versi:** sinkron `0.9.6`.

## Tabel temuan (kumulatif dari dua plan)

| ID | Lokasi | Jenis | Bukti (command output) | Status |
|----|--------|-------|------------------------|--------|
| BUG-01 | `config/default.yaml` allowlist | 6 tool terdaftar tapi absen allowlist (`todo_clear`, `cargo_outdated`, `episodic_remember/recall/recent/forget`) → agent tak bisa memanggil | `/tmp/probe_allowlist.py`: "TERDAFTAR tapi ABSEN (6)" | **PERBAIKAN** |
| BUG-02 | `src/dhybrid/tools/__init__.py` | dead-entry `orchestrator`: di allowlist tapi tak pernah terdaftar (loop generik tanpa `client_factory`) | probe: `'orchestrator' in reg._tools` → False | **PERBAIKAN** |
| BUG-03 | `src/dhybrid/skills/loader.py:399` | F821: `search_marketplace_skills` panggil `search_skills` yang tak di-import → NameError ditelan `except` → selalu `[]` (pencarian marketplace mati) | `ruff check --select F821`; test RED → 3 passed | **PERBAIKAN** |
| BUG-04 | `src/dhybrid/tools/db_migrate.py:34-49` | `create_migration()` menulis file baru tanpa cek duplikat → **60 file `create_users_table`** dengan `up_sql` identik (hanya beda header Revision/Created); tool db_migrate mengotori folder migrasi tiap dipanggil | probe hash: 60 file, 1 up_sql unik; `test_db_migrate.py` RED→GREEN | **PERBAIKAN** |
| DEBT-01 | 17 file (`src/` + `tests/`) | 68 error lint ruff pre-existing (I001/F401/F811/BLE001/PLW1510/PYI034/UP037/dll) | `ruff check` → "Found 68 errors" → kini "All checks passed!" | **PERBAIKAN** |
| SEC-01 | `prometheus_exporter.py` | B104: metrics server default bind `0.0.0.0` → expose /metrics ke semua interface | bandit B104 | **PERBAIKAN** (host → `127.0.0.1`) |
| SEC-02 | `project_memory.py` | B324: `hashlib.md5` tanpa `usedforsecurity=False` (hash fitur, bukan kripto) | bandit B324 | **PERBAIKAN** |
| LOG-01 | `skills/marketplace.py` + `loader.py` | 9 handler `except Exception` bisu — soft-return tanpa jejak galat (contoh nyata: NameError BUG-03 tak pernah terlihat) | grep `except Exception` → tidak ada logging | **PERBAIKAN** (logger.exception/warning) |
| FP-01 | `tools/orchestrator.py` | `orchestrator` "tidak terdaftar" saat probe tanpa `client_factory` — graceful non-bug | probe tanpa/ dengan cf | **FALSE-POSITIVE** |
| FP-02 | `tools/web.py` ×3 | B310 urlopen — semua URL divalidasi http/https (web_fetch/http_request) atau hardcoded https (DDG) | bandit B310 + review guard scheme | **FALSE-POSITIVE** (nosec) |
| FP-03 | `tools/power_scaffold.py` | B701 jinja `autoescape=False` — template KODE program, bukan HTML user | bandit B701 | **FALSE-POSITIVE** (nosec) |
| FP-04 | `tools/project_memory.py` | B608 f-string SQL — query parameterized (`?` + `ids`) | bandit B608 + review | **DIPERBAIKI** — query di-rewrite ke `json_each(?)` (parameterized penuh, tanpa interpolasi string) → B608 tidak relevan, `# nosec` dihapus |
| OFFPHA-01 | `tools/terminal.py`,`tests.py` | `shell=True` — BY DESIGN (tool terminal/pytest), `# nosec B602` | grep | **FALSE-POSITIVE** |
| OFFPHA-02 | `session/context.py:74-78` | auto-resume ordering — sudah lookup-dulu-baru-insert (komentar eksplisit) | test `test_auto_resume_loads_last_session_for_cwd` | **BERSIH** |
| OFFPHA-03 | 5 `*_toolchain.py` + `cli.py` | `PLW1510` subprocess tanpa `check` — semua memeriksa returncode manual; kini ditambah `check=False` eksplisit | ruff | **PERBAIKAN** (chore) |
| OFFPHA-04 | 16 `except Exception` | semuanya INTENSIONAL (soft-return/ramah): toolchain 8, skills 5, test 2 — ditandai `# noqa` | review tiap lokasi | **WONTFIX** (noqa) |
| CLEAN-01 | deps `pyproject.toml` | `markitdown[pdf,docx,pptx,xlsx]` ✓, `tenacity>=9.0` ✓, tak ada torch/sentence-transformers keras (user veto) | grep pyproject | **BERSIH** |
| CLEAN-02 | security | anti-traversal scaffold (`is_relative_to`), tak ada secret hardcode (hanya nama env var) | test_security + test_power_scaffold | **BERSIH** |
| CLEAN-03 | runtime | `dhybrid doctor` semua check OK (92 tool allowlist), smoke offline: model lemah → quality=0 `stopped_early=True` (jujur) | `doctor` output + `/tmp/smoke_audit.py` | **BERSIH** |
| CLEAN-04 | `migrations/` | **60 → 1** file `create_users_table` (sisakan 1 canonical; sisanya identik hanya beda header) | `md5sum` up_sql: 1 unik | **BERSIH** |
| CLEAN-05 | test anti-junk | WeakClient (tanpa tool-call, janji tanpa bukti) → quality<100 + stopped_early — guard anti-junk bertahan | `test_loop_weak_model_no_toolcalls_no_fake_done` | **BERSIH** |

## Perbaikan yang dilakukan (TDD)

### BUG-01 (commit e4805b3)
- `config/default.yaml`: tambahkan 6 tool ke `tool.allowlist`.
- Regresi: `tests/unit/test_allowlist_audit.py` (invariant registry⊆allowlist).

### BUG-02 (commit e4805b3)
- `tools/__init__.py`: pindahkan `orchestrator` keluar loop generik → `orchestrator.register(reg, max_chars, client_factory)`.
- Regresi: `tests/unit/test_allowlist_audit.py` → `test_orchestrator_hadir_hanya_jika_client_factory`.

### BUG-03 (commit 8c0f9f8)
- `loader.py`: tambahkan `search_skills` ke import marketplace.
- Regresi: `tests/unit/test_skills_marketplace_search.py` (3 test: terdefinisi, list kosong, menemukan skill).

### DEBT-01 (commit 14ff022) — 68 → 0
- `I001/F401/F811/UP037/RUF022/SIM117`: auto-fix `ruff --fix`.
- `PLW1510`: `check=False` di `cli.py:188` + 5 toolchain.
- `BLE001` (13 lokasi) + `S110/S112`: `# noqa` (handler intensional).
- `PYI034`: `__enter__ -> Self` (tracing.py).
- `B018`: `_ = ctx.memory`.

### BUG-04 (putaran 4) — dedup migrasi
- `db_migrate.py`: `Migration.timestamp` kini mikro-detik (`%f`) agar konten beda selalu file unik; `create_migration` cek `_find_existing(name, up_sql)` sebelum menulis — konten identik → kembalikan `Migration` yang ada.
- Regresi: `tests/unit/test_db_migrate.py` (3 test: dedup, konten beda → file baru, file dapat di-upgrade).
- `migrations/`: hapus 59 duplikat (git rm), sisakan 1 canonical.

### SEC-01/SEC-02 (putaran 4)
- `prometheus_exporter.py`: default host `0.0.0.0` → `127.0.0.1` (metrics tidak lagi terekspos ke semua interface tanpa diminta).
- `project_memory.py`: `hashlib.md5(..., usedforsecurity=False)`.
- FP bandit (B310×3, B701) ditandai `# nosec` + alasan; B608 project_memory diperbaiki struktural (json_each); `[tool.bandit]` skips by-design B404/B603/B607/B110/B112/B101 terdokumentasi di `pyproject.toml`.

### LOG-01 (putaran 4)
- `marketplace.py`: `export_skill`/`import_skill` → `logger.exception`; loop `list_published_skills` → `logger.warning` (skill rusak dilewati, ada jejak) + `name` dipindah keluar `try` (fix possibly-unbound).
- `loader.py`: 4 wrapper (export/install/list/search) → `logger.exception`.

### Coverage (putaran 4)
- Baseline total 82%; `tests/unit/test_files_smoke.py` (7 test) menaikkan `tools/files.py` 19% → 94% (read offset/limit/truncate, write parent-dir, penolakan traversal, register).

## Verifikasi akhir
```bash
cd /home/firman/dhybrid-agent
.venv/bin/python -m pytest -q --no-cov        # 556 passed, 12 skipped
.venv/bin/python -m ruff check src tests       # All checks passed!
.venv/bin/bandit --configfile pyproject.toml -r src/   # 0 temuan
.venv/bin/pip-audit                            # 0 vulnerabilities
git status --short                             # bersih (kecuali untracked plan docs/.trae)
git push origin main
```
