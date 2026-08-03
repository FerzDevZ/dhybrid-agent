# Power-Up Pip Packages & Auto-Skill Lebih Banyak — Rencana Implementasi (v0.9.0)

> **Untuk Hermes:** gunakan skill subagent-driven-development untuk mengerjakan plan ini task-by-task (TDD ketat: test gagal → implementasi → lulus → commit).

**Goal:** Menjadikan dhybrid-agent jauh lebih powerful dengan (A) tool-tool baru berbasis pip packages populer (sistem, templating/scaffold, analisis data SQL, PDF/Excel edit, deteksi MIME) dan (B) sistem auto-skill yang jauh lebih agresif & cerdas (skill dari Q&A berulang, update skill lama, digest kandidat skill di akhir sesi, saran skill saat fallback `general` dipakai terus).

**Architecture:**
- (A) Tool baru didaftarkan **kondisional** (soft-register): modul tool mencoba `import` dependency-nya; gagal → tool tidak terdaftar, tidak muncul di spec, dan saat user mengetik namanya → pesan ramah "butuh `pip install dhybrid-agent[power]`". Pola ini sudah dipakai `documents.py` (markitdown) & `vision.py` (rapidocr), jadi konsisten.
- (B) Auto-skill diperluas dari "1 skill per run sukses" menjadi pipeline: (1) skill dari Q&A berulang (pertanyaan sama ≥2x → skill pengetahuan), (2) update skill lama yang terbukti lebih lengkap, (3) digest kandidat skill di akhir sesi (pilihan bernomor, pola clarify), (4) sinyal fallback `general` dipakai ≥3x → saran buat skill spesifik. Semua tetap tanpa LLM untuk keputusan (heuristik murni, hemat token), kecuali digest akhir yang memakai ringkasan LLM opsional.

**Tech Stack:** Python 3.12, pip packages baru: `psutil`, `jinja2`, `duckdb`, `pypdf`, `openpyxl`, `python-magic` (extra `power`). Existing: rich, prompt_toolkit, litellm, tree-sitter, markitdown, sqlite-vec, rapidfuzz.

---

## Konteks Saat Ini (bekal implementer)

- Repo: `/home/firman/dhybrid-agent`, branch `main`, versi sekarang **0.8.2** (HEAD `367cf789`), rilis berjalan: 315 test lulus, coverage 68.84%, ruff 0.
- **Gate rilis wajib:** `ruff check src tests scripts` = 0 error; `python3 -m pytest --cov=dhybrid --cov-fail-under=65` lulus; versi sinkron (pyproject.toml + `src/dhybrid/__init__.py` + CHANGELOG.md + README.md); smoke script PTY `scripts/smoke_clarify.py` OK; lalu `git push` + update produksi `~/.dhybrid-agent` (git pull + `pip install -e '.[vision,e2e,power]'`).
- **Dependency saat ini** (`pyproject.toml`): httpx, pyyaml, prompt_toolkit, markitdown[pdf,docx,pptx,xlsx], trafilatura, rapidfuzz, pydantic, ddgs, rich, tree-sitter(+python/php/javascript), sqlite-vec, beautifulsoup4, lxml, litellm. Extras: `e2e` (playwright), `vision` (rapidocr-onnxruntime, python-xlib), `dev`.
- **Cara daftar tool** (`src/dhybrid/tools/__init__.py:12-55`): `build_tools()` memanggil `mod.register(reg, max_chars=max_chars)` per modul; modul tool punya fungsi `register(reg, ...)` yang memanggil `reg.register(name, description, parameters, fn)` (lihat `registry.py:26`). Tool di-allowlist via `config/default.yaml` → `tool.allowlist` (sekarang **31** tool, termasuk `clarify`).
- **Auto-skill sekarang** (`src/dhybrid/ui/repl.py:431-459` `_auto_learn_skill`): setelah tiap run — `auto_skill_worthwhile()` (file dibuat / tool mutasi / run_tests) → `slugify(raw)` → cek duplikat nama (skip kalau ada) → `build_skill_md()` → tulis ke `<workspace>/skills/<name>/SKILL.md`. `TRIVIAL_SLUGS` memfilter sapaan. Skill loader: `src/dhybrid/skills/loader.py` (`list_skills`, `select_skills`, `inject_skills`, `build_skill_md`, `slugify`, `auto_skill_worthwhile`, `MUTATING_TOOLS`).
- **SessionContext** (`src/dhybrid/session/context.py`): `ctx.clarify_state`, `ctx.clarify_just_answered`, `ctx.facts` (FactStore), `ctx.tools.tool_count`, `ctx.memory` (MemoryStore sqlite per proyek), `ctx.workspace`.
- **Pola clarify pra-prompt** (`src/dhybrid/ui/repl.py`): `detect_ambiguity()` → print pilihan bernomor → `input()` → `[keputusan user]` / `[jawaban user]` di-push ke konteks. Pola ini dipakai ulang untuk digest skill akhir sesi.
- Bahasa komunikasi & commit message: **Indonesia**.

---

## Bagian A — Power-Up Pip Packages (Tool Baru)

### Task 1: Infrastruktur soft-register tool (dependency optional)

**Objective:** Tool yang butuh dependency opsional tidak boleh merusak startup; kalau dependency tak ada, tool di-skip dengan pesan ramah saat dipanggil.

**Files:**
- Create: `src/dhybrid/tools/soft.py`
- Modify: `src/dhybrid/tools/__init__.py:42-46` (daftarkan modul power)
- Test: `tests/unit/test_soft_register.py`

**Step 1: Tulis test gagal**

```python
# tests/unit/test_soft_register.py
import pytest
from dhybrid.tools.registry import ToolRegistry
from dhybrid.tools import soft


def test_soft_register_skips_missing_dep(monkeypatch):
    reg = ToolRegistry()
    monkeypatch.setattr(soft, "_import_any", lambda mods: None)  # dep tidak ada
    soft.register(reg, max_chars=100)
    assert "data_query" not in {s["name"] for s in reg.specs()}


def test_soft_register_registers_when_dep_present(monkeypatch):
    reg = ToolRegistry()
    monkeypatch.setattr(soft, "_import_any", lambda mods: object())
    soft.register(reg, max_chars=100)
    names = {s["name"] for s in reg.specs()}
    assert {"sys_info", "scaffold", "data_query"} <= names


def test_execute_missing_dep_gives_friendly_error(monkeypatch):
    reg = ToolRegistry()
    monkeypatch.setattr(soft, "_import_any", lambda mods: None)
    soft.register(reg, max_chars=100)
    out = reg.execute("data_query", {"sql": "SELECT 1"})
    assert "power" in out and "pip install" in out
```

**Step 2:** Jalankan → FAIL (modul `soft` belum ada).

**Step 3: Implementasi minimal** — `src/dhybrid/tools/soft.py`:

```python
"""Tool 'power' — dependency opsional (psutil/jinja2/duckdb/pypdf/openpyxl).

Soft-register: kalau dependency belum terpasang, tool TIDAK terdaftar;
kalau dipanggil (allowlist masih berisi nama) → pesan ramah cara install.
"""
from __future__ import annotations

import importlib

POWER_EXTRA = "pip install -e '.[power]'"  # atau pip install dhybrid-agent[power]


def _import_any(mods: list[str]):
    for m in mods:
        try:
            return importlib.import_module(m)
        except ImportError:
            continue
    return None


def _need(reg, name: str, mods: list[str], description: str, parameters: dict, fn):
    mod = _import_any(mods)
    if mod is None:
        # tetap daftarkan sebagai tool 'palsu' dengan pesan install ramah
        def _missing(**kw):
            return f"ERROR: tool '{name}' butuh package: {', '.join(mods)} — install: {POWER_EXTRA}"

        reg.register(name, description + " (butuh package opsional)", parameters, _missing)
        return
    reg.register(name, description, parameters, fn)


def register(reg, max_chars: int = 8000):
    from dhybrid.tools import power_sys, power_scaffold, power_data, power_pdf, power_xlsx

    power_sys.register(reg, _need=_need)
    power_scaffold.register(reg, _need=_need)
    power_data.register(reg, _need=_need, max_chars=max_chars)
    power_pdf.register(reg, _need=_need)
    power_xlsx.register(reg, _need=_need)
```

Catatan desain: tool tetap di-allowlist di `config/default.yaml` supaya spec konsisten; yang berbeda hanya body fn. Tool yang belum terpasang tidak muncul di `spec_text()` karena `ToolRegistry.specs()` menampilkan semua — ubah `registry.specs()` agar tool dengan fn `_missing` ditandai (opsional: tambah field `available: bool` di ToolSpec; langkah ini cukup: `_missing` tetap terdaftar — spec tetap muncul supaya model tahu tool ADA tapi butuh install; keputusan: **spec tetap tampil** dengan keterangan "butuh package").

**Step 4:** Jalankan → PASS. **Step 5: Commit:** `feat: soft-register tool power — dependency opsional tanpa merusak startup`

---

### Task 2: Extra `power` di pyproject + allowlist + wiring build_tools

**Objective:** Dependency power dideklarasikan sebagai extra, allowlist default memuat tool baru, `build_tools` mendaftarkannya.

**Files:**
- Modify: `pyproject.toml:32-39` (tambah extra `power`)
- Modify: `src/dhybrid/tools/__init__.py` (import + register `soft`)
- Modify: `config/default.yaml` (allowlist += 5 nama tool power)
- Test: `tests/unit/test_build_tools_power.py`

**Step 1: Test gagal**

```python
# tests/unit/test_build_tools_power.py
from dhybrid.config import Config
from dhybrid.tools import build_tools


def test_build_tools_registers_power_when_installed(tmp_path):
    cfg = Config.load("config/default.yaml")
    cfg.workspace = tmp_path
    reg = build_tools(cfg)
    names = {s["name"] for s in reg.specs()}
    assert {"sys_info", "scaffold", "data_query", "pdf_ops", "xlsx_edit"} <= names
    # allowlist default memuat semuanya
    for n in ("sys_info", "scaffold", "data_query", "pdf_ops", "xlsx_edit"):
        assert n in reg.allowlist
```

**Step 2:** FAIL (belum terdaftar). **Step 3:**

```yaml
# config/default.yaml — tool.allowlist tambahkan 5 nama:
#   ... (31 nama lama) ..., "sys_info", "scaffold", "data_query", "pdf_ops", "xlsx_edit"
```

```toml
# pyproject.toml
power = [
    "psutil>=5.9",
    "jinja2>=3.1",
    "duckdb>=1.0",
    "pypdf>=4.0",
    "openpyxl>=3.1",
    "python-magic>=0.4",
]
```

`src/dhybrid/tools/__init__.py`: tambah `soft` ke tuple import + `soft.register(reg, max_chars=max_chars)` di loop `for mod in (...)`.

**Step 4:** PASS (pastikan venv dev sudah `pip install -e '.[power]'`). **Step 5: Commit:** `feat: extra power — psutil/jinja2/duckdb/pypdf/openpyxl/python-magic + allowlist 36`

---

### Task 3: Tool `sys_info` — kesehatan sistem (psutil)

**Objective:** Agent bisa cek CPU/RAM/disk/proses/memori virtual dalam satu panggilan ringkas — berguna sebelum build berat atau debugging "kenapa lambat".

**Files:**
- Create: `src/dhybrid/tools/power_sys.py`
- Test: `tests/unit/test_power_sys.py`

**Step 1: Test gagal**

```python
# tests/unit/test_power_sys.py
from dhybrid.tools import power_sys
from dhybrid.tools.registry import ToolRegistry


def test_sys_info_basic(monkeypatch):
    reg = ToolRegistry()
    calls = {}

    def fake_virtual_memory():
        calls["vm"] = True
        return type("V", (), {"percent": 42.0, "available": 1 << 30})()

    monkeypatch.setattr(power_sys.psutil, "virtual_memory", fake_virtual_memory)
    out = power_sys._sys_info()
    assert "CPU" in out and "RAM" in out and "42" in out


def test_sys_info_registers(monkeypatch):
    reg = ToolRegistry()
    power_sys.register(reg, _need=lambda reg, n, d, p, f, **k: f(n, d, p, f))
    names = {s["name"] for s in reg.specs()}
    assert "sys_info" in names
    out = reg.execute("sys_info", {})
    assert not out.startswith("ERROR")
```

**Step 2:** FAIL. **Step 3:**

```python
# src/dhybrid/tools/power_sys.py
import psutil


def _sys_info() -> str:
    vm = psutil.virtual_memory()
    lines = [
        f"CPU: {psutil.cpu_percent(interval=0.2)}% ({psutil.cpu_count()} core)",
        f"RAM: {vm.percent}% terpakai ({vm.available // (1<<20)} MB bebas)",
        f"Disk: {psutil.disk_usage('/').percent}% terpakai",
        f"Proses: {len(psutil.pids())} berjalan",
    ]
    return "\n".join(lines)


def register(reg, _need=None, **kw):
    (_need or _default_need)(reg, "sys_info", ["psutil"], "Cek kesehatan sistem: CPU, RAM, disk, jumlah proses", {}, _sys_info)
```

**Step 4:** PASS. **Step 5: Commit:** `feat: tool sys_info — CPU/RAM/disk/proses via psutil`

---

### Task 4: Tool `scaffold` — generate file dari template (jinja2)

**Objective:** Scaffold project/file dari template Jinja2 dengan variabel — lebih kuat dari write_file mentah untuk membuat banyak file konsisten (Laravel controller, React component, dst). Aman: resolusi path dicek tidak keluar dari direktori target.

**Files:**
- Create: `src/dhybrid/tools/power_scaffold.py`
- Test: `tests/unit/test_power_scaffold.py`

**Step 1: Test gagal**

```python
# tests/unit/test_power_scaffold.py
from dhybrid.tools import power_scaffold


def test_scaffold_renders_template(tmp_path):
    src = tmp_path / "tmpl"
    src.mkdir()
    (src / "hello.txt.j2").write_text("Halo {{ nama }}!")
    out = power_scaffold._scaffold(str(src), str(tmp_path / "out"), {"nama": "Dunia"})
    assert "Dunia" in out
    assert (tmp_path / "out" / "hello.txt").read_text() == "Halo Dunia!"


def test_scaffold_blocks_path_traversal(tmp_path):
    src = tmp_path / "tmpl"
    src.mkdir()
    (src / "x.txt.j2").write_text("x")
    out = power_scaffold._scaffold(str(src), str(tmp_path / "out"), {"nama": ".."})
    assert "ERROR" in out  # traversal harus ditolak
```

**Step 2:** FAIL. **Step 3:**

```python
# src/dhybrid/tools/power_scaffold.py
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, StrictUndefined


def _scaffold(template_dir: str, target_dir: str, variables: dict) -> str:
    tdir, tgt = Path(template_dir), Path(target_dir)
    if not tdir.is_dir():
        return f"ERROR: template dir tidak ada: {template_dir}"
    env = Environment(loader=FileSystemLoader(str(tdir)), undefined=StrictUndefined, autoescape=False)
    created = 0
    for tmpl in tdir.rglob("*.j2"):
        rel = tmpl.relative_to(tdir).with_suffix("")
        dest = (tgt / rel).resolve()
        if not dest.is_relative_to(tgt.resolve()):
            return f"ERROR: path traversal diblokir: {rel}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(env.get_template(tmpl.relative_to(tdir).as_posix()).render(**variables))
        created += 1
    return f"OK: {created} file di-scaffold dari {template_dir} → {target_dir}"
```

**Step 4:** PASS. **Step 5: Commit:** `feat: tool scaffold — generate file dari template jinja2 (aman traversal)`

---

### Task 5: Tool `data_query` — SQL langsung ke CSV/JSONL (duckdb)

**Objective:** Analisis data tanpa Python: `SELECT` ke file CSV/JSONL/Parquet via duckdb, read-only, hasil dipotong (hemat token). Ini "penunjang powerful" untuk data task.

**Files:**
- Create: `src/dhybrid/tools/power_data.py`
- Test: `tests/unit/test_power_data.py`

**Step 1: Test gagal**

```python
# tests/unit/test_power_data.py
from dhybrid.tools import power_data


def test_data_query_csv(tmp_path):
    f = tmp_path / "data.csv"
    f.write_text("nama,umur\nAndi,20\nBudi,30\n")
    out = power_data._data_query(f"SELECT * FROM read_csv_auto('{f}') WHERE umur > 25", max_rows=10)
    assert "Budi" in out and "Andi" not in out


def test_data_query_blocks_write(tmp_path):
    f = tmp_path / "d.csv"
    f.write_text("a\n1\n")
    out = power_data._data_query("CREATE TABLE x AS SELECT 1", max_rows=10)
    assert "ERROR" in out  # read-only: CREATE/INSERT/DROP/UPDATE/DELETE ditolak
```

**Step 2:** FAIL. **Step 3:**

```python
# src/dhybrid/tools/power_data.py
import duckdb

_FORBIDDEN = ("create", "insert", "update", "delete", "drop", "alter", "attach", "copy", "export")


def _data_query(sql: str, max_rows: int = 20) -> str:
    low = sql.lower().strip()
    if any(low.startswith(k) or f" {k} " in low for k in _FORBIDDEN):
        return "ERROR: data_query read-only — query tulis (CREATE/INSERT/UPDATE/DELETE/dst) ditolak"
    con = duckdb.connect(":memory:")
    try:
        rows = con.execute(sql).fetchmany(max_rows + 1)
        cols = [d[0] for d in con.description or []]
    except Exception as e:  # noqa: BLE001
        return f"ERROR: {e}"
    lines = ["\t".join(map(str, cols))]
    lines += ["\t".join(str(c) for c in r) for r in rows[:max_rows]]
    if len(rows) > max_rows:
        lines.append(f"... ({len(rows)} baris pertama, potong {max_rows})")
    return "\n".join(lines)
```

**Step 4:** PASS. **Step 5: Commit:** `feat: tool data_query — SQL read-only ke CSV/JSONL/Parquet via duckdb`

---

### Task 6: Tool `pdf_ops` — merge & split PDF (pypdf)

**Objective:** Merge beberapa PDF jadi satu; split PDF per halaman/rentang — melengkapi `documents` (baca) dengan operasi tulis PDF.

**Files:**
- Create: `src/dhybrid/tools/power_pdf.py`
- Test: `tests/unit/test_power_pdf.py`

**Step 1: Test gagal**

```python
# tests/unit/test_power_pdf.py
from dhybrid.tools import power_pdf


def test_pdf_merge(tmp_path):
    # buat 2 pdf mini via pypdf writer
    from pypdf import PdfWriter

    def mk(name):
        w = PdfWriter()
        w.add_blank_page(200, 200)
        p = tmp_path / name
        with open(p, "wb") as fh:
            w.write(fh)
        return str(p)

    out = power_pdf._pdf_merge([mk("a.pdf"), mk("b.pdf")], str(tmp_path / "ab.pdf"))
    assert "OK" in out and (tmp_path / "ab.pdf").exists()


def test_pdf_merge_blocks_missing_file(tmp_path):
    out = power_pdf._pdf_merge([str(tmp_path / "no.pdf")], str(tmp_path / "x.pdf"))
    assert "ERROR" in out
```

**Step 2:** FAIL. **Step 3:**

```python
# src/dhybrid/tools/power_pdf.py
from pathlib import Path
from pypdf import PdfWriter


def _pdf_merge(sources: list[str], target: str) -> str:
    writer = PdfWriter()
    for s in sources:
        p = Path(s)
        if not p.exists():
            return f"ERROR: file tidak ada: {s}"
        try:
            writer.append(str(p))
        except Exception as e:  # noqa: BLE001
            return f"ERROR: gagal baca {s}: {e}"
    t = Path(target)
    t.parent.mkdir(parents=True, exist_ok=True)
    with open(t, "wb") as fh:
        writer.write(fh)
    return f"OK: {len(sources)} pdf digabung → {target}"
```

**Step 4:** PASS. **Step 5: Commit:** `feat: tool pdf_ops — merge PDF via pypdf`

---

### Task 7: Tool `xlsx_edit` — edit Excel (openpyxl)

**Objective:** Set cell / append baris / buat sheet baru di .xlsx — melengkapi markitdown (baca) dengan edit. Pilihan: tulis ke file BARU agar tidak merusak file asli.

**Files:**
- Create: `src/dhybrid/tools/power_xlsx.py`
- Test: `tests/unit/test_power_xlsx.py`

**Step 1: Test gagal**

```python
# tests/unit/test_power_xlsx.py
from dhybrid.tools import power_xlsx


def test_xlsx_set_cell(tmp_path):
    src = tmp_path / "in.xlsx"
    from openpyxl import Workbook

    wb = Workbook()
    wb.active["A1"] = "lama"
    wb.save(src)

    out = power_xlsx._xlsx_edit(str(src), str(tmp_path / "out.xlsx"), [{"cell": "A1", "value": "baru"}])
    assert "OK" in out

    from openpyxl import load_workbook

    assert load_workbook(tmp_path / "out.xlsx").active["A1"].value == "baru"
    # file asli tidak berubah
    assert load_workbook(src).active["A1"].value == "lama"
```

**Step 2:** FAIL. **Step 3:**

```python
# src/dhybrid/tools/power_xlsx.py
from pathlib import Path
from openpyxl import load_workbook


def _xlsx_edit(source: str, target: str, edits: list[dict]) -> str:
    if not Path(source).exists():
        return f"ERROR: file tidak ada: {source}"
    wb = load_workbook(source)
    ws = wb.active
    n = 0
    for e in edits or []:
        if "cell" in e:
            ws[e["cell"]] = e.get("value")
            n += 1
        elif "append" in e:
            ws.append(e["append"])
            n += 1
    Path(target).parent.mkdir(parents=True, exist_ok=True)
    wb.save(target)
    return f"OK: {n} edit diterapkan → {target} (file asli tidak diubah)"
```

**Step 4:** PASS. **Step 5: Commit:** `feat: tool xlsx_edit — edit Excel via openpyxl (salinan, asli aman)`

---

### Task 8: Deteksi MIME di vision/paste (python-magic, fallback ekstensi)

**Objective:** `/pasteshot` & `read_image` memakai python-magic untuk memastikan clipboard/screenshot benar-benar PNG/JPEG sebelum diproses; fallback ke ekstensi bila magic tak ada (tidak wajib power).

**Files:**
- Modify: `src/dhybrid/tools/vision.py` (fungsi `_is_image_bytes`)
- Test: `tests/unit/test_vision_mime.py`

**Step 1: Test gagal**

```python
# tests/unit/test_vision_mime.py
from dhybrid.tools import vision


def test_is_image_png_bytes():
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
    assert vision._is_image_bytes(png) is True


def test_is_image_rejects_text_bytes():
    assert vision._is_image_bytes(b"not an image at all") is False
```

**Step 2:** FAIL. **Step 3:**

```python
# di vision.py
def _is_image_bytes(data: bytes) -> bool:
    if data[:8] == b"\x89PNG\r\n\x1a\n" or data[:2] == b"\xff\xd8":
        return True  # magic PNG/JPEG langsung, tanpa dependency
    try:
        import magic  # python-magic (extra power)

        return (magic.from_buffer(data, mime=True) or "").startswith("image/")
    except (ImportError, Exception):  # noqa: BLE001
        return False
```

**Step 4:** PASS. **Step 5: Commit:** `feat: deteksi MIME image di vision — magic bytes + python-magic opsional`

---

## Bagian B — Auto-Skill Lebih Banyak & Lebih Cerdas

### Task 9: Skill dari Q&A berulang (recurring knowledge skill)

**Objective:** Pertanyaan yang sama/jenis sama ditanyakan ≥2x dalam sesi → simpan sebagai **skill pengetahuan** (tanpa syarat file dibuat). Ini menutup gap: sekarang Q&A tidak pernah jadi skill (`auto_skill_worthwhile` butuh bukti file).

**Files:**
- Modify: `src/dhybrid/session/context.py` (track `qa_history`)
- Modify: `src/dhybrid/ui/repl.py` (`_auto_learn_skill` + deteksi berulang)
- Modify: `src/dhybrid/skills/loader.py` (`build_skill_md` param `kind="task"|"knowledge"`)
- Test: `tests/unit/test_auto_skill_qa.py`

**Step 1: Test gagal**

```python
# tests/unit/test_auto_skill_qa.py
from dhybrid.skills.loader import build_skill_md, auto_skill_worthwhile
from dhybrid.ui.repl import _is_repeated_question_prompt


def test_qa_repeat_detection():
    assert _is_repeated_question_prompt("apa itu laravel", ["apa itu laravel?"]) is True
    assert _is_repeated_question_prompt("buat web", ["apa itu laravel?"]) is False


def test_knowledge_skill_md():
    md = build_skill_md("apa-itu-laravel", "tentang laravel", "apa itu laravel?", ["web_search"], "Laravel = framework PHP.", kind="knowledge")
    assert "Laravel" in md and "Tujuan" in md
```

**Step 2:** FAIL. **Step 3:**

```python
# loader.py — build_skill_md tambah param kind
def build_skill_md(name, description, goal, tools_used, result, steps=None, kind="task"):
    ...
    if kind == "knowledge":
        parts.append(f"**Jawaban dari sesi nyata:**\n\n{result[:400]}\n")
    ...

# repl.py — deteksi Q&A berulang (rapidfuzz ratio, sudah jadi dep)
from rapidfuzz import fuzz

def _is_repeated_question_prompt(prompt: str, history: list[str], thresh: float = 0.85) -> bool:
    p = prompt.lower().strip()
    return any(fuzz.ratio(p, h.lower()) >= thresh * 100 for h in history[-6:])

# context.py — di SessionContext.__init__ tambah:
self.qa_history: list[str] = []

# repl.py _run_one setelah run:
if not auto_skill_worthwhile(...):
    # jalur knowledge: prompt bertanya & sudah pernah ditanyakan
    if _is_repeated_question_prompt(raw, ctx.qa_history):
        name = slugify(raw)
        if name not in TRIVIAL_SLUGS and not any(s.name == name for s in ctx.skills):
            md = build_skill_md(name, desc, raw, tools_used, final, kind="knowledge")
            tulis ke <workspace>/skills/<name>/SKILL.md
    ctx.qa_history.append(raw)
```

**Step 4:** PASS. **Step 5: Commit:** `feat: auto-skill pengetahuan dari Q&A berulang (rapidfuzz ≥85%)`

---

### Task 10: Update skill lama yang terbukti lebih lengkap

**Objective:** Sekarang skill dengan nama sama di-skip selamanya (`if any(s.name == name ...): return`). Ubah: sesi baru yang menghasilkan LEBIH BANYAK langkah/tool dari skill lama → timpa + catat di body `(diperbarui dari sesi ...)`. Aman: tetap skip bila skill lama lebih lengkap.

**Files:**
- Modify: `src/dhybrid/ui/repl.py:450-452`
- Test: `tests/unit/test_auto_skill_update.py`

**Step 1: Test gagal**

```python
# tests/unit/test_auto_skill_update.py
from dhybrid.ui.repl import _should_update_skill


def test_update_when_new_richer():
    old = "1. pakai tool `write_file`"
    new = "1. pakai tool `terminal`\n2. pakai tool `write_file`\n3. pakai tool `run_tests`"
    assert _should_update_skill(old, new) is True


def test_no_update_when_old_richer():
    old = "1. a\n2. b\n3. c"
    new = "1. a"
    assert _should_update_skill(old, new) is False
```

**Step 2:** FAIL. **Step 3:**

```python
def _should_update_skill(old_steps: str, new_steps: str) -> bool:
    return len(new_steps.strip().splitlines()) > len(old_steps.strip().splitlines()) + 1

# di _auto_learn_skill:
existing = next((s for s in ctx.skills if s.name == name), None)
if existing and not _should_update_skill(existing.body or "", md):
    return
if existing:
    md += f"\n*(diperbarui dari sesi nyata — langkah lebih lengkap)*"
```

**Step 4:** PASS. **Step 5: Commit:** `feat: auto-skill update — sesi lebih lengkap menimpa skill lama`

---

### Task 11: Digest kandidat skill di akhir sesi (pilihan bernomor)

**Objective:** Setelah N run (mis. ≥5) dalam satu sesi REPL, tampilkan daftar kandidat skill yang layak (sudah lolos `auto_skill_worthwhile`) tapi belum sempat disimpan otomatis (mis. karena prompt tanpa kata kunci), dengan pilihan bernomor: `1..n` simpan, `Enter` simpan semua, `0`/`skip` lewati. Memakai pola clarify (tanpa tool clarify — cukup print + input, sticky flag `skill_digest_shown`).

**Files:**
- Modify: `src/dhybrid/ui/repl.py` (fungsi `_maybe_skill_digest`)
- Modify: `src/dhybrid/session/context.py` (`skill_candidates` + `skill_digest_shown`)
- Test: `tests/unit/test_skill_digest.py`

**Step 1: Test gagal**

```python
# tests/unit/test_skill_digest.py
from dhybrid.ui.repl import _maybe_skill_digest


def test_digest_offers_candidates(tmp_path, monkeypatch, capsys):
    ctx = _make_ctx(tmp_path, monkeypatch)  # pola test_repl_clarify
    ctx.steps = 6  # ≥5 run
    ctx.skill_candidates = ["buat-login", "setup-docker"]
    monkeypatch.setattr("builtins.input", lambda *a: "1")
    _maybe_skill_digest(ctx)
    out = capsys.readouterr().out
    assert "buat-login" in out and "skill" in out.lower()
    assert ctx.skill_digest_shown is True


def test_digest_skips_when_few_runs(tmp_path, monkeypatch, capsys):
    ctx = _make_ctx(tmp_path, monkeypatch)
    ctx.steps = 2
    _maybe_skill_digest(ctx)
    assert capsys.readouterr().out == ""
```

**Step 2:** FAIL. **Step 3:**

```python
def _maybe_skill_digest(ctx) -> None:
    if ctx.skill_digest_shown or ctx.steps < 5 or not ctx.skill_candidates:
        return
    ctx.skill_digest_shown = True
    print(style("\n💡 Beberapa task sukses bisa jadi skill reusable:", "1;33"))
    for i, c in enumerate(ctx.skill_candidates, 1):
        print(f"   {i}. {c}")
    print("   (ketik nomor, Enter = simpan semua, 0 = skip)")
    ans = input("> ").strip().lower()
    picked = ctx.skill_candidates if (not ans or ans in ("lanjutkan", "l", "ya", "y")) else (
        [ctx.skill_candidates[int(ans) - 1]] if ans.isdigit() and 1 <= int(ans) <= len(ctx.skill_candidates) else []
    )
    for c in picked:
        _save_candidate_skill(ctx, c)  # panggil build_skill_md + tulis file
    if picked:
        print(style(f"  [skill tersimpan] {', '.join(picked)}", "90"))
```

Dipanggil di akhir loop REPL setelah `_auto_learn_skill`. Kandidat diisi `_auto_learn_skill` saat `slugify` gagal memberi nama bermakna tapi task nyata (masuk `ctx.skill_candidates` dengan nama deskriptif dari tool combo).

**Step 4:** PASS. **Step 5: Commit:** `feat: digest kandidat skill akhir sesi — simpan bernomor / Enter semua / skip`

---

### Task 12: Saran skill saat fallback `general` dipakai terus

**Objective:** Fallback `general` dipakai ≥3x dalam sesi (tanpa skill spesifik cocok) → tampilkan saran sekali: "Banyak promptmu tak tertangkap skill spesifik. Mau kubuatkan skill untuk pola ini? (ketik nama / Enter skip)". Ini "lebih banyak otomatis skill" dari arah deteksi celah.

**Files:**
- Modify: `src/dhybrid/ui/repl.py` (hitung fallback di `_run_one` + saran)
- Modify: `src/dhybrid/session/context.py` (`fallback_uses` counter)
- Test: `tests/unit/test_fallback_suggestion.py`

**Step 1: Test gagal**

```python
# tests/unit/test_fallback_suggestion.py
from dhybrid.ui.repl import _maybe_suggest_skill


def test_suggest_after_3_fallback(tmp_path, monkeypatch, capsys):
    ctx = _make_ctx(tmp_path, monkeypatch)
    ctx.fallback_uses = 3
    monkeypatch.setattr("builtins.input", lambda *a: "analisis-log")
    _maybe_suggest_skill(ctx, "tolong analisis log error ini")
    out = capsys.readouterr().out
    assert "skill" in out.lower()
    assert (tmp_path / "skills" / "analisis-log" / "SKILL.md").exists()


def test_no_suggest_below_threshold(tmp_path, monkeypatch, capsys):
    ctx = _make_ctx(tmp_path, monkeypatch)
    ctx.fallback_uses = 2
    _maybe_suggest_skill(ctx, "halo")
    assert capsys.readouterr().out == ""
```

**Step 2:** FAIL. **Step 3:**

```python
def _maybe_suggest_skill(ctx, raw: str) -> None:
    if ctx.fallback_uses < 3 or getattr(ctx, "skill_suggested", False):
        return
    ctx.skill_suggested = True
    print(style("\n💡 Banyak prompt belum tertangkap skill spesifik (fallback general ≥3x).", "1;33"))
    name = slugify(raw)
    if name and name not in TRIVIAL_SLUGS:
        print(f"   Ketik nama skill untuk menyimpan pola ini (mis. '{name}'), atau Enter untuk skip.")
        ans = input("> ").strip().lower()
        if ans and ans not in ("skip", "tidak", "no", "0"):
            simpan skill dengan nama ans (build_skill_md kind='task', tools dari tool_count sesi)
```

Increment `ctx.fallback_uses` di `_run_one` setiap kali feedback skill menampilkan `(fallback)`.

**Step 4:** PASS. **Step 5: Commit:** `feat: saran buat skill saat fallback general ≥3x`

---

### Task 13: Validasi & perbaikan skill (lint frontmatter)

**Objective:** Skill rusak (frontmatter tanpa `name`/`description`, YAML invalid) tidak boleh meng-crash `list_skills` atau meng-inject sampah. Loader: tandai rusak, skip inject, dan print peringatan sekali. Ini menjaga kualitas saat auto-skill makin agresif.

**Files:**
- Modify: `src/dhybrid/skills/loader.py` (`list_skills` → validasi)
- Test: `tests/unit/test_skill_lint.py`

**Step 1: Test gagal**

```python
# tests/unit/test_skill_lint.py
from dhybrid.skills.loader import list_skills


def test_list_skills_skips_broken(tmp_path):
    good = tmp_path / "good" / "SKILL.md"
    good.parent.mkdir()
    good.write_text("---\nname: good\ndescription: ok\n---\nbody")
    bad = tmp_path / "bad" / "SKILL.md"
    bad.parent.mkdir()
    bad.write_text("---\nname: [unclosed\n---\nrusak")
    skills = list_skills(tmp_path)
    names = [s.name for s in skills]
    assert "good" in names and "bad" not in names
```

**Step 2:** FAIL (sekarang mungkin crash atau ikut). **Step 3:** bungkus parse frontmatter dalam try/except; `Skill` dengan `valid=False` diskip di `select_skills`/`inject_skills`. **Step 4:** PASS. **Step 5: Commit:** `feat: lint skill — frontmatter rusak di-skip tanpa crash`

---

### Task 14: Rilis 0.9.0 — gate, smoke, push, produksi

**Objective:** Versi sinkron, gate penuh, smoke PTY, rilis ke GitHub, update produksi.

**Files:**
- Modify: `pyproject.toml` (`version = "0.9.0"`), `src/dhybrid/__init__.py`, `CHANGELOG.md` (blok `[0.9.0]`), `README.md` (bullet power-up + auto-skill), `scripts/smoke_clarify.py` (bila perlu: tambah cek tool power terdaftar)
- Install extra power di venv dev & produksi: `pip install -e '.[vision,e2e,power]'`

**Langkah:**
1. `ruff check src tests scripts` → 0 error.
2. `python3 -m pytest --cov=dhybrid --cov-fail-under=65 -q` → semua lulus, coverage ≥65%.
3. Smoke: `python3 scripts/smoke_clarify.py` → `[SMOKE OK]`.
4. Verifikasi tool power di REPL sungguhan (PTY): prompt `cek kesehatan sistem` → agent pakai `sys_info`; `analisis data.csv pakai sql` → `data_query`.
5. `git add -A && git commit -m "feat: rilis 0.9.0 — power tools (psutil/jinja2/duckdb/pypdf/openpyxl/magic) + auto-skill lebih cerdas (Q&A, update, digest, saran)"`.
6. `git push origin main`; `cd ~/.dhybrid-agent && git pull && pip install -e '.[vision,e2e,power]'`; verifikasi `python3 -c "import dhybrid; print(dhybrid.__version__)"` = 0.9.0.
7. Lapor ke user + demo singkat.

---

## Files yang Akan Berubah (ringkasan)

| File | Aksi |
|---|---|
| `pyproject.toml` | extra `power` + versi 0.9.0 |
| `src/dhybrid/__init__.py` | versi 0.9.0 |
| `config/default.yaml` | allowlist +5 tool power (→ 36) |
| `src/dhybrid/tools/__init__.py` | daftarkan `soft` |
| `src/dhybrid/tools/soft.py` | BARU — soft-register |
| `src/dhybrid/tools/power_sys.py` | BARU — psutil |
| `src/dhybrid/tools/power_scaffold.py` | BARU — jinja2 |
| `src/dhybrid/tools/power_data.py` | BARU — duckdb |
| `src/dhybrid/tools/power_pdf.py` | BARU — pypdf |
| `src/dhybrid/tools/power_xlsx.py` | BARU — openpyxl |
| `src/dhybrid/tools/vision.py` | MIME detect |
| `src/dhybrid/skills/loader.py` | `build_skill_md(kind=)`, lint skill |
| `src/dhybrid/session/context.py` | `qa_history`, `skill_candidates`, `skill_digest_shown`, `fallback_uses`, `skill_suggested` |
| `src/dhybrid/ui/repl.py` | knowledge skill, update skill, digest, saran fallback |
| `CHANGELOG.md`, `README.md` | rilis 0.9.0 |
| `tests/unit/test_soft_register.py`, `test_build_tools_power.py`, `test_power_sys.py`, `test_power_scaffold.py`, `test_power_data.py`, `test_power_pdf.py`, `test_power_xlsx.py`, `test_vision_mime.py`, `test_auto_skill_qa.py`, `test_auto_skill_update.py`, `test_skill_digest.py`, `test_fallback_suggestion.py`, `test_skill_lint.py` | BARU (13 file test) |

## Test / Validasi

- Per task: TDD (test gagal → implementasi → lulus → commit).
- Gate akhir (Task 14): ruff 0, pytest penuh + coverage ≥65%, smoke PTY, demo REPL sungguhan untuk `sys_info` & `data_query`, versi sinkron, push, produksi.

## Risiko, Tradeoff, Pertanyaan Terbuka

- **Bobot dependency**: `duckdb` ~20MB wheel, `psutil`/`jinja2`/`pypdf`/`openpyxl` ringan. Semua di extra `power` — install default tetap ringan (filosofi hemat). Tanya user saat eksekusi: **install `power` sebagai extra (default ON di produksi) atau wajib?** Rekomendasi: extra + auto-install di produksi.
- **Spec tool yang belum terpasang**: keputusan di Task 1 — spec tetap tampil dengan keterangan "butuh package" (model tahu tool ada; kalau dipanggil → pesan install). Alternatif: sembunyikan total. Tradeoff: spec tampil = model tidak bingung kenapa tool hilang; tapi sedikit token ekstra.
- **Knowledge skill** (Task 9) bisa menghasilkan skill "sampah" bila pertanyaan umum ("apa itu x") sering diulang — mitigasi: threshold rapidfuzz 0.85 + hanya sesi yang jawabannya substantif (final ≥100 char) + tetap kena TRIVIAL_SLUGS.
- **Update skill** (Task 10) berisiko menimpa skill buatan tangan user — mitigasi: hanya update skill yang `description` mengandung "skill otomatis" (tanda lahir dari auto-skill), skill user manual tidak pernah ditimpa.
- **Digest akhir sesi** (Task 11) menyela alur REPL — mitigasi: muncul maksimal 1x per sesi (sticky flag), hanya saat ≥5 run, dan bisa di-skip total via `skills.auto_learn: false` (sudah ada).
- **Saran fallback** (Task 12) bisa mengganggu — mitigasi: sekali per sesi, hanya ≥3 fallback, jawaban default = skip.
- **duckdb** di sandbox terminal: `read_csv_auto` bisa baca file apa pun yang bisa diakses agent — sama dengan hak terminal, bukan risiko baru. Query read-only di-enforce di kode (bukan hanya prompt).
- **Jinja2 template dir**: template bisa berisi ekspresi Python — `StrictUndefined` + traversal guard + hanya membaca dari dir yang eksplisit user berikan.
- Urutan task B (9-13) independen satu sama lain; bisa dikerjakan paralel setelah Task 1-2 selesai (infrastruktur A).

---

## Ringkasan untuk User

- **A. Power pip packages** (extra `power`, 6 package → 5 tool baru + MIME detect): `sys_info` (psutil), `scaffold` (jinja2), `data_query` (duckdb SQL ke CSV/JSONL), `pdf_ops` (pypdf), `xlsx_edit` (openpyxl). Semua soft-register: tanpa package → tool tetap aman, pesan install ramah.
- **B. Auto-skill lebih banyak**: skill pengetahuan dari Q&A berulang, update skill lama yang lebih lengkap, digest kandidat skill di akhir sesi (pilihan bernomor), saran skill saat fallback general ≥3x, + lint skill anti-rusak.
- Rilis **0.9.0** setelah semua task hijau.
