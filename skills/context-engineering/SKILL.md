---
name: context-engineering
description: Kelola konteks chat, kompaksi, hemat token, hindari lupa instruksi
---

# Context Engineering — Hemat Token & Jaga Konteks

1. Pantau pemakaian: `dhybrid tokens` (per sesi) — kalau prompt token
   membengkak, kompaksi: `/compact` (manual) atau biarkan otomatis saat
   budget lunak tercapai.
2. Output tool yang panjang (> 2-3 baris) jangan dibiarkan menumpuk di
   riwayat — ringkas hasil grep/read ke fakta penting sebelum lanjut.
3. Satu task = satu pesan; jangan campur 3 instruksi dalam satu prompt.
4. Riwayat panjang membuat model kecil "lupa" instruksi awal — taruh
   konteks penting (path file, keputusan) di ringkasan sesi: `/compact`
   menghasilkan ringkasan yang dipertahankan setelah `/clear`.
5. Gunakan skill inject (otomatis) daripada menulis ulang instruksi panjang
   setiap prompt — skill yang relevan di-inject sendiri ke prompt.

Larangan: membiarkan loop berjalan sampai budget keras tanpa kompaksi;
menyalin ulang instruksi besar berulang-ulang.
