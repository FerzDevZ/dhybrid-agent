"""Test loop pause untuk clarify — guardrail terpisah dari ask_user."""

from dhybrid.agent.loop import AgentLoop, LoopResult
from dhybrid.tools.clarify import ClarifyState


class _DummyClient:
    def stream(self, messages, **kw):
        yield from ()

    def complete(self, messages, **kw):
        from dhybrid.llm.base import ChatMessage, ChatResponse, Usage

        return ChatResponse(
            message=ChatMessage(role="assistant", content="x"),
            usage=Usage(), model="dummy",
        )

    def model_name(self):
        return "dummy"


def _loop(**kw) -> AgentLoop:
    from dhybrid.tools.registry import ToolRegistry

    return AgentLoop(_DummyClient(), ToolRegistry(), **kw)


def test_loop_pauses_on_clarify():
    st = ClarifyState(interactive=True)
    st.pending = {"question": "q", "options": ["PHP", "Next.js"], "default_index": 1}
    loop = _loop(clarify_state=st)
    result = LoopResult()
    assert loop._maybe_pause_for_user(result, "teks")
    assert result.pending_question == {
        "question": "q",
        "options": ["PHP", "Next.js"],
        "default_index": 1,
    }
    assert st.pending is None


def test_loop_no_pause_without_pending():
    st = ClarifyState(interactive=True)
    loop = _loop(clarify_state=st)
    result = LoopResult()
    assert not loop._maybe_pause_for_user(result, "teks")
    assert result.pending_question is None


def test_loop_clarify_fires_when_ask_empty():
    from dhybrid.tools.ask import AskState

    ask = AskState(interactive=True)  # pending kosong
    st = ClarifyState(interactive=True)
    st.pending = {"question": "q", "options": ["a"], "default_index": 1}
    loop = _loop(ask_state=ask, clarify_state=st)
    result = LoopResult()
    assert loop._maybe_pause_for_user(result, "teks")
    assert result.pending_question is not None
    assert result.pending_question["question"] == "q"
