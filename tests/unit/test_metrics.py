"""TDD unit tests for the in-memory prometheus-style metrics module.

Test contract:
  - Counter: increment(int), value (int), reset()
  - Histogram: observe(value), buckets default to _DEFAULT_BUCKETS, count/sum
  - Global REGISTRY (dict name -> metric) with lookup
  - 8 global counters registered (tokens_prompt/completion/cache, api_calls,
    api_errors, turn_latency_ms, cost_total_usd, tokens_total)
"""
import pytest

from dhybrid.efficiency.metrics import (
    _DEFAULT_BUCKETS,
    REGISTRY,
    Counter,
    Histogram,
    api_calls,
    api_errors,
    cost_total_usd,
    tokens_cache,
    tokens_completion,
    tokens_prompt,
    turn_latency_ms,
)

_NAMED_COUNTERS = [
    tokens_prompt,
    tokens_completion,
    tokens_cache,
    api_calls,
    api_errors,
    turn_latency_ms,
    cost_total_usd,
]


def test_counter_increment_and_value():
    c = Counter("demo")
    assert c.value == 0
    c.increment()
    assert c.value == 1
    c.increment(5)
    assert c.value == 6
    assert isinstance(c.value, int)


def test_counter_reset():
    c = Counter("demo")
    c.increment(10)
    assert c.value == 10
    c.reset()
    assert c.value == 0


def test_histogram_observe_count_sum():
    h = Histogram("lat", buckets=[0.1, 0.5, 1.0])
    assert h.count == 0
    assert h.sum == 0
    h.observe(0.05)
    h.observe(0.4)
    h.observe(2.0)
    assert h.count == 3
    assert h.sum == pytest.approx(2.45)


def test_histogram_default_buckets_and_cumulative():
    assert _DEFAULT_BUCKETS == [
        0.005,
        0.01,
        0.025,
        0.05,
        0.1,
        0.25,
        0.5,
        0.75,
        1.0,
        2.5,
        5.0,
        10.0,
    ]
    h = Histogram("d")
    # fresh histogram: every bucket empty
    assert h.buckets == {b: 0 for b in _DEFAULT_BUCKETS}
    # 0.007 <= every boundary except 0.005 ; 7.0 <= only 10.0
    h.observe(0.007)
    h.observe(7.0)
    b = h.buckets
    assert b[0.005] == 0
    assert b[0.01] == 1
    assert b[10.0] == 2
    assert h.count == 2
    assert h.sum == pytest.approx(7.007)


def test_global_registry_lookup():
    # the named module-level objects are the registered metrics
    for counter in _NAMED_COUNTERS:
        assert counter.name in REGISTRY
        assert REGISTRY[counter.name] is counter
        assert isinstance(REGISTRY.get(counter.name), Counter)


def test_registry_supports_histograms():
    reg = REGISTRY.__class__()
    h = Histogram("ad_hoc", buckets=[1.0])
    reg.register(h)
    assert reg.get("ad_hoc") is h
    assert "ad_hoc" in reg


@pytest.mark.parametrize("counter", _NAMED_COUNTERS)
def test_named_counters_are_global_counters(counter):
    assert isinstance(counter, Counter)
    assert counter.name in REGISTRY
    assert REGISTRY[counter.name] is counter


def test_eight_global_counters_registered():
    counters = [m for m in REGISTRY.values() if isinstance(m, Counter)]
    assert len(counters) == 8
    names = [m.name for m in counters]
    for counter in _NAMED_COUNTERS:
        assert counter.name in names
    # the 8th: total tokens (prompt + completion)
    assert "tokens_total" in names
