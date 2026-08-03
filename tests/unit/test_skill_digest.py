"""Task 11: digest kandidat skill di akhir sesi (pilihan bernomor)."""
from dhybrid.ui.repl import _maybe_skill_digest


def test_digest_offers_candidates(tmp_path, monkeypatch, capsys):
    ctx, _, _ = _make_ctx(tmp_path, monkeypatch)
    ctx.run_count = 6
    ctx.skill_candidates = [
        {"name": "buat-login", "md": "md-login"},
        {"name": "setup-docker", "md": "md-docker"},
    ]
    monkeypatch.setattr("builtins.input", lambda *a: "1")
    _maybe_skill_digest(ctx)
    out = capsys.readouterr().out
    assert "buat-login" in out and "skill" in out.lower()
    assert ctx.skill_digest_shown is True
    assert (ctx.workspace / "skills" / "buat-login" / "SKILL.md").read_text() == "md-login"
    assert not (ctx.workspace / "skills" / "setup-docker" / "SKILL.md").exists()


def test_digest_enter_saves_all(tmp_path, monkeypatch, capsys):
    ctx, _, _ = _make_ctx(tmp_path, monkeypatch)
    ctx.run_count = 5
    ctx.skill_candidates = [
        {"name": "buat-login", "md": "md-login"},
        {"name": "setup-docker", "md": "md-docker"},
    ]
    monkeypatch.setattr("builtins.input", lambda *a: "")
    _maybe_skill_digest(ctx)
    assert (ctx.workspace / "skills" / "setup-docker" / "SKILL.md").read_text() == "md-docker"


def test_digest_skips_when_few_runs(tmp_path, monkeypatch, capsys):
    ctx, _, _ = _make_ctx(tmp_path, monkeypatch)
    ctx.run_count = 2
    ctx.skill_candidates = [{"name": "buat-login", "md": "x"}]
    _maybe_skill_digest(ctx)
    assert capsys.readouterr().out == ""


def test_digest_zero_skips(tmp_path, monkeypatch, capsys):
    ctx, _, _ = _make_ctx(tmp_path, monkeypatch)
    ctx.run_count = 7
    ctx.skill_candidates = [{"name": "buat-login", "md": "x"}]
    monkeypatch.setattr("builtins.input", lambda *a: "0")
    _maybe_skill_digest(ctx)
    assert not (ctx.workspace / "skills" / "buat-login" / "SKILL.md").exists()


from tests.unit.test_repl_clarify import _make_ctx
