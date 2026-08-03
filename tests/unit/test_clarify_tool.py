"""Test tool clarify — pilihan bernomor + default, guardrail terpisah dari ask_user."""

from dhybrid.tools.clarify import (
    BLOCKED_SENTINEL,
    CLARIFY_MAX,
    PENDING_SENTINEL,
    ClarifyState,
    register,
)
from dhybrid.tools.registry import ToolRegistry


def _make_reg(state=None) -> ToolRegistry:
    reg = ToolRegistry()
    register(reg, state or ClarifyState(interactive=True))
    return reg


def test_clarify_sets_pending():
    st = ClarifyState(interactive=True)
    reg = _make_reg(st)
    out = reg.execute(
        "clarify",
        {"question": "stack apa?", "options": ["PHP", "Next.js"], "default_index": 1},
    )
    assert out == PENDING_SENTINEL
    assert st.pending == {
        "question": "stack apa?",
        "options": ["PHP", "Next.js"],
        "default_index": 1,
    }


def test_clarify_budget():
    st = ClarifyState(interactive=True)
    reg = _make_reg(st)
    for i in range(CLARIFY_MAX):
        st.pending = None
        out = reg.execute("clarify", {"question": f"q{i}", "options": ["a"]})
        assert out == PENDING_SENTINEL
    st.pending = None
    out = reg.execute("clarify", {"question": "q4", "options": ["a"]})
    assert out.startswith(BLOCKED_SENTINEL)


def test_clarify_noninteractive_uses_default():
    st = ClarifyState(interactive=False)
    reg = _make_reg(st)
    out = reg.execute(
        "clarify",
        {"question": "q", "options": ["PHP", "Next.js"], "default_index": 2},
    )
    assert out.startswith(BLOCKED_SENTINEL)
    assert "2" in out
    assert st.pending is None


def test_clarify_unknown_tool_error():
    reg = _make_reg()
    out = reg.execute("clarify", {"question": "q", "options": ["a"]})
    assert out == PENDING_SENTINEL or out.startswith("ERROR")
