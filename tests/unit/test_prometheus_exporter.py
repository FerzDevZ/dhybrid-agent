"""TDD tests for prometheus-style exporter (format counters -> text exposition)."""

from dhybrid.efficiency.metrics import Counter, api_calls
from dhybrid.efficiency.prometheus_exporter import export_metrics, format_counter


def test_format_counter_simple():
    c = Counter("my_events_total", "test events")
    c.inc(5)
    out = format_counter(c)
    assert "# HELP my_events_total test events" in out
    assert "# TYPE my_events_total counter" in out
    assert "my_events_total 5" in out


def test_export_metrics_includes_global_counters():
    out = export_metrics()
    for name in ("tokens_prompt", "tokens_completion", "api_calls", "api_errors", "cost_total_usd", "tokens_total"):
        assert name in out
    assert "# HELP tokens_prompt prompt tokens (tiktoken)" in out
    assert "# TYPE tokens_total counter" in out


def test_export_metrics_increment_reflected():
    api_calls.reset()
    api_calls.inc(10)
    out = export_metrics()
    assert "api_calls 10" in out
