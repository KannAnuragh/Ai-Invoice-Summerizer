"""
Event Publishers
================
Helper functions to publish events from various services.
"""

import structlog
from typing import Dict, Any, Optional

from .message_queue import get_message_queue, Message, EventType, MessagePriority

logger = structlog.get_logger(__name__)


async def publish_event(
    event_type: EventType,
    data: Dict[str, Any],
    priority: MessagePriority = MessagePriority.NORMAL,
    correlation_id: Optional[str] = None
) -> bool:
    """
    Publish an event to the message queue.
    
    Args:
        event_type: Type of event
        data: Event data
        priority: Message priority
        correlation_id: Correlation ID for tracking
        
    Returns:
        True if published successfully
    """
    try:
        queue = get_message_queue()
        if not queue:
            logger.warning("Message queue not available")
            return False
        
        message = Message(
            event_type=event_type,
            data=data,
            priority=priority,
            correlation_id=correlation_id
        )
        
        result = await queue.publish(message)
        
        if result:
            logger.debug(
                "Event published",
                event_type=event_type.value,
                correlation_id=correlation_id
            )
        
        return result
        
    except Exception as e:
        logger.error(
            "Failed to publish event",
            event_type=event_type.value,
            error=str(e)
        )
        return False


# Invoice Events

async def publish_invoice_uploaded(
    invoice_id: str,
    document_id: str,
    filename: str,
    size: int,
    storage_path: str,
    vendor_id: Optional[str] = None
) -> bool:
    """Publish invoice uploaded event."""
    return await publish_event(
        EventType.INVOICE_UPLOADED,
        {
            "invoice_id": invoice_id,
            "document_id": document_id,
            "filename": filename,
            "size": size,
            "storage_path": storage_path,
            "vendor_id": vendor_id
        },
        priority=MessagePriority.HIGH,
        correlation_id=document_id
    )


async def publish_invoice_processed(
    invoice_id: str,
    extracted_data: Dict[str, Any]
) -> bool:
    """Publish invoice processing completion event."""
    return await publish_event(
        EventType.INVOICE_PROCESSED,
        {
            "invoice_id": invoice_id,
            "extracted_data": extracted_data
        },
        priority=MessagePriority.NORMAL,
        correlation_id=invoice_id
    )


async def publish_invoice_approved(
    invoice_id: str,
    approver: str,
    comments: Optional[str] = None
) -> bool:
    """Publish invoice approval event."""
    return await publish_event(
        EventType.INVOICE_APPROVED,
        {
            "invoice_id": invoice_id,
            "approver": approver,
            "comments": comments
        },
        priority=MessagePriority.HIGH,
        correlation_id=invoice_id
    )


async def publish_invoice_rejected(
    invoice_id: str,
    rejector: str,
    reason: str
) -> bool:
    """Publish invoice rejection event."""
    return await publish_event(
        EventType.INVOICE_REJECTED,
        {
            "invoice_id": invoice_id,
            "rejector": rejector,
            "reason": reason
        },
        priority=MessagePriority.HIGH,
        correlation_id=invoice_id
    )


async def publish_invoice_paid(
    invoice_id: str,
    amount: float,
    currency: str,
    transaction_id: str
) -> bool:
    """Publish invoice payment completion event."""
    return await publish_event(
        EventType.INVOICE_PAID,
        {
            "invoice_id": invoice_id,
            "amount": amount,
            "currency": currency,
            "transaction_id": transaction_id
        },
        priority=MessagePriority.HIGH,
        correlation_id=invoice_id
    )


# Payment Events

async def publish_payment_initiated(
    invoice_id: str,
    transaction_id: str,
    amount: float,
    currency: str,
    payment_method: str
) -> bool:
    """Publish payment initiation event."""
    return await publish_event(
        EventType.PAYMENT_INITIATED,
        {
            "invoice_id": invoice_id,
            "transaction_id": transaction_id,
            "amount": amount,
            "currency": currency,
            "payment_method": payment_method
        },
        priority=MessagePriority.NORMAL,
        correlation_id=transaction_id
    )


async def publish_payment_completed(
    invoice_id: str,
    transaction_id: str,
    amount: float,
    currency: str
) -> bool:
    """Publish payment completion event."""
    return await publish_event(
        EventType.PAYMENT_COMPLETED,
        {
            "invoice_id": invoice_id,
            "transaction_id": transaction_id,
            "amount": amount,
            "currency": currency
        },
        priority=MessagePriority.HIGH,
        correlation_id=transaction_id
    )


async def publish_payment_failed(
    invoice_id: str,
    transaction_id: str,
    error: str
) -> bool:
    """Publish payment failure event."""
    return await publish_event(
        EventType.PAYMENT_FAILED,
        {
            "invoice_id": invoice_id,
            "transaction_id": transaction_id,
            "error": error
        },
        priority=MessagePriority.CRITICAL,
        correlation_id=transaction_id
    )


async def publish_payment_refunded(
    invoice_id: str,
    transaction_id: str,
    amount: float,
    currency: str,
    reason: Optional[str] = None
) -> bool:
    """Publish payment refund event."""
    return await publish_event(
        EventType.PAYMENT_REFUNDED,
        {
            "invoice_id": invoice_id,
            "transaction_id": transaction_id,
            "amount": amount,
            "currency": currency,
            "reason": reason
        },
        priority=MessagePriority.HIGH,
        correlation_id=transaction_id
    )


# ERP Events

async def publish_erp_sync_started(
    invoice_id: str,
    provider: str,
    sync_type: str
) -> bool:
    """Publish ERP sync start event."""
    return await publish_event(
        EventType.ERP_SYNC_STARTED,
        {
            "invoice_id": invoice_id,
            "provider": provider,
            "sync_type": sync_type
        },
        priority=MessagePriority.NORMAL,
        correlation_id=invoice_id
    )


async def publish_erp_sync_completed(
    invoice_id: str,
    provider: str,
    erp_record_id: str,
    sync_type: str
) -> bool:
    """Publish ERP sync completion event."""
    return await publish_event(
        EventType.ERP_SYNC_COMPLETED,
        {
            "invoice_id": invoice_id,
            "provider": provider,
            "erp_record_id": erp_record_id,
            "sync_type": sync_type
        },
        priority=MessagePriority.NORMAL,
        correlation_id=invoice_id
    )


async def publish_erp_sync_failed(
    invoice_id: str,
    provider: str,
    error: str
) -> bool:
    """Publish ERP sync failure event."""
    return await publish_event(
        EventType.ERP_SYNC_FAILED,
        {
            "invoice_id": invoice_id,
            "provider": provider,
            "error": error
        },
        priority=MessagePriority.HIGH,
        correlation_id=invoice_id
    )


# Approval Events

async def publish_approval_requested(
    invoice_id: str,
    required_approvers: list[str],
    due_date: Optional[str] = None
) -> bool:
    """Publish approval request event."""
    return await publish_event(
        EventType.APPROVAL_REQUESTED,
        {
            "invoice_id": invoice_id,
            "required_approvers": required_approvers,
            "due_date": due_date
        },
        priority=MessagePriority.HIGH,
        correlation_id=invoice_id
    )


async def publish_approval_assigned(
    task_id: str,
    invoice_id: str,
    approver_id: str
) -> bool:
    """Publish approval task assignment event."""
    return await publish_event(
        EventType.APPROVAL_ASSIGNED,
        {
            "task_id": task_id,
            "invoice_id": invoice_id,
            "approver_id": approver_id
        },
        priority=MessagePriority.NORMAL,
        correlation_id=task_id
    )


async def publish_approval_completed(
    task_id: str,
    invoice_id: str,
    approver_id: str,
    decision: str,
    comments: Optional[str] = None
) -> bool:
    """Publish approval completion event."""
    return await publish_event(
        EventType.APPROVAL_COMPLETED,
        {
            "task_id": task_id,
            "invoice_id": invoice_id,
            "approver_id": approver_id,
            "decision": decision,
            "comments": comments
        },
        priority=MessagePriority.HIGH,
        correlation_id=task_id
    )


# System Events

async def publish_system_error(
    component: str,
    error: str,
    severity: str = "error",
    details: Optional[Dict[str, Any]] = None
) -> bool:
    """Publish system error event."""
    return await publish_event(
        EventType.SYSTEM_ERROR,
        {
            "component": component,
            "error": error,
            "severity": severity,
            "details": details or {}
        },
        priority=MessagePriority.CRITICAL if severity == "critical" else MessagePriority.HIGH,
        correlation_id=None
    )


async def publish_system_warning(
    component: str,
    warning: str,
    details: Optional[Dict[str, Any]] = None
) -> bool:
    """Publish system warning event."""
    return await publish_event(
        EventType.SYSTEM_WARNING,
        {
            "component": component,
            "warning": warning,
            "details": details or {}
        },
        priority=MessagePriority.NORMAL,
        correlation_id=None
    )
