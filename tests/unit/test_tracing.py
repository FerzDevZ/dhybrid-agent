"""Tests for OpenTelemetry tracing."""
from dhybrid.efficiency.tracing import SpanKind, SpanStatus, get_tracer, init_tracing


def test_init_tracing_returns_tracer():
    """Test that init_tracing returns a tracer."""
    tracer = init_tracing(service_name="test-service")
    assert tracer is not None


def test_get_tracer_returns_same_instance():
    """Test that get_tracer returns the same tracer instance."""
    init_tracing(service_name="test-service")
    tracer1 = get_tracer()
    tracer2 = get_tracer()
    assert tracer1 is tracer2


def test_span_creation():
    """Test creating spans with different kinds."""
    tracer = init_tracing(service_name="test-service")
    
    with tracer.start_span("test-span", kind=SpanKind.INTERNAL) as span:
        assert span.name == "test-span"
        assert span.kind == SpanKind.INTERNAL


def test_span_attributes():
    """Test setting span attributes."""
    tracer = init_tracing(service_name="test-service")
    
    with tracer.start_span("test-span") as span:
        span.set_attribute("key1", "value1")
        span.set_attribute("key2", 123)
        assert span.attributes.get("key1") == "value1"
        assert span.attributes.get("key2") == 123


def test_nested_spans():
    """Test nested span creation."""
    tracer = init_tracing(service_name="test-service")
    
    with tracer.start_span("parent") as parent, tracer.start_span("child", parent=parent) as child:
        assert child.parent is parent


def test_span_events():
    """Test adding events to spans."""
    tracer = init_tracing(service_name="test-service")
    
    with tracer.start_span("test-span") as span:
        span.add_event("event1", {"key": "value"})
        events = span.events
        assert len(events) == 1
        assert events[0].name == "event1"
        assert events[0].attributes == {"key": "value"}


def test_span_status():
    """Test setting span status."""
    tracer = init_tracing(service_name="test-service")
    
    with tracer.start_span("test-span") as span:
        span.set_status(SpanStatus.OK, "success")
        assert span.status == SpanStatus.OK
        assert span.status_message == "success"
        
        span.set_status(SpanStatus.ERROR, "failed")
        assert span.status == SpanStatus.ERROR
        assert span.status_message == "failed"