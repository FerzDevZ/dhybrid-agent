"""CLI entry point — dhybrid: repl | run | tokens | resume | sessions | skills."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dhybrid import __version__
from dhybrid.config import Config
from dhybrid.dotenv import load_standard_dotenvs
from dhybrid.session.context import SessionContext
from dhybrid.session.store import SessionStore
from dhybrid.ui.render import style
from dhybrid.ui.repl import repl_loop, run_agent


def _build_context(args) -> SessionContext:
    cfg = Config.load(Path(args.config) if args.config else None)
    store = SessionStore(cfg.workspace / "sessions.sqlite")
    cwd = args.cwd or "."
    ctx = SessionContext(cfg, store, cwd=cwd, yes_mode=getattr(args, "yes", False))
    if getattr(args, "model", None):
        ctx.set_model(args.model)
    return ctx


def cmd_repl(args) -> int:
    ctx = _build_context(args)
    return repl_loop(ctx)


def cmd_run(args) -> int:
    ctx = _build_context(args)
    print(f"dhybrid: {ctx.current_model_label()}")
    final = run_agent(ctx, args.prompt)
    print()
    print(final)
    print(style(f"\n[tokens: {ctx.budget.used:,} | biaya: ${ctx.last_cost:.4f} | "
                f"sesi: {ctx.sid}]", "90"))
    return 0


def cmd_tokens(args) -> int:
    cfg = Config.load(Path(args.config) if args.config else None)
    store = SessionStore(cfg.workspace / "sessions.sqlite")
    if args.session_id:
        rows = store.usage(args.session_id)
        label = args.session_id
    else:
        rows = store.usage()
        label = "semua sesi"
    tot_p = sum(r["prompt"] for r in rows)
    tot_c = sum(r["completion"] for r in rows)
    tot_cached = sum(r["cached"] for r in rows)
    cost = sum(r["cost"] for r in rows)
    print(f"penggunaan token ({label}):")
    print(f"  prompt       : {tot_p:>10,}")
    print(f"  completion   : {tot_c:>10,}")
    print(f"  cached       : {tot_cached:>10,}")
    print(f"  cache-hit    : {(tot_cached / tot_p * 100) if tot_p else 0:5.1f}%")
    print(f"  estimasi     : ${cost:.4f}")
    # simulasi tanpa hemat: cached ikut dibayar
    if tot_cached:
        print(f"  hemat cache  : ~{tot_cached:,} token input tidak dibayar ulang")
    if not args.session_id:
        print("\nper sesi:")
        by_sess: dict[str, dict] = {}
        for r in rows:
            b = by_sess.setdefault(r["session_id"], {"prompt": 0, "completion": 0, "cached": 0, "cost": 0.0})
            b["prompt"] += r["prompt"]; b["completion"] += r["completion"]
            b["cached"] += r["cached"]; b["cost"] += r["cost"]
        for sid, b in sorted(by_sess.items()):
            print(f"  {sid}  p={b['prompt']:,} c={b['completion']:,} cached={b['cached']:,} ${b['cost']:.4f}")
    return 0


def cmd_resume(args) -> int:
    from dhybrid.llm.base import ChatMessage

    ctx = _build_context(args)
    info = ctx.store.get_session(args.session_id)
    if not info:
        print(f"ERROR: sesi {args.session_id} tidak ditemukan")
        return 1
    ctx.sid = args.session_id
    ctx.ctx.summary = info["summary"] or None
    for m in ctx.store.last_messages(args.session_id, n=5):
        ctx.ctx.push(ChatMessage(role=m["role"], content=m["content"]))
    print(style(f"melanjutkan sesi {args.session_id} — {info['title']}", "36"))
    if info["summary"]:
        print(style(f"ringkasan: {info['summary'][:200]}", "90"))
    return repl_loop(ctx)


def cmd_sessions(args) -> int:
    cfg = Config.load(Path(args.config) if args.config else None)
    store = SessionStore(cfg.workspace / "sessions.sqlite")
    for s in store.sessions(limit=20):
        print(f"  {s['id']}  {s['created'][:16]}  {s['title'][:60]}")
    return 0


def cmd_skills(args) -> int:
    from dhybrid.skills.loader import list_skills

    cfg = Config.load(Path(args.config) if args.config else None)
    skills = list_skills(Path(args.cwd or ".") / cfg.skills.get("dir", "skills"))
    for sk in skills:
        print(f"  {sk.name} — {sk.description}")
    if not skills:
        print("(tidak ada skill)")
    return 0


def main(argv: list[str] | None = None) -> int:
    load_standard_dotenvs()
    parser = argparse.ArgumentParser(
        prog="dhybrid",
        description="dhybrid-agent — CLI coding agent hemat token (hybrid routing). "
                    "Tanpa subcommand = langsung masuk sesi interaktif.",
    )
    parser.add_argument("--version", action="version", version=f"dhybrid-agent {__version__}")
    parser.add_argument("--config", default=None, help="path config.yaml (default: config/default.yaml)")
    parser.add_argument("--cwd", default=None, help="working directory")
    parser.add_argument("--model", default=None, help="preset model utama (mis. anthropic-big)")
    parser.add_argument("--yes", action="store_true", help="non-interaktif: tolak perintah berbahaya otomatis")
    sub = parser.add_subparsers(dest="command")

    repl = sub.add_parser("repl", help="sesi interaktif (default saat tanpa subcommand)")
    run = sub.add_parser("run", help="satu prompt sekali jalan")
    run.add_argument("prompt")
    tok = sub.add_parser("tokens", help="dashboard token & biaya")
    tok.add_argument("session_id", nargs="?", default=None)
    res = sub.add_parser("resume", help="lanjutkan sesi lama (via ringkasan)")
    res.add_argument("session_id")
    sub.add_parser("sessions", help="daftar sesi")
    sub.add_parser("skills", help="daftar skill")

    # opsi global boleh ditulis sesudah subcommand juga (tanpa menimpa nilai global)
    for p in (repl, run, res):
        p.add_argument("--model", default=argparse.SUPPRESS)
        p.add_argument("--yes", action="store_true", default=argparse.SUPPRESS)
        p.add_argument("--cwd", default=argparse.SUPPRESS)

    args = parser.parse_args(argv)
    # default: tanpa subcommand → langsung agent menu / sesi interaktif
    if args.command is None:
        args.command = "repl"
    handlers = {
        "repl": cmd_repl,
        "run": cmd_run,
        "tokens": cmd_tokens,
        "resume": cmd_resume,
        "sessions": cmd_sessions,
        "skills": cmd_skills,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
