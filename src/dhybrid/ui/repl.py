"""REPL — loop interaktif dhybrid-agent."""

from __future__ import annotations

from dhybrid import __version__
from dhybrid.agent.hooks import Hooks
from dhybrid.agent.loop import AgentLoop, LoopConfig
from dhybrid.skills.loader import inject_skills
from dhybrid.ui.commands import handle_command
from dhybrid.ui.render import stream_print, style
from dhybrid.ui.status import (
    format_status,  # noqa: F401  (API publik, dipakai doctor nanti)
)


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


BANNER = r"""
  ██████╗ ██╗   ██╗██╗  ██╗██████╗ ██████╗ ██╗██████╗
  ██╔══██╗╚██╗ ██╔╝██║  ██║██╔══██╗██╔══██╗██║██╔══██╗
  ██║  ██║ ╚████╔╝ ███████║██████╔╝██████╔╝██║██████╔╝
  ██║  ██║  ╚██╔╝  ██╔══██║██╔═══╝ ██╔═══╝ ██║██╔═══╝
  ██████╔╝   ██║   ██║  ██║██║     ██║     ██║██║
  ╚═════╝    ╚═╝   ╚═╝  ╚═╝╚═╝     ╚═╝     ╚═╝╚═╝
"""


def check_update_notice() -> str | None:
    """Notifikasi update (cek max 1x/hari via cache mtime)."""
    import time
    from pathlib import Path

    from dhybrid.updater import update_available
    cache = Path.home() / ".dhybrid" / ".update-check"
    if cache.exists() and time.time() - cache.stat().st_mtime < 86400:
        return None
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.touch()
    try:
        return "⚠ update tersedia — jalankan: dhybrid self-update" if update_available() else None
    except Exception:  # noqa: BLE001
        return None


def show_welcome(ctx) -> None:
    """Banner + menu utama lengkap (muncul setiap kali dhybrid dijalankan)."""
    print(style(BANNER, "36"))
    print(style(f"  dhybrid-agent v{__version__} — coding agent hemat token (hybrid routing)", "1;36"))
    print(f"  model utama : {ctx.current_model_label()}")
    print(f"  workspace   : {ctx.cwd}")
    print()
    print("  MENU — pilih dengan prefix /, atau langsung ketik pertanyaan:")
    print()
    print("  ⚙️  /settings           semua pengaturan: model (manual), key, preset, dsb")
    print("  🤖 /model <nama>        ganti model (preset / manual, mis. gpt-5.6-luna)   /key <prov> <nilai>  set key")
    print("  💰 /tokens              dashboard token & biaya               /compact             ringkas konteks")
    print("  📂 /sessions            sesi sebelumnya                       /clear               reset percakapan")
    print("  🧠 /skills              lihat skill aktif                     /help                semua perintah")
    print("  🚪 /quit                keluar")
    print()
    print(style("  Tips: tanpa API key pun bisa dipakai — route opencode zen gratis sudah jadi default.", "90"))
    notice = check_update_notice()  # internal sudah try/except, tidak akan raise
    if notice:
        print(style(notice, "33"))


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

    show_welcome(ctx)
    if not _has_api_key(ctx):
        print(
            style(
                "PERINGATAN: model aktif butuh API key yang belum terisi. "
                "Set via /settings (menu 3), /key <provider> <nilai>, "
                "atau pakai model gratis: /model opencode-zen-fast",
                "33",
            )
        )
    ctx.hooks = _make_hooks(ctx)

    # REPL history (readline stdlib) — panah atas untuk prompt sebelumnya
    history_file = ctx.workspace / "history"
    try:
        import readline

        if history_file.exists():
            readline.read_history_file(history_file)
        readline.set_history_length(500)
    except (ImportError, OSError):
        readline = None

    try:
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
    finally:
        if readline is not None:
            try:
                readline.write_history_file(history_file)
            except OSError:
                pass


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

    # catat berapa banyak yang benar-benar ter-streaming ke layar
    streamed = {"chars": 0}
    orig_delta = ctx.hooks.on_delta

    def _counting_delta(text: str) -> None:
        streamed["chars"] += len(text)
        if orig_delta:
            orig_delta(text)

    ctx.hooks.on_delta = _counting_delta
    try:
        final = run_agent(ctx, prompt)
    finally:
        ctx.hooks.on_delta = orig_delta

    # jawaban final: tampilkan bila belum ter-stream (error / respons kosong / non-stream)
    if final and final.strip():
        if final.startswith("[error"):
            print(style(final, "31"))
        elif streamed["chars"] == 0:
            print(final)

    print(style(f"\n[done — {ctx.budget.used:,} token, ${ctx.last_cost:.4f}]", "90"))
    if ctx.router:
        print(style(f"[routing: small={ctx.router.stats['small']} big={ctx.router.stats['big']}]", "90"))

    # F9: auto-skill — tawarkan simpan sesi sukses sebagai skill (hanya saat interaktif)
    _maybe_save_skill(ctx, raw, final)


def _maybe_save_skill(ctx, raw: str, final: str) -> None:
    import sys
    from pathlib import Path

    from dhybrid.skills.loader import build_skill_md

    if not sys.stdin.isatty():
        return
    try:
        ans = input(style("  Simpan sesi ini sebagai skill? (y/N) ", "36")).strip().lower()
        if ans not in ("y", "yes"):
            return
        name = input("  Nama skill (mis. fix-pdf-bug): ").strip() or "custom-skill"
        desc = input("  Deskripsi singkat: ").strip() or f"Skill dari sesi: {raw[:50]}"
    except (EOFError, KeyboardInterrupt):
        return
    tools_used = [n for n, c in ctx.tools.tool_count.items() if c > 0]
    md = build_skill_md(name, desc, raw, tools_used, final)
    target = Path(ctx.cwd) / "skills" / name / "SKILL.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(md)
    print(style(f"  OK: skill tersimpan di {target}", "32"))


def _make_hooks(ctx) -> Hooks:
    hooks = Hooks()
    hooks.on_delta = stream_print
    hooks.on_step = _make_step_hook(ctx)
    hooks.on_compaction = lambda summary: print(style(f"\n[kompaksi] {summary[:120]}...", "35"))
    hooks.on_tool = lambda name, args, output: print(style(f"\n  ⚙ {name}({_short_args(args)})", "90"))
    return hooks


def _make_step_hook(ctx):
    """Catat usage & progres — TANPA statusline \r (dulu merusak teks streaming)."""

    def on_step(step: int, model: str, usage, budget_used: int) -> None:
        ctx.steps = step
        if usage is not None:
            ctx.record_usage(model, usage)

    return on_step


def _short_args(args: dict) -> str:
    s = ", ".join(f"{k}={str(v)[:40]}" for k, v in list(args.items())[:2])
    return s[:80]


def _has_api_key(ctx) -> bool:
    cfg = ctx.model_cfg
    if cfg.api_key():
        return True
    # route zen dengan model *-free tidak butuh API key
    return bool(cfg.base_url and "opencode.ai/zen" in cfg.base_url and "-free" in cfg.model)
