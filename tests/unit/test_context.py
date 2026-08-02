from dhybrid.efficiency.compress import compact_conversation
from dhybrid.efficiency.context import ContextManager
from dhybrid.llm.base import ChatMessage, ChatResponse, Usage


class FakeClient:
    def __init__(self, out="Tujuan: fix bug"):
        self.out = out

    def complete(self, messages, **kw):
        assert kw.get("max_tokens") is not None
        return ChatResponse(message=ChatMessage(role="assistant", content=self.out), usage=Usage(), model="fake")

    def stream(self, messages, **kw):
        raise NotImplementedError


def _msgs(n):
    return [ChatMessage(role="user" if i % 2 == 0 else "assistant", content=f"m{i}") for i in range(n)]


def test_compaction_keeps_recent():
    cm = ContextManager(keep_recent=4)
    for m in _msgs(10):
        cm.push(m)
    assert len(cm.candidates_for_compaction()) == 6
    cm.apply_compaction("ringkasan")
    assert cm.compactions == 1
    assert len(cm.messages) == 4
    rendered = cm.render("SYS")
    assert rendered[0].content == "SYS"
    assert rendered[1].content.startswith("Berikut ringkasan")


def test_no_compaction_when_small():
    cm = ContextManager(keep_recent=8)
    for m in _msgs(3):
        cm.push(m)
    assert cm.candidates_for_compaction() == []
    cm.apply_compaction("x")
    assert cm.compactions == 0


def test_render_includes_system_and_summary():
    cm = ContextManager(keep_recent=2)
    cm.push(ChatMessage(role="user", content="halo"))
    out = cm.render("SYS")
    assert out[0].role == "system" and out[0].content == "SYS"
    assert out[1].role == "user"


def test_compact_conversation_uses_client():
    out = compact_conversation(FakeClient("Tujuan: fix bug"), [ChatMessage(role="user", content="a")])
    assert out == "Tujuan: fix bug"
