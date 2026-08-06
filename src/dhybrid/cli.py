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


def _build_context(args, resume: bool = False, sid: str | None = None, interactive: bool = True) -> SessionContext:
    cfg = Config.load(Path(args.config) if args.config else None)
    store = SessionStore(cfg.workspace / "sessions.sqlite")
    # normalisasi cwd (absolut + resolve symlink) supaya auto-resume konsisten
    # antar pemanggilan: `dhybrid repl` (cwd=".") dan `dhybrid --cwd /x/repl`
    # dari folder yg sama harus dianggap proyek yang sama.
    cwd = str(Path(args.cwd or ".").expanduser().resolve())
    ctx = SessionContext(cfg, store, cwd=cwd, yes_mode=getattr(args, "yes", False), resume=resume, sid=sid, interactive=interactive)
    if getattr(args, "model", None):
        ctx.set_model(args.model)
    return ctx


def cmd_repl(args) -> int:
    ctx = _build_context(args, resume=not getattr(args, "fresh", False), interactive=True)
    return repl_loop(ctx)


def cmd_run(args) -> int:
    # one-shot: non-interaktif — tool ask_user diblokir, agent pilih default sendiri
    ctx = _build_context(args, interactive=False)
    if getattr(args, "json", False):
        import json

        result = run_agent(ctx, args.prompt)
        payload = {
            "session": ctx.sid,
            "model": ctx.model_cfg.model,
            "provider": ctx.model_cfg.provider,
            "final_text": result.final_text,
            "quality_score": result.quality_score,
            "files_created": result.files_created,
            "tests_passed": result.tests_passed,
            "stopped_early": result.stopped_early,
            "escalated": result.escalated,
            "escalation_count": result.escalation_count,
            "steps": result.steps,
            "token_used": ctx.budget.used,
            "cost_usd": round(ctx.last_cost, 6),
        }
        print(json.dumps(payload, ensure_ascii=False))
        return 0
    print(f"dhybrid: {ctx.current_model_label()}")
    result = run_agent(ctx, args.prompt)
    print()
    print(result.final_text)
    tp = result.tests_passed
    tmark = "✓" if tp else ("✗" if tp is False else "—")
    escl_tag = f" ⤴{result.escalation_count}" if result.escalated_quality else ""
    esc_msg = " (escalation: model → kuat)" if result.escalated_quality else ""
    if result.stopped_early:
        esc_msg += " (belum ada bukti file dibuat)"
    # stopped_early=True bisa berarti task selesai natural atau STUCK
    from dhybrid.efficiency.lazy import needs_change_check
    from dhybrid.ui.rich_ui import print_done
    is_natural_stop = needs_change_check(result.final_text)
    label = " DONE" if (result.stopped_early and is_natural_stop) else (" STUCK" if result.stopped_early else " DONE")
    print_done(
        f"{label} — {ctx.budget.used:,} token · ${ctx.last_cost:.4f} "
        f"· kualitas {result.quality_score}/100{escl_tag} "
        f"· {result.files_created} file{esc_msg} "
        f"· test {tmark} · sesi: {ctx.sid}"
    )
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
    totals = {"prompt": tot_p, "completion": tot_c, "cached": tot_cached, "cost": cost}
    per_session: list[tuple[str, dict]] | None = None
    if not args.session_id:
        by_sess: dict[str, dict] = {}
        for r in rows:
            b = by_sess.setdefault(r["session_id"], {"prompt": 0, "completion": 0, "cached": 0, "cost": 0.0})
            b["prompt"] += r["prompt"]; b["completion"] += r["completion"]
            b["cached"] += r["cached"]; b["cost"] += r["cost"]
        per_session = sorted(by_sess.items())
    from dhybrid.ui.rich_ui import print_tokens

    print_tokens(label, totals, per_session)
    if tot_cached:
        print(f"  hemat cache  : ~{tot_cached:,} token input tidak dibayar ulang")
    return 0


def cmd_resume(args) -> int:
    from dhybrid.llm.base import ChatMessage

    cfg = Config.load(Path(args.config) if args.config else None)
    store = SessionStore(cfg.workspace / "sessions.sqlite")
    info = store.get_session(args.session_id)
    if not info:
        print(f"ERROR: sesi {args.session_id} tidak ditemukan")
        return 1
    # sid diteruskan → SessionContext TIDAK membuat sesi baru (tidak ada orphan).
    ctx = _build_context(args, sid=args.session_id)
    ctx.ctx.summary = info["summary"] or None
    for m in store.last_messages(args.session_id, n=5):
        ctx.ctx.push(ChatMessage(role=m["role"], content=m.get("content") or ""))
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


def cmd_doctor(args) -> int:
    from dhybrid.doctor import run_doctor

    cfg = Config.load(Path(args.config) if args.config else None)
    return run_doctor(cfg, offline=args.offline)


def cmd_self_update(args) -> int:
    from dhybrid.updater import self_update

    print(self_update())
    return 0


def cmd_install(args) -> int:
    """Run the installer (reinstall/update)."""
    import os
    import subprocess
    
    install_dir = os.path.expanduser("~/.dhybrid-agent")
    script_path = os.path.join(install_dir, "install.sh")
    
    if not os.path.exists(script_path):
        print(f"ERROR: install.sh not found at {script_path}")
        print("Run the one-liner instead:")
        print("  curl -fsSL https://raw.githubusercontent.com/FerzDevZ/dhybrid-agent/main/install.sh | bash")
        return 1
    
    env = os.environ.copy()
    if getattr(args, 'use_uv', False):
        env['DHYBRID_USE_UV'] = '1'
    if getattr(args, 'branch', None):
        env['DHYBRID_BRANCH'] = args.branch
    if getattr(args, 'install_dir', None):
        env['DHYBRID_INSTALL_DIR'] = args.install_dir
    
    result = subprocess.run(["bash", script_path], env=env, check=False)
    return result.returncode


def main(argv: list[str] | None = None) -> int:
    load_standard_dotenvs()
    parser = argparse.ArgumentParser(
        prog="dhybrid",
        description="dhybrid-agent — CLI coding agent hemat token (hybrid routing). "
                    "Tanpa subcommand = langsung masuk sesi interaktif.\n"
                    "Subcommands: repl, run, tokens, resume, sessions, skills, doctor, self-update, install",
    )
    parser.add_argument("--version", action="version", version=f"dhybrid-agent {__version__}")
    parser.add_argument("--config", default=None, help="path config.yaml (default: config/default.yaml)")
    parser.add_argument("--cwd", default=None, help="working directory")
    parser.add_argument("--model", default=None, help="preset model utama (mis. anthropic-big)")
    parser.add_argument("--yes", action="store_true", help="non-interaktif: tolak perintah berbahaya otomatis")
    parser.add_argument("--list-presets", action="store_true", help="cetak daftar preset (untuk shell completion)")
    sub = parser.add_subparsers(dest="command")

    repl = sub.add_parser("repl", help="sesi interaktif (default saat tanpa subcommand)")
    repl.add_argument("--fresh", action="store_true",
                      help="mulai sesi BARU (jangan auto-resume sesi terakhir di proyek ini)")
    run = sub.add_parser("run", help="satu prompt sekali jalan")
    run.add_argument("prompt")
    run.add_argument("--json", action="store_true",
                     help="output JSON terstruktur (final_text, skor, token, biaya)")
    tok = sub.add_parser("tokens", help="dashboard token & biaya")
    tok.add_argument("session_id", nargs="?", default=None)
    res = sub.add_parser("resume", help="lanjutkan sesi lama (via ringkasan)")
    res.add_argument("session_id")
    sub.add_parser("sessions", help="daftar sesi")
    sub.add_parser("skills", help="daftar skill")
    doc = sub.add_parser("doctor", help="diagnosa config, key, koneksi, update")
    doc.add_argument("--offline", action="store_true", help="tanpa cek network")
    sub.add_parser("self-update", help="perbarui dhybrid-agent dari GitHub")
    inst = sub.add_parser("install", help="jalankan installer (reinstall/update)")
    inst.add_argument("--use-uv", action="store_true", help="gunakan uv untuk install lebih cepat")
    inst.add_argument("--branch", default=None, help="branch git (default: main)")
    inst.add_argument("--install-dir", default=None, help="direktori instalasi (default: ~/.dhybrid-agent)")

    # opsi global boleh ditulis sesudah subcommand juga (tanpa menimpa nilai global)
    for p in (repl, run, res, inst):
        p.add_argument("--model", default=argparse.SUPPRESS)
        p.add_argument("--yes", action="store_true", default=argparse.SUPPRESS)
        p.add_argument("--cwd", default=argparse.SUPPRESS)

    args = parser.parse_args(argv)
    if args.list_presets:
        cfg = Config.load(Path(args.config) if args.config else None)
        print("\n".join(sorted(cfg.presets)))
        return 0
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
        "doctor": cmd_doctor,
        "self-update": cmd_self_update,
        "install": cmd_install,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
