"""
OpenTelemetry Distributed Tracing
=================================
Distributed tracing for request flow visibility.
"""

import os
from typing import Optional, Dict, Any, Callable
from functools import wraps
from contextlib import contextmanager
import uuid

import structlog

logger = structlog.get_logger(__name__)

# Try to import OpenTelemetry
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
    from opentelemetry.trace import Status, StatusCode
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    logger.warning("OpenTelemetry not installed, tracing will use fallback")


# Configuration
SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "invoice-summarizer")
OTEL_EXPORTER_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")


class TracingContext:
    """Simple tracing context for when OpenTelemetry is not available."""
    
    def __init__(
        self,
        trace_id: Optional[str] = None,
        span_id: Optional[str] = None,
        operation: Optional[str] = None,
    ):
        self.trace_id = trace_id or uuid.uuid4().hex[:16]
        self.span_id = span_id or uuid.uuid4().hex[:8]
        self.operation = operation
        self.attributes: Dict[str, Any] = {}
        self.events: list = []
        self.status = "ok"
    
    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value
    
    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        self.events.append({"name": name, "attributes": attributes or {}})
    
    def set_status(self, status: str, description: Optional[str] = None) -> None:
        self.status = status
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "operation": self.operation,
            "attributes": self.attributes,
            "events": self.events,
            "status": self.status
        }


class Tracer:
    """
    Distributed tracing wrapper.
    
    Uses OpenTelemetry when available, falls back to simple context tracking.
    """
    
    def __init__(self, service_name: str = SERVICE_NAME):
        self.service_name = service_name
        self._tracer = None
        self._propagator = None
        
        if OTEL_AVAILABLE:
            self._init_otel()
        else:
            logger.info("Using fallback tracing (OpenTelemetry not available)")
    
    def _init_otel(self) -> None:
        """Initialize OpenTelemetry tracing."""
        # Create resource
        resource = Resource.create({
            "service.name": self.service_name,
            "service.version": "1.0.0",
        })
        
        # Create provider
        provider = TracerProvider(resource=resource)
        
        # Add exporters
        if OTEL_EXPORTER_ENDPOINT:
            try:
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
                otlp_exporter = OTLPSpanExporter(endpoint=OTEL_EXPORTER_ENDPOINT)
                provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
                logger.info("OTLP exporter configured", endpoint=OTEL_EXPORTER_ENDPOINT)
            except ImportError:
                logger.warning("OTLP exporter not available")
        
        # Console exporter for development
        if os.getenv("OTEL_CONSOLE_EXPORT", "false").lower() == "true":
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        
        # Set global provider
        trace.set_tracer_provider(provider)
        
        # Get tracer
        self._tracer = trace.get_tracer(self.service_name)
        self._propagator = TraceContextTextMapPropagator()
        
        logger.info("OpenTelemetry tracing initialized", service=self.service_name)
    
    @contextmanager
    def start_span(
        self,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
    ):
        """
        Start a new span.
        
        Usage:
            with tracer.start_span("process_invoice", {"invoice_id": "123"}):
                # Your code here
        """
        if OTEL_AVAILABLE and self._tracer:
            with self._tracer.start_as_current_span(name) as span:
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, str(value) if value is not None else "")
                try:
                    yield span
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise
        else:
            # Fallback to simple context
            ctx = TracingContext(operation=name)
            if attributes:
                for key, value in attributes.items():
                    ctx.set_attribute(key, value)
            
            try:
                yield ctx
            except Exception as e:
                ctx.set_status("error", str(e))
                raise
            finally:
                # Log for visibility
                logger.debug("Span completed", **ctx.to_dict())
    
    def extract_context(self, carrier: Dict[str, str]) -> Any:
        """Extract trace context from headers."""
        if OTEL_AVAILABLE and self._propagator:
            return self._propagator.extract(carrier=carrier)
        
        # Fallback: extract trace ID from header
        trace_id = carrier.get("x-trace-id") or carrier.get("traceparent", "").split("-")[1] if carrier.get("traceparent") else None
        return TracingContext(trace_id=trace_id)
    
    def inject_context(self, carrier: Dict[str, str]) -> None:
        """Inject trace context into headers."""
        if OTEL_AVAILABLE and self._propagator:
            self._propagator.inject(carrier=carrier)
        else:
            # Fallback: add trace ID header
            carrier["x-trace-id"] = uuid.uuid4().hex[:16]
    
    def get_current_trace_id(self) -> Optional[str]:
        """Get current trace ID."""
        if OTEL_AVAILABLE:
            span = trace.get_current_span()
            if span:
                return format(span.get_span_context().trace_id, "032x")
        return None
    
    def get_current_span_id(self) -> Optional[str]:
        """Get current span ID."""
        if OTEL_AVAILABLE:
            span = trace.get_current_span()
            if span:
                return format(span.get_span_context().span_id, "016x")
        return None


# Singleton instance
_tracer: Optional[Tracer] = None


def get_tracer() -> Tracer:
    """Get or create tracer instance."""
    global _tracer
    if _tracer is None:
        _tracer = Tracer()
    return _tracer


# Decorators
def traced(name: Optional[str] = None, attributes: Optional[Dict[str, Any]] = None):
    """
    Decorator to automatically trace a function.
    
    Usage:
        @traced("process_invoice")
        async def process_invoice(invoice_id: str):
            ...
    """
    def decorator(func: Callable):
        span_name = name or f"{func.__module__}.{func.__name__}"
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            with get_tracer().start_span(span_name, attributes) as span:
                # Add function arguments as attributes
                if hasattr(span, "set_attribute"):
                    for i, arg in enumerate(args[:3]):  # First 3 args
                        span.set_attribute(f"arg_{i}", str(arg)[:100])
                    for key, value in list(kwargs.items())[:3]:  # First 3 kwargs
                        span.set_attribute(f"kwarg_{key}", str(value)[:100])
                
                return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            with get_tracer().start_span(span_name, attributes) as span:
                if hasattr(span, "set_attribute"):
                    for i, arg in enumerate(args[:3]):
                        span.set_attribute(f"arg_{i}", str(arg)[:100])
                    for key, value in list(kwargs.items())[:3]:
                        span.set_attribute(f"kwarg_{key}", str(value)[:100])
                
                return func(*args, **kwargs)
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


# Middleware helper
async def tracing_middleware_helper(request, call_next):
    """Helper for integrating with FastAPI middleware."""
    tracer = get_tracer()
    
    # Extract context from headers
    headers = dict(request.headers)
    context = tracer.extract_context(headers)
    
    with tracer.start_span(
        f"{request.method} {request.url.path}",
        attributes={
            "http.method": request.method,
            "http.url": str(request.url),
            "http.host": request.headers.get("host", ""),
        }
    ) as span:
        response = await call_next(request)
        
        if hasattr(span, "set_attribute"):
            span.set_attribute("http.status_code", response.status_code)
        
        return response
