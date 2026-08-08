"""Unit tests for AgentLoop state machine transitions."""

from __future__ import annotations

from dhybrid.agent.loop.state_machine import (
    LoopState,
    StateMachine,
    TransitionResult,
)


def test_initial_state():
    sm = StateMachine()
    assert sm.state == LoopState.INITIALIZING


def test_valid_transition_thinking_to_executing():
    sm = StateMachine(LoopState.THINKING)
    assert sm.transition(LoopState.EXECUTING, "tool call") == TransitionResult.ALLOWED
    assert sm.state == LoopState.EXECUTING


def test_invalid_transition_completed_to_thinking():
    sm = StateMachine(LoopState.COMPLETED)
    assert sm.transition(LoopState.THINKING, "resume") == TransitionResult.INVALID
    assert sm.state == LoopState.COMPLETED  # state tidak berubah


def test_terminal_state_cannot_leave():
    for terminal in (LoopState.COMPLETED, LoopState.STUCK, LoopState.ERROR):
        sm = StateMachine(terminal)
        assert sm.transition(LoopState.THINKING, "x") == TransitionResult.INVALID


def test_history_records_transitions():
    sm = StateMachine(LoopState.THINKING)
    sm.transition(LoopState.EXECUTING, "run tool")
    sm.transition(LoopState.OBSERVING, "observe result")
    assert len(sm.history) == 2
    assert sm.history[0].from_state == LoopState.THINKING
    assert sm.history[0].to_state == LoopState.EXECUTING
    assert sm.history[1].reason == "observe result"


def test_nudge_loop_prevented():
    sm = StateMachine(LoopState.NUDGING)
    # self-loop NUDGING→NUDGING tidak valid
    assert sm.transition(LoopState.NUDGING, "again") != TransitionResult.ALLOWED


def test_escalate_loop_prevented():
    sm = StateMachine(LoopState.ESCALATING)
    assert sm.transition(LoopState.ESCALATING, "again") != TransitionResult.ALLOWED


def test_on_transition_callback():
    calls = []

    def cb(t):
        calls.append((t.from_state, t.to_state))

    sm = StateMachine(LoopState.THINKING, on_transition=cb)
    sm.transition(LoopState.EXECUTING, "x")
    assert calls == [(LoopState.THINKING, LoopState.EXECUTING)]


def test_full_lifecycle_flow():
    """Simulasi alur normal: THINK → EXECUTE → OBSERVE → THINK → COMPLETED."""
    sm = StateMachine()
    assert sm.transition(LoopState.THINKING, "start") == TransitionResult.ALLOWED
    assert sm.transition(LoopState.EXECUTING, "tool") == TransitionResult.ALLOWED
    assert sm.transition(LoopState.OBSERVING, "result") == TransitionResult.ALLOWED
    assert sm.transition(LoopState.THINKING, "next") == TransitionResult.ALLOWED
    assert sm.transition(LoopState.COMPLETED, "done") == TransitionResult.ALLOWED
    assert sm.is_terminal()


def test_reset():
    sm = StateMachine(LoopState.COMPLETED)
    sm.reset()
    assert sm.state == LoopState.INITIALIZING
    assert sm.history == []


def test_all_valid_transitions_defined():
    """Setiap state punya transisi valid (kecuali terminal)."""
    for state in LoopState:
        if state in (LoopState.COMPLETED, LoopState.STUCK, LoopState.ERROR):
            assert not StateMachine(state).can_transition(LoopState.THINKING)
        else:
            # setiap state non-terminal minimal bisa keluar
            assert StateMachine(state).can_transition(LoopState.ERROR)
