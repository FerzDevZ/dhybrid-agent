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


def run_agent(ctx, prompt: str, push_prompt: bool = True) -> LoopResult:
    """Jalankan satu task agent; kembalikan hasil (termasuk skor kualitas).

    push_prompt=False dipakai untuk meneruskan jawaban user (ask_user) yang
    sudah di-push manual sebagai pesan biasa — jawaban TIDAK boleh diproses
    sebagai prompt (tidak di-parse tool-call, tidak memicu nudge build)."""
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
    result = loop.run(prompt, ctx.system_prompt, push_prompt=push_prompt)

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

    # REPL prompt: prompt_toolkit (TTY) — history search Ctrl-R, autocomplete
    # /command & nama skill, paste multi-line. Fallback: input() polos untuk
    # non-TTY (piped: `echo "halo" | dhybrid repl`) supaya scripting tetap jalan.
    history_file = ctx.workspace / "history"
    pt_session = None
    try:
        import sys as _sys

        if _sys.stdin.isatty():
            from prompt_toolkit import PromptSession
            from prompt_toolkit.history import FileHistory

            pt_session = PromptSession(history=FileHistory(str(history_file)))
    except (ImportError, OSError):
        pt_session = None

    # daftar kata untuk autocomplete: semua slash-command + nama skill
    SLASH_COMMANDS = [
        "/help", "/settings", "/setup", "/key", "/model", "/tokens", "/compact",
        "/clear", "/sessions", "/skills", "/skill", "/skill off", "/remember",
        "/rmem", "/forget", "/fmem", "/memories", "/mem", "/search-memory", "/quit",
    ]

    def _repl_prompt() -> str:
        nonlocal pt_session
        if pt_session is not None:
            from prompt_toolkit.completion import FuzzyCompleter, WordCompleter

            words = list(SLASH_COMMANDS)
            words += [s.name for s in ctx.all_skills]
            words += ["/skill " + s.name for s in ctx.all_skills]
            pt_session.completer = FuzzyCompleter(
                WordCompleter(sorted(set(words)), ignore_case=True)
            )
            return pt_session.prompt(style("dhybrid> ", "32")).strip()
        return input(style("dhybrid> ", "32")).strip()

    try:
        while True:
            try:
                raw = _repl_prompt()
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
        pass  # try/finally dipertahankan; history disimpan otomatis oleh FileHistory


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
            # jawaban user = PESAN biasa, bukan prompt: tidak di-parse tool-call,
            # tidak dicocokkan skill, tidak memicu nudge build.
            from dhybrid.llm.base import ChatMessage

            ctx.ctx.push(ChatMessage(role="user", content=f"[jawaban user] {answer}"))
            result = run_agent(ctx, "", push_prompt=False)
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
    # Hanya bila ada KARYA nyata (file dibuat / tool mutasi / test dijalankan) —
    # sapaan & eksplorasi ("haloo?", "lanjutkan") tidak menghasilkan skill.
    # Matikan: config skills.auto_learn=false atau env DHYBRID_NO_SKILL=1.
    if ctx.cfg.skills.get("auto_learn", True) and not os.environ.get("DHYBRID_NO_SKILL"):
        _auto_learn_skill(ctx, raw, final, result)

    # Debug dump: DHYBRID_DEBUG=1 → simpan konteks & hasil run ke file
    # (~/.dhybrid/debug/) untuk reproduksi masalah model/tool.
    if os.environ.get("DHYBRID_DEBUG"):
        _dump_debug(ctx, raw, result)


# Prompt receh yang tidak pernah layak jadi skill, apa pun hasilnya
TRIVIAL_SLUGS = {
    "hai", "halo", "hello", "hi", "hey", "p", "test", "tes", "coba", "cek",
    "check", "task", "ya", "iya", "ok", "oke", "yes", "sip", "mantap", "bagus",
    "thanks", "makasih", "terima-kasih", "lanjutkan", "lanjutin", "lanjut",
    "teruskan", "continue", "next", "silahkan", "ayo", "gas", "setuju",
    "apa", "siapa", "kapan", "dimana", "kenapa", "bagaimana",
}


def _auto_learn_skill(ctx, raw: str, final: str, result=None) -> None:
    from dhybrid.skills.loader import (
        auto_skill_worthwhile,
        build_skill_md,
        slugify,
    )

    tools_used = [n for n, c in ctx.tools.tool_count.items() if c > 0]
    files_created = result.files_created if result else 0
    tests_passed = result.tests_passed if result else None
    if not auto_skill_worthwhile(
        tools_used, ctx.tools.tool_count, final, files_created, tests_passed
    ):
        return
    name = slugify(raw)
    if name == "task" or not any(c.isalpha() for c in name) or name in TRIVIAL_SLUGS:
        # prompt tidak punya kata kunci bermakna (sapaan / "4" / "123" / "lanjutkan")
        # → bukan skill yang reusable; jangan buat sampah
        return
    if any(s.name == name for s in ctx.skills):
        # skill dengan nama sama sudah ada (repo/workspace) → jangan timpa
        return
    desc = (raw.strip()[:70] or "task") + " — skill otomatis dari sesi nyata"
    steps = "\n".join(f"{i + 1}. pakai tool `{t}`" for i, t in enumerate(tools_used))
    md = build_skill_md(name, desc, raw.strip()[:150], tools_used, final, steps=steps)
    target = ctx.workspace / "skills" / name / "SKILL.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(md)
    print(style(f"  [skill otomatis] {name} → {target}", "90"))


def _dump_debug(ctx, raw: str, result) -> None:
    """Simpan konteks + hasil run ke ~/.dhybrid/debug/ saat DHYBRID_DEBUG=1 —
    untuk reproduksi masalah prompt/model/tool tanpa harus menyalin terminal."""
    import json
    import time

    debug_dir = ctx.workspace / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    path = debug_dir / f"{ts}_{ctx.sid}.json"
    payload = {
        "session": ctx.sid,
        "prompt": raw,
        "model": ctx.model_cfg.model,
        "provider": ctx.model_cfg.provider,
        "result": {
            "final_text": getattr(result, "final_text", ""),
            "quality_score": getattr(result, "quality_score", None),
            "files_created": getattr(result, "files_created", None),
            "tests_passed": getattr(result, "tests_passed", None),
            "stopped_early": getattr(result, "stopped_early", None),
            "escalated": getattr(result, "escalated", None),
            "steps": getattr(result, "steps", None),
            "budget_used": getattr(result, "budget_used", None),
            "compacted": getattr(result, "compacted", None),
        },
        "tool_count": ctx.tools.tool_count,
        "messages": [
            {
                "role": m.role,
                "content": (m.content or "")[:2000],
                "tool_calls": getattr(m, "tool_calls", None),
            }
            for m in ctx.ctx.messages
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(style(f"[debug] dump: {path}", "90"))


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
