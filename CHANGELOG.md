# Changelog

Semua perubahan penting dhybrid-agent dicatat di sini.
Format mengikuti [Keep a Changelog](https://keepachangelog.com/id-ID/1.1.0/),
versi mengikuti [Semantic Versioning](https://semver.org/).

## [0.7.0] - 2026-08-03

### Agent sekarang bisa MELIHAT + menerima paste apa pun

- **Tool `read_image` — baca gambar/screenshot jadi teks.** Dua jalur,
  tidak bergantung penuh pada API key:
  1. Vision LLM (utama) — default byNara (OpenAI-compatible,
     router.bynara.id/v1, `BYNARA_API_KEY`; model = model utama yang aktif).
     Override env: `DHYBRID_VISION_PROVIDER` / `DHYBRID_VISION_MODEL` /
     `DHYBRID_VISION_BASE_URL` / `DHYBRID_VISION_API_KEY_ENV`.
  2. OCR lokal (tanpa API key sama sekali) — `rapidocr-onnxruntime`
     (ONNX, tanpa torch) → pytesseract → pesan ramah. Pasang: `pip install -e '.[vision]'`.
- **ChatMessage multimodal** (`llm/base.py`): `content` kini bisa list of
  parts (`text_part`/`image_part` data-URI). OpenAI-compatible client
  meneruskan apa adanya; AnthropicClient mengonversi ke blok image base64.
  Ini juga membuka jalan: agent bisa kirim gambar ke model kapan pun.
- **`/shot [nama]`** — screenshot layar penuh (ImageMagick `import`) ke
  `~/.dhybrid/captures/`, siap dibaca `read_image`. Bug UI/visual cukup
  di-screenshot, tidak perlu dijelaskan pakai kata-kata.
- **`/paste [nama]`** — mode tempel multi-baris (selesai Ctrl+D / baris
  titik): otomatis tersimpan ke `~/.dhybrid/pastes/<nama>.txt` DAN di-inject
  ke konteks agent sebagai pesan user — paste error/log/bukti sesi sekali
  tempel, agent langsung paham tanpa markup rusak.
- Allowlist default 28 → 29 tool (`read_image`). Extra baru `vision`.
- **271 test lulus**, ruff 0, coverage 67.1% (gate 65). OCR lokal
  terverifikasi nyata tanpa key: teks "Login gagal: 401 Unauthorized"
  terbaca dari gambar yang dibuat on-the-fly.

## [0.6.0] - 2026-08-03

### Fitur baru: 8 paket pendukung (eksekusi penuh "Kerjakan Semuanya")

1. **pydantic — validasi argumen tool** (`tools/validate.py`): gerbang tipe
   sebelum eksekusi. Kelas bug nyata `terminal(command=</parameter)` /
   `find_files(path=-la, pattern=*)` kini ditolak lebih awal dengan pesan jelas;
   koersi aman int↔str, `required`/`min_length` ditegakkan, argumen ekstra tetap
   diteruskan.
2. **ddgs — web_search via API resmi DuckDuckGo** (paket `ddgs`): scraping HTML
   hardcoded jadi fallback otomatis; hasil kini memuat snippet (title+url+body).
   Env `DHYBRID_WEB_SEARCH=html` untuk memaksa jalur lama.
3. **rich — UI profesional**: blok DONE jadi Panel (repl & run), dashboard
   `/tokens` jadi Table. Otomatis polos di non-TTY/NO_COLOR (standar no-color.org).
4. **tree-sitter — tool `code_map`**: AST fungsi/class per file (python, php,
   javascript) + rentang baris — konteks struktur tanpa baca seluruh file.
5. **sqlite-vec — tool `mem_index`/`mem_search`/`mem_reset`**: memory kode
   proyek, chunk 40 baris → vektor char 3-gram 256-d (L2-normalisasi), pencarian
   top-k via virtual table `vec0`; fallback cosine Python bila ekstensi gagal.
   DB per proyek di `<cwd>/.dhybrid/mem.sqlite` (env `DHYBRID_MEM_DB`).
6. **beautifulsoup4 + lxml — fallback ekstraksi `web_fetch`**: trafilatura →
   bs4+lxml (robust untuk HTML rusak) → parser internal → regex. `<title>` kini
   benar-benar terisi (sebelumnya selalu URL).
7. **litellm — adapter `LiteLLMClient` opsional**: provider `litellm` mendukung
   100+ model ("openai/gpt-4o", "anthropic/...", "gemini/...", dll). Default
   path openai/anthropic TIDAK berubah; import lambat, `drop_params=True`.
8. **playwright — tool `browser`** (extra `e2e`): navigate/click/type/snapshot
   headless untuk verifikasi web E2E (mis. app Laravel lokal); state browser
   dipertahankan antar panggilan; pesan ramah bila belum di-install.

+5 tool baru masuk allowlist default (23 → 28). Deps baru masuk `dependencies`
(playwright di optional-dependencies `e2e`). **257 test lulus**, ruff 0,
coverage 67.3% (gate 65).

## [0.5.5] - 2026-08-03

### Bugfix: agent MASIH berhenti prematur walau sudah di-nudge (sesi nyata #5–#12)

Empat sesi repl 0.5.4 dari `/home/firman/ppj` masih berakhir `DONE — 0 file`
setelah model menulis "Saya akan uji performa..." / "Mari verifikasi dengan
curl:" — nudge niat 0.5.4 bekerja, tapi budget `max_nudges` (3×) habis cepat,
model free terus berjanji tanpa eksekusi, dan escalation chain kosong (tidak
ada model kuat sebagai penyelamat).

- **Budget nudge diperbesar tanpa escalation chain**: `intent_budget =
  max_nudges * 2` bila `escalation_chain` kosong — satu-satunya jalan adalah
  memaksa model yang sama bekerja lebih lama. 3 janji beruntun tidak lagi
  cukup untuk DONE.
- **Aktivitas tool me-reset budget nudge**: model yang SELANG-SELING janji dan
  eksekusi (`cd` lalu "Mari verifikasi...") tidak kehabisan nudge di tengah
  pekerjaan — `nudges = 0` setiap ada tool call.
- **PERINGATAN TERAKHIR (hard nudge)**: setelah budget niat habis tanpa
  aktivitas, satu pesan keras "respons berikutnya WAJIB tool call, kalau tidak
  sesi dihentikan dan dilaporkan gagal" — model diberi satu kesempatan
  terakhir sebelum berhenti jujur (bukan berhenti diam-diam).
- **Frasa "mari verifikasi/cek/jalankan/buat/mulai"** masuk INTENT_HINTS —
  "Server sudah running. Mari verifikasi dengan curl:" kini terdeteksi niat.

+3 test regresi (budget diperluas, reset-on-activity, hard nudge).
Total **222 test lulus**, ruff 0.

## [0.5.3] - 2026-08-03

### Bugfix UI/UX
- **Prompt REPL bocor escape code** (`^[[32mdhybrid> ^[[0m` tampil literal):
  prompt_toolkit tidak menerima string ber-ANSI dari `style()` — dirender
  sebagai notasi `^[` di terminal. Sekarang pakai FormattedText
  `[("ansigreen", "dhybrid> ")]`. Terverifikasi via smoke PTY nyata.
- **`style()` hormati `NO_COLOR`** (standar no-color.org): kalau env
  `NO_COLOR` diset, output teks polos walau di TTY. +3 unit test
  (tests/unit/test_render.py).

## [0.5.4] - 2026-08-03

### Bugfix: agent "tidak benar benar bisa menyelesaikan" (laporan sesi repl)

Dua kegagalan dari sesi nyata (setup Laravel + Breeze di /home/firman/ppj):

1. **Tool garbage dari markup XML rusak** — model free menulis
   `<tool_call><parameter name="terminal">...` tanpa penutup valid; parser
   natural-language menangkap kata "terminal"/"command" DI DALAM markup itu dan
   mengeksekusi perintah sampah (`</parameter` → shell error
   `/bin/sh: cannot open /parameter`).
   - `text_parser.py`: teks berisi fragmen markup tool yang rusak
     (`<tool_call`, `<parameter`, `</parameter`, `<invoke`, `<function`,
     ````tool``) TIDAK lagi diterjemahkan parser NL → `[]` (loop menangani
     sebagai teks biasa, bukan menembak tool).
   - `parsing.py` `strip_tool_block`: tag `<parameter ...>`/`</parameter>`
     ikut dibersihkan → markup rusak tidak bocor mentah ke transkrip.
   - `terminal.py`: command kosong/whitespace → ERROR, bukan sukses palsu.

2. **Berhenti prematur di niat** — model menulis "Server belum berjalan. Saya
   akan cek dan start server:" (niat, belum eksekusi) lalu loop langsung DONE
   "0 file".
   - `loop.py`: deteksi NIAT tanpa eksekusi (`_expresses_intent`: frasa
     "saya akan..."/"nanti..."/"sekarang saya"/kalimat berakhir ":") → di-nudge
     INTENT_MSG ("EKSEKUSI SEKARANG") sampai `max_nudges`, tidak difinalkan.
   - Sinyal niat TIDAK menimpa jawaban yang sudah mengandung sinyal selesai.

+3 test (parser markup rusak, strip parameter, loop nudge niat).
Total **219 test lulus**, ruff 0.

## [0.5.2] - 2026-08-03

### Dev tooling (Tier 3 — kualitas pengembangan)
- **CI diperluas**: job `security` baru (bandit + pip-audit) + gate coverage
  `--cov-fail-under=65` di job test (baseline 65.2%).
- **Bandit 0 finding**: `shell=True` di terminal/tests diberi `# nosec`
  berjustifikasi (by design — ada gerbang is_dangerous); sisanya di-skip via
  `.bandit.yml` dengan alasan tertulis (tool runner lokal).
- **pip-audit bersih**: tidak ada kerentanan dependensi.
- **pre-commit**: `.pre-commit-config.yaml` (ruff lint, versi disinkron v0.16.1
  dengan venv; format TIDAK dipaksakan agar tidak reformat 123 file sekaligus).
- **pytest-cov + pytest-xdist**: `pytest -n auto` (11.9s → 9.6s), coverage
  per-modul tersedia; titik terlemah tercatat: commands 9%, repl 18%, git 24%.
- deps dev baru: pytest-cov, pytest-xdist, bandit, pip-audit, pre-commit.

## [0.5.1] - 2026-08-03

### Fitur Baru (Tier 1: paket pendukung)
- **read_document** (markitdown): agent kini bisa baca PDF/DOCX/XLSX/PPTX/HTML
  → markdown. Sebelumnya cuma file teks polos. Terdaftar di allowlist default.
- **REPL prompt_toolkit**: history search (Ctrl-R), autocomplete /command &
  nama skill (fuzzy), paste multi-line. Non-TTY (piped) tetap fallback input().
- **web_fetch pakai trafilatura**: ekstraksi artikel bersih (nav/iklan dibuang)
  → output lebih pendek & hemat token; fallback ke parser internal.
- **Skill matching rapidfuzz**: typo "debuging" → skill debugging tetap
  ter-inject; skill relevan + mirip prompt naik prioritas.
- dependensi baru: prompt_toolkit, markitdown[pdf,docx,pptx,xlsx], trafilatura,
  rapidfuzz (semua opsional-impor — error beri pesan install yang jelas).

## [0.5.0] - 2026-08-03

### Diperbaiki
- **apply_patch dari parser teks mengirim `old_string="<<PLACEHOLDER>>"`** yang
  dijamin gagal → error palsu & noise nudge/escalation. Sekarang HANYA pola
  dua-sisi ("ganti X menjadi Y di file Z") yang memicu apply_patch; tanpa
  old_string nyata, tool tidak di-fire. Modul text_parser (191 baris, auto-fire
  tool) kini punya test sendiri (9 unit test).
- **Prosa model bisa auto-fire write_file** — kalimat niat/hedge ("saya AKAN
  buat...", "perlu buat...", "mungkin...") di-penalty confidence ×0.4; perintah
  imperatif di awal kalimat ("Buatkan file X...") di-boost; ambang aman tanpa
  mengorbankan perintah read/grep/list.
- **Auto-skill kontaminasi antar-run** — `tool_count` di-reset tiap awal run
  (`registry.reset_counts()`), jadi prompt receh di run ke-2 tidak menumpang
  tool run ke-1 untuk lahir jadi skill.
- **Jawaban user (ask_user) diproses sebagai prompt mentah** — bisa memicu
  nudge build & parsing. Sekarang di-push sebagai pesan biasa
  (`push_prompt=False`), tidak di-parse/di-nudge/di-double-push.
- **Prosa model dibuang saat tool block ter-parse** (`text=""`) — sekarang
  `strip_tool_block` membersihkan markup saja, penjelasan model tetap masuk
  riwayat.
- **ask_user boros 1 model call** — loop pause LANGSUNG setelah tool ask_user
  dieksekusi, tanpa call tambahan (test `steps == 1`).

### Ditambahkan
- `dhybrid doctor` diperluas: cek chain eskalasi (preset mati terdeteksi —
  menemukan chain user 0/3 hidup), cek allowlist tool inti keblokir, cek
  skill bawaan vs workspace (flag sampah ≥ 5).
- `/skill ls | info <nama> | rm <nama>` — hapus hanya skill workspace
  (auto-learn), skill bawaan ditolak.
- `DHYBRID_DEBUG=1` → dump konteks & hasil run ke `~/.dhybrid/debug/` JSON.
- Failover chain saat error beruntun TANPA router (coba preset chain berikutnya).
- `dhybrid run --json` — output JSON terstruktur (final_text, skor, token, biaya).
- Cache `web_search` per sesi (TTL 120 detik) — query berulang tidak hit DDG lagi.
- Toggle auto-skill: `skills.auto_learn: false` di config atau `DHYBRID_NO_SKILL=1`.
- 5 skill baru: `laravel-scaffold`, `free-model-survival`, `context-engineering`,
  `token-budget-debugging`, `session-hygiene` (total 31).

## [0.4.3] - 2026-08-03

### Diperbaiki
- **"DONE" tanpa kerja nyata** (laporan user): prompt "mulai setup dan kerjakan
  project login register" tidak dikenali sebagai permintaan membangun karena
  kata "kerjakan"/"setup" tidak ada di `BUILD_VERBS` → agent bebas klaim
  selesai tanpa bukti. Sekarang: `BUILD_VERBS` diperluas (kerjakan, setup,
  install, perbaiki, tulis, hapus, deploy, dll).
- **"lanjutkan"/"ya" tidak diwarisi konteks membangun** — prompt lanjutan
  sekarang mewarisi status build dari riwayat sesi, jadi klaim selesai tanpa
  bukti tetap ditolak.
- **Klaim "selesai/berhasil/done" tidak lagi mem-bypass nudge** — build tanpa
  bukti (0 file, tanpa write_file/apply_patch/git_commit/test) di-nudge
  `EVIDENCE_MSG` sampai `max_nudges`, bukan langsung finalize.
- **Auto-skill sampah** — guard `auto_skill_worthwhile` bocor: sesi eksplorasi
  (ls/grep/read/fetch, >= 4 tool) dianggap layak → 21 skill sampah terlanjur
  dibuat ("hai", "lanjutkan", "task", dll). Sekarang butuh KARYA nyata: file
  dibuat, tool mutasi, atau test dijalankan; plus stoplist prompt receh dan
  dedupe nama skill. Skill sampah lama di ~/.dhybrid/skills/ dibersihkan.
- 21 skill sampah otomatis dihapus dari workspace user.

## [0.4.2] - 2026-08-03

### Ditambahkan
- Tool `ask_user(prompt, options)` — agent boleh tanya keputusan ke user di
  tengah loop; guardrail: maks 2x/sesi, diblokir di mode non-interaktif
  (`dhybrid run` — agent harus pilih default sendiri). Golden rule #1 direvisi:
  "eksekusi dulu; tanya hanya via ask_user bila pilihan berdampak besar".
- Paksa skill: `/skill <nama>` (berlaku tiap prompt) dan `@nama_skill` di prompt;
  feedback `[skill aktif: ...]` ditampilkan setelah tiap prompt.
- Matching skill lebih pintar: sinonim/alias ("crash" → debugging), skor
  berbobot (kata langka lebih kuat), cocok dengan riwayat sesi, nama skill
  ikut dihitung.
- 5 skill debugging/analisis baru: root-cause-analysis, performance-profiling,
  api-debugging, sql-query-optimization, concurrency-debugging (total 26).
- Fix: `web_search` & `http_request` ternyata tidak ada di default allowlist
  config — sekarang aktif.

### Diperbaiki
- Import tak terpakai + urutan import (ruff bersih).

## [0.4.1] - 2026-08-03

### Ditambahkan
- Tool `web_search` (DuckDuckGo, tanpa API key) & `http_request` (REST generik,
  Authorization tidak bocor ke output, retry 429/5xx dengan backoff) di
  `tools/web.py`.
- 4 slash-command memory di REPL: `/remember`, `/forget`, `/memories`,
  `/search-memory`.
- Parser tool-call mendukung 5 format (bare JSON, index alias, array,
  tag `<function=..>`, tag `arg_key`/`arg_value`) + dedupe + `strip_tool_block`.
- Validator `rm -rf` memblokir target root sistem, `/home`, dan traversal;
  target spesifik dalam workspace tetap lewat konfirmasi user.
- 11 skill baru: web-search, web-github, gitlab-lazy, code-sandbox,
  database-query, api-http-request, web-scraping-extraction, skills-sh,
  memory-persistence, notion-trello-jira, customer-support-rag.
- LICENSE MIT + field `license` di pyproject.

### Diperbaiki
- Escaping test parsing; `test_parsing.py` 12/12 lulus.
- 2 temuan ruff di `security.py` (blind except, SIM103).

## [0.4.0] - 2026-08-02

### Ditambahkan
- Parse tool-call format `<function=..>` + `arg_key`/`arg_value`.
- Retry 429 dengan backoff, progress live, injeksi known-facts.
- Auto-resume sesi per-proyek + injeksi memori jangka panjang relevan ke
  konteks awal sesi.
- Provider toggle di `/settings`; escalation skip provider disabled/401.

### Diperbaiki
- Agent selalu memberi respons (tidak terserap format tool-call).
- Agent tidak berhenti prematur saat membangun (bukti file nyata, folder
  dependensi diabaikan).
- Sinkronisasi versi pyproject ↔ runtime `__version__` (0.4.1).

## [0.1.0] - 2026-07-31

### Ditambahkan
- CLI repl + one-shot run + resume.
- Multi-provider cloud (OpenAI/Anthropic/OpenRouter/Gemini/Groq/DeepSeek/byNara).
- 12 teknik hemat token + metering (`/tokens`).
- Tool: terminal (gerbang keamanan), files, patch, search, git, tests, todo,
  memory (FTS5), subagent, MCP.
- Skills + sessions + benchmark harness.
- CI green (ruff + pytest) via GitHub Actions.
