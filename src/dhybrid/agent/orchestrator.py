"""Multi-agent orchestrator — decompose complex tasks into sub-tasks handled by specialized subagents."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from dhybrid.agent.loop import AgentLoop, LoopConfig
from dhybrid.tools.registry import ToolRegistry


@dataclass
class TaskPlan:
    """Plan for a multi-agent task decomposition."""
    tasks: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"tasks": self.tasks, "metadata": self.metadata}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskPlan:
        return cls(tasks=data.get("tasks", []), metadata=data.get("metadata", {}))


class Orchestrator:
    """Orchestrates multi-agent workflows by decomposing tasks and delegating to subagents."""

    def __init__(
        self,
        client_factory: Callable[[str], Any],
        tools: ToolRegistry,
        cwd: str = ".",
    ):
        """Initialize orchestrator.

        Args:
            client_factory: Callable that creates LLMClient instances for subagents
            tools: ToolRegistry with available tools
            cwd: Working directory
        """
        self.client_factory = client_factory
        self.tools = tools
        self.cwd = cwd

    def plan(self, goal: str, context: str = "") -> TaskPlan:
        """Decompose a high-level goal into a multi-agent task plan.

        Args:
            goal: High-level goal description
            context: Optional additional context

        Returns:
            TaskPlan with planner, executor, reviewer tasks
        """
        # Simple rule-based decomposition - in future could use LLM for planning
        tasks = [
            {
                "role": "planner",
                "goal": f"Analyze and create detailed plan for: {goal}",
                "context": context,
                "priority": 1,
            },
            {
                "role": "executor",
                "goal": f"Implement the solution for: {goal}",
                "context": context,
                "priority": 2,
            },
            {
                "role": "reviewer",
                "goal": f"Review and verify the implementation for: {goal}",
                "context": context,
                "priority": 3,
            },
        ]
        return TaskPlan(tasks=tasks, metadata={"goal": goal, "context": context})

    def execute_plan(self, plan: TaskPlan) -> list[dict[str, Any]]:
        """Execute a task plan by running subagents for each task.

        Args:
            plan: TaskPlan to execute

        Returns:
            List of results from each subagent
        """
        results = []
        for task in sorted(plan.tasks, key=lambda t: t.get("priority", 0)):
            role = task["role"]
            goal = task["goal"]
            context = task.get("context", "")

            # Create subagent with role-specific system prompt
            system_prompt = self._get_system_prompt(role)
            client = self.client_factory("opencode-zen-fast")  # Use fast model for subagents

            loop = AgentLoop(
                client_or_router=client,
                tools=self.tools,
                cwd=self.cwd,
                cfg=LoopConfig(max_steps=10),
            )

            full_prompt = f"{context}\n\nTask: {goal}" if context else goal
            result = loop.run(full_prompt, system_prompt)

            results.append({
                "role": role,
                "goal": goal,
                "final_text": result.final_text,
                "quality_score": result.quality_score,
                "files_created": result.files_created,
                "tests_passed": result.tests_passed,
                "steps": result.steps,
            })

        return results

    def _get_system_prompt(self, role: str) -> str:
        """Get role-specific system prompt."""
        prompts = {
            "planner": (
                "You are a senior software architect. Analyze the task and create a detailed, "
                "actionable implementation plan. Break down complex work into clear steps. "
                "Focus on architecture, data models, APIs, and integration points. "
                "Output a structured plan with specific files to create/modify."
            ),
            "executor": (
                "You are a senior software engineer. Execute the implementation plan precisely. "
                "Write clean, minimal code following project conventions. "
                "Use tools to create/modify files, run tests, and verify your work. "
                "Report exactly what was created/modified and test results."
            ),
            "reviewer": (
                "You are a senior code reviewer. Review the implementation for correctness, "
                "security, performance, and maintainability. Run tests and verify behavior. "
                "Report any issues found and whether the implementation meets requirements."
            ),
        }
        return prompts.get(role, prompts["executor"])