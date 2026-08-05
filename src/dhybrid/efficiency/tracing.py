"""OpenTelemetry tracing integration for distributed tracing."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False

# Current span context variable
_current_span: ContextVar[Span | None] = ContextVar("_current_span", default=None)


class SpanKind(Enum):
    """OpenTelemetry span kinds."""
    INTERNAL = "internal"
    SERVER = "server"
    CLIENT = "client"
    PRODUCER = "producer"
    CONSUMER = "consumer"


class SpanStatus(Enum):
    """Span status codes."""
    UNSET = "unset"
    OK = "ok"
    ERROR = "error"


@dataclass
class SpanEvent:
    """Span event with timestamp and attributes."""
    name: str
    attributes: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=lambda: __import__('time').time())


@dataclass
class Span:
    """Lightweight span implementation (works without OTEL)."""
    name: str
    kind: SpanKind = SpanKind.INTERNAL
    parent: Span | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[SpanEvent] = field(default_factory=list)
    status: SpanStatus = SpanStatus.UNSET
    status_message: str = ""
    _otel_span: Any = None  # Actual OTEL span if available

    def set_attribute(self, key: str, value: Any) -> None:
        """Set a span attribute."""
        self.attributes[key] = value

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        """Add an event to the span."""
        self.events.append(SpanEvent(name=name, attributes=attributes or {}))

    def set_status(self, status: SpanStatus | str, message: str = "") -> None:
        """Set span status."""
        if isinstance(status, str):
            status = SpanStatus(status)
        self.status = status
        self.status_message = message

    def __enter__(self) -> Span:
        token = _current_span.set(self)
        self._token = token
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        _current_span.reset(self._token)
        if exc_type is not None:
            self.set_status(SpanStatus.ERROR, str(exc_val))
        # If using real OTEL, end the span
        if self._otel_span:
            self._otel_span.end()


class NoOpTracer:
    """No-op tracer when OTEL is not available."""

    def start_span(self, name: str, kind: SpanKind = SpanKind.INTERNAL, parent: Span | None = None) -> Span:
        return Span(name=name, kind=kind, parent=parent)


class OTelTracer:
    """OpenTelemetry tracer wrapper."""

    def __init__(self, tracer):
        self._tracer = tracer

    def start_span(self, name: str, kind: SpanKind = SpanKind.INTERNAL, parent: Span | None = None) -> Span:
        otel_kind = getattr(trace.SpanKind, kind.name, trace.SpanKind.INTERNAL)
        otel_parent = parent._otel_span if parent and parent._otel_span else None
        
        ctx = trace.set_span_in_context(otel_parent) if otel_parent else None
        otel_span = self._tracer.start_span(name, kind=otel_kind, context=ctx)
        
        span = Span(name=name, kind=kind, parent=parent, _otel_span=otel_span)
        return span


_tracer_instance: Any | None = None


def init_tracing(
    service_name: str = "dhybrid-agent",
    otlp_endpoint: str | None = None,
    console_export: bool = False,
) -> Any:
    """Initialize OpenTelemetry tracing.
    
    Args:
        service_name: Service name for traces
        otlp_endpoint: OTLP gRPC endpoint (e.g., "http://localhost:4317")
        console_export: Whether to also export to console
    
    Returns:
        Tracer instance
    """
    global _tracer_instance
    
    if not OTEL_AVAILABLE:
        _tracer_instance = NoOpTracer()
        return _tracer_instance
    
    # Create resource
    resource = Resource.create({"service.name": service_name})
    
    # Create tracer provider
    provider = TracerProvider(resource=resource)
    
    # Add exporters
    if console_export:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    
    if otlp_endpoint:
        otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    
    # Set global tracer provider
    trace.set_tracer_provider(provider)
    
    # Get tracer
    otel_tracer = trace.get_tracer(service_name)
    _tracer_instance = OTelTracer(otel_tracer)
    
    return _tracer_instance


def get_tracer() -> Any:
    """Get the current tracer instance."""
    global _tracer_instance
    if _tracer_instance is None:
        _tracer_instance = init_tracing()
    return _tracer_instance


def get_current_span() -> Span | None:
    """Get the currently active span from context."""
    return _current_span.get()


@contextmanager
def trace_context(name: str, kind: SpanKind = SpanKind.INTERNAL, attributes: dict[str, Any] | None = None):
    """Context manager for creating a span."""
    tracer = get_tracer()
    with tracer.start_span(name) as span:
        if attributes:
            for k, v in attributes.items():
                span.set_attribute(k, v)
        yield span