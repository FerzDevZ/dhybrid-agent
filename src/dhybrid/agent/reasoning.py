"""ReasoningTrace — capture and display agent's reasoning process for debugging and learning."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class ReasoningStep:
    """A single reasoning step."""
    phase: str
    thought: str
    tools_used: list[str]
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)


class ReasoningTrace:
    """Capture and format the agent's reasoning trace."""

    def __init__(self):
        self.steps: list[ReasoningStep] = []

    def add_step(
        self,
        phase: str,
        thought: str,
        tools_used: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Add a reasoning step."""
        step = ReasoningStep(
            phase=phase,
            thought=thought,
            tools_used=tools_used or [],
            metadata=metadata or {},
        )
        self.steps.append(step)

    def get_steps(self) -> list[dict[str, Any]]:
        """Get all steps as list of dicts."""
        return [
            {
                "phase": step.phase,
                "thought": step.thought,
                "tools_used": step.tools_used,
                "timestamp": step.timestamp,
                "metadata": step.metadata,
            }
            for step in self.steps
        ]

    def format_for_prompt(self, max_steps: int = 10) -> str:
        """Format reasoning trace for injection into prompt."""
        if not self.steps:
            return ""
        
        lines = ["[REASONING TRACE]"]
        for i, step in enumerate(self.steps[-max_steps:], 1):
            tools = f" (tools: {', '.join(step.tools_used)})" if step.tools_used else ""
            lines.append(f"  {i}. [{step.phase}]{tools}: {step.thought[:200]}")
        return "\n".join(lines)

    def clear(self) -> None:
        """Clear all steps."""
        self.steps = []

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "steps": [
                {
                    "phase": step.phase,
                    "thought": step.thought,
                    "tools_used": step.tools_used,
                    "timestamp": step.timestamp,
                    "metadata": step.metadata,
                }
                for step in self.steps
            ]
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReasoningTrace:
        """Deserialize from dict."""
        trace = cls()
        for step_data in data.get("steps", []):
            step = ReasoningStep(
                phase=step_data["phase"],
                thought=step_data["thought"],
                tools_used=step_data.get("tools_used", []),
                timestamp=step_data.get("timestamp", datetime.now(UTC).isoformat()),
                metadata=step_data.get("metadata", {}),
            )
            trace.steps.append(step)
        return trace

    def __len__(self) -> int:
        return len(self.steps)

    def __bool__(self) -> bool:
        return bool(self.steps)