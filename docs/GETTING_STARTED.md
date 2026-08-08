# Getting Started — Panduan Pemula Langkah-demi-Langkah

Dokumen ini berisi perintah yang perlu diketik dan apa yang terjadi di baliknya. Tidak perlu memahami cara kerja internal — cukup ikuti langkahnya.

## Langkah 1 — Instalasi

Jalankan (zsh/bash):

```bash
curl -fsSL https://raw.githubusercontent.com/FerzDevZ/dhybrid-agent/main/install.sh | bash
```

Yang dilakukan skrip:
- Clone repo ke `~/.dhybrid-agent`
- Buat environment python (`venv`) + dependensi
- Buat symlink `~/.local/bin/dhybrid` → perintah `dhybrid` bisa dipakai dari mana saja
- Buat file `.env` → wajib diisi API key

Setelah instalasi, buka `~/.dhybrid-agent/.env` dan isi minimal satu key provider (OpenAI, Anthropic, Gemini, atau lainnya). Tanpa key, dhybrid tetap jalan sebagai chatbot dengan provider gratis (opencode-zen & byNara).

### Alternatif manual
```bash
git clone git@github.com:FerzDevZ/dhybrid-agent.git
cd dhybrid-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env     # lalu isi key
```

## Langkah 2 — Pastikan Sehat

```bash
dhybrid doctor
```

Yang dicek: config, kunci API, koneksi ke chain, allowlist tool, dan skill. Lihat baris bertanda OK atau gagal. Semua OK = siap pakai. Ada yang gagal → selesaikan dulu (biasanya masalah key atau config).

## Langkah 3 — Jalankan Sesi Interaktif (REPL)

```bash
dhybrid repl
```

Masuk mode interaktif. Prompt siap menerima perintah. Contoh:

```
buat aplikasi web TODO sederhana dengan Flask
```

Alur agent: merencanakan → menulis file → menjalankan test → memberi ringkasan jujur.

Ganti folder kerja ke proyek lain: `dhybrid --cwd /path/proyekamu repl`. Auto-resume: mulai sesi lagi di proyek yang sama → konteks lama dilanjutkan.

## Langkah 4 — Perintah Penting Saat REPL

Di dalam REPL, ketik salah satu slash command:

| Perintah | Dampak |
|----------|--------|
| `/help` | Daftar semua perintah |
| `/model <nama>` | Ganti model utama (mis. `anthropic-big`) |
| `/tokens` | Dashboard token & biaya sesi ini |
| `/compact` | Ringkas konteks agar hemat token |
| `/sessions` | Daftar semua sesi |
| `/skills` | Lihat / aktifkan skill |
| `/clear` | Mulai percakapan baru (reset konteks) |
| `/quit` | Keluar |
| `Ctrl-D` | Keluar (shortcut) |

Ubah model langsung dari prompt: `/model gemini-fast`, `/model openai-big`, dst.

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

## Langkah 6 — Cek Penggunaan & Lanjutkan Sesi

```bash
dhybrid tokens                  # dashboard token+biaya semua sesi
dhybrid sessions                # daftar session
dhybrid resume <session_id>     # lanjutkan sesi lama (dari ringkasan)
dhybrid skills                  # daftar skill
```

## Hal yang Perlu Diingat

- Data lokal: SQLite di `~/.dhybrid/` — sesi, memori, cache. Tidak terkirim ke server mana pun selain LLM yang kamu pilih.
- Tanpa API key: dhybrid mencoba provider gratis (opencode-zen `*-free`, byNara) dulu.
- Tetap saring perintah agent — tools terminal memakai gerbang keamanan + konfirmasi untuk perintah berbahaya.