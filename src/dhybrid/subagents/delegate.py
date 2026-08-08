"""Subagent delegation — jalankan AgentLoop terisolasi, kembalikan ringkasan.

Konteks subagent TIDAK PERNAH masuk konteks utama → hemat token besar.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from threading import Lock

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


def delegate_parallel(
    goals: list[str],
    client_factory,
    tools: ToolRegistry,
    system_prompt: str,
    max_steps: int = 15,
    budget_factory=None,
    max_workers: int | None = None,
) -> list[DelegateResult]:
    """Jalankan N sub-agent PARALEL (satu client baru per task via factory).

    Task independen (ganti modul A, B, C) dieksekusi bersamaan → percepatan
    total runtime. Hasil dikumpulkan sesuai urutan `goals`. Aman untuk model
    streaming: tiap thread memakai client sendiri (factory), bukan berbagi
    satu client (yang mungkin tidak thread-safe).
    """
    if budget_factory is None:
        budget_factory = lambda: TokenBudget(soft=10**9, hard=10**9)
    results: list[DelegateResult | None] = [None] * len(goals)
    lock = Lock()

    def _run(idx: int, goal: str) -> None:
        res = delegate(
            goal,
            client_factory(),
            tools,
            system_prompt,
            max_steps=max_steps,
            budget=budget_factory(),
        )
        with lock:
            results[idx] = res

    workers = max_workers or min(len(goals), 8)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_run, i, g) for i, g in enumerate(goals)]
        for fut in as_completed(futures):
            # re-raise task error di thread utama supaya bug tidak tenggelam
            fut.result()
    return [r for r in results if r is not None]
