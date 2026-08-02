from dhybrid.agent.loop import AgentLoop, LoopConfig
from dhybrid.agent.router import HybridRouter
from dhybrid.efficiency.budget import TokenBudget
from dhybrid.efficiency.context import ContextManager
from dhybrid.llm.base import ChatMessage, ChatResponse, LLMClient, StreamEvent, Usage
from dhybrid.tools.registry import ToolRegistry


class ScriptedClient(LLMClient):
    def __init__(self, replies, name="fake"):
        self.replies = replies
        self.name = name
        self.calls = 0
        self.last_messages = None

    def stream(self, messages, **kw):
        self.calls += 1
        self.last_messages = messages
        if self.calls <= len(self.replies):
            r = self.replies[self.calls - 1]
            if r.startswith("tool:"):
                _, name, arg = r.split(":", 2)
                yield StreamEvent(kind="tool_call", tool_call={"id": "t1", "name": name, "arguments": {"q": arg}})
            elif r == "errtool":
                yield StreamEvent(kind="tool_call", tool_call={"id": "t1", "name": "boom", "arguments": {}})
            else:
                text = r.removeprefix("text:")
                yield StreamEvent(kind="delta", text=text)
        else:
            yield StreamEvent(kind="delta", text="selesai")
        yield StreamEvent(kind="done", usage=Usage(prompt_tokens=10, completion_tokens=5))

    def complete(self, messages, **kw):
        return ChatResponse(message=ChatMessage(role="assistant", content="ok"), usage=Usage(), model=self.name)

    def model_name(self):
        return self.name


def _tools():
    reg = ToolRegistry()
    reg.register("grep", "cari", {"q": {"type": "string"}}, lambda q: f"src/a.py:1: {q}")
    reg.register("boom", "gagal", {}, lambda: 1 / 0)
    return reg


def test_loop_tool_then_final():
    loop = AgentLoop(
        ScriptedClient(["tool:grep:x", "text:ketemu: line 1"]),
        _tools(),
        ContextManager(),
        TokenBudget(soft=10**9, hard=10**9),
    )
    res = loop.run("cari x", "kamu agent")
    assert res.final_text == "ketemu: line 1"
    assert res.steps == 2


def test_loop_early_stop_signal():
    loop = AgentLoop(
        ScriptedClient(["text:TIDAK ADA YANG PERLU DIUBAH."]),
        _tools(),
        ContextManager(),
        TokenBudget(soft=10**9, hard=10**9),
    )
    res = loop.run("cek", "sys")
    assert res.stopped_early


def test_loop_budget_hard_stop():
    loop = AgentLoop(
        ScriptedClient(["tool:grep:x", "tool:grep:x", "tool:grep:x"]),
        _tools(),
        ContextManager(),
        TokenBudget(soft=10, hard=15),  # setiap step +15 → habis cepat
        cfg=LoopConfig(max_steps=10),
    )
    res = loop.run("cari", "sys")
    assert res.budget_exhausted


def test_loop_escalates_to_big_on_errors():
    small = ScriptedClient(["errtool", "errtool", "text:jawaban kecil"], name="small")
    big = ScriptedClient(["text:jawaban besar"], name="big")
    router = HybridRouter(big_client=big, small_client=small, cache=None)
    loop = AgentLoop(router, _tools(), ContextManager(), TokenBudget(soft=10**9, hard=10**9))
    res = loop.run("jalankan pytest lalu perbaiki", "sys")
    assert res.escalated
    assert res.final_text == "jawaban besar"


def test_loop_tool_errors_dont_loop_forever():
    loop = AgentLoop(
        ScriptedClient(["errtool", "errtool", "errtool", "text:akhir"]),
        _tools(),
        ContextManager(),
        TokenBudget(soft=10**9, hard=10**9),
        cfg=LoopConfig(max_steps=4),
    )
    res = loop.run("x", "sys")
    assert res.steps <= 4
