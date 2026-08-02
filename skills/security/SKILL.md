---
name: security
description: Keamanan kode, injection, path traversal, secret, input validation
---

# Keamanan Kode

Cek wajib saat menyentuh kode yang menerima input:
1. **Injection** — jangan gabungkan input mentah ke shell/SQL tanpa escape.
2. **Path traversal** — validasi path user (`../`), batasi ke direktori yang diizinkan.
3. **Secret** — API key/password TIDAK boleh hardcode/commit; pakai env var.
4. **Input validation** — tipe, panjang, rentang; jangan percaya input.
5. **Error handling** — jangan bocorkan detail internal ke user (traceback).

Perintah shell: hindari `shell=True` dengan input user; pakai list args + shlex.
