"""Slash commands untuk REPL."""

from __future__ import annotations

from dhybrid.ui.render import style


def print_help() -> None:
    print(
        style(
            """
/help            — bantuan ini
/model [preset]  — lihat / ganti model utama (preset: openai-fast, anthropic-big, ...)
/tokens          — dashboard token & biaya sesi ini
/compact         — paksa kompaksi konteks (ringkas pesan lama)
/clear           — reset konteks percakapan (simpan ringkasan)
/sessions        — daftar sesi sebelumnya
/skills          — daftar skill yang tersedia
/quit, /exit     — keluar
""",
            "36",
        )
    )


def handle_command(cmd: str, ctx) -> bool:
    """Return True bila harus keluar."""
    parts = cmd.split(maxsplit=1)
    name = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    if name in ("/quit", "/exit"):
        return True
    if name == "/help":
        print_help()
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
