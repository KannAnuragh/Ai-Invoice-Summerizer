"""
Prometheus Metrics Collector
============================
Observability metrics for monitoring system health and performance.
"""

import time
from typing import Optional, Dict, Any, Callable
from functools import wraps
from contextlib import contextmanager

import structlog

logger = structlog.get_logger(__name__)

# Try to import Prometheus client
try:
    from prometheus_client import (
        Counter, Histogram, Gauge, Summary, Info,
        generate_latest, CONTENT_TYPE_LATEST,
        CollectorRegistry, REGISTRY
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning("prometheus_client not installed, metrics disabled")


class MetricsCollector:
    """
    Central metrics collector for the invoice processing system.
    
    Tracks:
    - Request latency and counts
    - OCR processing times and accuracy
    - AI/LLM usage and costs
    - Invoice processing pipeline stages
    - Error rates and types
    """
    
    def __init__(self, namespace: str = "invoice_ai"):
        self.namespace = namespace
        self._initialized = False
        
        if PROMETHEUS_AVAILABLE:
            self._init_metrics()
    
    def _init_metrics(self) -> None:
        """Initialize Prometheus metrics."""
        
        # === HTTP Request Metrics ===
        self.http_requests_total = Counter(
            f"{self.namespace}_http_requests_total",
            "Total HTTP requests",
            ["method", "endpoint", "status"]
        )
        
        self.http_request_duration = Histogram(
            f"{self.namespace}_http_request_duration_seconds",
            "HTTP request duration in seconds",
            ["method", "endpoint"],
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        )
        
        # === Invoice Processing Metrics ===
        self.invoices_processed_total = Counter(
            f"{self.namespace}_invoices_processed_total",
            "Total invoices processed",
            ["source", "status"]
        )
        
        self.invoice_processing_duration = Histogram(
            f"{self.namespace}_invoice_processing_duration_seconds",
            "Invoice end-to-end processing duration",
            ["stage"],
            buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0]
        )
        
        self.invoices_pending = Gauge(
            f"{self.namespace}_invoices_pending",
            "Number of invoices pending processing",
            ["stage"]
        )
        
        # === OCR Metrics ===
        self.ocr_operations_total = Counter(
            f"{self.namespace}_ocr_operations_total",
            "Total OCR operations",
            ["language", "status"]
        )
        
        self.ocr_processing_duration = Histogram(
            f"{self.namespace}_ocr_processing_duration_seconds",
            "OCR processing duration per page",
            ["language"],
            buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0]
        )
        
        self.ocr_confidence = Histogram(
            f"{self.namespace}_ocr_confidence",
            "OCR confidence score distribution",
            ["language"],
            buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0]
        )
        
        self.ocr_word_count = Histogram(
            f"{self.namespace}_ocr_word_count",
            "Words extracted per page",
            buckets=[10, 50, 100, 200, 500, 1000, 2000]
        )
        
        # === AI/LLM Metrics ===
        self.llm_requests_total = Counter(
            f"{self.namespace}_llm_requests_total",
            "Total LLM API requests",
            ["provider", "model", "operation", "status"]
        )
        
        self.llm_request_duration = Histogram(
            f"{self.namespace}_llm_request_duration_seconds",
            "LLM API request duration",
            ["provider", "model"],
            buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0]
        )
        
        self.llm_tokens_used = Counter(
            f"{self.namespace}_llm_tokens_total",
            "Total LLM tokens used",
            ["provider", "model", "type"]  # type: input/output
        )
        
        self.llm_cost_usd = Counter(
            f"{self.namespace}_llm_cost_usd_total",
            "Total LLM API cost in USD",
            ["provider", "model"]
        )
        
        # === Extraction Metrics ===
        self.extraction_fields_total = Counter(
            f"{self.namespace}_extraction_fields_total",
            "Total fields extracted",
            ["field_type", "status"]  # status: success/missing/low_confidence
        )
        
        self.extraction_confidence = Histogram(
            f"{self.namespace}_extraction_confidence",
            "Field extraction confidence distribution",
            ["field_type"],
            buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0]
        )
        
        # === Validation Metrics ===
        self.validation_checks_total = Counter(
            f"{self.namespace}_validation_checks_total",
            "Total validation checks performed",
            ["check_type", "result"]  # result: pass/fail/warning
        )
        
        self.anomalies_detected_total = Counter(
            f"{self.namespace}_anomalies_detected_total",
            "Total anomalies detected",
            ["anomaly_type", "severity"]
        )
        
        self.risk_score = Histogram(
            f"{self.namespace}_risk_score",
            "Invoice risk score distribution",
            buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        )
        
        # === Workflow Metrics ===
        self.approvals_total = Counter(
            f"{self.namespace}_approvals_total",
            "Total approval actions",
            ["action", "auto"]  # action: approve/reject/escalate, auto: true/false
        )
        
        self.approval_duration = Histogram(
            f"{self.namespace}_approval_duration_seconds",
            "Time from submission to approval decision",
            buckets=[60, 300, 600, 1800, 3600, 7200, 14400, 28800, 86400]
        )
        
        self.sla_breaches_total = Counter(
            f"{self.namespace}_sla_breaches_total",
            "Total SLA breaches",
            ["breach_type"]
        )
        
        # === System Metrics ===
        self.active_users = Gauge(
            f"{self.namespace}_active_users",
            "Number of active users"
        )
        
        self.queue_size = Gauge(
            f"{self.namespace}_queue_size",
            "Size of processing queues",
            ["queue_name"]
        )
        
        # === Error Tracking ===
        self.errors_total = Counter(
            f"{self.namespace}_errors_total",
            "Total errors",
            ["error_type", "component"]
        )
        
        self._initialized = True
        logger.info("Prometheus metrics initialized", namespace=self.namespace)
    
    # === Recording Methods ===
    
    def record_http_request(
        self,
        method: str,
        endpoint: str,
        status: int,
        duration: float
    ) -> None:
        """Record HTTP request metrics."""
        if not PROMETHEUS_AVAILABLE:
            return
        
        self.http_requests_total.labels(
            method=method,
            endpoint=endpoint,
            status=str(status)
        ).inc()
        
        self.http_request_duration.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)
    
    def record_invoice_processed(
        self,
        source: str,
        status: str,
        duration: Optional[float] = None,
        stage: Optional[str] = None
    ) -> None:
        """Record invoice processing metrics."""
        if not PROMETHEUS_AVAILABLE:
            return
        
        self.invoices_processed_total.labels(
            source=source,
            status=status
        ).inc()
        
        if duration and stage:
            self.invoice_processing_duration.labels(stage=stage).observe(duration)
    
    def record_ocr_operation(
        self,
        language: str,
        status: str,
        duration: float,
        confidence: float,
        word_count: int
    ) -> None:
        """Record OCR operation metrics."""
        if not PROMETHEUS_AVAILABLE:
            return
        
        self.ocr_operations_total.labels(
            language=language,
            status=status
        ).inc()
        
        self.ocr_processing_duration.labels(language=language).observe(duration)
        self.ocr_confidence.labels(language=language).observe(confidence)
        self.ocr_word_count.observe(word_count)
    
    def record_llm_request(
        self,
        provider: str,
        model: str,
        operation: str,
        status: str,
        duration: float,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float = 0.0
    ) -> None:
        """Record LLM API request metrics."""
        if not PROMETHEUS_AVAILABLE:
            return
        
        self.llm_requests_total.labels(
            provider=provider,
            model=model,
            operation=operation,
            status=status
        ).inc()
        
        self.llm_request_duration.labels(
            provider=provider,
            model=model
        ).observe(duration)
        
        if input_tokens:
            self.llm_tokens_used.labels(
                provider=provider,
                model=model,
                type="input"
            ).inc(input_tokens)
        
        if output_tokens:
            self.llm_tokens_used.labels(
                provider=provider,
                model=model,
                type="output"
            ).inc(output_tokens)
        
        if cost_usd:
            self.llm_cost_usd.labels(
                provider=provider,
                model=model
            ).inc(cost_usd)
    
    def record_extraction(
        self,
        field_type: str,
        status: str,
        confidence: Optional[float] = None
    ) -> None:
        """Record field extraction metrics."""
        if not PROMETHEUS_AVAILABLE:
            return
        
        self.extraction_fields_total.labels(
            field_type=field_type,
            status=status
        ).inc()
        
        if confidence is not None:
            self.extraction_confidence.labels(field_type=field_type).observe(confidence)
    
    def record_anomaly(self, anomaly_type: str, severity: str) -> None:
        """Record detected anomaly."""
        if not PROMETHEUS_AVAILABLE:
            return
        
        self.anomalies_detected_total.labels(
            anomaly_type=anomaly_type,
            severity=severity
        ).inc()
    
    def record_approval(
        self,
        action: str,
        is_auto: bool,
        duration_seconds: Optional[float] = None
    ) -> None:
        """Record approval action."""
        if not PROMETHEUS_AVAILABLE:
            return
        
        self.approvals_total.labels(
            action=action,
            auto=str(is_auto).lower()
        ).inc()
        
        if duration_seconds:
            self.approval_duration.observe(duration_seconds)
    
    def record_error(self, error_type: str, component: str) -> None:
        """Record an error."""
        if not PROMETHEUS_AVAILABLE:
            return
        
        self.errors_total.labels(
            error_type=error_type,
            component=component
        ).inc()
    
    # === Utility Methods ===
    
    @contextmanager
    def timer(self, metric_name: str, labels: Optional[Dict[str, str]] = None):
        """Context manager to time operations."""
        start = time.time()
        try:
            yield
        finally:
            duration = time.time() - start
            if PROMETHEUS_AVAILABLE and hasattr(self, metric_name):
                metric = getattr(self, metric_name)
                if labels:
                    metric.labels(**labels).observe(duration)
                else:
                    metric.observe(duration)
    
    def get_metrics(self) -> bytes:
        """Generate Prometheus metrics output."""
        if not PROMETHEUS_AVAILABLE:
            return b"# Prometheus client not installed\n"
        
        return generate_latest(REGISTRY)
    
    def get_content_type(self) -> str:
        """Get Prometheus content type."""
        if not PROMETHEUS_AVAILABLE:
            return "text/plain"
        
        return CONTENT_TYPE_LATEST


# Singleton instance
_metrics: Optional[MetricsCollector] = None


def get_metrics() -> MetricsCollector:
    """Get or create metrics collector instance."""
    global _metrics
    if _metrics is None:
        _metrics = MetricsCollector()
    return _metrics


# Decorators
def track_request(endpoint: str):
    """Decorator to track HTTP request metrics."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.time()
            status = 200
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status = 500
                raise
            finally:
                duration = time.time() - start
                get_metrics().record_http_request(
                    method="POST",  # Simplified
                    endpoint=endpoint,
                    status=status,
                    duration=duration
                )
        return wrapper
    return decorator


def track_llm(provider: str, model: str, operation: str):
    """Decorator to track LLM API calls."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.time()
            status = "success"
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status = "error"
                raise
            finally:
                duration = time.time() - start
                get_metrics().record_llm_request(
                    provider=provider,
                    model=model,
                    operation=operation,
                    status=status,
                    duration=duration
                )
        return wrapper
    return decorator
