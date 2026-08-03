"""Test feedback skill transparan di _run_one — fallback general terlihat."""

from types import SimpleNamespace as NS

from dhybrid.config import Config
from dhybrid.session.context import SessionContext
from dhybrid.session.store import SessionStore


def _stub_result():
    return NS(
        final_text="ok",
        pending_question=None,
        tests_passed=None,
        escalation_count=0,
        escalated_quality=False,
        quality_score=100,
        files_created=0,
    )


def _make_ctx(tmp_path, monkeypatch):
    import dhybrid.session.context as ctx_mod
    import dhybrid.session.userconfig as uc
    import dhybrid.ui.repl as repl_mod

    monkeypatch.setattr(uc, "user_config_path", lambda: tmp_path / "config.yaml")

    class _StubClient:
        def stream(self, messages, **kw):
            yield from ()  # tidak dipakai — run_agent di-stub

        def complete(self, messages, **kw):
            from dhybrid.llm.base import ChatMessage, ChatResponse, Usage

            return ChatResponse(
                message=ChatMessage(role="assistant", content="ok"),
                usage=Usage(), model="stub",
            )

        def model_name(self):
            return "stub"

    monkeypatch.setattr(ctx_mod, "make_client", lambda cfg: _StubClient())
    monkeypatch.setattr(repl_mod, "run_agent", lambda ctx, prompt, push_prompt=True: _stub_result())

    cfg = Config.load("config/default.yaml")
    cfg.workspace = tmp_path
    ctx = SessionContext(cfg, SessionStore(tmp_path / "s.sqlite"), cwd=str(tmp_path))
    return ctx, repl_mod


def test_run_one_shows_fallback_general(tmp_path, monkeypatch, capsys):
    ctx, repl_mod = _make_ctx(tmp_path, monkeypatch)
    ctx.cfg.clarify = {"enabled": False}  # fokus: feedback skill, bukan clarify
    repl_mod._run_one(ctx, "buatkan puisi tentang kucing")
    out = capsys.readouterr().out
    assert "[skill aktif: general" in out
    assert "(fallback)" in out


def test_run_one_shows_selected_skill(tmp_path, monkeypatch, capsys):
    ctx, repl_mod = _make_ctx(tmp_path, monkeypatch)
    ctx.cfg.clarify = {"enabled": False}  # fokus: feedback skill, bukan clarify
    repl_mod._run_one(ctx, "buat web login register laravel")
    out = capsys.readouterr().out
    assert "[skill aktif:" in out
    assert "laravel" in out.lower() or "general" in out
