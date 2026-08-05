# 🚀 Getting Started — Panduan Pemula Langkah-demi-Langkah

> Di sini semua **apa yang harus ditekan/diketik**, dan **kemana akan lari**.
> Kamu tidak perlu mengerti cara kerja internal — cukup ikuti langkah.
>
> **[⬅️ Kembali ke Perpustakaan](README.md)** • **[📖 Referensi Cepat](QUICK_REFERENCE.md)**

---

## Langkah 1 — Instalasi

**Tekan / ketik** (zsh/bash):

```bash
curl -fsSL https://raw.githubusercontent.com/FerzDevZ/dhybrid-agent/main/install.sh | bash
```

**Apa yang terjadi (lari ke mana):**
- Repo di-clone ke `~/.dhybrid-agent`
- Dibuat environment python (`venv`) + dependensi
- Symlink `~/.local/bin/dhybrid` dibuat → kamu bisa ketik `dhybrid` dari mana saja
- File `.env` dibuat → **kamu harus isi API key**

> 🔑 **Setelah instal** — buka `.env` (`~/.dhybrid-agent/.env`) dan isi minimal satu
> key provider (OpenAI / Anthropic / Gemini / lainnya). Tanpa key, dhybrid tetap
> jalan sebagai chatbot dengan provider gratis (opencode-zen & byNara).

### Alternatif manual
```bash
git clone git@github.com:FerzDevZ/dhybrid-agent.git
cd dhybrid-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env     # lalu isi key
```

---

## Langkah 2 — Pastikan Sehat

**Tekan / ketik:**

```bash
dhybrid doctor
```

**Apa yang dicek (lari ke mana):** config, kunci API, koneksi ke chain, allowlist
tool, dan skill. Lihat baris bertanda ✅ / ❌. Semua ✅ = siap pakai.
`❌` apa pun → selesaikan dulu (biasa masalah key atau config).

---

## Langkah 3 — Jalankan Sesi Interaktif (REPL)

**Tekan / ketik:**

```bash
dhybrid repl
```

**Apa yang terjadi:** masuk mode interaktif. Prompt siap menerima perintah.
Ketik sesuatu seperti:

```
buat aplikasi web TODO sederhana dengan Flask
```

Agent akan: **merencanakan → menulis file → menjalankan test → memberi ringkasan jujur.**

> 💡 Ganti **folder kerja** ke proyek lain: `dhybrid --cwd /path/proyekamu repl`.
> Auto-resume: mulai sesi lagi di proyek yang sama → konteks lama dilanjutkan.

---

## Langkah 4 — Perintah Penting Saat REPL

Di dalam REPL, ketik salah satu **slash perintah**:

| Tekan | Efek (lari ke) |
|-------|----------------|
| `/help` | Daftar semua perintah |
| `/model <nama>` | Ganti model utama (mis. `anthropic-big`) |
| `/tokens` | Dashboard token & biaya sesi ini |
| `/compact` | Ringkas konteks agar hemat token |
| `/sessions` | Daftar semua sesi |
| `/skills` | Lihat / aktifkan skill |
| `/clear` | Mulai percakapan baru (reset konteks) |
| `/quit` | Keluar |
| `Ctrl-D` | Keluar (shortcut) |

**Dan ubah model langsung dari prompt:** `/model gemini-fast`, `/model openai-big`, dst.

---

## Langkah 5 — Jalankan Tugas Sekali Jalan (Non-Interaktif)

Untuk tugas yang "sekali, lalu selesai" (dipakai di skrip/CI):

```bash
# Satu prompt
dhybrid run "refactor fungsi login di src/auth.py lalu jalankan test-nya"

# Output JSON terstruktur (buat automasi)
dhybrid run --json "cek isi repo ini"

# Kerja di proyek lain tanpa pindah folder
dhybrid --cwd /home/user/proyek run "tambah test untuk modul paying"
```

---

## Langkah 6 — Cek Penggunaan & Lanjutkan Sesi

```bash
dhybrid tokens                  # dashboard token+biaya semua sesi
dhybrid sessions                # daftar session
dhybrid resume <session_id>     # lanjutkan sesi lama (dari ringkasan)
dhybrid skills                  # daftar skill
```

---

## 🧭 Alur singkat "apa → ke mana" untuk pemula

| Kamu mau | Tekan/lakukan | Kemudian |
|----------|---------------|----------|
| Instal alat ini | ketik perintah curl di atas | isi `.env` → `dhybrid doctor` |
| Cek kesehatan | `dhybrid doctor` | ☑ semua → lanjut |
| Bicara dengan agent | `dhybrid repl` | ketik tugas → amati alur: plan → code → test |
| Sekali tugas, cepat | `dhybrid run "..."` | langsung hasil, keluar |
| Belajar perintah lebih jauh | `/help` saat REPL | kembalilah kesini [QUICK_REFERENCE](QUICK_REFERENCE.md) |

---

## 🛟 Koneksi & Satu Hal yang Perlu Diingat

- **Data lokal**: SQLite di `~/.dhybrid/` — sesi, memori, cache. Tidak terkirim ke server mana pun selain LLM yang kamu pilih.
- **Tanpa API key?** dhybrid akan coba provider **gratis** (opencode zen `*-free`, byNara) dulu.
- **Perhatian**: tetap saring perintah agent — tools terminal memakai gerbang keamanan + konfirmasi untuk perintah berbahaya.

---

**Siap.** Mulai di [LANGKAH 1](#langkah-1--instalasi), lalu tekan perintah di sepanjang jalan. 🎉