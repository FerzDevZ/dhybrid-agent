---
name: token-budget-debugging
description: Lacak pemborosan token, biaya per tool, output panjang, budget keras
---

# Debugging Pemborosan Token

1. Ukur dulu: `dhybrid tokens` → prompt vs completion vs cached. Kalau
   prompt membengkak, masalahnya di KONTEKS (riwayat), bukan model.
2. Tool yang paling boros: output panjang dari read_file/grep/find_files
   dengan limit besar — selalu pakai limit kecil dulu (mis. 30 baris),
   naikkan hanya kalau perlu.
3. Cek `max_output_chars` di config (default 8000) — hasil tool yang
   terpotong malah membuat model mengulang-ulang panggilan.
4. `DHYBRID_DEBUG=1` → dump konteks & hasil run ke ~/.dhybrid/debug/ —
   lihat pesan mana yang membengkak (biasanya tool output berulang).
5. Loop berulang (nudge/escalation) memakan token: kalau prompt yang sama
   dipanggil > 3× tanpa progres, perbaiki instruksi, jangan tambah konteks.

Larangan: menaikkan budget tanpa tahu penyebabnya; membiarkan tool output
raksasa masuk riwayat berulang-ulang.
