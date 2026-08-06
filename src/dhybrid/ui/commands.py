"""Slash commands untuk REPL."""

from __future__ import annotations

from pathlib import Path

from dhybrid.dotenv import set_env_key
from dhybrid.efficiency.budget import TokenBudget
from dhybrid.session.memory import MemoryStore
from dhybrid.ui.render import style


def _mem() -> MemoryStore:
    """MemoryStore singleton (buat repl commands)."""
    return MemoryStore()

# nama ramah -> env var API key
PROVIDERS = [
    ("OpenAI", "OPENAI_API_KEY"),
    ("Anthropic", "ANTHROPIC_API_KEY"),
    ("OpenRouter", "OPENROUTER_API_KEY"),
    ("Gemini", "GEMINI_API_KEY"),
    ("Groq", "GROQ_API_KEY"),
    ("DeepSeek", "DEEPSEEK_API_KEY"),
    ("byNara", "BYNARA_API_KEY"),
    ("OpenCode Zen (opsional, gratis)", "OPENCODE_ZEN_API_KEY"),
]


PROVIDER_ENABLE_FILE = Path.home() / ".dhybrid" / "provider_enable.json"


def _load_provider_enabled() -> dict:
    """Muat state enable/disable provider dari file."""
    if PROVIDER_ENABLE_FILE.exists():
        import json
        try:
            return json.loads(PROVIDER_ENABLE_FILE.read_text())
        except Exception:  # noqa: BLE001,S110 — file corrupt → fallback default semua enabled
            pass
    # default: semua enabled
    return {name: True for name, _ in PROVIDERS}


def _save_provider_enabled(state: dict) -> None:
    import json
    PROVIDER_ENABLE_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROVIDER_ENABLE_FILE.write_text(json.dumps(state, indent=2))


def _key_status() -> list[tuple[str, str, bool]]:
    import os

    enabled = _load_provider_enabled()
    return [(name, env, bool(os.environ.get(env)) and enabled.get(name, True)) for name, env in PROVIDERS]


def print_help() -> None:
    print(
        style(
            """
MENU LENGKAP — pilih dengan prefix / :

  ⚙️  /settings           SEMUA pengaturan dalam satu menu (model manual, key, preset, dsb)
  🔑 /key <prov> <nilai> set key cepat, contoh: /key openai sk-xxxx
  🤖 /model [preset]     ganti model cepat (preset / provider:model / manual)
  💰 /tokens             dashboard token & biaya sesi ini
  📂 /compact            ringkas konteks (pesan lama)
  📂 /clear              reset konteks percakapan
  📂 /sessions           daftar sesi sebelumnya
  📸 /shot [nama]        screenshot layar → ~/.dhybrid/captures/ (agent bisa baca via read_image)
  📋 /pasteshot [nama]   ambil GAMBAR dari clipboard (SS Shift+PrtSc) → file + siap dibaca
  📋 /paste [nama]       tempel teks panjang → file .txt + langsung masuk konteks agent
  🧠 /skills             daftar skill yang tersedia
  🎯 /skill <nama>       paksa pakai skill tertentu tiap prompt (off = kembali otomatis)
  💾 /remember <k> <v>  simpan fakta jangka panjang
  🗑️  /forget <k>        hapus fakta memorip
  📜 /memories          lihat fakta terbaru
  🔍 /search-memory <q>  cari fakta (FTS)
  🚪 /quit, /exit        keluar

CLI (di luar REPL): dhybrid run "<prompt>" · dhybrid resume <id> ·
dhybrid tokens · dhybrid sessions
""",
            "36",
        )
    )


def _list_presets(ctx) -> None:
    for preset in sorted(ctx.registry.names()):
        mc = ctx.registry.resolve(preset)
        print(f"    {preset:<18} {mc.model}  (via {mc.provider})")


def cmd_settings(ctx) -> None:
    """Satu menu untuk semua pengaturan: model (manual), key, preset, token."""
    while True:
        print(style("\n=== PENGATURAN ===", "1;36"))
        print(f"  model utama : {ctx.current_model_label()}")
        key_row = "  api key     : " + " | ".join(
            f"{n.split()[0]} {'✓' if ok else '✗'}" for n, e, ok in _key_status()
        )
        print(key_row)
        print()
        print("  1. Ganti model utama  (preset / provider:model / model manual apa pun)")
        print("  2. Atur API key      (pilih provider mana yang diisi)")
        print("  3. Daftar semua preset")
        print("  4. Token & biaya sesi")
        print("  5. Kelola provider   (hidup/matikan provider)")
        print("  6. Kelola skill      (hidup/matikan)")
        print("  0. Kembali")
        try:
            choice = input("  pilih (0-6): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("  [kembali]")
            return
        if choice == "0":
            return
        if choice == "1":
            _settings_model(ctx)
        elif choice == "2":
            cmd_setup(ctx)
        elif choice == "3":
            _list_presets(ctx)
        elif choice == "4":
            _print_tokens(ctx)
        elif choice == "5":
            _provider_cmd(ctx)
        elif choice == "6":
            _skills_cmd(ctx, "")
        else:
            print(style("  pilihan tidak valid", "33"))


def _provider_cmd(ctx) -> None:
    """Hidup/matikan provider (enable/disable)."""
    import os
    enabled = _load_provider_enabled()

    while True:
        print(style("\n=== KELOLA PROVIDER ===", "1;36"))
        for i, (name, env) in enumerate(PROVIDERS, start=1):
            status = "✓" if enabled.get(name, True) else "✗"
            key_mark = "🔑" if os.environ.get(env) else "  "
            print(f"  {i}. {name:<32} {status}  {key_mark}  ({env})")
        print("  0. Kembali")
        try:
            choice = input(f"  pilih provider (0-{len(PROVIDERS)}): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("  [kembali]")
            return
        if choice == "0":
            return
        try:
            name, env = PROVIDERS[int(choice) - 1]
        except (ValueError, IndexError):
            print(style("  pilihan tidak valid", "33"))
            continue
        enabled[name] = not enabled.get(name, True)
        _save_provider_enabled(enabled)
        print(style(f"  OK: {name} → {'AKTIF ✓' if enabled[name] else 'NONAKTIF ✗'}", "32"))


def _settings_model(ctx) -> None:
    print("  Preset tersedia:")
    _list_presets(ctx)
    try:
        val = input("  Nama preset ATAU model manual (mis. gpt-5.6-luna, anthropic:claude-opus-5) [kosong = batal]: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("  [batal]")
        return
    if not val:
        return
    if val.startswith("/"):
        print(style("  (input dimulai '/' — dianggap perintah, model tidak diubah)", "33"))
        return
    try:
        print(style("  " + ctx.set_model(val), "32"))
    except KeyError as e:
        print(style(f"  ERROR: {e}", "31"))


def cmd_setup(ctx) -> None:
    """Wizard API key — PILIH provider dulu, baru tempel key-nya (tidak ditanya 1-per-1)."""
    import os

    while True:
        print(style("\n=== ATUR API KEY ===", "1;36"))
        print("  pilih provider mana yang mau diisi:")
        for i, (name, env) in enumerate(PROVIDERS, start=1):
            ok = bool(os.environ.get(env))
            mark = "✓" if ok else "✗"
            note = "  (opsional, gratis)" if "ZEN" in env else ""
            print(f"  {i}. {name:<32} {mark}{note}")
        print("  0. Kembali")
        try:
            choice = input(f"  pilih provider (0-{len(PROVIDERS)}): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("  [kembali]")
            return
        if choice == "0":
            return
        try:
            name, env = PROVIDERS[int(choice) - 1]
        except (ValueError, IndexError):
            print(style("  pilihan tidak valid", "33"))
            continue
        try:
            val = input(f"  Paste key {name} ({env}) [kosong = batal]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("  [batal]")
            continue
        if not val:
            continue
        p = set_env_key(env, val)
        print(style(f"  OK: {env} disimpan di {p} — langsung aktif.", "32"))


def cmd_key(ctx, arg: str) -> None:
    """/key <provider> <nilai> — mis. /key openai sk-xxxx"""
    parts = arg.split(maxsplit=1)
    if len(parts) != 2:
        print(style("Pemakaian: /key <provider> <nilai>  (provider: openai, anthropic, openrouter, gemini, groq, deepseek, zen)", "33"))
        return
    name, value = parts[0].lower(), parts[1].strip()
    env_map = {n.split()[0].lower(): e for n, e in PROVIDERS}
    if name == "zen":
        env = "OPENCODE_ZEN_API_KEY"
    else:
        env = env_map.get(name)
        if env is None:
            print(style(f"Provider '{name}' tidak dikenal. Pilih: {', '.join(sorted(env_map))}, zen", "31"))
            return
    p = set_env_key(env, value)
    print(style(f"OK: {env} disimpan di {p} — langsung aktif.", "32"))


def _clipboard_image_bytes() -> bytes | None:
    """Gambar dari clipboard X11 (hasil SS Shift+PrtSc dll).

    Prioritas: binary xclip → python-xlib (pure python, tanpa sudo).
    None bila clipboard tidak berisi gambar / bukan X11."""
    import subprocess
    import time

    # 1) xclip (binary umum)
    try:
        r = subprocess.run(
            ["xclip", "-selection", "clipboard", "-t", "image/png", "-o"],
            capture_output=True, timeout=5, check=False,
        )
        if r.returncode == 0 and r.stdout:
            return r.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # 2) python-xlib — minta selection CLIPBOARD target image/png
    try:
        from Xlib import X, display
    except ImportError:
        return None
    try:
        d = display.Display()
        root = d.screen().root
        win = root.create_window(0, 0, 1, 1, 0, X.CopyFromParent)
        clip = d.intern_atom("CLIPBOARD")
        png = d.intern_atom("image/png")
        prop = d.intern_atom("_DHYBRID_CLIP")
        win.convert_selection(clip, png, prop, X.CurrentTime)
        d.sync()
        deadline = time.time() + 3
        data: bytes | None = None
        while time.time() < deadline:
            while d.pending_events():
                ev = d.next_event()
                if ev.type == X.SelectionNotify:
                    if ev.property != X.NONE:
                        raw = win.get_full_property(prop, X.AnyPropertyType)
                        if raw:
                            data = bytes(raw.value)
                    return data
            time.sleep(0.05)
        d.close()
        return None
    except Exception:  # noqa: BLE001 — bukan X11 / clipboard kosong
        return None


def cmd_pasteshot(ctx, arg: str) -> None:
    """/pasteshot [nama] — ambil GAMBAR dari clipboard (hasil SS) → file + siap dibaca.

    Alur: Shift+PrtSc (screenshot ke clipboard) → /pasteshot → read_image.
    Tidak bisa paste gambar langsung ke terminal — ini jalur terdekatnya."""
    from datetime import datetime

    cap_dir = Path.home() / ".dhybrid" / "captures"
    cap_dir.mkdir(parents=True, exist_ok=True)
    data = _clipboard_image_bytes()
    if not data:
        print(style(
            "Clipboard tidak berisi gambar. Cara pakai: screenshot dulu "
            "(mis. Shift+PrtSc atau gnome-screenshot -c), lalu /pasteshot.",
            "33",
        ))
        return
    from dhybrid.tools.vision import _is_image_bytes

    if not _is_image_bytes(data[:4096]):
        print(style("Clipboard bukan gambar (magic bytes tidak cocok PNG/JPEG).", "33"))
        return
    name = (arg.strip() or datetime.now().astimezone().strftime("%Y%m%d-%H%M%S"))
    if not name.lower().endswith((".png", ".jpg")):
        name += ".png"
    out = cap_dir / name
    out.write_bytes(data)
    print(style(f"OK: {out} ({len(data)} bytes) — gambar dari clipboard tersimpan.", "32"))
    print("lalu minta agent baca: read_image path=" + str(out) + "  (atau ketik prompt biasa)")


def cmd_shot(ctx, arg: str) -> None:
    """/shot [nama] — screenshot layar penuh (ImageMagick import) ke captures/."""
    import subprocess
    from datetime import datetime

    cap_dir = Path.home() / ".dhybrid" / "captures"
    cap_dir.mkdir(parents=True, exist_ok=True)
    name = (arg.strip() or datetime.now().astimezone().strftime("%Y%m%d-%H%M%S"))
    if not name.lower().endswith((".png", ".jpg")):
        name += ".png"
    out = cap_dir / name
    try:
        subprocess.run(
            ["import", "-window", "root", str(out)],
            check=True, capture_output=True, timeout=30,
        )
    except FileNotFoundError:
        print(style("ERROR: ImageMagick 'import' tidak ada — install: sudo apt install imagemagick", "31"))
        return
    except subprocess.CalledProcessError as e:
        err = (e.stderr or b"").decode(errors="replace").strip()
        print(style(f"ERROR screenshot: {err or e}", "31"))
        return
    print(style(f"OK: {out}", "32"))
    print("lalu minta agent baca: read_image path=" + str(out) + "  (atau ketik prompt biasa, agent bisa pakai sendiri)")


def cmd_paste(ctx, arg: str) -> None:
    """/paste [nama] — tempel teks multi-baris → file .txt + inject ke konteks.

    Selesai dengan Ctrl+D (atau baris berisi titik saja). Isi otomatis jadi
    pesan user berikutnya sehingga agent langsung membacanya."""
    from datetime import datetime

    paste_dir = Path.home() / ".dhybrid" / "pastes"
    paste_dir.mkdir(parents=True, exist_ok=True)
    name = (arg.strip() or datetime.now().astimezone().strftime("%Y%m%d-%H%M%S"))
    if not name.lower().endswith(".txt"):
        name += ".txt"
    out = paste_dir / name
    print(style("Mode paste — tempel teks sekarang; selesai dengan Ctrl+D atau baris berisi titik saja.", "36"))
    lines: list[str] = []
    try:
        while True:
            line = input()
            if line.strip() == ".":
                break
            lines.append(line)
    except (EOFError, KeyboardInterrupt):
        pass
    content = "\n".join(lines).strip()
    if not content:
        print(style("(kosong — tidak disimpan)", "33"))
        return
    out.write_text(content)
    print(style(f"OK: {out} ({len(content)} char) — dikirim ke konteks agent.", "32"))
    try:
        from dhybrid.llm.base import ChatMessage

        msg = f"[PASTE USER — {out}]\n\n{content}"
        if len(msg) > 30000:
            msg = msg[:30000] + "\n…[terpotong, file lengkap di path di atas]"
        ctx.push(ChatMessage(role="user", content=msg))
    except Exception as e:  # noqa: BLE001 — konteks gagal di-push → file tetap tersimpan
        print(style(f"(file tersimpan, tapi gagal di-inject ke konteks: {e})", "33"))


def handle_command(cmd: str, ctx) -> bool:
    """Return True bila harus keluar."""
    parts = cmd.split(maxsplit=1)
    name = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    if name in ("/quit", "/exit"):
        return True
    if name == "/help":
        print_help()
    elif name == "/settings":
        cmd_settings(ctx)
    elif name == "/setup":
        cmd_setup(ctx)
    elif name == "/key":
        cmd_key(ctx, arg)
    elif name == "/model":
        if arg:
            try:
                print(style(ctx.set_model(arg), "32"))
            except KeyError as e:
                print(style(f"ERROR: {e}", "31"))
                print(f"preset tersedia: {', '.join(ctx.registry.names())}")
        else:
            print(f"model aktif: {ctx.current_model_label()}")
            print(f"preset tersedia: {', '.join(ctx.registry.names())}")
            try:
                val = input("  Nama preset / provider:model / model manual [kosong = batal]: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("  [batal]")
                return False
            if val:
                if val.startswith("/"):
                    print(style("  (input dimulai '/' — dianggap perintah, model tidak diubah)", "33"))
                    return False
                try:
                    print(style(ctx.set_model(val), "32"))
                except KeyError as e:
                    print(style(f"ERROR: {e}", "31"))
    elif name == "/models":
        _list_presets(ctx)
    elif name == "/tokens":
        _print_tokens(ctx)
    elif name == "/compact":
        from dhybrid.efficiency.compress import compact_conversation

        cands = ctx.ctx.candidates_for_compaction()
        if not cands:
            print("(konteks masih pendek — belum perlu kompaksi)")
        else:
            client = ctx.router.small if ctx.router else ctx._fresh_client()
            summary = compact_conversation(client, cands)
            ctx.ctx.apply_compaction(summary)
            print(style(f"OK: konteks dikompaksi ({len(cands)} pesan -> ringkasan)", "32"))
    elif name == "/clear":
        ctx.ctx.messages.clear()
        ctx.ctx.budget = TokenBudget(ctx.ctx.cfg.budget)
        print("OK: konteks & budget direset — sesi baru dimulai")
    elif name == "/sessions":
        for s in ctx.store.sessions(limit=15):
            print(f"  {s['id']}  {s['created'][:16]}  {s['title']}")
    elif name == "/skills":
        _skills_cmd(ctx, arg)
    elif name == "/skill":
        _skill_cmd(ctx, arg)
    elif name in ("/remember", "/rmem"):
        _cmd_remember(ctx, arg)
    elif name in ("/forget", "/fmem"):
        _cmd_forget(ctx, arg)
    elif name in ("/memories", "/mem"):
        _cmd_memories(ctx)
    elif name == "/search-memory":
        _cmd_search_memory(ctx, arg)
    elif name == "/shot":
        cmd_shot(ctx, arg)
    elif name == "/pasteshot":
        cmd_pasteshot(ctx, arg)
    elif name == "/paste":
        cmd_paste(ctx, arg)
    else:
        print(style(f"command tidak dikenal: {name} (ketik /help)", "33"))
    return False


def _skill_cmd(ctx, arg: str) -> None:
    """/skill <nama> — paksa inject skill tertentu tiap prompt (untuk sesi ini).
    /skill off|none|clear — hapus paksaan (kembali otomatis).
    /skill ls — daftar semua skill (sama dengan /skills).
    /skill info <nama> — tampilkan isi skill.
    /skill rm <nama> — hapus skill WORKSPACE (hasil auto-learn); skill bawaan ditolak.
    /skill — tampilkan paksaan aktif."""
    arg = arg.strip()
    if not arg:
        if ctx.forced_skills:
            print(style("skill paksa aktif: " + ", ".join(ctx.forced_skills), "36"))
        else:
            print("(tidak ada skill paksa — otomatis berdasarkan relevansi kata kunci)")
        return
    parts = arg.split(maxsplit=1)
    cmd, rest = parts[0].lower(), (parts[1] if len(parts) > 1 else "").strip()
    if cmd == "ls":
        _skills_cmd(ctx, "")
        return
    if cmd == "info":
        if not rest:
            print(style("pemakaian: /skill info <nama>", "33"))
            return
        target = next((s for s in ctx.all_skills if s.name == rest.lower()), None)
        if not target:
            print(style(f"skill '{rest}' tidak dikenal — cek /skills", "31"))
            return
        print(style(f"=== {target.name} ===", "36"))
        print(style(f"deskripsi: {target.description}", "1"))
        print(target.body)
        return
    if cmd == "rm":
        if not rest:
            print(style("pemakaian: /skill rm <nama>", "33"))
            return
        _skill_rm(ctx, rest.lower())
        return
    if arg.lower() in ("off", "none", "clear", "reset"):
        ctx.forced_skills = []
        print(style("OK: paksaan skill dihapus — kembali ke otomatis.", "32"))
        return
    if not any(s.name == arg.lower() for s in ctx.all_skills):
        print(style(f"skill '{arg}' tidak dikenal — cek /skills", "31"))
        return
    if arg.lower() not in ctx.forced_skills:
        ctx.forced_skills.append(arg.lower())
    print(style(f"OK: skill '{arg.lower()}' DIPAKSA inject tiap prompt (sampai /skill off).", "32"))


def _skill_rm(ctx, name: str) -> None:
    """Hapus skill — hanya dari workspace (hasil auto-learn), skill bawaan/repo
    TIDAK boleh dihapus lewat CLI (hindari menghapus skill yang dikelola git)."""
    target = next((s for s in ctx.all_skills if s.name == name), None)
    if not target:
        print(style(f"skill '{name}' tidak dikenal — cek /skills", "31"))
        return
    ws_root = (ctx.workspace / "skills").resolve()
    try:
        is_workspace = ws_root in target.path.resolve().parents
    except OSError:
        is_workspace = False
    if not is_workspace:
        print(style(f"skill '{name}' adalah skill bawaan — hapus manual dari {target.path.parent}", "33"))
        return
    target.path.unlink(missing_ok=True)
    try:
        target.path.parent.rmdir()  # hapus folder skill yang kini kosong
    except OSError:
        pass
    ctx.reload_skills()
    print(style(f"OK: skill workspace '{name}' dihapus.", "32"))


def _skills_cmd(ctx, arg: str) -> None:
    """/skills — daftar semua skill (✓ aktif / ✗ nonaktif).
    /skills <nama> — hidup/matikan skill (tersimpan permanen)."""
    if arg:
        from dhybrid.session.userconfig import toggle_skill

        name = arg.strip()
        if not any(s.name == name for s in ctx.all_skills):
            print(style(f"skill '{name}' tidak dikenal", "31"))
            return
        enabled, _ = toggle_skill(name)
        ctx.reload_skills()
        print(style(f"OK: skill '{name}' → {'AKTIF ✓' if enabled else 'NONAKTIF ✗'} (tersimpan)", "32" if enabled else "33"))
        return
    if not ctx.all_skills:
        print("(tidak ada skill)")
        return
    print(style("SKILLS (hidup/matikan: /skills <nama>):", "1;36"))
    for sk in ctx.all_skills:
        on = sk.name not in ctx.disabled_skills
        mark = "✓" if on else "✗"
        print(f"  {mark} {sk.name:<22} {sk.description[:52]}")
    n_on = len(ctx.skills)
    print(style(f"  ({n_on}/{len(ctx.all_skills)} aktif)", "90"))


def _print_tokens(ctx) -> None:
    rows = ctx.store.usage(ctx.sid)
    tot_p = sum(r["prompt"] for r in rows)
    tot_c = sum(r["completion"] for r in rows)
    tot_cached = sum(r["cached"] for r in rows)
    cost = sum(r["cost"] for r in rows)
    ratio = (tot_cached / tot_p) if tot_p else 0.0
    print(f"  prompt       : {tot_p:>9,} token")
    print(f"  completion   : {tot_c:>9,} token")
    print(f"  cached       : {tot_cached:>9,} token")
    print(f"  cache-hit    : {ratio * 100:5.1f}%")
    print(f"  estimasi     : ${cost:.4f}")
    print(f"  budget       : {ctx.budget.used:,}/{ctx.budget.soft:,} (soft) — "
          f"{ctx.budget.history and ctx.budget.history[-1]['cum'] or 0:,}")
    print(f"  routing      : small={ctx.router.stats.get('small', 0)} big={ctx.router.stats.get('big', 0)}"
          if ctx.router else "  routing      : (router non-aktif)")


def _cmd_remember(ctx, arg: str) -> None:
    """/remember <key> <value> — simpan fakta jangka panjang.
    Contoh: /remember user.lang id"""
    parts = arg.split(maxsplit=1)
    if len(parts) < 2:
        print(style("Pemakaian: /remember <key> <value>  (mis. /remember user.lang id)", "33"))
        return
    key, value = parts[0], parts[1].strip()
    print(style("  " + _mem().remember(key, value), "32"))


def _cmd_forget(ctx, arg: str) -> None:
    """/forget <key> — hapus fakta memorip."""
    if not arg.strip():
        print(style("Pemakaian: /forget <key>", "33"))
        return
    print(style("  " + _mem().forget(arg.strip()), "32"))


def _cmd_memories(ctx) -> None:
    """/memories — tampilkan fakta terbaru."""
    out = _mem().recent()
    if not out:
        print("(memori kosong — pakai /remember <key> <value> untuk menyimpan)")
        return
    print(style("MEMORI TERBARU:", "1;36"))
    for line in out.splitlines():
        print("  " + line)


def _cmd_search_memory(ctx, arg: str) -> None:
    """/search-memory <query> — cari fakta via FTS."""
    if not arg.strip():
        print(style("Pemakaian: /search-memory <kata kunci>", "33"))
        return
    out = _mem().search(arg.strip())
    print(out if out else "(tidak ada memori cocok)")
