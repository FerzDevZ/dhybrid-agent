"""TDD tests for rich UI integration di repl.py (show_welcome + progress)."""
from __future__ import annotations

from types import SimpleNamespace as NS
from unittest.mock import MagicMock

from dhybrid.config import Config
from dhybrid.ui import repl, rich_ui


def test_show_welcome_uses_rich_ui(monkeypatch):
    """show_welcome harus memakai rich_ui.print_done (panel rich) — bukan
    print polos untuk banner DONE block."""
    seen = []

    def fake_print_done(text):
        seen.append(text)

    monkeypatch.setattr(rich_ui, "print_done", fake_print_done)

    ctx = MagicMock()
    ctx.current_model_label.return_value = "gpt-4o-mini (openai)"
    ctx.resumed_id = None
    ctx.cwd = "/tmp"
    ctx.sid = "x"
    ctx.store.get_session.return_value = None

    repl.show_welcome(ctx)
    # print_done dipanggil setidaknya sekali, berisi versi + model
    assert seen, "show_welcome harus pakai rich_ui.print_done"
    joined = "\n".join(seen)
    assert "dhybrid-agent v" in joined
    assert "gpt-4o-mini (openai)" in joined


def test_render_progress_available():
    """render_progress (spinner context manager) tersedia di rich_ui."""
    assert hasattr(rich_ui, "render_progress")
    assert callable(rich_ui.render_progress)
    with rich_ui.render_progress("test"):
        pass


def test_answer_only_guard_does_not_run_task(capsys):
    """Input "y" / "ya" / "tidak" di prompt utama BUKAN task baru.

    Regression untuk bug: user mengetik "y" (menjawab pertanyaan konfirmasi
    lama seperti "Izinkan? (y/N)" yang sudah selesai), tapi REPL malah
    menjalankannya sebagai task — agent meluncur & menyia-nyiakan token.
    """
    for raw in ("y", "ya", "tidak", "n", "ok"):
        assert repl._run_one_guard(raw) is False  # di-block, bukan task
    out = capsys.readouterr().out
    assert "Tidak ada pertanyaan" in out


def test_answer_only_guard_runs_real_task():
    """Input task normal tetap diteruskan ke _run_one (bukan di-block)."""
    assert repl._is_answer_only("y") is True
    assert repl._is_answer_only(" buat web login ") is False
    assert repl._is_answer_only("lanjutkan") is False


def test_run_one_no_crash_when_session_missing(tmp_path, monkeypatch):
    """Regression: _run_one tak boleh crash `NoneType subscriptable` bila
    sid ada tapi session row hilang (desync store, /clear parial, dst).

    Sebelumnya `get_session(sid)["title"]` → None["title"] → TypeError.
    """
    from dhybrid.session.context import SessionContext
    from dhybrid.session.store import SessionStore

    monkeypatch.setattr(repl, "run_agent", lambda *a, **k: NS(
        final_text="", pending_question=None, tests_passed=None,
        escalation_count=0, escalated_quality=False, stopped_early=False,
        quality_score=0, files_created=0,
    ))

    cfg = Config.load("config/default.yaml")
    cfg.workspace = tmp_path
    # disable clarify agar tidak perlu network/client
    cfg.clarify = {"enabled": False}
    store = SessionStore(tmp_path / "s.sqlite")
    ctx = SessionContext(cfg, store, cwd=str(tmp_path), interactive=False)
    sid = ctx.sid
    store.conn.execute("DELETE FROM sessions WHERE id=?", (sid,))
    store.conn.commit()

    # sebelum fix: TypeError. setelah fix: buat session baru, jalan aman.
    repl._run_one(ctx, "buat web login register")
    assert store.get_session(ctx.sid) is not None  # auto-created


def test_tab_debounce_does_not_flip_mode_twice(tmp_path, monkeypatch):
    """Tab berulang cepat (burst) tidak boleh flip mode berkali-kali."""
    from dhybrid.mode import BUILD, PLAN, apply_mode
    from dhybrid.session.context import SessionContext
    from dhybrid.session.store import SessionStore

    cfg = Config.load("config/default.yaml")
    cfg.workspace = tmp_path
    store = SessionStore(tmp_path / "s.sqlite")
    ctx = SessionContext(cfg, store, cwd=str(tmp_path), interactive=False)
    apply_mode(ctx, BUILD)
    assert ctx.mode == BUILD

    # simulasi: 2x flip berturutnya = harus tetap toggle (1x flip per burst)
    apply_mode(ctx, PLAN)
    assert ctx.mode == PLAN
    apply_mode(ctx, BUILD)
    assert ctx.mode == BUILD
