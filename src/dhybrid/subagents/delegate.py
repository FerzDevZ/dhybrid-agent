"""Subagent delegation — jalankan AgentLoop terisolasi, kembalikan ringkasan.

Konteks subagent TIDAK PERNAH masuk konteks utama → hemat token besar.
"""

from __future__ import annotations

from dataclasses import dataclass

from dhybrid.agent.loop import AgentLoop, LoopConfig
from dhybrid.efficiency.budget import TokenBudget
from dhybrid.efficiency.context import ContextManager
from dhybrid.llm.base import LLMClient
from dhybrid.tools.registry import ToolRegistry


@dataclass
class DelegateResult:
    text: str
    steps: int
    compacted: bool


def delegate(
    goal: str,
    client: LLMClient,
    tools: ToolRegistry,
    system_prompt: str,
    max_steps: int = 15,
    budget: TokenBudget | None = None,
) -> DelegateResult:
    """Jalankan sub-agent dengan konteks bersih; hasil = jawaban final (cap)."""
    loop = AgentLoop(
        client,
        tools,
        ctx=ContextManager(keep_recent=6),
        budget=budget or TokenBudget(soft=10**9, hard=10**9),
        cfg=LoopConfig(max_steps=max_steps),
    )
    result = loop.run(goal, system_prompt)
    return DelegateResult(text=result.final_text, steps=result.steps, compacted=result.compacted)
