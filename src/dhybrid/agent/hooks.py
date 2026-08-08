"""Hooks — callback lifecycle agent (metering, logging, UI streaming)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from dhybrid.llm.base import Usage


@dataclass
class Hooks:
    on_delta: Callable[[str], None] | None = None            # (text) -> None  — streaming ke UI
    on_step: Callable[[int, str, Usage | None, int], None] | None = None
    on_tool: Callable[[str, dict, str], None] | None = None
    on_compaction: Callable[[str], None] | None = None
    on_finish: Callable[[Any], None] | None = None
    on_nudge: Callable[[str, str], None] | None = None       # (nudge_type, message)
    on_escalation: Callable[[str, str], None] | None = None  # (preset_name, reason)
    on_state_transition: Callable[[str, str, str], None] | None = None  # (from, to, reason)

    def delta(self, text: str) -> None:
        if self.on_delta:
            self.on_delta(text)

    def step(self, step: int, model: str, usage: Usage | None, budget_used: int) -> None:
        if self.on_step:
            self.on_step(step, model, usage, budget_used)

    def tool(self, name: str, args: dict, output: str) -> None:
        if self.on_tool:
            self.on_tool(name, args, output)

    def compaction(self, summary: str) -> None:
        if self.on_compaction:
            self.on_compaction(summary)

    def finish(self, result) -> None:
        if self.on_finish:
            self.on_finish(result)

    def nudge(self, nudge_type: str, message: str) -> None:
        if self.on_nudge:
            self.on_nudge(nudge_type, message)

    def escalation(self, preset_name: str, reason: str) -> None:
        if self.on_escalation:
            self.on_escalation(preset_name, reason)

    def state_transition(self, from_state: str, to_state: str, reason: str) -> None:
        if self.on_state_transition:
            self.on_state_transition(from_state, to_state, reason)
