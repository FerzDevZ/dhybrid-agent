---
name: performance
description: Optimasi performa, profiling, kompleksitas, hemat resource
---

# Optimasi Performa (Minimal)

Urutan kerja:
1. Ukur DULU (profile: waktu, jumlah panggilan) — jangan optimasi tanpa data.
2. Cari bottleneck terbesar (sering: loop dalam, query berulang, I/O).
3. Perbaiki dengan perubahan paling kecil:
   - hoist perhitungan keluar loop
   - cache hasil yang berulang
   - hindari O(n²) → O(n) bila mudah
   - batasi I/O (baca sekali, proses banyak)
4. Verifikasi: ukur lagi, pastikan lebih cepat & test tetap hijau.

Larangan: micro-optimasi prematur, "premature optimization is the root of all evil".
