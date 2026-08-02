# dhybrid-agent v0.3.0 — Implementation Plan (F1-F6)

> **Untuk Hermes:** gunakan skill `subagent-driven-development` untuk mengimplementasikan plan ini task-by-task.

**Goal:** Implementasi 6 fitur v0.3.0 "Praktis & Stabil": model persisten (F1), doctor (F2), self-update (F3), CI (F4), shell completion (F5), REPL history (F6) — semuanya TDD, commit kecil, verifikasi live via route zen gratis.

**Architecture:** Fitur ops baru di lapisan `src/dhybrid/session/` (userconfig) + modul baru `doctor.py`, `updater.py`; distribusi di `.github/workflows/` + `scripts/`; UI polish di `ui/repl.py`. Tidak mengubah arsitektur inti agent loop.

**Tech Stack:** Python 3.12 stdlib (argparse, sqlite3, subprocess, readline) + pyyaml (sudah ada) + GitHub Actions. TANPA dependensi baru untuk F1-F3, F6; F5 murni skrip shell.

**Kondisi awal:** HEAD `c1bc218`, 81 test hijau, ruff clean. Default model = zen `deepseek-v4-flash-free` (gratis, tanpa API key) → jalur verifikasi live tanpa biaya.

---

## FASE A — F1: Pilihan Model Persisten

### Task A1: Modul UserConfig (load/save `~/.dhybrid/config.yaml`)

**Objective:** API kecil untuk membaca & menulis override config user, terpisah dari config bawaan.

**Files:**
- Create: `src/dhybrid/session/userconfig.py`
- Test: `tests/unit/test_userconfig.py`

**Step 1: tulis test gagal** `tests/unit/test_userconfig.py`:
```python
from dhybrid.session import userconfig

def test_load_empty_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(userconfig, "user_config_path", lambda: tmp_path / "config.yaml")
    assert userconfig.load_user_config() == {}

def test_save_and_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(userconfig, "user_config_path", lambda: tmp_path / "config.yaml")
    userconfig.save_model_choice({"provider": "openai", "model": "x-model", "base_url": None, "api_key_env": "K"})
    data = userconfig.load_user_config()
    assert data["model"]["model"] == "x-model"
    assert tmp_path.joinpath("config.yaml").exists()
```

**Step 2: run → FAIL** — `pytest tests/unit/test_userconfig.py -v` → `ModuleNotFoundError`.

**Step 3: implementasi** `src/dhybrid/session/userconfig.py`:
```python
"""User config — override pilihan user di ~/.dhybrid/config.yaml (persisten)."""
from __future__ import annotations

from pathlib import Path

import yaml


def user_config_path() -> Path:
    return Path.home() / ".dhybrid" / "config.yaml"


def load_user_config() -> dict:
    p = user_config_path()
    if not p.exists():
        return {}
    try:
        data = yaml.safe_load(p.read_text()) or {}
        return data if isinstance(data, dict) else {}
    except yaml.YAMLError:
        return {}


def save_model_choice(cfg) -> None:
    """Simpan pilihan model (terima ModelConfig atau dict)."""
    p = user_config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    data = load_user_config()
    if hasattr(cfg, "provider"):  # ModelConfig
        m = {"provider": cfg.provider, "model": cfg.model,
             "base_url": cfg.base_url, "api_key_env": cfg.api_key_env}
    else:
        m = cfg
    data["model"] = m
    p.write_text(yaml.safe_dump(data, sort_keys=False))
```

**Step 4: run → PASS** — `pytest tests/unit/test_userconfig.py -v` → 2 passed.

**Step 5: commit** — `git add -A && git commit -m "feat: user config persistence module"`

### Task A2: Merge user config ke `Config.load`

**Objective:** `Config.load()` membaca user config dan blok `model:` menimpanya (presets tidak di-override).

**Files:**
- Modify: `src/dhybrid/config.py` (di akhir `load()`, sebelum env override)
- Test: `tests/unit/test_config.py`

**Step 1: test gagal** — tambah:
```python
def test_user_config_overrides_model(tmp_path, monkeypatch):
    import dhybrid.session.userconfig as uc
    monkeypatch.setattr(uc, "user_config_path", lambda: tmp_path / "config.yaml")
    uc.save_model_choice({"provider": "openai", "model": "user-model", "base_url": "http://x/v1", "api_key_env": "K"})
    cfg = Config.load("config/default.yaml")
    assert cfg.model.model == "user-model"
    assert cfg.model.base_url == "http://x/v1"
```
Run → FAIL (`user-model` tidak muncul).

**Step 2: implementasi** — di `config.py` `load()`, setelah blok `presets` dan sebelum env override:
```python
        # user override (~/.dhybrid/config.yaml) — menimpa model bawaan
        from dhybrid.session.userconfig import load_user_config
        user = load_user_config()
        if "model" in user and isinstance(user["model"], dict):
            for k, v in user["model"].items():
                if hasattr(cfg.model, k):
                    setattr(cfg.model, k, v)
```
(import di dalam fungsi → hindari circular import; userconfig hanya import yaml+pathlib.)

**Step 3: run → PASS.**
**Step 4: commit** — `git commit -am "feat: config load merge user overrides"`

### Task A3: Wire persistensi ke `set_model` / `set_small_model`

**Files:**
- Modify: `src/dhybrid/session/context.py:125-152`
- Test: `tests/unit/test_settings.py`

**Step 1: test gagal** — tambah di `test_settings.py`:
```python
def test_set_model_persists(tmp_path, monkeypatch):
    import dhybrid.session.userconfig as uc
    monkeypatch.setattr(uc, "user_config_path", lambda: tmp_path / "config.yaml")
    ctx.set_model("opencode-zen-big")
    data = uc.load_user_config()
    assert data["model"]["model"] == "claude-sonnet-5"
```

**Step 2: implementasi** — di `set_model()`, sebelum `return`:
```python
        from dhybrid.session.userconfig import save_model_choice
        save_model_choice(new_cfg)
        return f"model utama -> {preset} ({new_cfg.model} via {new_cfg.provider}) — tersimpan permanen"
```
Sama untuk `set_small_model` (simpan `cfg` kecil; tambah kunci `small_model: name`):
```python
        from dhybrid.session.userconfig import load_user_config, user_config_path
        data = load_user_config()
        data["small_model"] = name
        user_config_path().write_text(__import__("yaml").safe_dump(data, sort_keys=False))
```

**Step 3: run → PASS** — `pytest tests/unit/test_settings.py -v`.

**Step 4: verifikasi live** (tanpa key):
```bash
dhybrid --model openrouter-big && dhybrid   # menu harus tampil openrouter-big/claude-sonnet-4
```
Expected: baris `model utama : anthropic/claude-sonnet-4 (openai)` di welcome. Lalu reset: hapus `~/.dhybrid/config.yaml`.

**Step 5: commit** — `git commit -am "feat: pilihan model persisten (set_model/set_small_model)"`

---

## FASE B — F2: `dhybrid doctor`

### Task B1: Checker statis (tanpa network)

**Objective:** Fungsi murni per cek: config, model resolve, workspace writable, sqlite writable, python version.

**Files:**
- Create: `src/dhybrid/doctor.py`
- Test: `tests/unit/test_doctor.py`

**Step 1: test gagal** `tests/unit/test_doctor.py`:
```python
from dhybrid.config import Config
from dhybrid.doctor import check_config, check_model_resolves, check_workspace_writable

def test_checks_ok(tmp_path):
    cfg = Config.load("config/default.yaml")
    cfg.workspace = tmp_path
    assert check_config(cfg)[0] is True
    assert check_model_resolves(cfg)[0] is True
    assert check_workspace_writable(cfg)[0] is True

def test_workspace_ro_fails(tmp_path):
    cfg = Config(); cfg.workspace = tmp_path / "no/such/dir"
    assert check_workspace_writable(cfg)[0] is False
```

**Step 2: implementasi** `src/dhybrid/doctor.py` (awal):
```python
"""dhybrid doctor — diagnosa config, key, koneksi, update."""
from __future__ import annotations
from pathlib import Path
import os
from dhybrid.config import Config

def check_config(cfg: Config) -> tuple[bool, str]:
    return True, f"config OK (model: {cfg.model.model})"

def check_model_resolves(cfg: Config) -> tuple[bool, str]:
    from dhybrid.llm.registry import ModelRegistry
    try:
        ModelRegistry(cfg).resolve(cfg.model.model)
        return True, f"model ter-resolve: {cfg.model.model}"
    except Exception as e:  # noqa: BLE001
        return False, f"model gagal resolve: {e}"

def check_workspace_writable(cfg: Config) -> tuple[bool, str]:
    try:
        cfg.workspace.mkdir(parents=True, exist_ok=True)
        probe = cfg.workspace / ".doctor-probe"
        probe.write_text("x"); probe.unlink()
        return True, f"workspace writable: {cfg.workspace}"
    except OSError as e:
        return False, f"workspace tidak writable: {e}"

def check_python() -> tuple[bool, str]:
    import sys
    ok = sys.version_info >= (3, 12)
    return ok, f"python {sys.version.split()[0]} ({'OK' if ok else 'butuh >= 3.12'})"
```

**Step 3: run → PASS.**
**Step 4: commit** — `git commit -am "feat: doctor static checks"`

### Task B2: Checker network + API key status (flag `--offline`)

**Files:**
- Modify: `src/dhybrid/doctor.py`
- Test: `tests/unit/test_doctor.py`

**Step 1: test** (tanpa network nyata — mock `httpx.post`):
```python
def test_key_status(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    cfg = Config.load("config/default.yaml")
    from dhybrid.doctor import key_status
    rows = key_status(cfg)
    assert any("OPENAI" in r and "✗" in r for r in rows)

def test_network_check_ok(monkeypatch):
    import httpx
    def fake_post(url, **kw):
        return httpx.Response(200, json={"object": "list", "data": []}, request=httpx.Request("POST", url))
    monkeypatch.setattr(httpx, "post", fake_post)
    from dhybrid.doctor import check_endpoint
    ok, msg = check_endpoint("https://x/v1", timeout=5)
    assert ok is True
```

**Step 2: implementasi** — tambah:
```python
def key_status(cfg: Config) -> list[str]:
    from dhybrid.ui.commands import PROVIDERS
    rows = []
    for name, env in PROVIDERS:
        mark = "✓" if os.environ.get(env) else "✗"
        rows.append(f"{name}: {mark}")
    return rows

def check_endpoint(base_url: str, timeout: int = 5) -> tuple[bool, str]:
    import httpx
    try:
        r = httpx.get(f"{base_url}/models", timeout=timeout)
        return r.status_code == 200, f"GET {base_url}/models -> HTTP {r.status_code}"
    except Exception as e:  # noqa: BLE001
        return False, f"{base_url}: {type(e).__name__}: {e}"
```

**Step 3: run → PASS.**
**Step 4: commit** — `git commit -am "feat: doctor network + key checks"`

### Task B3: Update check + `run_doctor()` agregator + CLI wiring

**Files:**
- Modify: `src/dhybrid/doctor.py` (tambah `run_doctor(cfg, offline)`), `src/dhybrid/cli.py` (subcommand `doctor`)
- Test: `tests/e2e/test_cli_smoke.py`

**Step 1: implementasi agregator** — `run_doctor` mencetak baris `[✓]/[✗] label — detail` untuk: python, config, model resolve, workspace, 1 endpoint model aktif (skip jika `offline`), key status. Return 0/1.

**Step 2: CLI** — di `main()`:
```python
    doc = sub.add_parser("doctor", help="diagnosa config, key, koneksi, update")
    doc.add_argument("--offline", action="store_true", help="tanpa cek network")
```
handler → `cmd_doctor(args)` → `run_doctor(cfg, args.offline)`.

**Step 3: smoke test** — `pytest tests/e2e/test_cli_smoke.py` tambah:
```python
def test_doctor_runs():
    p = run_cli("--cwd", "/tmp", "doctor", "--offline")
    assert p.returncode in (0, 1)
    assert "python" in p.stdout and "config" in p.stdout
```

**Step 4: verifikasi live** — `dhybrid doctor` → semua baris `[✓]` (default zen tanpa key tetap ✓ koneksi karena gratis).
**Step 5: commit** — `git commit -am "feat: dhybrid doctor"`

---

## FASE C — F3: Self-Update

### Task C1: `updater.py` core

**Files:**
- Create: `src/dhybrid/updater.py`
- Test: `tests/unit/test_updater.py`

**Step 1: test** (mock subprocess):
```python
from dhybrid.updater import update_available, self_update

def test_update_available_true(monkeypatch):
    def fake_run(cmd, **kw):
        class P: returncode = 0
        return P()
    monkeypatch.setattr("subprocess.run", fake_run)
    # bandingkan HEAD != origin/main dengan _git_out mock
    monkeypatch.setattr("dhybrid.updater._git_out", lambda *a: "abc123\n")
    assert update_available() is True
```

**Step 2: implementasi** `src/dhybrid/updater.py`:
```python
"""Self-update — perbarui instalasi dari git remote."""
from __future__ import annotations
import subprocess
from pathlib import Path

def install_dir() -> Path:
    return Path(__file__).resolve().parents[2]

def _git(args: list[str]) -> str:
    proc = subprocess.run(["git", "-C", str(install_dir()), *args],
                          capture_output=True, text=True, timeout=60)
    return (proc.stdout or "").strip()

def _git_out(args: list[str]) -> str:  # untuk mock test
    return _git(args)

def update_available() -> bool:
    try:
        _git(["fetch", "origin", "-q"])
        head = _git(["rev-parse", "HEAD"])
        remote = _git(["rev-parse", "origin/main"])
        return bool(head and remote and head != remote)
    except Exception:  # noqa: BLE001
        return False

def self_update() -> str:
    if not update_available():
        return "sudah versi terbaru."
    log = _git(["pull", "--ff-only", "origin", "main"])
    pip = subprocess.run([str(install_dir() / ".venv" / "bin" / "pip"), "install", "-q", "-e", str(install_dir())],
                         capture_output=True, text=True, timeout=180)
    return f"update selesai:\n{log}\n{(pip.stdout or '').strip()}"
```

**Step 3: run → PASS.**
**Step 4: commit** — `git commit -am "feat: updater core"`

### Task C2: CLI `self-update` + notifikasi welcome (cache 1x/hari)

**Files:**
- Modify: `src/dhybrid/cli.py` (subcommand), `src/dhybrid/ui/repl.py` (notifikasi)
- Test: `tests/e2e/test_cli_smoke.py`

**Step 1: CLI** — `self-update` subcommand → `print(self_update())`, exit 0.

**Step 2: notifikasi** — di `show_welcome`, panggil `check_update_notice()` (cache di `~/.dhybrid/.update-check`, TTL 24 jam; hanya tampil jika `update_available()`):
```python
def check_update_notice() -> str | None:
    import time
    from pathlib import Path
    from dhybrid.updater import update_available
    cache = Path.home() / ".dhybrid" / ".update-check"
    if cache.exists() and time.time() - cache.stat().st_mtime < 86400:
        return None
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.touch()
    return "⚠ update tersedia — jalankan: dhybrid self-update" if update_available() else None
```
(Simplifikasi: cek mtime; panggil update_available() hanya jika cache kedaluwarsa; touch setelah.)

**Step 3: test** — `dhybrid --cwd /tmp self-update` exit 0 & stdout berisi "terbaru" atau "update"; smoke welcome tidak crash.
**Step 4: commit** — `git commit -am "feat: self-update + notifikasi update"`

---

## FASE D — F4: GitHub Actions CI

### Task D1: Workflow CI

**Files:**
- Create: `.github/workflows/ci.yml`

**Step 1: tulis workflow:**
```yaml
name: CI
on:
  push:
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install
        run: |
          pip install --upgrade pip
          pip install -e ".[dev]"
      - name: Lint
        run: ruff check src tests
      - name: Test
        run: pytest -q
```

**Step 2: README badge** — tambah di README:
```markdown
![CI](https://github.com/FerzDevZ/dhybrid-agent/actions/workflows/ci.yml/badge.svg)
```

**Step 3: verifikasi** — push → buka tab Actions di GitHub → job hijau.
**Step 4: commit** — `git commit -am "ci: github actions (pytest + ruff) + badge"`

---

## FASE E — F5: Shell Completion

### Task E1: `dhybrid --list-presets` (sumber data completion)

**Files:**
- Modify: `src/dhybrid/cli.py`

**Step 1:** tambah flag `--list-presets` di parser utama:
```python
parser.add_argument("--list-presets", action="store_true", help="cetak daftar preset (untuk shell completion)")
```
di `main()` sebelum dispatch: `if args.list_presets: print("\n".join(sorted(Config.load(...).presets))); return 0`

**Step 2: verifikasi** — `dhybrid --list-presets | head -3` → `anthropic-big\n...`.
**Step 3: commit** — `git commit -am "feat: --list-presets for completion"`

### Task E2: Skrip completion bash + zsh

**Files:**
- Create: `scripts/completions.bash`, `scripts/completions.zsh`

**Step 1: `scripts/completions.bash`:**
```bash
_dhybrid_completions() {
    local cur="${COMP_WORDS[COMP_CWORD]}"
    if [[ $COMP_CWORD -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "repl run tokens resume sessions skills doctor self-update --model --cwd --config --yes --help --version --list-presets" -- "$cur") )
    elif [[ "${COMP_WORDS[1]}" == "--model" && $COMP_CWORD -eq 2 ]] || [[ "${COMP_WORDS[1]}" == "repl" && "${COMP_WORDS[2]}" == "--model" ]]; then
        COMPREPLY=( $(compgen -W "$(dhybrid --list-presets 2>/dev/null)" -- "$cur") )
    fi
}
complete -F _dhybrid_completions dhybrid
```

**Step 2: `scripts/completions.zsh`:** versi zsh (`compdef` + `_arguments` atau reuse bash via `bashcompinit` — pilih `compdef _dhybrid` dengan `_describe`).

**Step 3: verifikasi** — `bash -n scripts/completions.bash`; `zsh -n` (bila zsh ada). Manual: `source scripts/completions.bash && dhybrid <TAB>`.
**Step 4: commit** — `git commit -am "feat: shell completion bash/zsh"`

### Task E3: Installer wiring

**Files:**
- Modify: `install.sh`

**Step 1:** setelah symlink binary, tambah (guard marker `dhybrid-completion`):
```bash
case "${SHELL##*/}" in
  bash) grep -q "dhybrid-completion" "$HOME/.bashrc" 2>/dev/null || \
        printf '\n# dhybrid-completion\nsource %s/scripts/completions.bash\n' "$INSTALL_DIR" >> "$HOME/.bashrc" ;;
  zsh)  grep -q "dhybrid-completion" "$HOME/.zshrc" 2>/dev/null || \
        printf '\n# dhybrid-completion\nsource %s/scripts/completions.zsh\n' "$INSTALL_DIR" >> "$HOME/.zshrc" ;;
esac
```
**Step 2: verifikasi** — sandbox install (`HOME=$(mktemp -d)`): `.bashrc` memuat completion; `bash -n install.sh`.
**Step 3: commit** — `git commit -am "feat: installer wire completion"`

---

## FASE F — F6: REPL History

### Task F1: readline history (stdlib)

**Files:**
- Modify: `src/dhybrid/ui/repl.py`

**Step 1: implementasi** — di `repl_loop`, sebelum loop input:
```python
    history_file = ctx.workspace / "history"
    try:
        import readline
        if history_file.exists():
            readline.read_history_file(history_file)
        readline.set_history_length(500)
    except (ImportError, OSError):
        pass
```
dan saat keluar (sebelum `return 0` / setelah loop):
```python
    try:
        import readline
        readline.write_history_file(history_file)
    except (ImportError, OSError):
        pass
```
(Guard: workspace sudah dibuat di SessionContext.)

**Step 2: verifikasi manual** — jalankan repl, ketik 2 prompt, `/quit`; jalankan lagi → panah atas memunculkan prompt lama. Pastikan smoke test (`test_bare_dhybrid_launches_repl_with_menu`) tetap hijau.
**Step 3: commit** — `git commit -am "feat: repl history (readline)"`

---

## VERIFIKASI AKHIR v0.3.0

```bash
pytest tests/ -q                       # semua hijau (target: 85+ test)
ruff check src tests                    # bersih
dhybrid --cwd /tmp doctor --offline    # semua [✓] atau jelas ✗
dhybrid --cwd /tmp self-update         # "sudah versi terbaru" (di repo dev)
dhybrid --list-presets | wc -l         # >= 13
git tag v0.3.0 && git push origin main --tags
# update salinan terinstall:
git -C ~/.dhybrid-agent reset --hard origin/main && ~/.dhybrid-agent/.venv/bin/pip install -q -e ~/.dhybrid-agent
```

## RISIKO & TRADEOFF

- **F1:** user config bisa basi saat preset dihapus → merge hanya key yang dikenal; nilai `model:` eksplisit selalu menang (intended).
- **F2:** cek network bisa lambat (5s/provider) → default offline di mesin tanpa internet? Tradeoff: `doctor` default cek network model AKTIF saja (1 endpoint), `--offline` untuk skip.
- **F3:** `git pull --ff-only` bisa gagal jika repo install ada perubahan lokal → fallback `reset --hard origin/main` (repo install disposable; user config terpisah di ~/.dhybrid/).
- **F5:** completion zsh via bashcompinit butuh `autoload bashcompinit` → dokumentasikan di header skrip.
- **F6:** readline tidak tersedia di beberapa terminal → fallback `input()` otomatis (sudah di-handle try/except).

## OPEN QUESTIONS

1. F2: `doctor` perlu cek semua 13 preset atau hanya model aktif? (Rekomendasi: aktif + `--all` flag opsional.)
2. F5: priority bash dulu, zsh menyusul — oke? (Rekomendasi: ya, user di Linux bash.)
3. F3: notifikasi update setiap hari cukup? (Rekomendasi: ya, cache 24 jam.)

---

*Disusun 2026-08-02. Merujuk kondisi repo: HEAD c1bc218, 81 test, config.py load() + session/context.py set_model() seperti dibaca di atas.*
