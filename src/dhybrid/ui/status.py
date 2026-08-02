"""Statusline — token meter live saat agent bekerja."""

from __future__ import annotations

from dhybrid.efficiency.budget import TokenBudget


def fmt_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def format_status(
    budget: TokenBudget,
    model: str,
    steps: int,
    max_steps: int,
    cache_ratio: float = 0.0,
    cost: float = 0.0,
) -> str:
    pct = min(budget.used / max(budget.soft, 1) * 100, 999)
    return (
        f"[{model} | langkah {steps}/{max_steps} | "
        f"tokens {fmt_tokens(budget.used)}/{fmt_tokens(budget.soft)} ({pct:.0f}%) | "
        f"cache-hit {cache_ratio * 100:.0f}% | ${cost:.4f}]"
    )
