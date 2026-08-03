---
name: skills-sh
description: Import & convert skills from skills.sh directory into dhybrid SKILL.md
---

# skills.sh — Import & Convert Skills

[skills.sh](https://www.skills.sh) adalah direktori skill agen AI (cline, amp, goose,
antigravity, kiro-cli, dll). Skillnya rendah-kode (bisa di-`cp` langsung ke project,
bisa dipakai lewat MCP). Skill ini mengajarkan cara **menemukan, memetakan, dan
mengonversi skill dari skills.sh ke format dhybrid `SKILL.md`** secara manual & pakai helper.

## 1. Temukan skill yang sesuai

- Browse: https://www.skills.sh — filter per **agent** (cline, amp, goose, …) atau **topic**
  (build, debug, security, tdd, …).
- URL skill: `https://www.skills.sh/s/<skill-slug>`
- Setiap skill di skills.sh ada 2 bentuk:
  a) **file skill mentah** yang bisa `cp`/`curl` ke project (biasanya `skill.md` atau `.md`)
  b) **prompt** yang dimasukkan ke sistem prompt agen.

## 2. Kenali formatnya

skill di skills.sh punya metadata di tiap atas (YAML frontmatter atau komentar header):

```
---
name: "Build and Debug Extension"
tags: [build, debug, cline]
difficulty: beginner
agent: cline
---
# isi skill (markdown) ...
```

atau versi CLI: file `.md` biasa + manifest JSON terpisah.

## 3. Konversi ke dhybrid SKILL.md

dhybrid pakai format ini (lihat `skills/<nama>/SKILL.md` yang ada):

```markdown
---
name: <nama-apa-aja>
description: <satu baris — karena ini yang dipakai loader untuk keyword match>
---

# <Judul>

<Then: paste isi skill, sesuaikan heading level, buat numbered steps>
```

### Pemetaan otomatis (helper `skills_fetch.sh`)

File `skills/skills-sh/scripts/skills_fetch.sh` otomatis:

1. Mengambil halaman skill: `curl -sL https://www.skills.sh/s/<slug>`
2. Mengekstrak frontmatter + isi markdown (jika tersedia sebagi file mentah).
3. Menuliskan `SKILL.md` yang sudah ter-format dhybrid.

Usage:

```bash
dhybrid skills-sh/scripts/skills_fetch.sh <skill-slug>
# contoh:
dhybrid skills-sh/scripts/skills_fetch.sh cline-build-and-debug-extension
# -> tuliskan skills/<nama>/SKILL.md
```

> CATATAN: skills.sh merender isi skill via JS/React-Server-Components (RSC).
> `curl` saja belum selalu dapat isi penuh — gunakan helper ini untuk frontmatter+metadata.
> Isi lengkapnya biasanya ada sebagi file `.md` terbuka di repo skill (lihat link repo di halaman skill).

## 4. Contoh nyata (terverifikasi)

Skill berikut ada di skills.sh di `/s/cline-build-and-debug-extension` (agen: **cline**).
Ini dia konversinya ke format dhybrid:

```
---
name: cline-build-debug-extension
description: Cline — build & debug VS Code extension: scaffold, compile, test, package, release
---

# Build & Debug Extension (Cline)

Langkah kerja untuk build & debug ekstensi VS Code dari dalam Cline (cline bot):

1. **Init** — pastikan `package.json` punya `vsce` sebagi dependency dev:
   `npm i -D vsce`
2. **Compile** — `npm run compile` (biasanya `tsc -p ./`). Cek error TypeScript.
3. **Test** — `npm test` (vscode-test). Jika fail, baca output test runner, buka
   file test yang relevan, perbaiki, re-run.
4. **Debug** — jalankan `Launch Tests` di `.vscode/launch.json`. Pakai breakpoint.
5. **Package** — `npx vsce package` -> hasil `.vsix`.
6. **Release** — update `CHANGELOG.md`, bump versi di `package.json`,
   `npx vsce publish` (perlu `--pat` token publis VS Code).

Tips Cline:
- Baca `package.json` dulu untuk tau skrip apa saja yang tersedia.
- Baca README ekstensi untuk dependensi runtime.
- Jika `vsce` belum init, jalankan `npx vsce package --allow-star` dulu untuk cek.
```

## 5. Prinsip lazy (hemat token)

- Jangan copy **seluruh** skill ke sistem prompt. Cukup **ringkasan** 2-3 baris di
  memory, atau tag `<skills-sh>` dengan hanya poin penting.
- Loader dhybrid (`src/dhybrid/skills/loader.py`) **sudah** auto-inject skill relevan
  (keyword match >= 1, max 3 skill, dipotong). Jadi cukup letakkan `SKILL.md` — selebihnya otomatis.
- Saat dipicu, ekstrak **action verbs** (build, debug, test, package) jadi checklist
  satu baris / numbered list — jangan narasikan penuh.

## 6. Verifikasi

- `[ ]` skill ada di `skills/<nama>/SKILL.md` dengan frontmatter `name` + `description`.
- `[ ]` deskripsi mengandung keyword spesifik agen/topic (agen agar loader ketemu).
- `[ ]` isi ditulis sebagai langkah-langkah angka, tidak narasi panjang.
- `[ ]` tidak ada literal tag XML penutup (`<function=...>`) di source — pakai `chr(60)`
  helper atau hindari.

Trigger: user sebut/cari skill dari skills.sh, atau minta "convert skills.sh ke dhybrid".
