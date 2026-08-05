# conftest.py - Test isolation fixtures
import pytest
from dhybrid.efficiency.metrics import (
    REGISTRY, tokens_prompt, tokens_completion, tokens_cache,
    api_calls, api_errors, turn_latency_ms, cost_total_usd, tokens_total
)

# Original registry items (the 8 standard counters)
_ORIGINAL_REGISTRY_NAMES = frozenset([
    "tokens_prompt", "tokens_completion", "tokens_cache",
    "api_calls", "api_errors", "turn_latency_ms",
    "cost_total_usd", "tokens_total"
])

# Reset all global counters before each test
@pytest.fixture(autouse=True)
def reset_metrics():
    """Reset all global metrics counters before each test."""
    from dhybrid.efficiency.metrics import (
        REGISTRY, tokens_prompt, tokens_completion, tokens_cache,
        api_calls, api_errors, turn_latency_ms, cost_total_usd, tokens_total
    )
    
    # Reset all known counters
    for counter in [
        tokens_prompt, tokens_completion, tokens_cache,
        api_calls, api_errors, turn_latency_ms,
        cost_total_usd, tokens_total
    ]:
        counter.reset()
    
    # Remove any custom metrics added to REGISTRY (keep only original 8)
    custom_keys = [k for k in REGISTRY._items.keys() if k not in _ORIGINAL_REGISTRY_NAMES]
    for key in custom_keys:
        del REGISTRY._items[key]
    
    yield
    
    # Also reset after test for clean state
    for counter in [
        tokens_prompt, tokens_completion, tokens_cache,
        api_calls, api_errors, turn_latency_ms,
        cost_total_usd, tokens_total
    ]:
        counter.reset()
    
    # Clean up any custom metrics added during test
    custom_keys = [k for k in REGISTRY._items.keys() if k not in _ORIGINAL_REGISTRY_NAMES]
    for key in custom_keys:
        del REGISTRY._items[key]


# Also ensure clean REGISTRY for integration tests
@pytest.fixture
def clean_registry():
    """Provide a clean REGISTRY for tests that need it."""
    from dhybrid.efficiency.metrics import REGISTRY
    # Save original items
    original_items = dict(REGISTRY._items)
    yield REGISTRY
    # Restore
    REGISTRY._items = original_items