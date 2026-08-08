"""Agent Loop module — refactored modular ReAct loop.

Components:
- state_machine: Explicit state management with transitions
- nudge_controller: Multi-level nudge strategy
- escalation_policy: Cost/quality-based model escalation
- step_executor: Single step execution (model + tools)
- agent_loop: Main loop orchestrating all components
"""

from __future__ import annotations

from .agent_loop import AgentLoop, LoopConfig, LoopResult
from .escalation_policy import EscalationConfig, EscalationPolicy, EscalationResult
from .nudge_controller import NudgeConfig, NudgeController
from .state_machine import LoopState, StateMachine, Transition, TransitionResult
from .step_executor import StepConfig, StepExecutor, StepResult

__all__ = [
    "AgentLoop",
    "EscalationConfig",
    "EscalationPolicy",
    "EscalationResult",
    "LoopConfig",
    "LoopResult",
    "LoopState",
    "NudgeConfig",
    "NudgeController",
    "StateMachine",
    "StepConfig",
    "StepExecutor",
    "StepResult",
    "Transition",
    "TransitionResult",
]