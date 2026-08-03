---
name: session-hygiene
description: Kelola sesi panjang, resume, kompaksi, ringkasan, lanjutkan kerja
---

# Hygiene Sesi Panjang

1. Sesi panjang (> 1 jam / budget lunak tercapai): kompaksi dulu (`/compact`)
   sebelum lanjut — ringkasan otomatis dipertahankan.
2. Berhenti di tengah? Jangan khawatir: `dhybrid sessions` → cari sesi →
   `dhybrid resume <id>` melanjutkan via ringkasan + 5 pesan terakhir.
3. `/clear` mereset percakapan TAPI mempertahankan ringkasan — cocok saat
   konteks penuh tapi pekerjaan belum selesai.
4. Satu sesi = satu konteks proyek; pindah proyek = mulai sesi baru di
   direktori itu (auto-resume per direktori).
5. Di akhir sesi yang produktif: simpan keputusan penting sebagai skill
   (otomatis kalau ada karya nyata) atau ke memory (`/remember`) supaya
   sesi berikutnya tidak mulai dari nol.

Larangan: membiarkan sesi mati karena budget keras tanpa /compact;
mengulang pekerjaan yang sudah selesai di sesi lama.
