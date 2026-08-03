"""REPL — loop interaktif dhybrid-agent."""

from __future__ import annotations

import os

from dhybrid import __version__
from dhybrid.agent.hooks import Hooks
from dhybrid.agent.loop import AgentLoop, LoopConfig, LoopResult
from dhybrid.skills.loader import extract_skill_mentions, inject_skills, select_skills
from dhybrid.ui.commands import handle_command
from dhybrid.ui.render import stream_print, style
from dhybrid.ui.status import (
    format_status,  # noqa: F401  (API publik, dipakai doctor nanti)
)


def run_agent(ctx, prompt: str) -> LoopResult:
    """Jalankan satu task agent; kembalikan hasil (termasuk skor kualitas)."""
    # Saring chain escalation: hanya preset yang provider-nya enabled & resolvable.
    # Cegah 401/431: buang preset yang key-nya kosong (kecuali route gratis opencode-zen).
    raw_chain = ctx.model_cfg.chain or []
    chain: list[str] = []
    for preset in raw_chain:
        try:
            mc = ctx.registry.resolve(preset)
        except KeyError:
            continue  # provider disabled / preset tak dikenal → skip
        env = mc.api_key_env or ""
        # route gratis (opencode zen) boleh tanpa key; lainnya wajib ada key
        if env == "OPENCODE_ZEN_API_KEY" or (env and os.environ.get(env)):
            chain.append(preset)

    loop_cfg = LoopConfig(
        max_tool_output_chars=ctx.cfg.tool.get("max_output_chars", 8000),
        escalation_chain=chain,
    )

    def _client_factory(preset_name: str):
        # bila resolve kembali gagal (provider dinonaktifkan di tengah jalan),
        # lewati ke preset berikutnya daripada crash.
        from dhybrid.llm.providers import make_client
        try:
            return make_client(ctx.registry.resolve(preset_name))
        except KeyError:
            return None  # loop akan meng-escalate ulang / stop ramah

    loop = AgentLoop(
        ctx.router if ctx.router else ctx._fresh_client(),
        ctx.tools,
        ctx=ctx.ctx,
        budget=ctx.budget,
        cfg=loop_cfg,
        hooks=ctx.hooks,
        cwd=ctx.cwd,
        client_factory=_client_factory if chain else None,
        ask_state=ctx.ask_state,
    )
    result = loop.run(prompt, ctx.system_prompt)

    # simpan ke sesi (prompt kosong = kelanjutan jawaban user, tidak disimpan ganda)
    if prompt.strip():
        ctx.store.append_message(ctx.sid, "user", prompt[:2000])
    ctx.store.append_message(ctx.sid, "assistant", result.final_text[:4000])
    ctx.store.set_summary(
        ctx.sid,
        ctx.ctx.summary or "",
        result.final_text[:2000],
    )
    return result


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
    if getattr(ctx, "resumed_id", None):
        title = (ctx.store.get_session(ctx.sid) or {}).get("title", "") or ""
        suffix = f" — {title}" if title else ""
        print(style(f"  melanjutkan sesi terakhir di proyek ini: {ctx.resumed_id}{suffix}", "90"))
    print(f"  workspace   : {ctx.cwd}")
    print()
    print("  MENU — pilih dengan prefix /, atau langsung ketik pertanyaan:")
    print()
    print("  ⚙️  /settings           semua pengaturan: model (manual), key, preset, dsb")
    print("  🤖 /model <nama>        ganti model (preset / manual, mis. gpt-5.6-luna)   /key <prov> <nilai>  set key")
    print("  💰 /tokens              dashboard token & biaya               /compact             ringkas konteks")
    print("  📂 /sessions            sesi sebelumnya                       /clear               reset percakapan")
    print("  🧠 /skills              lihat & hidup/matikan skill           /help                semua perintah")
    print("  🎯 /skill <nama>        paksa pakai skill (off = otomatis)    @nama_skill di prompt juga bisa")
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


def _recent_user_history(ctx, n: int = 3) -> str:
    """Pesan user asli terakhir (tanpa injeksi sistem) untuk cocokkan skill.

    Supaya skill tetap relevan di percakapan panjang: user bilang "database"
    di awal, lalu "buatkan CRUD" — skill database tetap ikut ter-inject.
    """
    msgs = [
        m.content or ""
        for m in ctx.ctx.messages
        if m.role == "user" and not (m.content or "").lstrip().startswith("[")
    ]
    return "\n".join(m[:500] for m in msgs[-n:])


def _run_one(ctx, raw: str) -> None:
    # judul sesi dari prompt pertama
    if ctx.store.get_session(ctx.sid) and not ctx.store.get_session(ctx.sid)["title"].startswith("untitled"):
        pass
    else:
        ctx.store.conn.execute(
            "UPDATE sessions SET title=? WHERE id=?", (raw[:60], ctx.sid)
        )
        ctx.store.conn.commit()

    max_inject = ctx.cfg.skills.get("max_inject", 3)
    # @nama_skill di prompt = paksa skill itu; /skill <nama> = paksa untuk sesi.
    # Riwayat sesi ikut dicocokkan supaya skill tetap relevan di percakapan panjang.
    clean_raw, mentions = extract_skill_mentions(raw, {s.name for s in ctx.skills})
    force = mentions or (ctx.forced_skills or None)
    history = _recent_user_history(ctx)
    selected = select_skills(clean_raw, ctx.skills, history=history, force=force)
    prompt = inject_skills(
        clean_raw, ctx.skills,
        max_inject=max_inject,
        max_chars=ctx.cfg.skills.get("max_chars", 800),
        history=history,
        force=force,
    )
    if selected:
        shown = selected[:max_inject]
        tag = "paksa" if (mentions or ctx.forced_skills) else "aktif"
        print(style(f"[skill {tag}: {', '.join(shown)}]", "90"))
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
        result = run_agent(ctx, prompt)
        # tool ask_user dipanggil agent → tanya user, teruskan jawaban, lanjutkan
        while result.pending_question:
            pq = result.pending_question
            print(style("\n❓ " + str(pq.get("prompt", "?")), "1;36"))
            opts = pq.get("options") or []
            if opts:
                for i, o in enumerate(opts, 1):
                    print(f"   {i}. {o}")
                print("   (ketik nomor atau jawaban bebas — kosong = pilihan 1)")
            try:
                answer = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                answer = ""
            if not answer and opts:
                answer = opts[0]
            elif answer.isdigit() and opts:
                i = int(answer)
                if 1 <= i <= len(opts):
                    answer = opts[i - 1]
            result = run_agent(ctx, f"[jawaban user] {answer}")
    finally:
        ctx.hooks.on_delta = orig_delta
    final = result.final_text

    # jawaban final: tampilkan bila belum ter-stream (error / respons kosong / non-stream)
    if final and final.strip():
        if final.startswith("[error"):
            print(style(final, "31"))
        elif streamed["chars"] == 0:
            print(final)

    tp = result.tests_passed
    tmark = "✓" if tp else ("✗" if tp is False else "—")
    # format [done] yang rapi & profesional
    escl_tag = f" ⤴{result.escalation_count}" if result.escalated_quality else ""
    esc_msg = ""
    if result.escalated_quality:
        esc_msg = " (escalation: model → kuat)"
    print(style(
        "\n" + "─" * 44 + "\n"
        f" DONE — {ctx.budget.used:,} token · ${ctx.last_cost:.4f} "
        f"· kualitas {result.quality_score}/100{escl_tag} "
        f"· {result.files_created} file{esc_msg} "
        f"· test {tmark}\n"
        + "─" * 44,
        "90"
    ))
    if ctx.router:
        print(style(f"[routing: small={ctx.router.stats['small']} big={ctx.router.stats['big']}]{escl_tag}", "90"))

    # Auto-skill: sesi task nyata otomatis jadi skill (tanpa tanya manual).
    # Sapaan tanpa tool (mis. "haloo?") tidak menghasilkan skill.
    _auto_learn_skill(ctx, raw, final)


def _auto_learn_skill(ctx, raw: str, final: str) -> None:
    from dhybrid.skills.loader import (
        auto_skill_worthwhile,
        build_skill_md,
        slugify,
    )

    tools_used = [n for n, c in ctx.tools.tool_count.items() if c > 0]
    if not auto_skill_worthwhile(tools_used, ctx.tools.tool_count, final):
        return
    name = slugify(raw)
    if name == "task" or not any(c.isalpha() for c in name):
        # prompt tidak punya kata kunci bermakna (mis. user hanya ketik "4" / "123")
        # → bukan skill yang reusable; jangan buat sampah
        return
    desc = (raw.strip()[:70] or "task") + " — skill otomatis dari sesi nyata"
    steps = "\n".join(f"{i + 1}. pakai tool `{t}`" for i, t in enumerate(tools_used))
    md = build_skill_md(name, desc, raw.strip()[:150], tools_used, final, steps=steps)
    target = ctx.workspace / "skills" / name / "SKILL.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(md)
    print(style(f"  [skill otomatis] {name} → {target}", "90"))


def _make_hooks(ctx) -> Hooks:
    hooks = Hooks()
    hooks.on_delta = stream_print
    hooks.on_step = _make_step_hook(ctx)
    hooks.on_compaction = lambda summary: print(style(f"\n[kompaksi] {summary[:120]}...", "35"))
    hooks.on_tool = _tool_indicator
    return hooks


def _tool_indicator(name: str, args: dict, output: str) -> None:
    """Indikator tool ringkas + status: ⚙ nama(args) ✓ / ✗ (tanpa dump output)."""
    ok = not output.startswith("ERROR")
    mark = "✓" if ok else "✗"
    print(style(f"\n  ⚙ {name}({_short_args(args)}) {mark}", "90" if ok else "31"))


def _make_step_hook(ctx):
    """Catat usage & progres — TANPA statusline \r (dulu merusak teks streaming)."""

    def on_step(step: int, model: str, usage, budget_used: int) -> None:
        ctx.steps = step
        if usage is not None:
            ctx.record_usage(model, usage)

    return on_step


def _short_args(args: dict) -> str:
    """Ringkas argumen tool utk indikator — JANGAN bocorkan isi konten panjang."""
    parts = []
    for k, v in list(args.items())[:2]:
        if k == "content" and isinstance(v, str):
            parts.append(f"{k}=<{len(v)} chars>")
        else:
            s = str(v).replace("\n", " ")[:20]
            parts.append(f"{k}={s}")
    return ", ".join(parts)[:80]


def _has_api_key(ctx) -> bool:
    cfg = ctx.model_cfg
    if cfg.api_key():
        return True
    # route zen dengan model *-free tidak butuh API key
    return bool(cfg.base_url and "opencode.ai/zen" in cfg.base_url and "-free" in cfg.model)
