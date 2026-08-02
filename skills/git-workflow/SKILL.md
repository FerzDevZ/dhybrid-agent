---
name: git-workflow
description: Git commit message conventional, branch, status, workflow aman
---

# Git Workflow

Commit message (conventional):
- `feat:` fitur baru · `fix:` perbaikan bug · `refactor:` tanpa ubah perilaku
- `test:` tambah/perbaiki test · `docs:` dokumentasi · `chore:` tugas teknis
- `ci:` pipeline · `perf:` kinerja

Aturan:
- Commit kecil & fokus (satu perubahan per commit).
- Jangan commit file generated/rahasia (.env, build output) — cek git status dulu.
- Sebelum push: jalankan test.
- `git push --force` pada branch bersama = berbahaya — hindari.
