"""Integration test — seluruh stack (config → context → router → tools → store)."""


from dhybrid.config import Config
from dhybrid.llm.base import ChatMessage, ChatResponse, LLMClient, StreamEvent, Usage
from dhybrid.session.context import SessionContext
from dhybrid.session.store import SessionStore
from dhybrid.ui.repl import run_agent


class StubClient(LLMClient):
    """Balas turn1 = panggil tool grep; turn2 = jawaban final."""

    def __init__(self):
        self.calls = 0

    def stream(self, messages, **kw):
        self.calls += 1
        if self.calls == 1:
            yield StreamEvent(kind="tool_call", tool_call={"id": "t1", "name": "grep", "arguments": {"pattern": "def main"}})
        else:
            yield StreamEvent(kind="delta", text="ketemu: src/a.py:1 def main")
        yield StreamEvent(kind="done", usage=Usage(prompt_tokens=30, completion_tokens=10))

    def complete(self, messages, **kw):
        return ChatResponse(message=ChatMessage(role="assistant", content="ok"), usage=Usage(), model="stub")

    def model_name(self):
        return "stub-model"


def test_full_stack(monkeypatch, tmp_path):
    import dhybrid.session.context as ctx_mod

    monkeypatch.setattr(ctx_mod, "make_client", lambda cfg: StubClient())

    cfg = Config.load("config/default.yaml")
    cfg.workspace = tmp_path
    store = SessionStore(tmp_path / "s.sqlite")
    ctx = SessionContext(cfg, store, cwd=str(tmp_path))

    # tools terdaftar & allowlist berlaku
    assert len(ctx.tools.specs()) > 0

    final = run_agent(ctx, "cari fungsi def main")
    assert "ketemu: src/a.py:1 def main" in final

    # usage tercatat di SQLite
    rows = store.usage(ctx.sid)
    assert rows and rows[0]["prompt"] >= 30
    assert store.get_session(ctx.sid) is not None
    # pesan tersimpan untuk resume
    assert len(store.last_messages(ctx.sid)) >= 2

    # default config: SATU model (tanpa router) — semua tugas via model utama
    assert ctx.router is None


def test_skills_injected_into_prompt(monkeypatch, tmp_path):
    import dhybrid.session.context as ctx_mod

    monkeypatch.setattr(ctx_mod, "make_client", lambda cfg: StubClient())
    # buat skill tdd di workspace agar ter-inject
    sk_dir = tmp_path / "skills" / "tdd"
    sk_dir.mkdir(parents=True)
    (sk_dir / "SKILL.md").write_text(
        "---\nname: tdd\ndescription: TDD test driven development tulis test dulu\n---\nTDD: RED GREEN REFACTOR\n"
    )
    cfg = Config.load("config/default.yaml")
    cfg.workspace = tmp_path
    ctx = SessionContext(cfg, SessionStore(tmp_path / "s.sqlite"), cwd=str(tmp_path))
    assert ctx.skills and ctx.skills[0].name == "tdd"
    # prompt dengan kata "test" harus memicu inject skill
    from dhybrid.skills.loader import inject_skills

    out = inject_skills("bantu saya pakai TDD untuk fitur ini", ctx.skills)
    assert "[SKILL: tdd]" in out
