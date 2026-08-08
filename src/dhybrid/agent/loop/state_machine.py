"""State machine for AgentLoop — explicit states, transitions, and guards."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum


class LoopState(Enum):
    """Explicit loop states for clear debugging and testing."""
    INITIALIZING = "initializing"
    THINKING = "thinking"           # calling model, waiting for response
    EXECUTING = "executing"         # running tool calls
    OBSERVING = "observing"         # processing tool output, extracting facts
    NUDGING = "nudging"             # pushing nudge messages to model
    ESCALATING = "escalating"       # switching to stronger model
    COMPACTING = "compacting"       # context compaction
    REFLECTING = "reflecting"       # forced self-review pass before finalizing
    COMPLETED = "completed"         # natural stop (task done)
    STUCK = "stuck"                 # forced stop (budget, max_steps, no progress)
    PAUSED = "paused"               # waiting for user answer (ask_user/clarify)
    ERROR = "error"                 # unrecoverable error


class TransitionResult(Enum):
    """Result of a state transition attempt."""
    ALLOWED = "allowed"
    DENIED = "denied"
    INVALID = "invalid"


# Valid state transitions (from -> set of allowed to)
VALID_TRANSITIONS: dict[LoopState, set[LoopState]] = {
    LoopState.INITIALIZING: {LoopState.THINKING, LoopState.ERROR},
    LoopState.THINKING: {
        LoopState.EXECUTING,
        LoopState.NUDGING,
        LoopState.ESCALATING,
        LoopState.COMPLETED,
        LoopState.STUCK,
        LoopState.PAUSED,
        LoopState.COMPACTING,
        LoopState.REFLECTING,
        LoopState.ERROR,
    },
    LoopState.EXECUTING: {
        LoopState.OBSERVING,
        LoopState.PAUSED,
        LoopState.ERROR,
    },
    LoopState.OBSERVING: {
        LoopState.THINKING,
        LoopState.NUDGING,
        LoopState.ESCALATING,
        LoopState.COMPLETED,
        LoopState.STUCK,
        LoopState.PAUSED,
        LoopState.COMPACTING,
        LoopState.ERROR,
    },
    LoopState.NUDGING: {
        LoopState.THINKING,
        LoopState.ESCALATING,
        LoopState.COMPLETED,
        LoopState.STUCK,
        LoopState.ERROR,
    },
    LoopState.ESCALATING: {
        LoopState.THINKING,
        LoopState.ERROR,
    },
    LoopState.COMPACTING: {
        LoopState.THINKING,
        LoopState.ERROR,
    },
    LoopState.REFLECTING: {
        LoopState.THINKING,
        LoopState.ESCALATING,
        LoopState.COMPLETED,
        LoopState.STUCK,
        LoopState.ERROR,
    },
    LoopState.PAUSED: {
        LoopState.THINKING,
        LoopState.ERROR,
    },
    LoopState.COMPLETED: set(),      # terminal
    LoopState.STUCK: set(),          # terminal
    LoopState.ERROR: set(),          # terminal
}


@dataclass
class Transition:
    """Represents a state transition with metadata."""
    from_state: LoopState
    to_state: LoopState
    reason: str
    metadata: dict | None = None


class StateMachine:
    """Manages loop state transitions with guards and logging."""

    def __init__(
        self,
        initial_state: LoopState = LoopState.INITIALIZING,
        on_transition: Callable[[Transition], None] | None = None,
    ):
        self._state = initial_state
        self._history: list[Transition] = []
        self._on_transition = on_transition

    @property
    def state(self) -> LoopState:
        return self._state

    @property
    def history(self) -> list[Transition]:
        return list(self._history)

    def can_transition(self, to_state: LoopState) -> bool:
        """Check if transition is valid."""
        return to_state in VALID_TRANSITIONS.get(self._state, set())

    def transition(
        self,
        to_state: LoopState,
        reason: str = "",
        metadata: dict | None = None,
    ) -> TransitionResult:
        """Attempt state transition with validation."""
        if not self.can_transition(to_state):
            return TransitionResult.INVALID

        # Additional guards
        if not self._guard_transition(self._state, to_state):
            return TransitionResult.DENIED

        transition = Transition(
            from_state=self._state,
            to_state=to_state,
            reason=reason,
            metadata=metadata or {},
        )
        self._state = to_state
        self._history.append(transition)

        if self._on_transition:
            self._on_transition(transition)

        return TransitionResult.ALLOWED

    def _guard_transition(self, from_state: LoopState, to_state: LoopState) -> bool:
        """Additional semantic guards beyond basic transition validity."""
        # Prevent infinite nudge/escalate loops
        if from_state == LoopState.NUDGING and to_state == LoopState.NUDGING:
            return False
        if from_state == LoopState.ESCALATING and to_state == LoopState.ESCALATING:
            return False
        if from_state == LoopState.REFLECTING and to_state == LoopState.REFLECTING:
            return False
        # Can't go from terminal states
        return from_state not in (LoopState.COMPLETED, LoopState.STUCK, LoopState.ERROR)

    def is_terminal(self) -> bool:
        return self._state in (LoopState.COMPLETED, LoopState.STUCK, LoopState.ERROR)

    def reset(self, to_state: LoopState = LoopState.INITIALIZING) -> None:
        """Reset state machine (for testing or new run)."""
        self._state = to_state
        self._history.clear()