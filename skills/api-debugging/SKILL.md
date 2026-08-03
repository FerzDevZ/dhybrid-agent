---
name: api-debugging
description: Debug API HTTP REST, status code, error response, curl, request gagal, endpoint
---

# Debugging API / HTTP

1. Lihat REQUEST-nya dulu: method, URL, header, body. Kesalahan paling sering di sini.
2. Lihat RESPONSE lengkap: status code, header, body error (jangan cuma status).
3. Reproduksi manual dengan curl (tool http_request / terminal) — payload terkecil.
4. Periksa urutan: auth/token → CORS → validasi server → log server → data.
5. Catat kode status umum: 400 param salah, 401/403 auth, 404 route, 429 rate limit,
   5xx masalah server — tapi SELALU baca body error untuk detail.

Larangan: menebak "server error" tanpa membaca body; menambal di client padahal
salah di server (atau sebaliknya).
