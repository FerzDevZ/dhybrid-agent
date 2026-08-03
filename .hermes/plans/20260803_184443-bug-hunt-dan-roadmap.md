# Plan: Bug-Hunt dhybrid-agent + Roadmap Fitur & Skill

> **Untuk Hermes:** gunakan skill `subagent-driven-development` untuk eksekusi plan ini task-per-task.

**Goal:** Memetakan semua spot error/bug yang masih tersisa di dhybrid-agent (hasil search + test), lalu menyusun daftar perbaikan berprioritas + saran fitur & skill yang berurutan.

**Architecture:** Investigasi read-only selesai (test suite 193 lulus, 0 skip, 0 warning; inspeksi kode di modul agent/skills/ui/tools). Plan berisi: (A) temuan bug dengan bukti `file:line`, (B) task perbaikan TDD bite-sized, (C) roadmap fitur P0/P1/P2, (D) roadmap skill baru.

**Tech Stack:** Python 3.12, pytest, ruff, dhybrid-agent (repo `/home/firman/dhybrid-agent`, versi 0.4.3, 26 skill repo, branch main sinkron origin/main).

---

## Bagian A — Temuan Bug (hasil search + test)

Status test terakhir: **193 passed, 0 skipped, 0 warning** (pytest). Ruff 0 error. Berikut spot error/bug yang ditemukan dari inspeksi kode (belum tertutup test):

| ID | Sev | Lokasi | Masalah | Bukti |
|----|-----|--------|---------|-------|
| BUG-1 | TINGGI | `src/dhybrid/agent/text_parser.py:127` | `_parse_apply_patch` mengembalikan `old_string="<<PLACEHOLDER>>"` — string ini TIDAK PERNAH cocok dengan isi file → `apply_patch` dijamin ERROR tiap kali parser menangkap pola "ubah X menjadi Y". Error ini menaikkan counter `errors` di loop → memicu eskalasi/nudge palsu. | `text_parser.py:126-128`; `loop.py:338` auto-fire via `extract_tool_calls_from_text(text)` dengan `min_confidence=0.5` |
| BUG-2 | TINGGI | `src/dhybrid/agent/text_parser.py:13-17, 85-100, 153` | Ambang `min_confidence=0.5` terlalu rendah + tidak ada sinyal negatif: prosa model "Saya AKAN buat file test.py dengan isi ..." (niat/future tense) bisa auto-fire `write_file` dengan konten terpotong (regex `[\s\S]*?` non-greedy berhenti di tanda baca pertama). Write_file tidak sengaja = efek samping berbahaya. | `FILE_CREATE_PATTERNS[0]`; `_calculate_confidence` base 0.6; `extract_tool_calls_from_text` default `min_confidence=0.5` |
| BUG-3 | SEDANG | `src/dhybrid/ui/repl.py:326` | `tools_used` diambil dari `ctx.tools.tool_count` yang AKUMULATIF sepanjang sesi REPL (tidak di-reset per run — lihat `loop.py:361` yang hanya reset `self.tool_events`, bukan `tool_count`). Run ke-2 yang receh ("udah", "beres") di sesi yang run ke-1-nya pakai `write_file` → `any(t in MUTATING_TOOLS)` True → skill sampah lahir dengan slug receh (kalau lolos TRIVIAL_SLUGS). | `repl.py:326-331`; `loop.py:361` |
| BUG-4 | SEDANG | `src/dhybrid/ui/repl.py:272` | Jawaban user untuk `ask_user` diteruskan sebagai prompt mentah: `run_agent(ctx, f"[jawaban user] {answer}")` → ikut di-parse sebagai tool-call (user mengetik teks berformat tool → dieksekusi), ikut dicocokkan ke skill, ikut masuk `_recent_user_history`. Jawaban user harusnya jadi pesan biasa, bukan prompt yang bisa dieksekusi. | `repl.py:254-272` |
| BUG-5 | RENDAH | `src/dhybrid/cli.py:103` | `dhybrid resume <sid>` membuat `SessionContext` BARU → `AskState` baru → guardrail "maks 2x tanya per sesi" di-reset setiap kali resume. Logisnya per sesi (persist di store), bukan per invokasi. | `cli.py:103`; `ask.py:20-24` |
| BUG-6 | RENDAH | `src/dhybrid/agent/loop.py:341` | Saat tool block ter-parse, `text = ""` → seluruh prosa penjelasan model DIBUANG dari konteks. Model yang menjelaskan lalu memanggil tool kehilangan penjelasannya di riwayat → konteks tidak konsisten untuk model berikutnya. | `loop.py:336-342`; `parsing.py:236` (`strip_tool_block` tersedia tapi tidak dipakai di sini) |
| BUG-7 | RENDAH | `src/dhybrid/agent/loop.py:581` + `tools/ask.py:39-41` | `ask_user` dieksekusi sebagai tool → hasil `PENDING_SENTINEL` masuk konteks → loop memanggil model SEKALI LAGI (boros 1 call) → baru pause di iterasi teks berikutnya. Bisa pause langsung setelah tool `ask_user` dieksekusi. | `loop.py:566-582`; `ask.py:40` |
| GAP-1 | — | `tests/` | `text_parser.py` (191 baris, 6 pattern group, auto-fire ke tools) **0 test** — modul paling berisiko tanpa jaring pengaman. | `grep text_parser tests/` → 0 hit |
| GAP-2 | — | `tests/` | Tidak ada test untuk: auto-skill antar-run (BUG-3), alur `[jawaban user]` (BUG-4), AskState di resume (BUG-5). | — |

Catatan: exception handling di repo sudah disiplin (semua `except` ber-noqa BLE001 dengan alasan); `web.py`/`mcp.py`/`registry.py` aman. `parsing.py` (parser `<function=..>` + 5 gaya tool-call) SUDAH punya test (`tests/unit/test_parsing.py`, `test_streaming.py`).

---

## Bagian B — Rencana Perbaikan (TDD, task bite-sized)

### Task B1: Unit test text_parser + fix PLACEHOLDER apply_patch

**Objective:** `apply_patch` dari parser tidak lagi mengirim `old_string` placeholder yang dijamin gagal.

**Files:**
- Create: `tests/unit/test_text_parser.py`
- Modify: `src/dhybrid/agent/text_parser.py:120-128`

**Step 1: Tulis test gagal**

```python
# tests/unit/test_text_parser.py
from dhybrid.agent.text_parser import extract_tool_calls_from_text

def test_apply_patch_requires_real_old_string():
    # "ganti X menjadi Y di file" tanpa old_string konkret → JANGAN fire apply_patch
    calls = extract_tool_calls_from_text('ubah config.py menjadi versi baru', min_confidence=0.4)
    assert all(c["name"] != "apply_patch" for c in calls)

def test_apply_patch_with_old_and_new():
    calls = extract_tool_calls_from_text("ganti 'debug=true' menjadi 'debug=false' di config.py")
    patch = [c for c in calls if c["name"] == "apply_patch"]
    assert patch and "PLACEHOLDER" not in str(patch[0]["arguments"])
```

**Step 2: Jalankan → HARUS FAIL**

Run: `pytest tests/unit/test_text_parser.py -v`
Expected: FAIL — apply_patch tetap ter-emit dengan `old_string="<<PLACEHOLDER>>"`.

**Step 3: Implementasi minimal**

Ubah `_parse_apply_patch` di `text_parser.py`:
- Pattern lama `FILE_EDIT_PATTERNS[0]` hanya menangkap `new` → hapus dari daftar pattern `apply_patch`.
- Tambahkan pattern dua-sisi: `ganti|replace <OLD> dengan|menjadi|to <NEW> di|pada|in <file>`.
- `_parse_apply_patch` hanya return bila `old_string` DAN `new_string` keduanya non-kosong (trim `'`/`"`/`` ` ``); selain itu return `None` (tidak fire).

```python
FILE_EDIT_PATTERNS = [
    # HANYA dua-sisi: old DAN new harus ada, plus lokasi file — kalau tidak, skip
    r"(?:ganti|replace|ubah)\s+[`\"']?([\s\S]*?)[`\"']?\s+(?:dengan|menjadi|to)\s+[`\"']?([\s\S]*?)[`\"']?\s+(?:di|pada|in)\s+[`\"']?([\w\/\.\-]+\.\w+)[`\"']?",
]
```

**Step 4: Jalankan → PASS**

Run: `pytest tests/unit/test_text_parser.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tests/unit/test_text_parser.py src/dhybrid/agent/text_parser.py
git commit -m "fix: apply_patch parser butuh old_string nyata (tolak placeholder)"
```

### Task B2: Gate confidence + sinyal negatif future-tense (text_parser)

**Objective:** Prosa "Saya AKAN buat ..." tidak auto-fire write_file.

**Files:**
- Modify: `src/dhybrid/agent/text_parser.py:85-100` (`_calculate_confidence`), `:153-173` (`extract_tool_calls_from_text`)

**Step 1: Test gagal**

```python
def test_future_tense_not_fired():
    # niat masa depan ≠ perintah eksekusi
    calls = extract_tool_calls_from_text("Saya akan buat file app.py dengan isi print('hi')")
    assert all(c["name"] != "write_file" for c in calls)

def test_explicit_command_fired():
    calls = extract_tool_calls_from_text("Buatkan file app.py dengan isi print('hi')")
    assert any(c["name"] == "write_file" for c in calls)
```

**Step 2: Jalankan → FAIL** (`pytest tests/unit/test_text_parser.py::test_future_tense_not_fired`)

**Step 3: Implementasi**

- `_calculate_confidence`: tambah sinyal NEGATIF — bila teks mengandung `akan|saya akan|rencana|nanti|nantinya|mau|ingin` dalam 5 kata sebelum match → `confidence *= 0.4`.
- `extract_tool_calls_from_text`: naikkan default `min_confidence` 0.5 → **0.75**; tambah param `min_confidence` tetap bisa di-override.
- Bila hasil `write_file`/`apply_patch` punya `content`/`new_string` yang berisi karakter `$`/backtick/`<` yang tidak seimbang → turunkan confidence (indikasi teks terpotong).

**Step 4: Jalankan → PASS** + regresi penuh: `pytest tests/ -q` → 193 + 4 test baru lulus.

**Step 5: Commit**

```bash
git commit -am "fix: text_parser tolak future-tense & naikkan ambang confidence 0.75"
```

### Task B3: Reset tool_count per run (matikan kontaminasi auto-skill antar-run)

**Objective:** Auto-skill hanya melihat tool run ini, bukan akumulasi sesi.

**Files:**
- Modify: `src/dhybrid/agent/loop.py:361` (setelah `self.tool_events = []`)
- Modify: `src/dhybrid/tools/registry.py` (tambah method `reset_counts()`)
- Modify: `tests/e2e/test_agent_loop.py` (test baru)

**Step 1: Test gagal**

```python
def test_auto_skill_not_contaminated_across_runs():
    # run 1 pakai write_file (buat skill sah) → run 2 prompt receh tanpa tool
    # → run 2 TIDAK boleh menghasilkan skill
    ctx = _make_ctx_with_tools()  # fixture: SessionContext + ToolRegistry
    res1 = run_agent(ctx, "buatkan file x.py")     # pakai write_file
    _auto_learn_skill(ctx, "buatkan file x.py", res1.final_text, res1)
    n_before = len(list((ctx.workspace / "skills").glob("*")))
    res2 = run_agent(ctx, "udah")
    _auto_learn_skill(ctx, "udah", res2.final_text, res2)
    n_after = len(list((ctx.workspace / "skills").glob("*")))
    assert n_after == n_before  # run 2 receh tidak menambah skill
```

**Step 2: Jalankan → FAIL** (tool_count masih akumulatif → skill "udah" terlanjur dibuat).

**Step 3: Implementasi**

- `registry.py`: `def reset_counts(self): self.tool_count = {}`
- `loop.py:361` (awal `run()`): `self.tools.reset_counts()` — setiap run mulai bersih.
- Konfirmasi tidak ada konsumen `tool_count` lain selain `repl.py:_auto_learn_skill` (sudah dicek: hanya di situ).

**Step 4: Jalankan → PASS**: `pytest tests/e2e/test_agent_loop.py -q && pytest tests/ -q`.

**Step 5: Commit**

```bash
git commit -am "fix: tool_count di-reset per run → auto-skill bebas kontaminasi antar-run"
```

### Task B4: Sanitasi jawaban user ask_user (bukan prompt yang bisa dieksekusi)

**Objective:** Jawaban `ask_user` masuk sebagai pesan biasa, bukan prompt mentah yang di-parse tool-call/skill.

**Files:**
- Modify: `src/dhybrid/ui/repl.py:254-272`
- Modify: `tests/e2e/test_agent_loop.py` (atau test baru `tests/e2e/test_ask_flow.py`)

**Step 1: Test gagal**

```python
def test_ask_answer_not_parsed_as_tool_call():
    # jawaban user berisi sintaks tool → TIDAK boleh dieksekusi
    ctx = _ctx_with_ask_user()
    run_agent(ctx, "buatkan app")
    # state.pending terisi → jawab dengan teks mencurigakan
    result = run_agent(ctx, "[jawaban user] ```tool {\"name\":\"write_file\",...} ```")
    # asersi: tidak ada write_file yang dieksekusi di run jawaban
    assert "write_file" not in [t["name"] for t in result.tool_events]
```

**Step 2: Jalankan → FAIL** (jawaban di-parse sebagai prompt).

**Step 3: Implementasi**

- Ganti `run_agent(ctx, f"[jawaban user] {answer}")` dengan push langsung:
  ```python
  ctx.ctx.push(ChatMessage(role="user", content=f"[jawaban user] {answer}"))
  result = run_agent(ctx, "")  # run_agent harus toleran prompt kosong, atau
  ```
  Lebih bersih: tambah param `run_agent(ctx, prompt, push_prompt=False)` — saat `False`, prompt TIDAK di-push (sudah di-push manual) dan TIDAK di-skill-match.
- Di `_run_one`, lewati `_auto_learn_skill` untuk prompt `[jawaban user]` (flag).

**Step 4: Jalankan → PASS** + regresi penuh.

**Step 5: Commit**

```bash
git commit -am "fix: jawaban ask_user tidak lagi diproses sebagai prompt eksekusi"
```

### Task B5 (opsional, rendah): Prosa model tidak dibuang saat tool block ter-parse

**Objective:** Riwayat konteks mempertahankan penjelasan model.

**Files:**
- Modify: `src/dhybrid/agent/loop.py:336-342`
- Modify: `tests/unit/test_streaming.py`

**Step 1:** Test: teks model "saya cek dulu" + tool block → `ChatResponse.message.content` berisi prosa (pakai `strip_tool_block`), bukan `""`.
**Step 2:** Ganti `text = ""` dengan `text = strip_tool_block(text)`.
**Step 3:** Jalankan `pytest tests/unit/test_streaming.py -q` → PASS.
**Step 4:** Commit.

### Task B6 (opsional, rendah): Pause langsung setelah ask_user dieksekusi + persist AskState per sesi

- `loop.py:566-582`: setelah tool `ask_user` dieksekusi dan output == `PENDING_SENTINEL` → panggil `_maybe_pause_for_user` segera, tanpa model call tambahan. Test: `test_loop_pauses_for_ask_user` diperbarui (steps berkurang 1).
- `cli.py:103` (resume): muat `ask_count` dari store sesi; tulis ulang saat simpan. Test: resume dua kali → hitungan tanya tetap.

---

## Bagian C — Roadmap Fitur (berurutan)

### P0 — Perbaikan yang harus duluan (minggu ini)
1. **F0-1: text_parser aman** (Task B1+B2) — menutup write_file/patch tak sengaja, modul paling berisiko.
2. **F0-2: auto-skill per-run + sanitasi jawaban user** (Task B3+B4) — menyempurnakan fix 0.4.3 (skill sampah & DONE prematur).

### P1 — Pengalaman pakai (2-4 minggu)
3. **F1-1: `dhybrid doctor` diperluas** — cek health: konfigurasi chain (big model terisi? key ada?), allowlist tool vs tool terdaftar (cegah kejadian web_search terkunci di 0.4.2), jumlah skill sampah, status sesi DB. `doctor.py` sudah ada — tinggal tambah cek.
4. **F1-2: `/skill` lebih kaya** — `/skill ls` (daftar + asal: repo/workspace), `/skill rm <nama>` (hapus skill sampah tanpa buka file), `/skill info <nama>` (isi ringkas). Menjawab keluhan "21 skill sampah" yang harus dibersihkan manual.
5. **F1-3: Debug dump** — env `DHYBRID_DEBUG` diperluas: tulis prompt konteks akhir + semua tool events ke `~/.dhybrid/debug/<timestamp>.json` untuk reproduksi bug agent (bukan cuma filter streaming).
6. **F1-4: Failover chain saat error beruntun** — setelah N error tool/API di model kecil, coba model berikutnya di `chain` (bukan hanya eskalasi kualitas). Sebagian sudah ada (`escalate_after_errors`) — tambah fallback provider saat 429/5xx beruntun (retry 429 sudah ada; lanjut ke failover).

### P2 — Fitur baru (bulan depan)
7. **F2-1: `dhybrid run --json`** — output hasil terstruktur (final_text, files, score, cost, tool_events) untuk scripting/CI. Cocok dengan mode non-interaktif yang sudah ada.
8. **F2-2: Cache web_search per sesi** — dedupe pencarian yang sama (hemat token + waktu).
9. **F2-3: Skill import dari URL/GitHub** — `dhybrid skill install <repo>` (pakai pola `import-external-skill` yang sudah ada di Hermes).
10. **F2-4: Auto-skill toggle di config** — `skills.auto_learn: true/false` + flag `--no-skill` untuk mode fokus (mati total).

---

## Bagian D — Roadmap Skill baru (untuk agent, ditulis SKILL.md 15-18 baris)

| Prioritas | Nama Skill | Alasan |
|-----------|-----------|--------|
| P0 | `laravel-scaffold` | User rutin bikin project Laravel (auth-app); skill berisi langkah scaffold + Breeze + verifikasi `php artisan serve` + cara cek halaman — mencegah DONE prematur ala sesi sebelumnya |
| P0 | `free-model-survival` | Pola prompt untuk model free/zen: format tool-call yang didukung (`<function=..>`, ```` ```tool ````), retry 429, hindari future-tense yang memicu text_parser (korelasi BUG-2) |
| P1 | `context-engineering` | Kapan kompaksi, ringkas fakta, hemat token per tool — agent jadi hemat di sesi panjang |
| P1 | `token-budget-debugging` | Melacak pemborosan token per tool call (pasangan F1-3/F2-2) |
| P2 | `session-hygiene` | Resume/compact/summary sesi panjang; kapan pakai `/compact` vs sesi baru |

Catatan: 3 skill analisis yang sudah ada (`root-cause-analysis`, `performance-profiling`, `api-debugging`, `sql-query-optimization`, `concurrency-debugging`) tetap; yang dibutuhkan adalah skill PROSEDURAL scaffold + survival model free.

---

## Files yang kemungkinan berubah

- `src/dhybrid/agent/text_parser.py` (B1, B2)
- `src/dhybrid/agent/loop.py` (B3, B5, B6)
- `src/dhybrid/tools/registry.py` (B3)
- `src/dhybrid/ui/repl.py` (B4)
- `src/dhybrid/cli.py`, `src/dhybrid/doctor.py` (B6, F1-1)
- `src/dhybrid/tools/web.py` (F2-2)
- `tests/unit/test_text_parser.py` (BARU), `tests/e2e/test_agent_loop.py`, `tests/unit/test_streaming.py`
- `config/default.yaml` (F2-4), `README.md`, `CHANGELOG.md`, `docs/roadmap.md`

## Tests / Validasi

- Per task: test dulu (RED) → implementasi (GREEN) → `pytest tests/ -q` penuh + `ruff check src/ tests/` 0 error.
- Akhir fase P0: **197+ test lulus** (193 + B1×2 + B2×2), versi bump 0.4.4 + CHANGELOG/roadmap sinkron, commit + push.
- Smoke test manual: jalankan `dhybrid repl` di folder kosong, prompt "buatkan file halo.txt dengan isi hai" → write_file TIDAK auto-fire dari prosa; prompt "buat file halo.txt berisi hai" → fire.

## Risiko & Tradeoff

- **Mengetatkan text_parser** (confidence 0.75) bisa membuat model free TIDAK bisa memanggil tool via kalimat natural yang sah → tradeoff: aman > agresif; mitigasi: pattern dua-sisi yang lebih tepat + test positif (perintah eksplisit tetap fire).
- **Reset tool_count per run** mengubah perilaku `_auto_learn_skill` untuk run yang sengaja memakai tool dari run sebelumnya (jarang) → acceptable.
- **`[jawaban user]` tanpa parse** berarti jawaban yang berisi "buatkan X" tidak akan memicu kerja — benar secara desain (jawaban = keputusan, bukan perintah baru).
- BUG-5/B6 (persist AskState) menyentuh skema store sesi → perlu migrasi ringan; tunda ke P1 bila risiko.

## Pertanyaan Terbuka

1. Apakah `escalation_chain` di config user terisi key yang valid? (default.yaml punya chain, tapi runtime user pakai opencode-zen free — apakah eskalasi pernah benar-benar jalan?)
2. Apakah text_parser (NL → tool) masih DIBUTUHKAN untuk model free yang dipakai, atau model sudah support native tool calling? (Kalau tidak dipakai lagi → usul matikan via config, bukan perbaiki pattern-nya.)
3. Apakah mau sekalian bikin skill `laravel-scaffold` di P0 (ada korelasi langsung dengan proyek auth-app yang tertunda)?
