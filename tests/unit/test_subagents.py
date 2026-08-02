from dhybrid.llm.base import ChatMessage, ChatResponse, LLMClient, StreamEvent, Usage
from dhybrid.subagents.delegate import delegate
from dhybrid.tools.registry import ToolRegistry


class ScriptedClient(LLMClient):
    def __init__(self, replies):
        self.replies = replies  # list: "tool:<name>:<arg>" atau "text:..."; terakhir = final
        self.calls = 0

    def stream(self, messages, **kw):
        self.calls += 1
        if self.calls <= len(self.replies):
            r = self.replies[self.calls - 1]
            if r.startswith("tool:"):
                _, name, arg = r.split(":", 2)
                yield StreamEvent(kind="tool_call", tool_call={"id": "t1", "name": name, "arguments": {"q": arg}})
            else:
                yield StreamEvent(kind="delta", text=r[len("text:") :])
        else:
            yield StreamEvent(kind="delta", text="selesai")
        yield StreamEvent(kind="done")

    def complete(self, messages, **kw):
        return ChatResponse(message=ChatMessage(role="assistant", content="ok"), usage=Usage(), model="fake")


def test_delegate_runs_isolated_loop():
    tools = ToolRegistry()
    tools.register("grep", "cari", {"q": {"type": "string"}}, lambda q: f"hit:{q}")
    client = ScriptedClient(["tool:grep:x", "text:ketemu"])
    result = delegate("cari x", client, tools, "system", max_steps=5)
    assert result.text == "ketemu"
    assert result.steps == 2
