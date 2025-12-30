"""
Event Bus
=========
Simple event emitter for inter-service communication.
In production, replace with Redis Streams, RabbitMQ, or Kafka.
"""

import asyncio
from typing import Dict, List, Callable, Any
from datetime import datetime
import structlog

logger = structlog.get_logger(__name__)


class EventBus:
    """
    Simple async event bus for local development.
    
    In production, this should be replaced with:
    - Redis Streams for simple pub/sub
    - RabbitMQ for reliable messaging
    - Kafka for high-throughput event streaming
    """
    
    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = {}
        self._event_log: List[dict] = []
    
    def subscribe(self, event_type: str, handler: Callable) -> None:
        """Subscribe a handler to an event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.debug("Handler subscribed", event_type=event_type)
    
    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        """Unsubscribe a handler from an event type."""
        if event_type in self._handlers:
            self._handlers[event_type].remove(handler)
    
    async def emit(self, event_type: str, data: Any = None) -> None:
        """Emit an event to all subscribed handlers."""
        event = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        self._event_log.append(event)
        
        logger.info("Event emitted", event_type=event_type)
        
        handlers = self._handlers.get(event_type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except Exception as e:
                logger.error(
                    "Event handler error",
                    event_type=event_type,
                    handler=handler.__name__,
                    error=str(e),
                )
    
    def get_event_log(self, limit: int = 100) -> List[dict]:
        """Get recent events for debugging."""
        return self._event_log[-limit:]


# Singleton instance
event_bus = EventBus()


# Event type constants
class EventTypes:
    """Standard event types."""
    # Ingestion
    INVOICE_UPLOADED = "invoice.uploaded"
    INVOICE_VALIDATED = "invoice.validated"
    INVOICE_DUPLICATE_DETECTED = "invoice.duplicate_detected"
    
    # Processing
    OCR_STARTED = "ocr.started"
    OCR_COMPLETED = "ocr.completed"
    OCR_FAILED = "ocr.failed"
    
    EXTRACTION_STARTED = "extraction.started"
    EXTRACTION_COMPLETED = "extraction.completed"
    EXTRACTION_FAILED = "extraction.failed"
    
    # AI
    SUMMARIZATION_COMPLETED = "summarization.completed"
    ANOMALY_DETECTED = "anomaly.detected"
    RISK_SCORE_CALCULATED = "risk.calculated"
    
    # Workflow
    REVIEW_REQUESTED = "workflow.review_requested"
    APPROVED = "workflow.approved"
    REJECTED = "workflow.rejected"
    ESCALATED = "workflow.escalated"
    SLA_WARNING = "workflow.sla_warning"
    SLA_BREACH = "workflow.sla_breach"
    
    # Integration
    ERP_SYNC_STARTED = "integration.erp_sync_started"
    ERP_SYNC_COMPLETED = "integration.erp_sync_completed"
    PAYMENT_INITIATED = "integration.payment_initiated"
