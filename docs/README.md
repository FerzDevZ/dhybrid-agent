# 📚 Dhybrid-Agent — Perpustakaan Dokumentasi

> **Lobi perpustakaan.** Pilih jalur sesuai siapa kamu dan apa yang mau dilakukan.
> Setiap tautan membawa ke "rak" yang relevan — langkah demi langkah, tanpa tersesat.
>
> Versi repo: **v0.9.6** • License: **MIT** • Python: **3.12+** • Local-first, tanpa server.

---

## 🚪 Mulai dari sini — pilih jalurmu

| Kamu ingin… | Klik ke sini → | Isinya |
|-------------|----------------|--------|
| 🆕 Baru kenal, mau langsung coba | **[Memulai Cepat](GETTING_STARTED.md)** | instal → doctor → repl → perintah pertama |
| 🔧 Mau **instal / update** di mesin | [Instalasi](https://github.com/FerzDevZ/dhybrid-agent#install) | one-liner, manual, uv |
| ⌨️ Cari **daftar perintah & slash REPL** | [Referensi Perintah](QUICK_REFERENCE.md) | `dhybrid …`, `/skill`, `/help` |
| 🎛️ Atur **model / provider / budget** | [Konfigurasi](ADVANCED_USAGE.md) | `config/default.yaml`, preset, env |
| 🛠️ Tahu **tools apa** yang tersedia | [Katalog Tools](COMPLETE_GUIDE.md#available-tools) | 70+ tools, alias |
| 🧠 Pahami **arsitektur** sistem | [Arsitektur](architecture.md) | lapisan + struktur folder |
| 💰 **Hemat token / biaya** | [Hemat Token](token-efficiency.md) | 12 teknik + cara mengukur |
| 🔬 Mau **turun ke kesehatan / audit** | [BUGS_AUDIT](BUGS_AUDIT.md) | temuan bug, perbaikan, status |
| 🌐 Dukung **multi-bahasa kode** | [Multi-Bahasa](MULTI_LANGUAGE_GUIDE.md) | Go, Rust, TypeScript, Java, C# |
| 🔭 Teknik **lanjutan & rahasia** | [Advanced Usage](ADVANCED_USAGE.md) | memori, sesi, subagent |
| 🗺️ Lihat **arah pengembangan** | [Roadmap](roadmap.md) | versi, fitur baru, ide |

> 💡 **Jalan pintas pemula — 3 langkah saja:**
> 1. [Instalasi](https://github.com/FerzDevZ/dhybrid-agent#install)
> 2. [RepL](https://github.com/FerzDevZ/dhybrid-agent#quickstart)
> 3. [Referensi Perintah](QUICK_REFERENCE.md)
>
> Semua dokumen lain adalah pendalaman — bisa dibuka kapan saja.

---

## 🏛️ Rak–rak perpustakaan (isi lengkap `docs/`)

### Rak A — Untuk Pengguna
| Dokumen | Isi |
|---------|-----|
| `docs/GETTING_STARTED.md` | 🌱 Panduan pemula langkah-demi-langkah ("tekan ini → ke mana") |
| `docs/QUICK_REFERENCE.md` | Lembar curang: perintah CLI & slash REPL |
| `docs/COMPLETE_GUIDE.md` | Panduan lengkap end-to-end (instal → pakai) |
| `docs/ADVANCED_USAGE.md` | Teknik lanjutan: sesi, memori, routing, subagent |

### Rak B — Arsitektur & Internals
| Dokumen | Isi |
|---------|-----|
| `docs/architecture.md` | Lapisan sistem: CLI → loop → efficiency → LLM → persistence |
| `docs/token-efficiency.md` | 12 teknik hemat token + pengukuran dampak |

### Rak C — Pengembang & Kualitas
| Dokumen | Isi |
|---------|-----|
| `docs/TECHNICAL_DOCS.md` | Dokumentasi teknik mendalam per modul |
| `docs/MULTI_LANGUAGE_GUIDE.md` | Support bahasa kode (linting/scaffold/tools) |
| `docs/BUGS_AUDIT.md` | Hasil audit error/bug + status tiap temuan |
| `docs/roadmap.md` | Roadmap & perencanaan fitur |

### Rak D — Rujukan
| Dokumen | Isi |
|---------|-----|
| `CHANGELOG.md` (root) | Riwayat rilis per versi |
| `EXPORTED_SKILLS.md` (root) | Daftar skill yang diekspor |
| `README.md` (root) | Lobi utama + fitur + instal + quickstart |

---

## 🧭 Kuis cepat: "Mau ke mana?"

1. **Baru mau coba** → [Instalasi](https://github.com/FerzDevZ/dhybrid-agent#install) → [Quickstart](https://github.com/FerzDevZ/dhybrid-agent#quickstart)
2. **Sudah jalan, bingung command** → [QUICK_REFERENCE](QUICK_REFERENCE.md)
3. **Mau pindah model / atur budget** → [ADVANCED_USAGE](ADVANCED_USAGE.md)
4. **Mau bantu develop** → [TECHNICAL_DOCS](TECHNICAL_DOCS.md) + [roadmap](roadmap.md)
5. **Skrip error / mau cek kesehatan** → [BUGS_AUDIT](BUGS_AUDIT.md) + `dhybrid doctor`

---

## ⚠️ Aktivasi GitHub Pages (opsional)

Dokumen ini bisa dibaca langsung dari repo (markdown). Untuk tampilan **web** ala
situs perpustakaan (navigasi sidebar), aktifkan GitHub Pages:

1. GitHub → repo **Settings → Pages**.
2. **Source**: **Deploy from a branch** → branch `main` → folder `docs`.
3. Save. Beberapa menit kemudian situs `https://<user>.github.io/<repo>/` aktif.
4. Beranda Pages akan memakai `docs/README.md` ini.

Pastikan semua `docs/*.md` sudah di-commit & push sebelum mengaktifkan Pages.