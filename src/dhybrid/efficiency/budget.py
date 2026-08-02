"""TokenBudget — pelacak pemakaian token & pemicu kompaksi."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TokenBudget:
    soft: int = 60000
    hard: int = 120000
    used: int = 0
    history: list[dict] = field(default_factory=list)

    def add(self, prompt: int, completion: int, cached: int = 0, tag: str = "") -> None:
        self.used += prompt + completion
        self.history.append(
            {
                "prompt": prompt,
                "completion": completion,
                "cached": cached,
                "tag": tag,
                "cum": self.used,
            }
        )

    @property
    def should_compact(self) -> bool:
        return self.used >= self.soft

    @property
    def exhausted(self) -> bool:
        return self.used >= self.hard

    @property
    def cache_hit_ratio(self) -> float:
        tot = sum(h["prompt"] for h in self.history)
        cac = sum(h["cached"] for h in self.history)
        return (cac / tot) if tot else 0.0

    def reset(self) -> None:
        self.used = 0
        self.history.clear()
