# Dokumentasi dhybrid-agent

Index dokumen proyek. Dipilih sesuai kebutuhan Anda. Versi repo: 0.9.6, Python ≥3.12, MIT.

## Dokumen pengguna

| Dokumen | Isi |
|---------|-----|
| [GETTING_STARTED.md](GETTING_STARTED.md) | Instalasi, konfigurasi, dan sesi REPL pertama pengalaman langkah demi langkah |
| [QUICK_REFERENCE.md](QUICK_REFERENCE.md) | Daftar seluruh perintah CLI + slash command, satu halaman |
| [COMPLETE_GUIDE.md](COMPLETE_GUIDE.md) | Panduan pengguna end-to-end: dari instal sampai deploy |
| [ADVANCED_USAGE.md](ADVANCED_USAGE.md) | Konfigurasi lanjutan: model, provider, budget, sesi, memori, subagent |
| [MULTI_LANGUAGE_GUIDE.md](MULTI_LANGUAGE_GUIDE.md) | Toolchain multi-bahasa (Go, Rust, TypeScript, Java, C#) |

## Dokumen internal & tooling

| Dokumen | Isi |
|---------|-----|
| [architecture.md](architecture.md) | Lapisan sistem dan aliran eksekusi per langkah |
| [token-efficiency.md](token-efficiency.md) | 12 teknik hemat token + cara mengukur dampak |
| [TECHNICAL_DOCS.md](TECHNICAL_DOCS.md) | Detail teknis per modul untuk kontributor |
| [BUGS_AUDIT.md](BUGS_AUDIT.md) | Hasil audit bug, temuan, dan status perbaikan |
| [roadmap.md](roadmap.md) | Arah pengembangan dan prioritas fitur |

## Rujukan root

- [README.md](../README.md) — fitur, instal, quickstart
- [CHANGELOG.md](../CHANGELOG.md) — riwayat rilis
- [EXPORTED_SKILLS.md](../EXPORTED_SKILLS.md) — daftar skill yang diekspor

## Catatan GitHub Pages (opsional)

Dokumen ini terbaca langsung dari repo (markdown). Jika ingin tampilan web dengan sidebar:

1. Repository → Settings → Pages.
2. Source: **Deploy from a branch** → branch `main` → folder `/docs`.
3. Simpan. Situs aktif di `https://<user>.github.io/<repo>/`.
4. Beranda memakai `docs/README.md` ini.

Pastikan semua `docs/*.md` sudah di-commit sebelum mengaktifkan Pages.