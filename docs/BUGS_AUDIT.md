# BUGS_AUDIT — dhybrid-agent v0.9.6

> Rekap audit pencarian bug (plan: `.hermes/plans/2026-08-06_090000-audit-bug-dhybrid-agent.md`).
> Status: DIAGNOSA / PERBAIKAN / WONTFIX / FALSE-POSITIVE.

## Ringkasan

- Baseline: full suite **545 passed, 12 skipped** (hijau). Versi sinkron (`0.9.6`).
- Kernel audit allowlist gating (pitfall #2): tool terdaftar di registry tapi absen dari
  `config/default.yaml` -> agent tidak bisa memanggil, sementara unit test yang memanggil
  fungsi langsung tetap hijau (false-green).

## Tabel temuan

| ID | Lokasi | Jenis | Bukti (command output) | Status |
|----|--------|-------|------------------------|--------|
| BUG-01 | `config/default.yaml` allowlist | Tool terdaftar tapi tidak di-allowlist: `todo_clear`, `cargo_outdated`, `episodic_remember`, `episodic_recall`, `episodic_recent`, `episodic_forget` | `probe_allowlist.py`: "TERDAFTAR tapi ABSEN dari allowlist (6)" | **PERBAIKAN** |
| BUG-02 | `src/dhybrid/tools/__init__.py` | dead-entry: tool `orchestrator` di allowlist tapi tidak pernah terdaftar | probe dgn `client_factory`: `'orchestrator' in reg._tools` -> `False` | **PERBAIKAN** |
| FP-01 | `tools/orchestrator.py` | `orchestrator` "tidak terdaftar" saat probe tanpa `client_factory` — **graceful** (bukan bug) | probe tanpa `client_factory` -> `False`; dengan `client_factory` -> `True` | **FALSE-POSITIVE** |

## Perbaikan

### BUG-01: 6 tool absen dari allowlist
- **Fix:** tambahkan ke `config/default.yaml` `tool.allowlist`:
  `todo_clear`, `cargo_outdated`, `episodic_remember`, `episodic_recall`,
  `episodic_recent`, `episodic_forget`.
- **Regresi:** `tests/unit/test_allowlist_audit.py` (`test_semua_tool_terdaftar_harus_di_allowlist`
  + `test_tool_tambahan_new_fix_di_allowlist`).
- Verify: `probe_allowlist.py` -> tidak ada tool registered-absent.

### BUG-02: `orchestrator` tidak pernah terdaftar
- **Akar:** `orchestrator` ada di loop generik `mod.register(reg, max_chars=max_chars)` yang
  tidak meneruskan `client_factory`; `orchestrator.register` `return` dini saat
  `client_factory is None` -> tool mati permanen di produksi.
- **Fix:** registrasi `orchestrator` terpisah dengan `client_factory`:
  `orchestrator.register(reg, max_chars=max_chars, client_factory=client_factory)`.
- **Regresi:** `tests/unit/test_allowlist_audit.py` → `test_orchestrator_hadir_hanya_jika_client_factory`.

## Verifikasi akhir
- `.venv/bin/python -m pytest -q` -> **545 passed, 12 skipped**
- `.venv/bin/python -m ruff check src tests` -> tidak ada error baru (I001 pre-existing di
  `tools/__init__.py` import block tidak disentuh).