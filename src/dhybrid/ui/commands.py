"""Slash commands untuk REPL."""

from __future__ import annotations

import json
from pathlib import Path

from dhybrid.dotenv import set_env_key
from dhybrid.ui.render import style

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
        except Exception:
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
  🧠 /skills             daftar skill yang tersedia
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
            is_on = enabled.get(name, True)
            has_key = bool(os.environ.get(env))
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
        print("OK: konteks percakapan direset (ringkasan dipertahankan)")
    elif name == "/sessions":
        for s in ctx.store.sessions(limit=15):
            print(f"  {s['id']}  {s['created'][:16]}  {s['title']}")
    elif name == "/skills":
        _skills_cmd(ctx, arg)
    else:
        print(style(f"command tidak dikenal: {name} (ketik /help)", "33"))
    return False


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
