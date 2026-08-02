---
name: debugging
description: Debug error traceback, sistematis, cari akar masalah, jangan menebak
---

# Debugging Sistematis

1. Baca error LENGKAP dulu: pesan, traceback, baris mana, file mana.
2. Reproduksi: jalankan ulang dengan input terkecil yang memicu error.
3. Cari akar masalah (root cause), bukan gejala. Tanya "mengapa" 3x.
4. Periksa asumsi: tipe data, nilai yang masuk, kondisi batas.
5. Perbaiki SATU penyebab, verifikasi dengan test terkecil, baru lanjut.

Larangan: menebak-nebak, mengubah banyak hal sekaligus, menghapus error
tanpa memahami (mis. suppress exception).
