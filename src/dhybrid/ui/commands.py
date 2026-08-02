"""Slash commands untuk REPL."""

from __future__ import annotations

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
    ("OpenCode Zen (opsional, gratis)", "OPENCODE_ZEN_API_KEY"),
]


def _key_status() -> list[tuple[str, str, bool]]:
    import os

    return [(name, env, bool(os.environ.get(env))) for name, env in PROVIDERS]


def print_help() -> None:
    print(
        style(
            """
MENU LENGKAP — pilih dengan prefix / :

  🔑 /setup              wizard atur API key (panduan interaktif)
  🔑 /key <prov> <nilai> set key cepat, contoh: /key openai sk-xxxx
  🤖 /model [preset]     lihat / ganti model utama
  🤖 /models             daftar semua preset model
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


def cmd_setup(ctx) -> None:
    """Wizard API key — cukup tempel key, sisanya diurus."""
    print(style("SETUP API KEY — tempel key untuk provider yang kamu punya (kosong = lewati):", "1;36"))
    missing = [(n, e) for n, e, ok in _key_status() if not ok]
    if not missing:
        print("  Semua API key sudah terisi. 👍")
        return
    for name, env in missing:
        try:
            val = input(f"  {name} ({env}): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("  [dibatalkan]")
            return
        if val:
            p = set_env_key(env, val)
            print(style(f"  OK: {env} disimpan di {p}", "32"))
    print(style("Selesai! Key langsung aktif di sesi ini.", "32"))


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
    elif name == "/setup":
        cmd_setup(ctx)
    elif name == "/key":
        cmd_key(ctx, arg)
    elif name == "/model":
        if arg:
            try:
                print(ctx.set_model(arg))
            except KeyError as e:
                print(style(f"ERROR: {e}", "31"))
                print(f"preset tersedia: {', '.join(ctx.registry.names())}")
        else:
            print(f"model aktif: {ctx.current_model_label()}")
            print(f"preset tersedia: {', '.join(ctx.registry.names())}")
    elif name == "/models":
        for preset in sorted(ctx.registry.names()):
            mc = ctx.registry.resolve(preset)
            print(f"  {preset:<18} {mc.model}  (via {mc.provider})")
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
        if ctx.skills:
            for sk in ctx.skills:
                print(f"  {sk.name} — {sk.description[:60]}")
        else:
            print("(tidak ada skill — buat skills/<nama>/SKILL.md)")
    else:
        print(style(f"command tidak dikenal: {name} (ketik /help)", "33"))
    return False


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
