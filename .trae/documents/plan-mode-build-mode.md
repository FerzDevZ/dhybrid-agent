# Plan: Plan Mode / Build Mode + Akses Kontrol Eskalasi

## Ringkasan
Tiga fitur keamanan/UX untuk `dhybrid-agent` agar workfaw lebih aman & terkontrol:

1. **Mode kerja Plan / Build** (`mode: plan|build`) — di toggle via **Tab** di REPL (prompt_toolkit), via `/plan` `/build` (slash-command), atau `dhybrid --mode plan`.
   - **Plan Mode**: agent hanya boleh OBSERVASI. Terminal dibatasi ke perintah read-only (`ls cat grep strings watch` dst, tanpa metachar shell). Tool mutasi (write_file, apply_patch, git_commit, dsb) diblokir lewat registry. Sistem prompt menyuruh agent untuk membuat temuan + rencana, bukan mengubah file.
   - **Build Mode**: eksekusi penuh diizinkan. Instruksi prompt: pastikan ada Issue (buat via tool `repo_issue` bila belum ada), kava, commit, lalu buat Issue (PR) via `repo_pr`, laporkan. PR/Issue dibuat ke GitHub/GitLab (deteksi dari `git remote -v`).
2. **Eskalasi harus izin user**: sebelum model auto-escalate (upgrade ke model lebih kuat) — baik jalur kualitas, error API, maupun tool-error → REPL bertanya dulu (`y/N`); **tolak = jangan eskalasi**. Default non-interaktif = tolak (fail-safe), env `DHYBRID_ESCALESC=AUTO` untuk mengizinkan.

Tidak menyentuh: failover provider (penyedia error → backup , untuk kontinuitas), dan cheapen (budget → model kecil) — keduanya bukan "eskalasi".

## State Saat Ini (hasil eksplorasi)

| Bagian | Lokasi | Kondisi |
|---|---|---|
| REPL prompt_toolkit | `src/dhybrid/ui/repl.py` | `PromptSession` tanpa keybinding; Tab = autocompleter default |
| Slash command | `src/dhybrid/ui/commands.py` | `handle_command` dengan map `/quit /help /settings ...` — bisa ditambah |
| Gate perintah terminal | `src/dhybrid/tools/terminal.py` | `confirm_fn` (repl set), `is_dangerous` dari `tools/security.py`; tanpa "readonly" |
| Tool registry | `src/dhybrid/tools/registry.py` | `ToolRegistry.execute` dengan `allowlist`; JIT render; tanpa flag readonly |
| Route client & eskalasi | `src/dhybrid/agent/loop/agent_loop.py` | 3 titik: `except` → `escalate_for_errors` (L656), quality → `escalate_for_quality` (L748), tool-error → `_pick_client(force="big")` (L860) |
| Policy eskalasi | `src/dhybrid/agent/loop/escalation_policy.py` | `EscalationConfig` + `_do_escalate`; tanpa gate user |
| Config | `src/dhybrid/config.py` + `config/default.yaml` | tanpa field mode/workflow |
| System prompt | `src/dhybrid/session/context.py` (`SessionContext.__init__`) | `BASE_PROMPT` + memory block; tanpa blok mode |
| CLI | `src/dhybrid/cli.py` | `main()` + subparser; `--yes`; `cmd_run` non-interaktif |
| Tools builder | `src/dhybrid/tools/__init__.py` | `build_tools(cfg, ...)`; dari sana semua tools diregistrasi |

## Perubahan yang Diusulkan

### 1. `src/dhybrid/config.py` + `config/default.yaml`
- Tambah field `Config.mode: str = "build"` dan `Config.workflow: dict` default `{"auto_issue": true, "auto_pr": true, "escalation": "ask"}` (`_apply_dict` otomatis karena dict).
- `default.yaml`: `mode: build` + `workflow: {auto_issue: true, auto_pr: true, escalation: ask}`.
- Tidak mengubah `ModelRegistry`.

### 2. `src/dhybrid/tools/terminal.py` — gerbang read-only
- Module `readonly: bool = False` (di-set REPL saat mode=plan).
- Fungsi `is_readonly_command(command) -> bool`:
  - pecah token (`shlex.split`), ambil binary pertama.
  - Allowlist `READONLY_BIN = {ls, cat, grep, rg, find, strings, watch, head, tail, wc, file, stat, which, whoami, date, env, git}` + toolchain read-only (`pytest`? — **tidak**, pytest mengeksekusi kode; gantu `pip show`? — tidak: tetap blokir).
  - `git` diizinkan hanya subcommand: `{status,diff,log,show,branch,remote,config,ls-files,ls-tree,rev-parse, grep}`.
  - Tolak bila ada metachar shell: `; | & && < > >> ( ) ` `` ` `` `$(` `$VAR`, `{`, `}`.
  - `watch ls -l` — izinkan (watch + read-only cmd).
  - Kecuali line kosong.
- `run_command`: `if readonly and not is_readonly_command: return "ERROR: Plan Mode — perintah mutasi diblok (observasi saja)"`. Letakkan sebelum `is_dangerous`.

### 3. `src/dhybrid/tools/registry.py` — gate tool readonly
- `ToolRegistry.__init__` tambah `self.readonly: bool = False`.
- Konstanta `READONLY_ALLOWED_TOOLS = frozenset({terminal, read_file, grep, find_files, web_fetch, web_search, http_request, sys_info, git_status, git_diff, git_log, code_map, code_map_multi, dep_graph, semantic_search, todo_list, skills, list_skills, poll_bg, memory_get, memory_search, mem_search, mem_index, episodic_recent, read_document, read_image, data_query, repo_issues})`.
- `execute()`: `if self.readonly and name not in READONLY_ALLOWED_TOOLS: return "ERROR: Mode Plan — tool '{name}' adalah mutasi; ganti ke Mode Build (Tab)."`
- `terminal` tetap boleh: yakapan internal gateway read-only-nya.

### 4. Repo tools baru — `src/dhybrid/tools/repo.py`
Fungsi + register(dengan `max_chars`):
- `_detect_forge()`: baca `git remote get-url origin` → `github`/`gitlab`/`None`; parse `owner/repo` (host apa pun).
- `repo_issues(limit=10)` — READ: `GET /repos/{o}/{r}/issues?state=open` (GitHub) / `GET /projects/{urlencoded}/issues?state=opened` (GitLab). Token: `GITHUB_TOKEN` | `GITLAB_TOKEN`. Return ringkasan `#id title` per baris.
- `repo_issue(title, body)` — POST create issue (GitHub `/issues`, GitLab `/issues`).
- `repo_pr(title, body)` — POST PR/MR: GitHub `/pulls` (head=branch saat ini, base=branch default dari repo), GitLab `/merge_requests`.
- Tiap create-butuh token; bila tak ada token → `ERROR: set GITHUB_TOKEN/GITLAB_TOKEN`.
- `repo.py` di daftarkan di `tools/__init__.py` `build_tools` (termasuk hanya jika repo git / saat tool baru). `repo_issue/repo_pr` MUTASI → otomatis terblokix di Plan Mode via registry.readonly. `repo_issues` masuk `READONLY_ALLOWED_TOOLS`.

### 5. `src/dhybrid/agent/loop/escalation_policy.py` — gate izin
- `EscalationConfig` + `confirm_fn: Callable[[str], bool] | None`.
- `_do_escalate(...)`: sebelum eksekusi switch, `if self.config.confirm_fn is not None and not self.config.confirm_fn(reason): return EscalationResult(escalated=False, new_client=None, ...reason="user menolak eskalasi")`.
- None = mode lama (otomatis) — biar unit test existing (yang pakai `EscalationPolicy` config langsung tanpa confirm) tetap hijau.

### 6. `src/dhybrid/agent/loop/agent_loop.py`
- `LoopConfig` + `escalation_confirm_fn: callable | None = None`.
- `__init__`: teruskan ke `EscalationConfig(confirm_fn=self.cfg.escalation_confirm_fn)`.
- helper `_escalate_permitted(reason) -> bool` (memanggil `cfg.escalation_confirm_fn` bila ada).
- Jalur ketiga (tool-error → `_pick_client(force="big")` L860): tambahkan `if not self._escalation_permitted("terlalu banyak error tool"): block dilewati` — jangan `result.escalated=True`.
- Jalur kualitas & error: sudah lewat `escalation_policy` → ya, policy yang menegakkan gate.
- Jangan ubah `_pick_client` failover provider (bukan eskalasi kuat).

### 7. `src/dhybrid/ui/repl.py` — Tab, prompt mode, wiring
- `ctx.mode` default dari `cfg.mode`.
- `_repl_prompt`: warna/label mode — `"[plan] dhybrid> "` (kuning) vs `"[build] dhybrid> "` (hijau) — pakai `FormattedText`/`style`.
- Keybinding (prompt_toolkit `KeyBindings`, dipass ke `pt_session.prompt(key_bindings=kb)` ... kalau signature default layak; Auto id:
  ```python
  @kb.add("tab")
  def _(event):
      buf = app_current_buffer
      if not buf.text.strip():
          _toggle_mode(ctx)   # plan ⇄ build
          event.app.invalidate()
      else:
          buf.complete_next()  # bawa autocomplete tetap berfungsi saat mengetik
  ```
- `_toggle_mode(ctx)`: switch `ctx.mode`; set `ctx.tools.readonly = (ctx.mode == "plan")`; set `terminal.readonly` sejak plan (import `dhybrid.tools.terminal`); cetak 1 baris status mode.
- init repl: `ctx.tools.readonly = ctx.mode == "plan"`; terminal.readonly sama.
- confirm_fn eskalasi di `run_agent` (repl): 
  ```python
  from dhybrid.agent.loop import LoopConfig
  loop_cfg = LoopConfig(..., escalation_confirm_fn=_ask_escalation)
  ```
  `_ask_escalation(reason)` → `input(f"⚠ model minta eskalasi ke model lebih kuat ({reason})\nIzinkan? (y/N) ") ...` — `KeyboardInterrupt/EOF → False`. Tolak bila non-interaktif/config `workflow.escalation != "ask"`.
  - Saat `ctx.yes_mode` atau `cfg.mode` workflow `escalation == "deny"` → `None` (auto-deny via caller `_escalation_permitted` default? Care: None berarti "no gate"=auto. Di REPL selalu pasang: bila deny mode → fungsi yang return False selalu).

### 8. `src/dhybrid/session/context.py` — mode instruksi di system prompt
- Setelah `memory_block`, tambah blok mode:
  ```python
  if self.mode == "plan":
      MODE_BLOCK = "MODE PLAN: hanya observasi. Tool mutasi (write/terminal build/git commit/repo_issue/repo_pr) diblokir oleh sistem. Perintah terminal hanya ls, cat, grep, strings, watch, dsb read-only. Jangan edit file. Akhiri dengan temuan + rencana eksekusi yang akan dilakukan di Mode Build."
  else:
      MODE_BLOCK = ("MODE BUILD: eksekusi penuh diizinkan. Kebijakan: (1) pastikan proyek mencatat pekerjaan ini sebagai Issue (repo_issue) bila belum ada; (2) kerjakan; (3) verifikasi; (4) commit; (5) buat PR via repo_pr bila fitur workflow.auto_pr aktif; (6) lapor.")
  self.system_prompt = build_system_prompt(...) + memory_block + "\n\n" + MODE_BLOCK
  ```
  - `auto_issue` diambil dari `cfg.workflow` .
  - Tambahkan juga parameter/setter: `ctx.set_mode(mode)` (mengubah `self.mode` + `self.system_prompt` di-rebuild? — rebuild berat; cukup simpan `self.mode`, pemanggil REPL menambah blok tiap run di `run_agent`):
  Actually simplest: `run_agent(ctx, prompt)` appends mode hint ke `prompt`? Tetap harus modify prompt: `prompt = f"[{ctx.mode.upper()}]\n{prompt}"`? Ragap: itu mengotori konteks. Lebih elegan: `LooSystemPrompt` — AgentLoop menerima `system_prompt` (dari `ctx.system_prompt`). `repl.run_agent` bisa pre-append blok:
  ```python
  base = ctx.system_prompt
  delta = _MODE_BLOCKS[ctx.mode]
  sys_prompt = base + "\n\n" + delta if delta not in base else base
  result = loop.run(prompt, sys_prompt, ...)
  ```
  Implement the mode-block concat di `repl.run_agent` / `cli.cmd_run` (satu helper `dhybrid.mode.instruct(ctx.mode, cfg)`) daripada menyentuh `SessionContext` — minim diff, mode bisa dipindah tanpa rebuild prompt.

  Pilih: helper baru `src/dhybrid/mode.py`:
  - `MODE_LABEL`, `mode_system_block(mode, workflow) -> str`, `apply_mode(ctx, mode=None)` (set ctx.mode + `ctx.tools.readonly` + `terminal.readonly`).
  - `run_agent` panggil `mode_system_block(ctx.mode, ctx.cfg.workflow)` dan gabung ke system_prompt sekali per run.

### 8. `src/dhybrid/ui/commands.py`
- `/plan` → `mode: plan`; `/plan` (restart); `/build`/`/build — mode: build`; `/mode` (toggle/show). (nama command: `/plan` `/ build` — avoid `?` `?` di kata kunci? Sederhana)
- Update `print_help()` & banner menu di `repl.show_welcome`.

### 9. `src/dhybrid/cli.py`
- `--mode plan|build` (global + di conn subparser repl/run) → `_build_context` `args.mode` → `ctx.mode` passaplikasi.
- `cmd_run`: setelah context: `apply_mode(ctx, args.mode)`; escalation_confirm_fn: `None` bila tty valid + stdin askf? — SIMPEL: non-interact → `fallback = workflow.escalation`; `"ask"`+ tty → ask; else deny. implement `_confirm_or_deny`:

### 10. Tests
- `tests/unit/test_plan_mode.py` (baru):
  - `is_readonly_command`: `ls -la` ✓; `cat a.txt` ✓; `strings file` ✓; `watch -n1 ss` ✓; `git status` ✓; deny: `rm -rf x`, `echo hi > f`, `a && b`, `cat a \`r m\``, `ls | head` (pipa = deny), `git push`, `npm install`.
  - registry readonly: set `reg.readonly=True` → `execute("write_file")` error & `execute("read_file")` ok.
  - loop escalation gate: `LoopConfig(escalation_confirm_fn=lambda r: False)` + script error → Result.escalated False; `lambda r: True` → True.
  - policy confirm: confirm_fn False → escalate result false.
  - mode block: `mode_system_block("plan",…)` contains  "MODE PLAN"; build contains "repo_pr".
- `tests/unit/test_repo_tools.py` (baru): pgmock `httpx.MockTransport` untuk URL GitHub/GitLab create issue/PR; no repo → error; no token → error.
Cek juga `tests/e2e/test_agent_loop.py` (escalation keyed — gate default None tetap auto) — semua tetap hijau.

## Keputusan & Asumsi
- Tab = `plan` ⇄ `build` SAAT buffer kosong; buffer berisi → Tab tetap autocomplete (tidak mengguntungkan UX lama).
- Non-interaktif (pipa / `dhybrid run`): eskalasi auto-toak (fail-safe) kecuali `workflow.escalation: auto` di config.
- Failover provider (penyedia sehat) dan cheapen (budget) tetap otomatis—bukan eskalasi.
- `repo_issue/repo_pr` butuh token env (`GITHUB_TOKEN`/`GITLAB_TOKEN`); tanpa token → error jelas. Tidak ada fitur MCP/graph API — cukup dasar (cocok untuk versi ini).
- Mode ada per-sesi REPL; config `mode` untuk default startup.

## Verifikasi
1. `ruff check src tests`
2. `pytest tests/unit/test_plan_mode.py tests/unit/test_repo_tools.py tests/e2e/test_agent_loop.py -q` — hijau.
3. Full suite `pytest -q` — 670+ hijau (tidak ada regresi).
4. Manual sanity (opsional): `dhybrid --mode plan` → Tab toggle, coba `buat file` → tool di blokir; `/build` → eksekusi normal.