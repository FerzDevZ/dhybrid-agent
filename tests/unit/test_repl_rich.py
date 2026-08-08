"""TDD tests for rich UI integration di repl.py (show_welcome + progress)."""
from __future__ import annotations

from unittest.mock import MagicMock

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
