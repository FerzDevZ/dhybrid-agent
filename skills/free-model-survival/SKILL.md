---
name: free-model-survival
description: Pakai model gratis/flash, tool-call format teks, retry 429, prompt hemat
---

# Bertahan dengan Model Gratis / Flash

1. Model free sering TOLAK format native tool-calling (400) — pakai format
   teks: ````tool {"name": "write_file", "arguments": {"path": "x"}}````
   (JSON satu baris di dalam blok) atau kalimat natural pendek.
2. Jangan menulis prosa niat ("saya AKAN buat...", "perlu...", "rencananya...")
   — itu bisa di-parse sebagai tool call atau malah tidak dieksekusi. Tulis
   langsung perintah imperatif: "Buatkan file X dengan isi Y".
3. Rate limit 429: tunggu sebentar lalu coba lagi (retry otomatis); kalau
   beruntun, naik ke model chain berikutnya daripada mengulang terus.
4. Jaga prompt pendek & satu instruksi per pesan; model flash gampang lupa
   konteks panjang — gunakan /compact atau /clear di tengah sesi.
5. Klaim "selesai" WAJIB disertai bukti (file dibuat / test lulus) — model
   kecil sering bilang selesai padahal belum; verifikasi dengan tool dulu.

Larangan: mengirim konteks raksasa ke model free; menyerah setelah 1× 429;
percaya "sudah beres" tanpa verifikasi file/test.
