---
name: tdd
description: TDD test-driven development red-green-refactor, tulis test dulu sebelum implementasi
---

# TDD (Test-Driven Development)

Alur WAJIB untuk fitur/kode baru:

1. **RED** — tulis test yang gagal dulu (tool `tdd_status` / `run_tests` → RED).
2. **GREEN** — tulis implementasi minimal sampai test lolos.
3. **REFACTOR** — bersihkan tanpa mengubah perilaku; test harus tetap hijau.

Aturan:
- Jangan implementasi sebelum test ditulis.
- Implementasi minimal: cukup bikin test hijau, tidak lebih.
- Tool `tdd_status` memberi status RED/GREEN/NO_TESTS — pakai sebelum & sesudah edit.
