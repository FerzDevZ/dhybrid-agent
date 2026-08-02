"""REPL — loop interaktif dhybrid-agent."""

from __future__ import annotations

from dhybrid.agent.hooks import Hooks
from dhybrid.agent.loop import AgentLoop, LoopConfig
from dhybrid.skills.loader import inject_skills
from dhybrid.ui.commands import handle_command
from dhybrid.ui.render import is_tty, stream_print, style
from dhybrid.ui.status import format_status


def run_agent(ctx, prompt: str) -> str:
    """Jalankan satu task agent; kembalikan jawaban final."""
    loop = AgentLoop(
        ctx.router if ctx.router else ctx._fresh_client(),
        ctx.tools,
        ctx=ctx.ctx,
        budget=ctx.budget,
        cfg=LoopConfig(max_tool_output_chars=ctx.cfg.tool.get("max_output_chars", 8000)),
        hooks=ctx.hooks,
    )
    result = loop.run(prompt, ctx.system_prompt)

    # simpan ke sesi
    ctx.store.append_message(ctx.sid, "user", prompt[:2000])
    ctx.store.append_message(ctx.sid, "assistant", result.final_text[:4000])
    ctx.store.set_summary(
        ctx.sid,
        ctx.ctx.summary or "",
        result.final_text[:2000],
    )
    return result.final_text


def repl_loop(ctx) -> int:
    from dhybrid.tools import terminal

    # gerbang keamanan: default minta konfirmasi; --yes = tolak otomatis
    if ctx.yes_mode:
        terminal.confirm_fn = None
    else:

        def _confirm(command: str) -> bool:
            try:
                return input(f"⚠ perintah berbahaya terdeteksi:\n  {command}\nJalankan? (y/N) ").strip().lower() in ("y", "yes")
            except (EOFError, KeyboardInterrupt):
                return False

        terminal.confirm_fn = _confirm

    print(style(f"dhybrid-agent v0.1.0 — model: {ctx.current_model_label()} — ketik /help", "1;36"))
    if not _has_api_key(ctx):
        print(
            style(
                "PERINGATAN: API key tidak ditemukan. Isi .env (lihat .env.example) "
                "atau set env var, lalu restart.",
                "33",
            )
        )
    ctx.hooks = _make_hooks(ctx)

    while True:
        try:
            raw = input(style("dhybrid> ", "32")).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye 👋")
            return 0
        if not raw:
            continue
        if raw.startswith("/"):
            if handle_command(raw, ctx):
                return 0
            continue
        if not ctx.sid:
            ctx.sid = ctx.store.new_session()
        try:
            _run_one(ctx, raw)
        except KeyboardInterrupt:
            print(style("\n[dibatalkan]", "33"))
        except Exception as e:  # noqa: BLE001
            print(style(f"\n[error] {type(e).__name__}: {e}", "31"))


def _run_one(ctx, raw: str) -> None:
    # judul sesi dari prompt pertama
    if ctx.store.get_session(ctx.sid) and not ctx.store.get_session(ctx.sid)["title"].startswith("untitled"):
        pass
    else:
        ctx.store.conn.execute(
            "UPDATE sessions SET title=? WHERE id=?", (raw[:60], ctx.sid)
        )
        ctx.store.conn.commit()

    prompt = inject_skills(
        raw, ctx.skills,
        max_inject=ctx.cfg.skills.get("max_inject", 3),
        max_chars=ctx.cfg.skills.get("max_chars", 800),
    )
    ctx.steps = 0
    ctx.last_cost = 0.0
    print()  # baris baru sebelum streaming
    run_agent(ctx, prompt)
    print(style(f"\n[done — {ctx.budget.used:,} token, ${ctx.last_cost:.4f}]", "90"))
    if ctx.router:
        print(style(f"[routing: small={ctx.router.stats['small']} big={ctx.router.stats['big']}]", "90"))


def _make_hooks(ctx) -> Hooks:
    hooks = Hooks()
    hooks.on_delta = stream_print
    hooks.on_step = _make_step_hook(ctx)
    hooks.on_compaction = lambda summary: print(style(f"\n[kompaksi] {summary[:120]}...", "35"))
    hooks.on_tool = lambda name, args, output: print(style(f"\n  ⚙ {name}({_short_args(args)})", "90"))
    return hooks


def _make_step_hook(ctx):
    max_steps = 20

    def on_step(step: int, model: str, usage, budget_used: int) -> None:
        ctx.steps = step
        if usage is not None:
            ctx.record_usage(model, usage)
        if is_tty():
            status = format_status(
                ctx.budget, model, step + 1, max_steps,
                cache_ratio=ctx.budget.cache_hit_ratio,
                cost=ctx.last_cost,
            )
            stream_print(style(f"\r{status}", "90"))

    return on_step


def _short_args(args: dict) -> str:
    s = ", ".join(f"{k}={str(v)[:40]}" for k, v in list(args.items())[:2])
    return s[:80]


def _has_api_key(ctx) -> bool:
    return bool(ctx.model_cfg.api_key())
