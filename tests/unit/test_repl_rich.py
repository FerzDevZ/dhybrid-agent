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
