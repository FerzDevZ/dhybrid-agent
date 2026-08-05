"""Tests for Prometheus metrics exporter."""
import pytest

from dhybrid.efficiency.metrics import REGISTRY, Counter, Histogram
from dhybrid.efficiency.prometheus_exporter import export_metrics, start_metrics_server


def _register_standard_metrics():
    """Re-register standard metrics after registry clear."""
    REGISTRY.register(Counter("tokens_prompt", "prompt tokens (tiktoken)"))
    REGISTRY.register(Counter("tokens_completion", "completion tokens"))
    REGISTRY.register(Counter("tokens_cache", "cached prompt tokens"))
    REGISTRY.register(Counter("api_calls", "total LLM API calls"))
    REGISTRY.register(Counter("api_errors", "LLM API errors"))
    REGISTRY.register(Counter("turn_latency_ms", "per-turn latency in ms"))
    REGISTRY.register(Counter("cost_total_usd", "accumulated cost USD * 1e6"))
    REGISTRY.register(Counter("tokens_total", "total tokens (prompt+completion)"))


def test_prometheus_exporter_basic():
    """Test basic export format."""
    REGISTRY.register(Counter("test_counter", "Test counter")).inc(5)
    
    output = export_metrics()
    assert "test_counter" in output
    assert "5" in output
    assert "# TYPE test_counter counter" in output


def test_prometheus_exporter_histogram():
    """Test histogram export."""
    h = REGISTRY.register(Histogram("test_histogram", "Test histogram"))
    h.observe(0.1)
    h.observe(0.5)
    h.observe(1.0)
    
    output = export_metrics()
    assert "test_histogram" in output
    assert "# TYPE test_histogram histogram" in output


def test_prometheus_exporter_labels():
    """Test counter with labels."""
    REGISTRY.register(Counter("test_labeled", "Test with labels", labels=("model",))).inc(3)
    
    output = export_metrics()
    assert "test_labeled" in output


def test_prometheus_server_start():
    """Test metrics server can start and stop."""
    import time

    import requests
    
    # Register test counter in the shared registry
    REGISTRY.register(Counter("test_counter", "Test counter")).inc(5)
    
    server = start_metrics_server(port=0)  # Random free port
    port = server.server_port
    
    try:
        time.sleep(0.2)  # Wait for server to start
        resp = requests.get(f"http://localhost:{port}/metrics", timeout=2)
        assert resp.status_code == 200
        assert "test_counter" in resp.text
        assert "5" in resp.text
    finally:
        server.shutdown()


def test_prometheus_exporter_existing_metrics():
    """Test that existing standard metrics are exported."""
    output = export_metrics()
    # Check existing metrics from metrics.py
    assert "tokens_prompt" in output
    assert "tokens_completion" in output
    assert "api_calls" in output
    assert "api_errors" in output
    assert "tokens_total" in output