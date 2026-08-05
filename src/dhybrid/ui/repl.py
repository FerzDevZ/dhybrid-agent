"""REPL — loop interaktif dhybrid-agent."""

from __future__ import annotations

import os

from dhybrid import __version__
from dhybrid.agent.hooks import Hooks
from dhybrid.agent.loop import AgentLoop, LoopConfig, LoopResult
from dhybrid.llm.base import ChatMessage
from dhybrid.skills.loader import extract_skill_mentions, inject_skills, select_skills
from dhybrid.ui import rich_ui
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
        clarify_state=getattr(ctx, "clarify_state", None),
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
    rich_ui.print_done(
        f"  dhybrid-agent v{__version__} — coding agent hemat token (hybrid routing)\n"
        f"  model utama : {ctx.current_model_label()}"
    )
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
        "/clear", "/sessions", "/shot", "/pasteshot", "/paste", "/skills", "/skill", "/skill off", "/remember",
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
            # prompt_toolkit TIDAK menerima string ber-ANSI (dirender literal
            # jadi "^[[32m..."); pakai FormattedText dengan nama warna ANSI.
            return pt_session.prompt([("ansigreen", "dhybrid> ")]).strip()
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
    # Reset buffer streaming output di non-TTY (cegah pecah karakter per baris)
    from dhybrid.ui.render import flush_stream
    flush_stream()  # aman di semua mode — no-op jika buffer kosong
    # judul sesi dari prompt pertama
    if ctx.store.get_session(ctx.sid) and not ctx.store.get_session(ctx.sid)["title"].startswith("untitled"):
        pass
    else:
        ctx.store.conn.execute(
            "UPDATE sessions SET title=? WHERE id=?",
            (raw[:60], ctx.sid),
        )
        ctx.store.conn.commit()

    # Clarify cerdas: prompt ambigu (mis. "buat web login" tanpa stack) → tanya
    # pilihan bernomor SEBELUM agent jalan (tanpa biaya token LLM). Jawaban
    # berupa angka / teks bebas / "Lanjutkan" (= default) masuk ke konteks
    # sebagai keputusan user & ikut memengaruhi pemilihan skill di bawah.
    # Turn setelah jawaban clarify TIDAK ditanya lagi (last_turn_was_answer).
    was_answered = getattr(ctx, "clarify_just_answered", False)
    ctx.clarify_just_answered = False
    clarify_cfg = getattr(ctx.cfg, "clarify", {}) or {}
    
    # Guard: max 1 clarify per turn untuk mencegah loop
    _clarify_done_this_turn = False
    
    if clarify_cfg.get("enabled", True) and ctx.ask_state.interactive:
        from dhybrid.agent.intent import detect_ambiguity

        hint = detect_ambiguity(
            raw,
            cwd=ctx.cwd,
            history=_recent_user_history(ctx),
            last_turn_was_answer=was_answered,
        )
        if hint and not _clarify_done_this_turn:
            # Pertanyaan digenerate AI (natural, selalu bervariasi); bila model
            # gagal/offline → fallback ke template pool (tetap bervariasi).
            if clarify_cfg.get("ai", True):
                try:
                    from dhybrid.agent.intent import generate_question

                    q = generate_question(raw, hint.options, ctx._fresh_client())
                    if q:
                        hint.question = q
                except Exception:  # noqa: BLE001,S110 — fallback template pool
                    pass  # pertanyaan template (pool) tetap dipakai
            opts = hint.options
            default_no = hint.default_index + 1
            print(style("\n❓ " + hint.question, "1;36"))
            for i, o in enumerate(opts, 1):
                mark = " (default)" if i == default_no else ""
                print(f"   {i}. {o}{mark}")
            print(
                style(
                    f"   (ketik nomor, teks bebas, atau Enter/Lanjutkan = opsi {default_no})",
                    "90",
                )
            )
            try:
                answer = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                answer = ""
            low = answer.lower()
            if not answer or low in ("lanjutkan", "l", "default", "ya", "y"):
                answer = opts[hint.default_index]
            elif answer.isdigit() and 1 <= int(answer) <= len(opts):
                answer = opts[int(answer) - 1]
            ctx.ctx.push(
                ChatMessage(role="user", content=f"[keputusan user] {answer}")
            )
            ctx.clarify_just_answered = True
            _clarify_done_this_turn = True
            raw = f"{raw}\n[stack dipilih: {answer}]"

    max_inject = ctx.cfg.skills.get("max_inject", 3)
    # @nama_skill di prompt = paksa skill itu; /skill <nama> = paksa untuk sesi.
    # Riwayat sesi ikut dicocokkan supaya skill tetap relevan di percakapan panjang.
    clean_raw, mentions = extract_skill_mentions(raw, {s.name for s in ctx.skills})
    force = mentions or (ctx.forced_skills or None)
    history = _recent_user_history(ctx)
    fallback_skill = ctx.cfg.skills.get("fallback", "general")
    selected = select_skills(
        clean_raw, ctx.skills, history=history, force=force, fallback=fallback_skill
    )
    prompt = inject_skills(
        clean_raw, ctx.skills,
        max_inject=max_inject,
        max_chars=ctx.cfg.skills.get("max_chars", 800),
        history=history,
        force=force,
        fallback=fallback_skill,
    )
    if selected:
        shown = selected[:max_inject]
        tag = "paksa" if (mentions or ctx.forced_skills) else "aktif"
        # transparan: skill umum cadangan ditandai (fallback) — user tahu
        # tidak ada skill khusus yang cocok, bukan diam-diam inject umum.
        note = (
            " (fallback)"
            if shown == ["general"] and not (mentions or ctx.forced_skills)
            else ""
        )
        if note:
            ctx.fallback_uses += 1
        print(style(f"[skill {tag}: {', '.join(shown)}{note}]", "90"))
    else:
        print(style("[skill aktif: (tidak ada yang cocok)]", "90"))
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
        with rich_ui.render_progress("menyelesaikan task"):
            result = run_agent(ctx, prompt)
        # tool ask_user dipanggil agent → tanya user, teruskan jawaban, lanjutkan
        # Guard: max 1 ask_user per turn untuk mencegah loop
        _ask_done_this_turn = False
        
        while result.pending_question and not _ask_done_this_turn:
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
            ctx.ctx.push(ChatMessage(role="user", content=f"[jawaban user] {answer}"))
            result = run_agent(ctx, "", push_prompt=False)
            _ask_done_this_turn = True
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
    # format [done] yang rapi & profesional (rich Panel saat TTY)
    escl_tag = f" ⤴{result.escalation_count}" if result.escalated_quality else ""
    esc_msg = ""
    if result.escalated_quality:
        esc_msg = " (escalation: model → kuat)"
    if result.stopped_early:
        esc_msg += " (belum ada bukti file dibuat)"
    from dhybrid.ui.rich_ui import print_done

    label = " STUCK" if result.stopped_early else " DONE"
    print_done(
        f"{label} — {ctx.budget.used:,} token · ${ctx.last_cost:.4f} "
        f"· kualitas {result.quality_score}/100{escl_tag} "
        f"· {result.files_created} file{esc_msg} "
        f"· test {tmark}"
    )
    if ctx.router:
        print(style(f"[routing: small={ctx.router.stats['small']} big={ctx.router.stats['big']}]{escl_tag}", "90"))

    # Auto-skill: sesi task nyata otomatis jadi skill (tanpa tanya manual).
    # Hanya bila ada KARYA nyata (file dibuat / tool mutasi / test dijalankan) —
    # sapaan & eksplorasi ("haloo?", "lanjutkan") tidak menghasilkan skill.
    # Matikan: config skills.auto_learn=false atau env DHYBRID_NO_SKILL=1.
    if ctx.cfg.skills.get("auto_learn", True) and not os.environ.get("DHYBRID_NO_SKILL"):
        _auto_learn_skill(ctx, raw, final, result)
        # (0.9.0) auto-skill lebih cerdas: saran fallback general ≥3x +
        # digest kandidat skill di akhir sesi (pilihan bernomor).
        _maybe_suggest_skill(ctx, raw, final)
        _maybe_skill_digest(ctx)
    ctx.run_count += 1

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
    ctx.qa_history.append(raw)
    worthwhile = auto_skill_worthwhile(
        tools_used, ctx.tools.tool_count, final, files_created, tests_passed
    )
    name = slugify(raw)
    usable = name != "task" and any(c.isalpha() for c in name) and name not in TRIVIAL_SLUGS
    if not usable:
        # prompt tanpa kata kunci bermakna (sapaan / "4" / "123" / "lanjutkan").
        # Task nyata tetap jadi KANDIDAT digest akhir sesi (bukan sampah skill).
        if worthwhile:
            cand = _candidate_name(raw, tools_used)
            if not any(c["name"] == cand for c in ctx.skill_candidates):
                desc = (raw.strip()[:70] or cand) + " — skill otomatis dari sesi nyata"
                steps = "\n".join(f"{i + 1}. pakai tool `{t}`" for i, t in enumerate(tools_used))
                md = build_skill_md(cand, desc, raw.strip()[:150], tools_used, final, steps=steps)
                ctx.skill_candidates.append({"name": cand, "md": md})
        return
    if not worthwhile:
        # jalur pengetahuan (0.9.0): Q&A berulang (rapidfuzz ≥70%) dengan
        # jawaban substantif → skill knowledge, tanpa syarat file dibuat.
        if (
            final
            and not final.startswith("[error")
            and len(final) >= 100
            and _is_repeated_question_prompt(raw, ctx.qa_history[:-1])
            and not any(s.name == name for s in ctx.skills)
        ):
            desc = (raw.strip()[:70] or name) + " — skill pengetahuan otomatis dari Q&A berulang"
            md = build_skill_md(name, desc, raw.strip()[:150], tools_used, final, kind="knowledge")
            _write_skill(ctx, name, md)
        return
    # jalur task: prosedur nyata (file dibuat / tool mutasi / test dijalankan)
    desc = (raw.strip()[:70] or name) + " — skill otomatis dari sesi nyata"
    steps = "\n".join(f"{i + 1}. pakai tool `{t}`" for i, t in enumerate(tools_used))
    md = build_skill_md(name, desc, raw.strip()[:150], tools_used, final, steps=steps)
    existing = next((s for s in ctx.skills if s.name == name), None)
    if existing:
        # (0.9.0) hanya timpa skill LAHIR dari auto-skill — skill buatan tangan
        # user tidak pernah disentuh — dan hanya bila langkah baru lebih lengkap.
        if "skill otomatis" not in (existing.description or ""):
            return
        if not _should_update_skill(existing.body or "", md):
            return
        md += "\n\n*(diperbarui dari sesi nyata — langkah lebih lengkap)*"
    _write_skill(ctx, name, md)


def _write_skill(ctx, name: str, md: str) -> None:
    """Tulis SKILL.md ke workspace auto-skill + feedback singkat."""
    target = ctx.workspace / "skills" / name / "SKILL.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(md)
    print(style(f"  [skill otomatis] {name} → {target}", "90"))


def _is_repeated_question_prompt(
    prompt: str, history: list[str], thresh: float = 0.75
) -> bool:
    """Pertanyaan yang sama/jenis sama pernah ditanyakan sebelumnya (rapidfuzz).

    token_set_ratio: toleran terhadap urutan kata beda ("cara install breeze"
    vs "bagaimana cara install breeze"), tapi beda topik tetap terpisah
    ("apa itu flutter?" vs "apa itu laravel?" = 68% < 75%).
    """
    from rapidfuzz import fuzz

    p = prompt.lower().strip()
    return any(fuzz.token_set_ratio(p, h.lower()) >= thresh * 100 for h in history[-6:])


def _should_update_skill(old_steps: str, new_steps: str) -> bool:
    """Sesi baru layak menimpa skill lama bila langkahnya jelas lebih lengkap."""
    return len(new_steps.strip().splitlines()) > len(old_steps.strip().splitlines()) + 1


def _candidate_name(raw: str, tools_used: list[str]) -> str:
    """Nama kandidat skill saat slugify gagal memberi nama bermakna."""
    from dhybrid.skills.loader import slugify

    name = slugify(raw)
    if name != "task" and any(c.isalpha() for c in name) and name not in TRIVIAL_SLUGS:
        return name
    return f"task-{tools_used[0]}" if tools_used else "task"


def _maybe_skill_digest(ctx) -> None:
    """(0.9.0) Akhir sesi: tawarkan kandidat skill yang belum tersimpan.

    Muncul maksimal 1x per sesi, hanya bila ≥5 run & ada kandidat.
    Enter = simpan semua, nomor = pilih satu, 0/skip = lewati."""
    if ctx.skill_digest_shown or ctx.run_count < 5 or not ctx.skill_candidates:
        return
    ctx.skill_digest_shown = True
    print(style("\n💡 Beberapa task sukses bisa jadi skill reusable:", "1;33"))
    for i, c in enumerate(ctx.skill_candidates, 1):
        print(f"   {i}. {c['name']}")
    print("   (ketik nomor, Enter = simpan semua, 0 = skip)")
    try:
        ans = input("> ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        ans = ""
    if not ans or ans in ("lanjutkan", "l", "ya", "y"):
        picked = list(ctx.skill_candidates)
    elif ans.isdigit() and 1 <= int(ans) <= len(ctx.skill_candidates):
        picked = [ctx.skill_candidates[int(ans) - 1]]
    else:
        picked = []
    for c in picked:
        _write_skill(ctx, c["name"], c["md"])
    if picked:
        print(style(f"  [skill tersimpan] {', '.join(c['name'] for c in picked)}", "90"))


def _maybe_suggest_skill(ctx, raw: str, final: str) -> None:
    """(0.9.0) Fallback general ≥3x → tawarkan membuat skill spesifik.

    Sekali per sesi; ketik nama → simpan, Enter/skip → lewati."""
    if ctx.fallback_uses < 3 or ctx.skill_suggested:
        return
    ctx.skill_suggested = True
    print(
        style(
            "\n💡 Banyak prompt belum tertangkap skill spesifik (fallback general ≥3x).",
            "1;33",
        )
    )
    from dhybrid.skills.loader import build_skill_md, slugify

    name = slugify(raw)
    if name == "task" or not any(c.isalpha() for c in name) or name in TRIVIAL_SLUGS:
        return
    print(f"   Ketik nama skill untuk menyimpan pola ini (mis. '{name}'), atau Enter untuk skip.")
    try:
        ans = input("> ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        ans = ""
    if ans and ans not in ("skip", "tidak", "no", "0"):
        tools_used = [n for n, c in ctx.tools.tool_count.items() if c > 0]
        desc = ans + " — skill otomatis dari sesi nyata"
        steps = "\n".join(f"{i + 1}. pakai tool `{t}`" for i, t in enumerate(tools_used))
        md = build_skill_md(ans, desc, raw.strip()[:150], tools_used, final, steps=steps)
        _write_skill(ctx, ans, md)


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
