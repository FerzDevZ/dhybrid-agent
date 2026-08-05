---
name: lihat-url-tersebut
description: Lihat/munculkan isi halaman web langsung dari URL tanpa perlu model eksternal (bisa untuk URL publik apapun)
---

# Lihat URL Tersebut

Lihat/munculkan isi halaman web langsung dari URL. Sangat berguna untuk
membaca tutorial, dokumentasi, blog, atau halaman web publik lainnya.

## Cara Pakai

Ketik saja:

```
lihat-url-tersebut https://www.contoh.com
```

Output berupa teks bersih (HTML sudah dibersihkan) dengan judul halaman
sebagai header (`# <title>`) dan isi utama di bawahnya.

Tools yang dipakai: `web_fetch` — tidak memerlukan model LLM tambahan,
jadi sangat hemat token dan tidak bisa error 403 karena API key.

## Verification

- [ ] `lihat-url-tersebut https://example.com` → menampilkan teks "This domain is for use..."
- [ ] `lihat-url-tersebut https://www.rumahweb.com/` → menampilkan konten Rumahweb
- [ ] URL tidak valid (bukan http/https) → pesan error jelas
- [ ] Timeout/halaman error → pesan error jelas, tidak crash
