"""Task 12: saran buat skill saat fallback general dipakai ≥3x."""
from dhybrid.ui.repl import _maybe_suggest_skill


def test_suggest_after_3_fallback(tmp_path, monkeypatch, capsys):
    ctx, _, _ = _make_ctx(tmp_path, monkeypatch)
    ctx.fallback_uses = 3
    ctx.tools.tool_count = {"grep": 2}
    monkeypatch.setattr("builtins.input", lambda *a: "analisis-log")
    _maybe_suggest_skill(ctx, "tolong analisis log error ini", "ok selesai")
    out = capsys.readouterr().out
    assert "skill" in out.lower()
    assert (tmp_path / "skills" / "analisis-log" / "SKILL.md").exists()


def test_no_suggest_below_threshold(tmp_path, monkeypatch, capsys):
    ctx, _, _ = _make_ctx(tmp_path, monkeypatch)
    ctx.fallback_uses = 2
    _maybe_suggest_skill(ctx, "halo", "ok")
    assert capsys.readouterr().out == ""


def test_suggest_only_once(tmp_path, monkeypatch, capsys):
    ctx, _, _ = _make_ctx(tmp_path, monkeypatch)
    ctx.fallback_uses = 5
    ctx.skill_suggested = True
    _maybe_suggest_skill(ctx, "analisis log", "ok")
    assert capsys.readouterr().out == ""


from tests.unit.test_repl_clarify import _make_ctx
