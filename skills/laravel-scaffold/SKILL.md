---
name: laravel-scaffold
description: Setup project Laravel, auth login register, Breeze, scaffolding PHP
---

# Scaffold Aplikasi Laravel

1. Cek dulu: `php -v`, `composer --version` — kalau tidak ada, install dulu
   (apt install php-cli php-mbstring php-xml php-curl composer).
2. Buat project: `composer create-project laravel/laravel <nama>` di direktori
   tujuan (bukan di dalam project lain).
3. Jalankan dulu `php artisan serve` & buka http://127.0.0.1:8000 — pastikan
   welcome page muncul SEBELUM menambah fitur.
4. Login/register: `composer require laravel/breeze --dev`, lalu
   `php artisan breeze:install` (pilih blade), `npm install && npm run build`,
   `php artisan migrate`. Route `/login`, `/register` otomatis ada.
5. Verifikasi NYATA: jalankan server, cek halaman login/register merespons
   200, dan jalankan test (`php artisan test`) — jangan klaim selesai tanpa itu.

Larangan: mengedit file Laravel tanpa memahami struktur (routes/, app/Http/Controllers/,
resources/views/); melewatkan `migrate` lalu bilang "auth sudah jalan".
