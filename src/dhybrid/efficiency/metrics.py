"""Observabilitas sederhana — Counter + Histogram + Registry (in-memory).

API mirip prometheus_client (Counter.inc, Histogram.observe) tapi tanpa dependensi
eksternal: cocok untuk agen CLI. Export ke /metrics bila perlu via Task 8.
"""
from __future__ import annotations

_DEFAULT_BUCKETS = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 10.0]


class Counter:
    """Counter sederhana: increment(int) / value / reset()."""

    def __init__(self, name: str, description: str = "", labels: tuple = ()):
        self.name = name
        self.description = description
        self.labels = labels
        self._value = 0

    @property
    def value(self) -> int:
        return self._value

    def inc(self, by: int = 1) -> None:
        self._value += by

    def increment(self, by: int = 1) -> None:
        self._value += by

    def get(self) -> int:
        return self._value

    def reset(self) -> None:
        self._value = 0

    def __int__(self) -> int:
        return self._value


class Histogram:
    """Histogram dengan cumulative buckets + count/sum."""

    def __init__(self, name: str, description: str = "", buckets=_DEFAULT_BUCKETS, labels=()):
        self.name = name
        self.description = description
        self._boundaries = list(buckets)
        self._bucket_counts: dict[float, int] = {b: 0 for b in self._boundaries}
        self._count = 0
        self._sum = 0.0

    @property
    def count(self) -> int:
        return self._count

    @property
    def sum(self) -> float:
        return self._sum

    @property
    def buckets(self) -> dict[float, int]:
        return dict(self._bucket_counts)

    def observe(self, value: float) -> None:
        self._count += 1
        self._sum += value
        for b in self._boundaries:
            if value <= b:
                self._bucket_counts[b] += 1

    def reset(self) -> None:
        self._bucket_counts = {b: 0 for b in self._boundaries}
        self._count = 0
        self._sum = 0.0


class Registry:
    """Registry nama -> metric (in-memory)."""

    def __init__(self) -> None:
        self._items: dict[str, object] = {}

    def register(self, metric: object) -> object:
        name = getattr(metric, "name", "")
        if name:
            self._items[name] = metric
        return metric

    def get(self, name: str) -> object | None:
        return self._items.get(name)

    def __getitem__(self, name: str) -> object:
        return self._items[name]

    def __contains__(self, name: object) -> bool:
        return name in self._items

    def values(self):
        return self._items.values()

    @property
    def names(self) -> list[str]:
        return list(self._items)


# ---- registry global + 8 counter standar ----
REGISTRY = Registry()

tokens_prompt: Counter = REGISTRY.register(Counter("tokens_prompt", "prompt tokens (tiktoken)"))
tokens_completion: Counter = REGISTRY.register(Counter("tokens_completion", "completion tokens"))
tokens_cache: Counter = REGISTRY.register(Counter("tokens_cache", "cached prompt tokens"))
api_calls: Counter = REGISTRY.register(Counter("api_calls", "total LLM API calls"))
api_errors: Counter = REGISTRY.register(Counter("api_errors", "LLM API errors"))
turn_latency_ms: Counter = REGISTRY.register(Counter("turn_latency_ms", "per-turn latency in ms"))
cost_total_usd: Counter = REGISTRY.register(Counter("cost_total_usd", "accumulated cost USD * 1e6"))
tokens_total: Counter = REGISTRY.register(Counter("tokens_total", "total tokens (prompt+completion)"))
