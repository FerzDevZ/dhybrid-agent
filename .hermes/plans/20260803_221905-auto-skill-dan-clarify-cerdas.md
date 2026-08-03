# Auto-Skill Wajib + Clarify Cerdas (Pilihan Bernomor & "Lanjutkan") — Implementation Plan

> **Untuk Hermes:** implementasikan plan ini task-by-task (TDD: tulis test gagal → buktikan gagal → implementasi minimal → buktikan lulus → commit).

**Goal:** (A) setiap prompt user DIJAMIN memuat skill yang relevan (fallback skill umum bila tak ada yang cocok) + umpan balik transparan; (B) saat prompt ambigu/underspecified (mis. "buat web login register"), agent OTOMATIS menawarkan pilihan bernomor (1. PHP/Laravel, 2. Next.js, 3. React...) dengan default + user cukup jawab angka, teks bebas, atau "Lanjutkan".

**Architecture:**
- (A) Perluas `select_skills`/`inject_skills` di `src/dhybrid/skills/loader.py`: kalau skor semua skill < min_score → fallback ke skill umum bawaan (`general`) yang selalu ada. Tampilkan `[skill aktif: general]` supaya transparan.
- (B) Modul baru `src/dhybrid/agent/intent.py` — heuristik deteksi ambiguitas + generator opsi stack (berbasis isi project di cwd). REPL menjalankan deteksi SEBELUM memanggil agent (tanpa biaya token LLM); bila terpicu → tampilkan pilihan bernomor → jawaban user di-push sebagai `[keputusan user: ...]` → baru agent jalan. Tool baru `clarify` (mirip `ask_user`, guardrail sendiri) untuk kasus agent butuh tanya DI TENGAH kerja.

**Tech Stack:** Python 3.12, pytest (TDD), ruff (gate 0), coverage ≥65%. Versi rilis: 0.8.0.

---

## Konteks Saat Ini (sudah diverifikasi di repo)

- Auto-skill sudah ada tapi TIDAK dijamin: `repl.py:_run_one` (baris ~247-264) memanggil `extract_skill_mentions` → `select_skills(..., min_score=1)` → `inject_skills`. Bila tak ada skill yang skornya ≥1 → TIDAK ada yang di-inject, dan tidak ada umpan balik.
- `loader.py:select_skills` sudah punya fuzzy matching (rapidfuzz, graceful kalau tidak terpasang) — skill "nyaris cocok" (fb ≥ 75) sudah bisa layak inject.
- Auto-learn skill dari sesi sukses SUDAH ada (`auto_skill_worthwhile` + `build_skill_md`, dipanggil di akhir `_run_one`) — task nyata otomatis jadi skill. Yang kurang: JAMINAN prompt selalu dapat skill + feedback.
- `ask_user` sudah ada (`tools/ask.py`): `AskState` (interactive, count, pending), guardrail ASK_MAX=2/sesi, alur pause loop (`loop.py:_maybe_pause_for_user` → `result.pending_question` → REPL tanya → push `[jawaban user]` → `run_agent("", push_prompt=False)`). REPL sudah menampilkan pilihan bernomor + default = pilihan 1 (repl.py baris ~282-305). **Pola ini dipakai ulang untuk `clarify`.**
- `Config.skills` = `{"dir", "max_inject", "max_chars"}`; `SessionContext` meng-hold `ask_state`, `forced_skills`, `skills` (reload via `reload_skills`).
- Allowlist tool ada di `config/default.yaml` (28 tool saat ini); `tools/__init__.py:build_tools` mendaftarkan tool via `register(reg)`.

---

## Proposed Approach

### Pillar A — Auto-skill WAJIB (tiap prompt dapat skill)

1. Bundle skill umum baru: `src/dhybrid/skills/general/SKILL.md` (di direktori install, ikut `list_skills(install_dir()/"skills")` — otomatis selalu tersedia, tidak perlu ubah loader list).
2. `select_skills` tambah param `fallback: str | None = "general"` → bila hasil akhir kosong dan skill `general` ada → return `["general"]`. Skor tetap dihitung dulu; fallback hanya menyala saat 0 cocok.
3. `_run_one` selalu print feedback: `[skill aktif: a, b]` ATAU `[skill aktif: (tidak ada yang cocok) → general]` ATAU `[skill aktif: - (semua mati/dinonaktifkan)]`.
4. Config baru `skills.auto_general: bool = True` untuk mematikan fallback.
5. Auto-learn tetap; tambahan kecil: nama skill hasil auto-learn yang bentrok dengan `general` dilewati.

### Pillar B — Clarify cerdas (pilihan bernomor + "Lanjutkan")

1. **`src/dhybrid/agent/intent.py` (BARU):**
   - `detect_ambiguity(prompt, cwd=None) -> ClarifyHint | None`:
     - TOKEN: kata kerja membangun tanpa stack: {buat, bikin, bangun, buatin, bikinin, bantu, minta, tolong, kerjakan, lanjutkan?} ∩ prompt, DAN tidak ada kata kunci stack (php, laravel, django, flask, rails, node, next, react, vue, svelte, angular, go, golang, rust, java, kotlin, swift, flutter, react-native, python, typescript, javascript, html, css, sql, mysql, postgres, sqlite, mongodb, docker, api, cli, desktop, game) di prompt.
     - prompt pendek: jumlah kata bermakna (setelah stopword) ≤ 5 → sinyal ambigu.
     - **Konfirmasi project**: cek cwd → `composer.json` (PHP/Laravel), `package.json` + `next.config.*` (Next.js), `package.json` + `vite.config.*` (React+Vite), `pubspec.yaml` (Flutter), `go.mod` (Go), `Cargo.toml` (Rust), `requirements.txt`/`pyproject.toml` (Python) → default = stack project, opsi = stack deteksi + 2 alternatif populer.
     - Skip: prompt sudah menyebut stack; prompt hanya sapaan/pertanyaan ya/tidak (panjang < 12 char tanpa kata kerja membangun); turn sebelumnya adalah jawaban clarify (cek via param `last_turn_was_answer: bool`).
     - `ClarifyHint` = `{question: str, options: list[str], default_index: int, confidence: float}`.
   - `STACK_OPTIONS` generator: kategori task → opsi:
     - web app ("login/register/web/landing/page/crud"): ["PHP (Laravel)", "Next.js", "React + Vite", "Python (Django/Flask)"]
     - cli/tool ("script/cli/tool/otomasi"): ["Python", "Node.js", "Go", "Rust"]
     - mobile ("aplikasi android/ios/mobile"): ["Flutter", "React Native", "Kotlin (native)", "Swift (iOS)"]
     - default: ["Python", "PHP (Laravel)", "Next.js", "React + Vite"]
2. **`src/dhybrid/tools/clarify.py` (BARU):** tool `clarify(question, options, default_index=1)` — `ClarifyState` terpisah (CLARIFY_MAX=3/sesi, bukan ASK_MAX=2); non-interaktif → return sentinel "pilih default N dan lanjutkan"; set `state.pending`. Daftarkan di `tools/__init__.py` + allowlist.
3. **Loop & REPL:**
   - `loop.py:_maybe_pause_for_user` diperluas: `result.pending_question` juga terisi dari `ClarifyState.pending` (atau cukup: `SessionContext` punya `clarify_state`; loop menerima keduanya). Paling sederhana: `AgentLoop.__init__` terima `clarify_state=None`; cek keduanya di `_maybe_pause_for_user`.
   - `repl.py:_run_one` — SEBELUM `run_agent`:
     1. `hint = detect_ambiguity(clean_raw, cwd=ctx.cwd)` (skip bila `ctx.ask_state.interactive` False, bila config `clarify.enabled` False, atau bila `ctx.clarify_just_answered` True).
     2. Bila hint → tampilkan: pertanyaan, opsi bernomor, `(ketik nomor, teks bebas, atau Enter/Lanjutkan = opsi {default})`.
     3. Jawaban: angka → opsi[n]; kosong/"lanjutkan"/"l"/"default" → opsi[default]; selainnya → teks bebas.
     4. `ctx.ctx.push(ChatMessage(role="user", content=f"[keputusan user] {answer}"))` → `run_agent` jalan normal (keputusan masuk konteks sebagai pesan user terakhir). Set `ctx.clarify_just_answered = True` (di-reset setelah turn ini; ditandai lewat flag sesi) supaya tidak clarify berulang.
   - Prompt UI pakai pola ask_user yang sudah ada (baris 282-305) — reuse, jangan duplikasi.
4. **Config & allowlist:** `Config.clarify = {"enabled": True, "max_per_session": 3}`; `config/default.yaml` tambah blok `clarify:` + `skills.auto_general: true` + tool `clarify` masuk allowlist (28 → 29).
5. Non-interaktif (`dhybrid run`): clarify diblokir otomatis (interactive=False) → agent pakai default; intent detection juga di-skip.

---

## Step-by-Step Plan (TDD, bite-sized)

### Task 1: Skill umum bawaan `general`

**Objective:** Ada skill cadangan yang selalu tersedia untuk di-inject saat tak ada skill yang cocok.

**Files:**
- Create: `src/dhybrid/skills/general/SKILL.md`
- Test: `tests/unit/test_loader_general.py`

**Step 1: Tulis test gagal**

```python
def test_general_skill_bundled(tmp_path):
    from dhybrid.skills.loader import list_skills
    skills = list_skills(tmp_path)  # kosong
    assert skills == []
```

**Step 2: Jalankan → PASS (test ini hanya sanity list_skills kosong; verifikasi bundling di Task 2)**

```bash
pytest tests/unit/test_loader_general.py -q
```

**Step 3: Buat SKILL.md** — konten singkat & hemat token (~25 baris), frontmatter `name: general`, `description: Panduan umum pengerjaan task coding yang solid: baca file dulu sebelum edit, patch kecil, verifikasi nyata sebelum klaim selesai, jangan berhenti prematur.` Isi: langkah-langkah umum berkualitas (baca konteks → rencana → eksekusi kecil → verifikasi → laporkan bukti), berlaku untuk task apa pun.

**Step 4: Verifikasi**

```bash
cd /home/firman/dhybrid-agent && source .venv/bin/activate
python3 -c "from dhybrid.skills.loader import list_skills; from dhybrid.session.context import install_dir; print([s.name for s in list_skills(install_dir()/'skills')])"
```
Expected: daftar berisi `general`.

**Step 5: Commit**

```bash
git add src/dhybrid/skills/general/SKILL.md tests/unit/test_loader_general.py
git commit -m "feat: skill umum bawaan general (fallback auto-skill)"
```

---

### Task 2: Fallback `general` di `select_skills` + `inject_skills`

**Objective:** Bila 0 skill cocok → otomatis inject `general` (default), bisa dimatikan.

**Files:**
- Modify: `src/dhybrid/skills/loader.py` (`select_skills` tambah `fallback: str | None = "general"`; `inject_skills` tidak berubah API — cukup pass-through)
- Test: `tests/unit/test_loader_general.py` (tambah)

**Step 1: Tulis test gagal**

```python
def test_select_skills_fallback_general():
    from dhybrid.skills.loader import Skill, select_skills
    sk = [Skill(name="database", description="sql query", body="x", path=None)]
    names = select_skills("buat web login", sk)  # tidak ada yang cocok
    assert names == ["general"]

def test_select_skills_fallback_disabled():
    from dhybrid.skills.loader import Skill, select_skills
    sk = [Skill(name="database", description="sql query", body="x", path=None)]
    names = select_skills("buat web login", sk, fallback=None)
    assert names == []

def test_inject_skills_fallback():
    from dhybrid.skills.loader import Skill, inject_skills
    sk = [Skill(name="general", description="panduan umum", body="[umum] baca dulu", path=None)]
    out = inject_skills("buat web login", sk)
    assert "[SKILL: general]" in out
```

**Step 2: Jalankan → FAIL** (fallback belum ada)

**Step 3: Implementasi minimal**

```python
def select_skills(prompt, skills, history="", force=None, min_score=1, fallback="general"):
    # ... logika lama ...
    if not ordered and fallback:
        by_name = {s.name: s for s in skills}
        if fallback in by_name:
            return [fallback]
    return [s.name for s in ordered]
```

**Step 4: Jalankan → PASS** (`pytest tests/unit/test_loader_general.py -q`)

**Step 5: Commit**

```bash
git commit -am "feat: fallback skill general saat tak ada skill cocok"
```

---

### Task 3: Feedback skill transparan di `_run_one`

**Objective:** User selalu TAHU skill apa yang aktif; kalau fallback dipakai, terlihat.

**Files:**
- Modify: `src/dhybrid/ui/repl.py:_run_one` (blok `if selected:` baris ~261-264)
- Test: `tests/unit/test_repl_skills_feedback.py` (BARU)

**Step 1: Tulis test gagal**

```python
def test_run_one_shows_fallback_feedback(monkeypatch, capsys):
    # mock ctx minimal + run_agent agar tidak memanggil LLM
    # panggil _run_one(ctx, "buat web login") → output mengandung "[skill aktif"
    # dan "general"
    ...
```

**Step 2: Jalankan → FAIL**

**Step 3: Implementasi**

```python
if selected:
    shown = selected[:max_inject]
    tag = "paksa" if (mentions or ctx.forced_skills) else "aktif"
    print(style(f"[skill {tag}: {', '.join(shown)}]", "90"))
else:
    print(style("[skill aktif: (tidak ada yang cocok)]", "90"))
```

Catatan: dengan Task 2, `selected` hampir selalu berisi `general` — cabang `else` tersisa untuk kasus `skills.auto_general=False` atau semua skill di-disable.

**Step 4: Jalankan → PASS** (+ pastikan test lama `test_repl*` tetap lulus)

**Step 5: Commit**

```bash
git commit -am "feat: feedback skill aktif selalu tampil (termasuk fallback general)"
```

---

### Task 4: Modul `intent.py` — deteksi ambiguitas + opsi stack

**Objective:** Heuristik murni (tanpa LLM, tanpa token) mengenali prompt underspecified dan menyiapkan opsi bernomor + default berbasis project di cwd.

**Files:**
- Create: `src/dhybrid/agent/intent.py`
- Test: `tests/unit/test_intent.py`

**Step 1: Tulis test gagal** (kasus inti)

```python
def test_detect_ambiguity_web_app():
    h = detect_ambiguity("buat web login register")
    assert h is not None
    assert "PHP" in h.options and "Next.js" in h.options
    assert h.default_index >= 0

def test_detect_ambiguity_explicit_stack():
    assert detect_ambiguity("buat web login pakai laravel") is None

def test_detect_ambiguity_smalltalk():
    assert detect_ambiguity("halo") is None
    assert detect_ambiguity("terima kasih") is None

def test_detect_ambiguity_project_context(tmp_path):
    (tmp_path / "composer.json").write_text("{}")
    h = detect_ambiguity("buat halaman login", cwd=str(tmp_path))
    assert h is not None
    assert h.default_index == 0  # default = PHP/Laravel
    assert h.options[0].startswith("PHP")

def test_detect_ambiguity_skipped_after_answer():
    assert detect_ambiguity("lanjutkan", last_turn_was_answer=True) is None
```

**Step 2: Jalankan → FAIL** (modul belum ada)

**Step 3: Implementasi** (struktur inti)

```python
BUILD_VERBS = {"buat", "bikin", "bangun", "buatin", "bikinin", "buatkan", "kerjakan", "minta", "tolong", "bantu"}
STACK_WORDS = {"php", "laravel", "django", "flask", "rails", "node", "next", "react", "vue", ...}
TASK_KINDS = [
    ({"login", "register", "web", "landing", "page", "crud", "halaman", "situs", "website", "api"}, STACK_OPTIONS_WEB),
    ({"cli", "script", "tool", "otomasi", "automation", "scraping"}, STACK_OPTIONS_CLI),
    ({"android", "ios", "mobile", "aplikasi", "app"}, STACK_OPTIONS_MOBILE),
]

def _detect_project_stack(cwd) -> str | None:  # composer.json → "php", dst.

def detect_ambiguity(prompt, cwd=None, last_turn_was_answer=False) -> ClarifyHint | None:
    if last_turn_was_answer:
        return None
    words = {w for w in re.findall(r"[a-z0-9]{3,}", prompt.lower()) if w not in STOPWORDS}
    if not (words & BUILD_VERBS):
        return None
    if words & STACK_WORDS:
        return None
    proj = _detect_project_stack(cwd)
    for kind_words, opts in TASK_KINDS:
        if words & kind_words:
            options = list(opts)
            if proj:
                options.insert(0, f"{proj_label(proj)} (proyek ini)")
            return ClarifyHint(...)
    if len(words) <= 5:  # pendek & ambigu
        options = ...
        return ClarifyHint(...)
    return None
```

**Step 4: Jalankan → PASS** (`pytest tests/unit/test_intent.py -q`)

**Step 5: Commit**

```bash
git add src/dhybrid/agent/intent.py tests/unit/test_intent.py
git commit -m "feat: intent.py — deteksi prompt ambigu + opsi stack + deteksi project cwd"
```

---

### Task 5: Tool `clarify` + state sendiri

**Objective:** Agent bisa tanya pilihan bernomor DI TENGAH kerja dengan guardrail sendiri (3x/sesi), terpisah dari ask_user (2x/sesi).

**Files:**
- Create: `src/dhybrid/tools/clarify.py`
- Modify: `src/dhybrid/tools/__init__.py` (register), `src/dhybrid/session/context.py` (buat `clarify_state`, wiring), `config/default.yaml` (allowlist)
- Test: `tests/unit/test_clarify_tool.py`

**Step 1: Tulis test gagal**

```python
def test_clarify_sets_pending():
    from dhybrid.tools.clarify import ClarifyState, register
    from dhybrid.tools.registry import ToolRegistry
    st = ClarifyState(interactive=True)
    reg = ToolRegistry()
    register(reg, st)
    out = reg.call("clarify", question="stack apa?", options=["PHP", "Next.js"], default_index=1)
    assert out == "CLARIFY_PENDING"
    assert st.pending == {"question": "stack apa?", "options": ["PHP", "Next.js"], "default_index": 1}

def test_clarify_budget():
    st = ClarifyState(interactive=True)
    for _ in range(3):
        st.pending = None
        out = st._ask("q", ["a", "b"], 1)  # atau via register
    assert "BLOCKED" in out  # lewat CLARIFY_MAX

def test_clarify_noninteractive():
    st = ClarifyState(interactive=False)
    out = st._ask("q", ["a", "b"], 1)
    assert "default" in out.lower()
```

**Step 2: Jalankan → FAIL**

**Step 3: Implementasi** — salin pola `ask.py` (AskState → ClarifyState, CLARIFY_MAX=3, sentinel `CLARIFY_PENDING`, deskripsi tool: "Tanya pilihan ke user dengan opsi bernomor + default. Jawab angka / teks bebas / 'Lanjutkan' = default. Maks 3x per sesi. Untuk pertanyaan berdampak besar pakai ask_user.")

**Step 4: Jalankan → PASS** + pastikan allowlist memuat `clarify` (cek `python3 -c "from dhybrid.tools import build_tools; ..."`).

**Step 5: Commit**

```bash
git add src/dhybrid/tools/clarify.py src/dhybrid/tools/__init__.py src/dhybrid/session/context.py config/default.yaml tests/unit/test_clarify_tool.py
git commit -m "feat: tool clarify — pilihan bernomor + default, guardrail 3x/sesi"
```

---

### Task 6: Loop pause untuk clarify

**Objective:** `_maybe_pause_for_user` juga mendeteksi `clarify_state.pending`.

**Files:**
- Modify: `src/dhybrid/agent/loop.py` (`__init__` terima `clarify_state=None`; `_maybe_pause_for_user` cek keduanya)
- Test: `tests/unit/test_loop_clarify.py`

**Step 1: Tulis test gagal**

```python
def test_loop_pauses_on_clarify():
    from dhybrid.tools.clarify import ClarifyState
    st = ClarifyState(interactive=True)
    st.pending = {"question": "q", "options": ["a"], "default_index": 1}
    # AgentLoop minimal (mock client) → result.pending_question terisi
```

**Step 2: Jalankan → FAIL**

**Step 3: Implementasi**

```python
def _maybe_pause_for_user(self, result, last_text):
    for st in (self.ask_state, self.clarify_state):
        if st is not None and st.pending:
            result.pending_question = st.pending
            st.pending = None
            return True
    return False
```

**Step 4: Jalankan → PASS**

**Step 5: Commit**

```bash
git commit -am "feat: loop pause juga untuk clarify (guardrail terpisah dari ask_user)"
```

---

### Task 7: REPL — clarify pra-prompt (pilihan bernomor + "Lanjutkan")

**Objective:** Sebelum agent dipanggil, prompt ambigu → tanya pilihan dulu (tanpa token LLM); jawaban masuk konteks sebagai keputusan user; tidak clarify berulang.

**Files:**
- Modify: `src/dhybrid/ui/repl.py` (`_run_one` — sisipkan blok clarify sebelum `run_agent`; reuse pola input ask_user)
- Modify: `src/dhybrid/session/context.py` (`clarify_just_answered` flag; reset di awal turn baru)
- Test: `tests/unit/test_repl_clarify.py`

**Step 1: Tulis test gagal**

```python
def test_run_one_clarify_then_answer(monkeypatch, capsys):
    # detect_ambiguity → hint; input() → "2"; pastikan
    # ctx.ctx.messages terakhir = "[keputusan user] Next.js"
    # dan run_agent terpanggil dengan prompt yang memuat keputusan

def test_run_one_no_clarify_for_explicit(monkeypatch):
    # detect_ambiguity None → tidak ada prompt tambahan

def test_run_one_lanjutkan_means_default(monkeypatch):
    # input() → "lanjutkan" → keputusan = opsi default

def test_run_one_skips_when_just_answered(monkeypatch):
    # ctx.clarify_just_answered=True → detect_ambiguity dilewati
```

**Step 2: Jalankan → FAIL**

**Step 3: Implementasi** — sisipkan di `_run_one` setelah blok skill, sebelum `run_agent`:

```python
# Clarify cerdas: prompt ambigu → tanya pilihan bernomor SEBELUM agent jalan
# (tanpa biaya token; "Lanjutkan"/kosong = opsi default).
clarify_cfg = ctx.cfg.clarify if hasattr(ctx.cfg, "clarify") else {"enabled": True}
if clarify_cfg.get("enabled", True) and ctx.ask_state.interactive and not getattr(ctx, "clarify_just_answered", False):
    from dhybrid.agent.intent import detect_ambiguity
    hint = detect_ambiguity(clean_raw, cwd=ctx.cwd)
    if hint:
        opts = hint.options
        print(style("\n❓ " + hint.question, "1;36"))
        for i, o in enumerate(opts, 1):
            mark = " (default)" if i == hint.default_index + 1 else ""
            print(f"   {i}. {o}{mark}")
        print(style(f"   (ketik nomor, teks bebas, atau Enter/Lanjutkan = opsi {hint.default_index + 1})", "90"))
        try:
            answer = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            answer = ""
        low = answer.lower()
        if not answer or low in ("lanjutkan", "l", "default", "ya"):
            answer = opts[hint.default_index]
        elif answer.isdigit() and 1 <= int(answer) <= len(opts):
            answer = opts[int(answer) - 1]
        ctx.ctx.push(ChatMessage(role="user", content=f"[keputusan user] {answer}"))
        ctx.clarify_just_answered = True
```

Reset `clarify_just_answered = False` di awal `_run_one` (setelah judul sesi), supaya prompt berikutnya bisa clarify lagi.

**Step 4: Jalankan → PASS** + seluruh suite lama lulus (perhatikan test yang memanggil `_run_one` dengan ctx mock — perlu tambah atribut `clarify_just_answered`/`cfg.clarify` di mock).

**Step 5: Commit**

```bash
git commit -am "feat: REPL clarify pra-prompt — pilihan bernomor + Lanjutkan=default, sekali per turn"
```

---

### Task 8: Config + dokumen + rilis 0.8.0

**Files:**
- Modify: `src/dhybrid/config.py` (field `clarify: dict = {"enabled": True, "max_per_session": 3}`; `skills.auto_general` default True), `config/default.yaml`, `pyproject.toml` (0.8.0), `src/dhybrid/__init__.py`, `CHANGELOG.md`, `README.md`
- Test: `tests/unit/test_config_clarify.py`

**Step 1-2: Test → FAIL** (assert `Config().clarify["enabled"] is True`; `Config().skills["auto_general"] is True`)

**Step 3: Implementasi** — field + YAML + dokumentasi (README: blok "Auto-skill & tanya cerdas": contoh sesi; CHANGELOG `[0.8.0]`).

**Step 4: Gate rilis penuh**

```bash
cd /home/firman/dhybrid-agent && source .venv/bin/activate
ruff check src tests
python3 -m pytest --cov=dhybrid --cov-fail-under=65 -q
```
Expected: ruff 0, semua lulus, coverage ≥65% (bawa ke ≥65% dengan test baru di atas; target ~275+ test).

**Step 5: Smoke nyata (REPL, X11/terminal user):**

```bash
dhybrid repl
> buat web login register
```
Expected: muncul `❓ ...` dengan 1. PHP (Laravel) 2. Next.js 3. React + Vite 4. Python ...; ketik `2` → agent jalan dengan konteks "Next.js"; `[skill aktif: general]` atau skill relevan tampil. Ulangi dengan prompt `buat web login pakai laravel` → TANPA clarify, langsung kerja.

**Step 6: Commit + push + update install user**

```bash
git add -A && git commit -m "feat: rilis 0.8.0 — auto-skill wajib (fallback general) + clarify cerdas (pilihan bernomor, Lanjutkan=default)"
git push origin main
cd /home/firman/.dhybrid-agent && git pull origin main && source .venv/bin/activate && pip install -e . -q
python3 -c "import dhybrid; print(dhybrid.__version__)"   # → 0.8.0
```

---

## Files yang Berubah (ringkas)

| File | Aksi |
|---|---|
| `src/dhybrid/skills/general/SKILL.md` | BARU — skill umum bawaan |
| `src/dhybrid/skills/loader.py` | MOD — `select_skills(fallback="general")` |
| `src/dhybrid/agent/intent.py` | BARU — `detect_ambiguity`, `ClarifyHint`, opsi stack, deteksi project |
| `src/dhybrid/tools/clarify.py` | BARU — tool `clarify` + `ClarifyState` (max 3/sesi) |
| `src/dhybrid/tools/__init__.py` | MOD — register `clarify` |
| `src/dhybrid/agent/loop.py` | MOD — `clarify_state` di `_maybe_pause_for_user` |
| `src/dhybrid/ui/repl.py` | MOD — clarify pra-prompt + feedback skill transparan |
| `src/dhybrid/session/context.py` | MOD — `clarify_state`, `clarify_just_answered` |
| `src/dhybrid/config.py` + `config/default.yaml` | MOD — `clarify` config, `skills.auto_general`, allowlist 29 |
| `tests/unit/test_{loader_general,intent,clarify_tool,loop_clarify,repl_clarify,repl_skills_feedback,config_clarify}.py` | BARU |
| `pyproject.toml`, `__init__.py`, `CHANGELOG.md`, `README.md` | MOD — versi 0.8.0 + docs |

## Tests / Validation

- Unit: 7 file test baru (estimasi +15-20 test) — daftar kasus per task di atas.
- Gate: `ruff check src tests` = 0; `pytest --cov=dhybrid --cov-fail-under=65` lulus (target ≥65%).
- Smoke manual: (1) prompt ambigu → pilihan muncul, angka/lanjutkan/teks bebas semua jalan; (2) prompt dengan stack eksplisit → tanpa clarify; (3) non-interaktif `dhybrid run "buat web"` → tidak nanya (auto default); (4) `[skill aktif: ...]` selalu tampil termasuk fallback `general`.

## Risks, Tradeoffs, Open Questions

- **Risiko clarify mengganggu** (user malas nanya-nanya): mitigasi — hanya fire saat confidence tinggi (kata kerja membangun + tanpa stack + pendek), sekali per turn, bisa dimatikan `clarify.enabled: false`, non-interaktif otomatis skip. Heuristik konservatif lebih baik daripada agresif.
- **Risiko fallback `general` menambah token tiap prompt**: body skill dibuat sangat ringkas (~300-500 char); `max_chars` tetap memotong.
- **Interaksi dengan ask_user**: dua tool terpisah, guardrail berbeda (2 vs 3) — tidak saling mengurangi kuota.
- **Fuzzy matching rapidfuzz** tidak wajib (sudah graceful) — tidak ada dependensi baru; `intent.py` murni stdlib (re, pathlib).
- **Open question**: apakah `detect_ambiguity` perlu juga mempertimbangkan riwayat sesi (mis. user sudah bilang "pakai laravel" di turn sebelumnya, lalu "buat loginnya")? → Jawaban desain: YA, tambahkan param `history` di Task 4 (skor kecil: kata stack di 3 pesan user terakhir = prompt dianggap sudah jelas). Masukkan ke test `test_detect_ambiguity_history` di Task 4.
- **Open question**: opsi stack bisa dikustomisasi user? → YAGNI untuk 0.8.0; cukup lewat config `clarify.custom_options` bila ada permintaan nyata.
