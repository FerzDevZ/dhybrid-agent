---
name: sql-query-optimization
description: Optimasi query SQL, lambat, index, explain, N+1, database, query, join
---

# Optimasi Query SQL

1. Lihat query + skema: tabel, kolom, index yang ada. Jalankan EXPLAIN QUERY PLAN.
2. Pola umum lambat: full table scan (tidak ada index), N+1 (query per baris),
   join tanpa index, fungsi pada kolom ber-index, mengambil kolom tak terpakai.
3. Perbaiki berurutan: index → tulis ulang query → denormalisasi (terakhir).
4. Verifikasi dengan EXPLAIN ulang + ukur waktu nyata pada data yang mirip produksi.
5. Batasi hasil (LIMIT), hindari SELECT *, batch insert/update bila banyak baris.

Larangan: menambah index sembarangan (tiap index memperlambat write), optimasi
untuk dataset kecil yang tidak akan membesar.
