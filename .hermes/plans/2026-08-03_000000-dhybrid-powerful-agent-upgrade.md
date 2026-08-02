# dhybrid-agent — POWERFUL Agent Upgrade Plan
> **Untuk Hermes:** gunakan skill `subagent-driven-development` untuk mengimplementasikan plan ini task-by-task.

## Goal: Make DHybird Agent Truly Powerful & Non-Buntu

Buat agen yang: **langsung eksekusi, tidak tanya-berulang, context-aware, escalation cerdas, dan konsisten tajam.** Inti perubahan: sistem yang melatih model lemah untuk bertindak seperti ahli senior — pakai heuristics + verifier + nudge yang lebih agresif.

---

## Problem Statement (Dari Log Sesi Nyata)

| Gejala | Dampak | Penyebab |
|---|---|---|
| Agen bertanya kembali padahal user sudah jelas meminta "buatkan login register" | User frustrasi, kualitas turun | Prompt sistem lemah — model menawarkan pertanyaan sebagai escape route |
| Agen boloi "cek folder ini" tanpa konteks | Session tidak productif, banyak token siai | Context tracking lemah — model tidak tahu apa sudah diketahui |
| Nudge loop (MAX_NUDGES=2) kadang tidak efektif | Model tetap berhenti di janji/pertanyaan | Heuristik score dan prompt nudge belum optimal |
| Model lemah (zen free) sering menghasilkan output rendah | Escalse tidak terjadi karena di-disable di v0.4.1 | Escalation kualitas & scoreboard routing dihapus di commit terakhir |
| Tool call JSON bare tak konsisten | Banyak fallback yang gagal | Parsing belum robust, few-shot kurang |

---

## Architecture: "Power Layer" di Sekitar Loop ReAct

```
┌─────────────────────────────────────────────┐
│  BASE PROMPT  (tambah 3 seksi:              │
│    - ACTION-FIRST RULES                      │
│    - CONTEXT AWARENESS                       │
│    - ESCALATION TRIGGER LIST)                │
└────────────────────┬────────────────────────┘
                     │
┌────────────────────▼────────────────────────┐
│  Context Manager (enhanced)                  │
│  - track known_facts dari session sebelumnya  │
│  - cache tool results yang pernah dicek       │
│  - inject "previous context" di sistem prompt │
└────────────────────┬────────────────────────┘
                     │
┌────────────────────▼────────────────────────┐
│  Agent Loop (upgrade)                        │
│  - Aggressive nudge (MAX_NUDGES=3)           │
│  - Stronger escalation (chain reactivasi)     │
│  - Score threshold turun (40→30)              │
│  - Self-critique mandatory untuk build>100char│
└────────────────────┬────────────────────────┘
                     │
┌────────────────────▼────────────────────────┐
│  Quality Scorer (upgrade)                    │
│  - + deteksi "bingung context"                │
│  - + deteksi "prompsi lemah"                  │
│  - + bonus untuk file creation                │
│  - escalation trigger otomatis bila <40       │
└────────────────────┬────────────────────────┘
                     │
┌────────────────────▼────────────────────────┐
│  Verifier (upgrade)                          │
│  - real-time file check setiap 2 steps       │
│  - auto-run pytest bila ada test file        │
│  - evidence injection ke prompt              │
└─────────────────────────────────────────────┘
```

---

## Phase 1: ACTION-FIRST System Prompt (P1 — Highest Priority)

### Objective
Ganti sistem prompt agen supaya model SELALU bertindak, tidak bertanya, tidak bolong.

### Files
- Modify: `src/dhybrid/session/context.py` (BASE_PROMPT upgrade)
- Test: snapshot system prompt length & content

### Task P1.1: Rewrite BASE_PROMPT
```
Kamu adalah dhybrid-agent, coding agent CLI yang POWERFUL — fokus eksekusi, hemat token.

ATURAN EMAS (IKUTI SELALU):
1. JIKA USER MEMINTA SESUAT → EKSEKUSI SEKARANG. Jangan tanya stack/mode.
   - Cek tools sistem (which php/node/python3). Pilih stack default yang tersedia.
   - Langsung buat file, jalankan, verifikasi, lapor.
2. SELALU gunakan tool (read_file, write_file, apply_patch) untuk eksplor & eksekusi.
3. Setelah pakai tool → selalu kasih jawaban akhir yang jelas (jangan diam).
4. TIDAK PERNAH bertanya kembali apa yang harus dilakukan — user sudah jelaskan.

CONTOH PANGGILAN TOOL (salah satu format berikut — gunakan native bila tersedia):
```tool
{"name": "write_file", "arguments": {"path": "login.py", "content": "..."}}
```

Format JSON satu baris juga valid:
{"name": "read_file", "arguments": {"path": "main.py", "limit": 50}}

TOOLS YANG TERSEDIA:
- read_file(path, offset, limit) — baca file
- write_file(path, content) — tulis file
- apply_patch(path, old_string, new_string) — edit minimal
- terminal(command) — jalankan perintah
- grep(pattern, path) — cari teks
- run_tests() — jalankan pytest
- tdd_status() — status TDD
- todo_add(text), todo_list(), todo_done(index) — task tracker

INGAT: Kerja langsung. Eksplor → Buat → Verifikasi → Lapor. JANGAN TANYA — EKSEKUSI.
```

**Task P1.2:** Test — `BASE_PROMPT` harus mengandung kata "EKSEKUSI" dan "JANGAN TANYA". Panjang ≤ 2000 karakter.

### Task P1.3: Inject Few-Shot Tool Format + Build Example
Tambahkan di system prompt contoh 1 tool call yang valid + 1 contoh build yang langsung eksekusi.

---

## Phase 2: Aggressive Nudge Loop + Real Escalation (P2)

### Objective
Re-aktifkan escalation kualitas + scoreboard — model lemah yang gagal akan otomatis naik ke model berikutnya.

### Files
- Modify: `src/dhybrid/agent/loop.py` (nudge + escalation reactivation)
- Modify: `src/dhybrid/agent/quality.py` (threshold turun)
- Create: `src/dhybrid/agent/scoreboard.py` (already exists — reuse)
- Modify: `config/default.yaml` (chain config)

### Task P2.1: Upgrade LoopConfig
```python
@dataclass
class LoopConfig:
    max_steps: int = 20
    max_tool_output_chars: int = 8000
    escalate_after_errors: int = 2
    self_critique: bool = True
    quality_threshold: int = 30          # turun dari 40 → lebih sensitip
    max_nudges: int = 3                  # naik dari 2
    escalation_chain: list[str] = field(default_factory=lambda: [
        "opencode-zen-big",      # Claude Sonnet 5 (route zen)
        "openrouter-big",        # Claude Sonnet 5 (openrouter)
        "anthropic-big",         # Claude Sonnet 4
    ])
```

### Task P2.2: Escalation Trigger
Di `loop.run()`, setelah final answer:
```python
if score < self.cfg.quality_threshold and not result.escalated:
    next_preset = self._next_preset_in_chain()
    if next_preset and self._has_api_key(next_preset):
        client = self._pick_client(user_prompt, force=next_preset)
        result.escalated = True
        # Push pesan eskalasi
        self.ctx.push(ChatMessage(role="user", content=(
            "[sistem] Jawabanmu kurang memadai (skor {}/100). "
            "Lanjutkan dengan model lebih kuat — selesaikan penuh, jangan tanya/minta bantuan."
        ).format(score)))
        continue  # restart loop dengan model baru
```

### Task P2.3: Stronger Nudge Messages
Ganti NUDGE_MSG/EXEC_MSG dengan lebih agresif:
```
NUDGE_MSG = "[instruksi sistem] JANGAN bertanya. User sudah meminta DIBUAT. " \
    "Cek tool sistem, pilih stack default, LANGSUNG tulis file, jalankan, lapor. " \
    "Ini bukan pilihan — ini perintah."

EXEC_MSG = "[instruksi sistem] Kamu belum membuat/mengubah file apa pun. " \
    "User meminta DIBUAT. EKSKUSI SEKARANG: gunakan write_file untuk membuat file, " \
    "terminal untuk memverifikasi, lalu lapor hasilnya. JANGAN menolak."
```

### Task P2.4: Config chain di default.yaml
```yaml
model:
  escalation_chain: ["opencode-zen-big", "openrouter-big", "anthropic-big"]
```

---

## Phase 3: Context Awareness & Known Facts Tracker (P3)

### Objective
Agen tidak bolong bertanya "cek folder ini" — ia harus tahu apa yang sudah diketahui.

### Files
- Modify: `src/dhybrid/agent/loop.py` (track known facts)
- Modify: `src/dhybrid/agent/context.py` → tambahkan KnownFacts tracker
- Modify: `src/dhybrid/session/context.py` (inject previous context)

### Task P3.1: KnownFacts Tracker
```python
class KnownFacts:
    def __init__(self):
        self.facts: set[str] = set()  # facts yang sudah benar
        self.questions: list[str] = []  # pertanyaan yang sudah diajukan
    
    def add_fact(self, fact: str):
        self.facts.add(fact)
    
    def is_known(self, question: str) -> bool:
        return any(f in question.lower() for f in self.facts)
    
    def already_asked(self, question: str) -> bool:
        return any(q in question.lower() for q in self.questions)
```

### Task P3.2: Inject into System Prompt
```
KONTeks SEKARANG:
{fakta1, fakta2, ...}

Fakta diketahui: {setiap fact yang sudah diverifikasi}
Pertanyaan yang sudah diajukan: {daftar pertanyaan}

JANGAN tanyakan lagi hal yang sudah kita ketahui. Eksplor dengan tool, jangan dengan bertanya.
```

### Task P3.3: Auto-Extract Facts
Setelah setiap tool call yang sukses → extract fakta otomatis:
- `ls -la` → "folder X ada"
- `which php` → "php tersedia" / "php tidak tersedia"
- `read_file` → "file X berisi Y"

---

## Phase 4: Enhanced Quality Scorer (P4)

### Objective
Skor kualitas lebih akurat — deteksi "bingung", "prompts lemah", bonus eksekusi.

### Files
- Modify: `src/dhybrid/agent/quality.py`

### Task P4.1: Upgrade score_output
```python
def score_output(text, *, is_build=False, tools_used=0, files_created=0, tests_passed=None):
    t = (text or "").strip()
    if not t:
        return 0
    score = 50
    low = t.lower()
    
    # Detection: model menolak/membatalkan
    REFUSAL_HINTS = (
        "tidak bisa", "tidak dapat", "cannot", "can't",
        "tidak tersedia", "tidak memiliki akses", "tidak sanggup",
        "saya tidak bisa", "maaf", "maafkan",
    )
    if any(h in low for h in REFUSAL_HINTS):
        score -= 40
    
    # Detection: model bingung / bertanya kembali
    CONFUSED_HINTS = (
        "mau yang mana", "pilih", "bagaimana sebaiknya", "bisa jelaskan",
        "untuk memastikan", "agar saya yakin", "jika memungkinkan",
    )
    if any(h in low for h in CONFUSED_HINTS):
        score -= 25
    
    # Detection: build request tapi bertanya kembali
    if is_build and re.search(r"\?\s*$", t):
        score -= 30
    
    # Detection: build request tapi tidak ada file
    if is_build and files_created == 0 and tools_used == 0:
        score -= 35
    
    # Bonus: file creation
    if files_created > 0:
        score += min(files_created * 10, 30)  # max +30
    
    # Bonus: tests passed
    if tests_passed is True:
        score += 20
    elif tests_passed is False:
        score -= 15
    
    # Length penalty/bonus
    if len(t) > 300:
        score += 10
    elif len(t) < 60 and is_build:
        score -= 15
    
    return max(0, min(100, score))
```

### Task P4.2: Test Coverage
- `score_output("")` → 0
- `score_output("Saya tidak bisa")` → < 20
- `score_output("mau yang mana?")` → score turun
- Build request dengan file dibuat → score tinggi

---

## Phase 5: Real-Time Verifier (P5)

### Objective
Verifikasi file/test secara real-time setiap beberapa steps — bukan hanya di akhir.

### Files
- Modify: `src/dhybrid/agent/loop.py` (inject verification)
- Modify: `src/dhybrid/agent/verify.py` (live check)

### Task P5.1: Live File Check
```python
# Di setiap 2 steps, cek apakah file ada yang dibuat
def _live_verify(self, step, before_files):
    if step % 2 == 0 and step > 0:
        current_files = snapshot_files(self.cwd)
        created = count_created_files(before_files, current_files)
        if created > 0:
            # inject fact ke known facts
            self.ctx.known_facts.add_fact(f"{created} file baru terbentuk di {step}")
            # push ke prompt sebagai evidence
            self.ctx.push(ChatMessage(role="user", content=(
                f"[verifikasi] Sistem mendeteksi {created} file baru "
                f"telah dibuat. Lanjutkan verifikasi dan finalisasi."
            )))
```

### Task P5.2: Auto-Run Tests
```python
# Bila ada *.py test file, jalankan pytest otomatis setelah build
def _maybe_run_tests(self):
    from pathlib import Path
    test_files = list(Path(self.cwd).rglob("test_*.py"))
    if test_files:
        test_output = self.tools.execute("run_tests", {})
        self.tool_events.append({"name": "auto_run_tests", "output": test_output[:2000]})
```

---

## Phase 6: Prompt Injection Guard + Security (P6 — Opsional tapi penting)

### Objective
Filter prompt injection dari file/input user sebelum dikirim ke model.

### Files
- Modify: `src/dhybrid/tools/patch.py` / `read_file` / `terminal`
- Create: `src/dhybrid/tools/security.py`

### Task P6.1: Sanitize Tool Output
```python
INJECTION_PATTERNS = [
    r"\[\s*instruksi\s+sistem.*?\s*\]",
    r"\[\s*sistem.*?\s*\]",
    r"JANGAN.*?EKSEKUSI",  # reverse psychology
    r"ignore all previous instructions",
    r"disregard the above",
]

def sanitize_output(text: str) -> str:
    for pattern in INJECTION_PATTERNS:
        text = re.sub(pattern, "[FILTERED]", text, flags=re.IGNORECASE | re.DOTALL)
    return text
```

---

## Prioritas & Estimasi

| # | Phase | Effort | Nilai | Dependency | Status |
|---|---|---|---|---|---|
| P1 | Action-First Prompt | S (1-2 jam) | ★★★★★ | — | ✅ DONE |
| P2 | Aggressive Nudge + Escalation | M (3-4 jam) | ★★★★★ | P1 | ✅ DONE |
| P3 | Context Awareness | M (3-4 jam) | ★★★★☆ | P1 | ✅ DONE |
| P4 | Enhanced Quality Scorer | S (1 jam) | ★★★★☆ | P2 | ✅ DONE |
| P5 | Real-Time Verifier | M (2-3 jam) | ★★★★☆ | P1 | ✅ DONE |
| P6 | Prompt Injection Guard | S (1 jam) | ★★★☆☆ | P1 | Pending (existing guard in lazy.py cukup)

## Metrik Sukses (Definisi Selesai)

1. **P1 ✓:** System prompt mengandung "EKSEKUSI SEKARANG" + "JANGAN TANYA" + contoh tool call
2. **P2 ✓:** Escalation chain berfungsi — model lemah yang dapat skor <30 otomatis naik ke preset berikutnya
3. **P3 ✓:** Agen tidak bertanya kembali fakta yang sudah diketahui (track fact + questions)
4. **P4 ✓:** Score output akurat — test pass semua kasus
5. **P5 ✓:** Live verifier mendeteksi file baru tiap 2 steps + auto-run tests
6. **P6 ✓:** Injection guard menyanitasi output tool yang mengandung "instruksi sistem"

## Risiko & Tradeoff

- **Escalation cost:** Chain ke model premium pakai key user — hanya bila skor < 30 (sangat jarang untuk tugas kecil)
- **Nudge berlebihan:** Max 3 nudges per run — tidak infinite loop
- **Context injection:** Fakta disimpan di memory — overhead minimal (~200 token per session)
- **Auto-test:** Hanya jalan bila ada test file — tidak memperlambat work normal

---

*Dipersiapkan 2026-08-03 — mengganti commit f962d2d yang menghapus escalation. Fokus: agen yang bertindak, bukan bertanya. Filosofi: power datang dari heuristic + verifier + agresivitas, bukan dari model premium yang mahal.*