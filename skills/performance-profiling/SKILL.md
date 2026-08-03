---
name: performance-profiling
description: Profil kinerja, cari bottleneck, lambat, slow, ukur dulu, optimasi, latency
---

# Profil & Optimasi Kinerja

1. UKUR DULU sebelum mengubah: profiler (cProfile/py-spy), timer, atau benchmark kecil.
   Tanpa angka baseline, optimasi = menebak.
2. Cari bottleneck NYATA: fungsi paling lama dipanggil, loop dalam query, I/O berulang.
3. Optimasi terurut dampak: algoritma/O(n) → cache → I/O batch → micro-opt terakhir.
4. Verifikasi dengan mengukur ulang — bandingkan sebelum/sesudah, tunjukkan angkanya.
5. Jangan optimasi bagian yang bukan bottleneck (YAGNI) — hemat waktu & token.

Larangan: "rasanya lambat", optimasi prematur, menghapus fitur demi kecepatan
tanpa persetujuan user.
