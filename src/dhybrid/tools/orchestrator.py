"""Tool orchestrator — multi-agent task orchestration (planner + executor + reviewer)."""

from __future__ import annotations

from dhybrid.agent.orchestrator import Orchestrator
from dhybrid.tools.registry import ToolRegistry


def register(reg: ToolRegistry, max_chars: int = 8000, client_factory=None) -> None:
    """Register orchestrator tool.

    Args:
        reg: Tool registry
        max_chars: Max output chars
        client_factory: Callable to create LLM clients for subagents
    """
    if client_factory is None:
        return  # Tool not available without client factory

    orch = Orchestrator(client_factory=client_factory, tools=reg)

    def orchestrator_tool(goal: str, context: str = "") -> str:
        """Orchestrate a complex task using multi-agent workflow (planner + executor + reviewer).

        Args:
            goal: High-level goal description
            context: Optional additional context
        """
        plan = orch.plan(goal, context)
        results = orch.execute_plan(plan)

        lines = [f"Orchestration complete for: {goal}"]
        lines.append(f"Plan: {len(plan.tasks)} tasks")
        for r in results:
            lines.append(f"  [{r['role']}] {r['goal'][:80]}...")
            lines.append(f"    Quality: {r['quality_score']}/100, Files: {r['files_created']}, Tests: {r['tests_passed']}")
            if r['final_text']:
                lines.append(f"    Summary: {r['final_text'][:200]}")
        return "\n".join(lines)

    reg.register(
        "orchestrator",
        "Multi-agent orchestration: decompose complex task into planner/executor/reviewer subagents.",
        {"goal": {"type": "string", "required": True}, "context": {"type": "string"}},
        orchestrator_tool,
    )