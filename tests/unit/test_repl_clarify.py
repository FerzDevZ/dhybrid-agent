"""Test REPL clarify pra-prompt — pilihan bernomor + Lanjutkan=default."""

import builtins
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
            yield from ()

        def complete(self, messages, **kw):
            from dhybrid.llm.base import ChatMessage, ChatResponse, Usage

            return ChatResponse(
                message=ChatMessage(role="assistant", content="ok"),
                usage=Usage(), model="stub",
            )

        def model_name(self):
            return "stub"

    monkeypatch.setattr(ctx_mod, "make_client", lambda cfg: _StubClient())
    captured = {"prompt": None, "push": True}

    def _fake_run_agent(ctx, prompt, push_prompt=True):
        captured["prompt"] = prompt
        captured["push"] = push_prompt
        return _stub_result()

    monkeypatch.setattr(repl_mod, "run_agent", _fake_run_agent)

    cfg = Config.load("config/default.yaml")
    cfg.workspace = tmp_path
    ctx = SessionContext(cfg, SessionStore(tmp_path / "s.sqlite"), cwd=str(tmp_path))
    return ctx, repl_mod, captured


def _last_user_msg(ctx) -> str:
    for m in reversed(ctx.ctx.messages):
        if m.role == "user":
            return m.content or ""
    return ""


def test_run_one_clarify_number_answer(tmp_path, monkeypatch, capsys):
    ctx, repl_mod, captured = _make_ctx(tmp_path, monkeypatch)
    monkeypatch.setattr(builtins, "input", lambda *a: "2")
    repl_mod._run_one(ctx, "buat web login register")
    out = capsys.readouterr().out
    assert "❓" in out
    assert "1. PHP (Laravel)" in out
    assert "(default)" in out
    assert "Lanjutkan" in out
    # keputusan masuk konteks + prompt agent memuatnya
    assert _last_user_msg(ctx) == "[keputusan user] Next.js"
    assert "Next.js" in captured["prompt"]
    assert ctx.clarify_just_answered is True


def test_run_one_clarify_lanjutkan_means_default(tmp_path, monkeypatch, capsys):
    ctx, repl_mod, _ = _make_ctx(tmp_path, monkeypatch)
    monkeypatch.setattr(builtins, "input", lambda *a: "lanjutkan")
    repl_mod._run_one(ctx, "buat web login")
    assert _last_user_msg(ctx) == "[keputusan user] PHP (Laravel)"


def test_run_one_clarify_empty_means_default(tmp_path, monkeypatch):
    ctx, repl_mod, _ = _make_ctx(tmp_path, monkeypatch)
    monkeypatch.setattr(builtins, "input", lambda *a: "")
    repl_mod._run_one(ctx, "buat web login")
    assert _last_user_msg(ctx) == "[keputusan user] PHP (Laravel)"


def test_run_one_clarify_free_text(tmp_path, monkeypatch):
    ctx, repl_mod, _ = _make_ctx(tmp_path, monkeypatch)
    monkeypatch.setattr(builtins, "input", lambda *a: "pakai golang aja")
    repl_mod._run_one(ctx, "buat web login")
    assert _last_user_msg(ctx) == "[keputusan user] pakai golang aja"


def test_run_one_no_clarify_for_explicit_stack(tmp_path, monkeypatch, capsys):
    ctx, repl_mod, captured = _make_ctx(tmp_path, monkeypatch)
    monkeypatch.setattr(builtins, "input", lambda *a: "2")
    repl_mod._run_one(ctx, "buat web login pakai laravel")
    out = capsys.readouterr().out
    assert "❓" not in out
    assert "[keputusan user]" not in _last_user_msg(ctx)
    assert "laravel" in captured["prompt"]


def test_run_one_skips_when_just_answered(tmp_path, monkeypatch, capsys):
    ctx, repl_mod, _ = _make_ctx(tmp_path, monkeypatch)
    ctx.clarify_just_answered = True  # turn sebelumnya = jawaban clarify
    monkeypatch.setattr(builtins, "input", lambda *a: "2")
    repl_mod._run_one(ctx, "buat web login")
    out = capsys.readouterr().out
    assert "❓" not in out
    assert "[keputusan user]" not in _last_user_msg(ctx)
    # flag sudah di-reset → turn berikutnya boleh clarify lagi
    assert ctx.clarify_just_answered is False


def test_run_one_clarify_disabled(tmp_path, monkeypatch, capsys):
    ctx, repl_mod, _ = _make_ctx(tmp_path, monkeypatch)
    ctx.cfg.clarify = {"enabled": False}
    monkeypatch.setattr(builtins, "input", lambda *a: "2")
    repl_mod._run_one(ctx, "buat web login")
    out = capsys.readouterr().out
    assert "❓" not in out
