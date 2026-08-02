---
name: project-scaffold
description: Buat project baru, scaffolding, setup struktur, cek tool tersedia (php composer node npm python), ikuti stack yang diminta user
---

# Scaffold Project Baru

Saat user minta "buat project X":

1. **IKUTI stack yang diminta user** (Laravel → Laravel, React → React).
   Jangan ganti ke stack lain tanpa persetujuan.
2. Cek tool yang dibutuhkan dulu: `which php composer node npm python3 pip3`
   — kalau tidak ada, beri tahu + tawarkan langkah instalasi.
3. Scaffold dengan tool resmi (composer create-project, npm create, dsb).
4. Struktur dasar + file minimal yang bisa langsung jalan.
5. Verifikasi: jalankan perintah yang membuktikan project hidup (versi, serve, test).

Jangan: menawarkan pilihan stack saat user sudah jelas memintanya.
