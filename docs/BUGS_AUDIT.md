# BUGS_AUDIT — dhybrid-agent v0.9.6

> Rekap audit menyeluruh error & bug (plan: `.hermes/plans/2026-08-06_101500-audit-lanjutan-error-bug-dhybrid-agent.md`).
> Status: DIAGNOSA / PERBAIKAN / WONTFIX / FALSE-POSITIVE.
> Audit sebelumnya: `.hermes/plans/2026-08-06_090000-audit-bug-dhybrid-agent.md`.

## Hasil akhir (gates)

- **Test:** `.venv/bin/python -m pytest -q --no-cov` → **548 passed, 12 skipped** (baseline 545 + 3 regresi BUG-03).
- **Lint:** `.venv/bin/python -m ruff check src tests` → **"All checks passed!"** (debt 68 → 0).
- **Pre-commit hook ruff kini pass** (sebelumnya selalu gagal oleh debt lint → semua commit terpaksa `--no-verify`).
- **Versi:** sinkron `0.9.6`.

## Tabel temuan (kumulatif dari dua plan)

| ID | Lokasi | Jenis | Bukti (command output) | Status |
|----|--------|-------|------------------------|--------|
| BUG-01 | `config/default.yaml` allowlist | 6 tool terdaftar tapi absen allowlist (`todo_clear`, `cargo_outdated`, `episodic_remember/recall/recent/forget`) → agent tak bisa memanggil | `/tmp/probe_allowlist.py`: "TERDAFTAR tapi ABSEN (6)" | **PERBAIKAN** |
| BUG-02 | `src/dhybrid/tools/__init__.py` | dead-entry `orchestrator`: di allowlist tapi tak pernah terdaftar (loop generik tanpa `client_factory`) | probe: `'orchestrator' in reg._tools` → False | **PERBAIKAN** |
| BUG-03 | `src/dhybrid/skills/loader.py:399` | F821: `search_marketplace_skills` panggil `search_skills` yang tak di-import → NameError ditelan `except` → selalu `[]` (pencarian marketplace mati) | `ruff check --select F821`; test RED → 3 passed | **PERBAIKAN** |
| BUG-04 | `src/dhybrid/tools/db_migrate.py:34-49` | `create_migration()` menulis file baru tanpa cek duplikat → **60 file `create_users_table`** dengan `up_sql` identik (hanya beda header Revision/Created); tool db_migrate mengotori folder migrasi tiap dipanggil | probe hash: 60 file, 1 up_sql unik | **DIAGNOSA → T2/T3** |
| DEBT-01 | 17 file (`src/` + `tests/`) | 68 error lint ruff pre-existing (I001/F401/F811/BLE001/PLW1510/PYI034/UP037/dll) | `ruff check` → "Found 68 errors" → kini "All checks passed!" | **PERBAIKAN** |
| FP-01 | `tools/orchestrator.py` | `orchestrator` "tidak terdaftar" saat probe tanpa `client_factory` — graceful non-bug | probe tanpa/ dengan cf | **FALSE-POSITIVE** |
| OFFPHA-01 | `tools/terminal.py`,`tests.py` | `shell=True` — BY DESIGN (tool terminal/pytest), `# nosec B602` | grep | **FALSE-POSITIVE** |
| OFFPHA-02 | `session/context.py:74-78` | auto-resume ordering — sudah lookup-dulu-baru-insert (komentar eksplisit) | test `test_auto_resume_loads_last_session_for_cwd` | **BERSIH** |
| OFFPHA-03 | 5 `*_toolchain.py` + `cli.py` | `PLW1510` subprocess tanpa `check` — semua memeriksa returncode manual; kini ditambah `check=False` eksplisit | ruff | **PERBAIKAN** (chore) |
| OFFPHA-04 | 16 `except Exception` | semuanya INTENSIONAL (soft-return/ramah): toolchain 8, skills 5, test 2 — ditandai `# noqa` | review tiap lokasi | **WONTFIX** (noqa) |
| CLEAN-01 | deps `pyproject.toml` | `markitdown[pdf,docx,pptx,xlsx]` ✓, `tenacity>=9.0` ✓, tak ada torch/sentence-transformers keras (user veto) | grep pyproject | **BERSIH** |
| CLEAN-02 | security | anti-traversal scaffold (`is_relative_to`), tak ada secret hardcode (hanya nama env var) | test_security + test_power_scaffold | **BERSIH** |
| CLEAN-03 | runtime | `dhybrid doctor` semua check OK (92 tool allowlist), smoke offline: model lemah → quality=0 `stopped_early=True` (jujur) | `doctor` output + `/tmp/smoke_audit.py` | **BERSIH** |

## Perbaikan yang dilakukan (TDD)

### BUG-01 (commit 2026 e4805b3)
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

## Verifikasi akhir
```bash
cd /home/firman/dhybrid-agent
.venv/bin/python -m pytest -q --no-cov        # 548 passed, 12 skipped
.venv/bin/python -m ruff check src tests       # All checks passed!
git status --short                             # bersih (kecuali untracked migrations/.trae)
git push origin main
```