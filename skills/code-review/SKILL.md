---
name: code-review
description: Review kode, cari bug, keamanan, best practice, umpan balik singkat
---

# Code Review

Periksa secara urut:
1. **Kebenaran** — logika, edge case, handling error.
2. **Keamanan** — injection, path traversal, secret hardcode, input tidak tervalidasi.
3. **Kualitas** — duplikasi, nama jelas, fungsi terlalu panjang, komentar menyesatkan.
4. **Kinerja** — kompleksitas tidak perlu, loop dalam query.

Umpan balik: spesifik (file:baris), singkat, beri saran perbaikan konkret.
Jangan meminta refactor besar tanpa alasan (YAGNI).
