---
name: general
description: Panduan umum pengerjaan task coding yang solid — baca dulu, patch kecil, verifikasi nyata, jangan berhenti prematur. Dipakai otomatis saat tidak ada skill khusus yang cocok.
---

# Panduan Umum Task Coding

1. **Pahami dulu, baru sentuh**: baca file relevan (routes, controller, model,
   config) sebelum mengubah apa pun. Jangan menebak struktur project.
2. **Rencana singkat dulu**: sebutkan langkah yang akan dikerjakan (1-2 baris),
   lalu eksekusi. Untuk task besar, pecah jadi langkah kecil.
3. **Patch minimal**: ubah sesedikit mungkin, hanya yang diperlukan task.
   Jangan refactor di luar lingkup. Ikuti gaya kode project yang ada.
4. **Verifikasi NYATA sebelum klaim selesai**: jalankan perintah/serve/test
   dan tunjukkan buktinya (output perintah, status HTTP, test lulus).
   Jangan bilang "DONE" tanpa bukti nyata.
5. **Jangan berhenti prematur**: kalau target masih bertanya/menawarkan
   pilihan, lanjutkan dengan default yang masuk akal atau tanya via tool
   yang tersedia. Kalau ada error, baca pesannya, cari akar masalahnya.
6. **Laporkan ringkas**: apa yang dibuat/diubah, bukti verifikasi, dan
   langkah berikutnya (kalau ada).
