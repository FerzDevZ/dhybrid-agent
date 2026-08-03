---
name: concurrency-debugging
description: Debug race condition, deadlock, thread, async, paralel, concurrency, mutex
---

# Debugging Konkurensi

1. Reproduksi: race condition sulit muncul — jalankan berulang, perbanyak iterasi,
   tambah sleep/jitter untuk memperbesar jendela balapan.
2. Cari state bersama: variabel global, file, DB, cache yang diakses multi-thread/async.
3. Periksa atomisitas: read-modify-write harus dalam satu lock/transaksi.
4. Deadlock: cari lock bersarang dengan urutan berbeda antar thread; gunakan
   urutan lock konsisten atau timeout.
5. Verifikasi: jalankan stress test (banyak iterasi, thread count tinggi) sebelum/sesudah.

Larangan: "tambah sleep" sebagai solusi race; menganggap aman karena "jarang terjadi";
menghapus concurrency daripada memperbaikinya.
