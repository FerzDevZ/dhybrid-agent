---
name: root-cause-analysis
description: Analisis akar masalah, kenapa crash/gagal, 5-why, bukti bukan tebakan, penyebab
---

# Analisis Akar Masalah (Root Cause)

1. Gejala ≠ penyebab. Tulis gejala persisnya (pesan error, perilaku, input pemicu).
2. Tanya "mengapa" berulang (5-why) sampai sampai ke keputusan/kode yang salah.
3. Kumpulkan BUKTI dulu: log, traceback, nilai variabel, riwayat git — jangan menebak.
4. Uji hipotesis dengan eksperimen terkecil (reproduksi minimal).
5. Perbaiki akarnya, bukan gejalanya; verifikasi gejala hilang + tidak ada regresi.

Larangan: menyalahkan "cache", "internet", "kebetulan" tanpa bukti; menambal gejala
(try/except kosong, sleep, hardcode) tanpa memahami penyebab.
