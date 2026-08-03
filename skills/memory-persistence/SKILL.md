---
name: memory-persistence
description: Persist context, user preferensi, & long-term facts across sessions via MemoryStore SQLite FTS5
---

# Memory / Context Persistence

Agent ini punya memory lokal (SQLite + FTS5) di `~/.dhybrid/memory.sqlite`.
Skill ini mengajarkan **cara & kebijakan** pakai memory agar konteks bertahan
multi-sesi — tidak cuma "ingat jawaban kemarin", tapi pola yang konsisten.

## Konsep utama (dari kode asli `src/dhybrid/session/memory.py`)

- **KV store** + **FTS5 index** — setiap entri punya `key`, `value`, `updated`.
- **diges** — saat sesi mulai, sistem injeksikan fakta *relevan* berdasar konteks
  (basename `cwd`, topik proyek, keyword) lewat FTS, *bukan* sekadar "terbaru".
- **budget** — setiap fakta dipotong `220` karakter, max ~8 entri per sesi.

## Operasi (via MemoryStore API)

```python
from dhybrid.session.memory import MemoryStore
m = MemoryStore()        # default ~/.dhybrid/memory.sqlite

m.remember("user.pria", "firman pakai bahasa Indonesia, suka singkat & teknis, pakai CLI")
m.remember("project.dhybrid-agent", "repo coding agent; Python 3.12 + venv; pytest; ruff; skills/ auto-inject")
m.remember("project.dhybrid-agent.api", "provider: openai-compatible + anthropic-native; preset opencode-zen free")

print(m.recall("user.pria"))      # ambil satu by key
print(m.search("firman bahasa"))  # pencarian bebas (FTS)
print(m.digest("dhybrid-agent src/agent"))  # fakta relevan utk path konteks ini
m.forget("key-lama")              # hapus
```

## Kebijaran / pola pakai

1. **Simpan fakta STABIL, bukan progres sementara.**
   - `user.pref.*` kebiasaan & bahasa
   - `project.<path-normalized>.*` detail teknis proyek (stack, cara run test, versi build)
   - `tooling.*` path tool/rumus; `workflow.*` langkah berulang (deploy, release)
   - JANGAN simpan: "task X selesai", "commit SHA", nomor PR/isiue — ini **stale** dan
     harus pakai `session_search` (Riwayat percakapan), bukan memory.

2. **Key naming konsisten** — `namespace.bawah` (dot-hierarki). Contoh:
   - `user.lang.id` = "bahasa Indonesia"
   - `project.dhybrid-agent.test-cmd` = "source .venv/bin/activate && python3 -m pytest"

3. **Relevansi, bukan rekencyh.** `digest(context)` pilih fakta yang *cocok konteks cwd*,
   jadi baca `key` berupa path/nama proyek — jangan narasikan umum.

4. **Potong & ringkas.** Memory dipotong 220 char/entri. Tulis value yang padat:
   satu fakta = satu baris. Kalau panjang, buat beberapa entri kecil.

5. **Inject di awal sesi, bukan di akhir.** Fact `digest` sudah di-inject otomatis oleh
   loader context (`src/dhybrid/session/context.py`) — jangan re-inject manual kecuali
   ada konteks baru yang jelas.

## Fitur tambahan / kemampuan agent (disarankan)

Skill ini mendukung pengembangan fitur berikut (belum semua ada di kode):

- `/remember <key> <value>` — command REPL set / overwrite memory (satu baris).
- `/forget <key>` — hapus fact by key (tab konfirmasi).
- `/memories` / `/mem` — list fact terbaru (dengan tag workspace yang relevan).
- `/search-memory <query>` — pencarian FTS bebas, tampilkan hasil.
- **Auto-simpan preferensi** — setelah user koreksi 2x hal yang sama (mis. "pakai
  bahasa Indonesia", "versi rapi di terminal"), tawarkan simpan ke `user.pref.*`.
- **Cross-project namespace** — fact otomatis berprefiks path proyek
  (`project.<normalized-path>.*`) agar memory antar proyek tidak bentrok.
- **Memory decay** (opsional) — flag `memory.ttl_days` agar fact lama auto-expired
  (hindar stale). Karena ini local-first, defaultnya "perpetual" — decay bersifat opt-in.

## Trigger / penggunaan

- User bilang: "ingatkan aku kalau...","simpan preferensi...","kamu masih ingat...?"
- Sebelum sesi baru: loader otomatis panggil `digest(cwd)` — fact relevan masuk context.
- Sesi diajari ini dapat trigger kata: `memory`, `persist`, `remember`, `fact`, `preference`.

## Verifikasi

- `[ ]` memory persisten di `~/.dhybrid/memory.sqlite` (bukan di RAM semata).
- `[ ]` `digest()` mereturn fact relevan konteks cwd (teks akhir sesi sebelumnya).
- `[ ]` tidak simpan data rahasia (`.env`, API key) ke memory — pakai `.env.example` / key manager.
- `[ ]` fact stale (SHA, nomor issue, progres task) tidak pernah masuk memory.
