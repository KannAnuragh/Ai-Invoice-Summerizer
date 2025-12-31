"""
Event Handlers
==============
Handlers for system events from message queue.
"""

import structlog
from typing import Dict, Any

from shared.message_queue import Message, EventType

logger = structlog.get_logger(__name__)


class InvoiceEventHandler:
    """Handle invoice-related events."""
    
    def __init__(self):
        self.logger = logger.bind(handler="InvoiceEventHandler")
    
    async def on_invoice_uploaded(self, message: Message):
        """Handle invoice upload event."""
        invoice_id = message.data.get("invoice_id")
        document_id = message.data.get("document_id")
        filename = message.data.get("filename")
        storage_path = message.data.get("storage_path")
        
        self.logger.info(
            "Invoice uploaded",
            invoice_id=invoice_id,
            filename=filename,
            correlation_id=message.correlation_id
        )
        
        # Trigger OCR processing and field extraction
        try:
            import sys
            import os
            sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'services'))
            from invoice_processor import get_invoice_processor
            
            processor = get_invoice_processor()
            
            # Process invoice (OCR + extraction)
            # This will automatically publish INVOICE_PROCESSED event
            extracted_data = await processor.process_invoice(
                document_id=document_id,
                invoice_id=invoice_id,
                file_path=storage_path,
                filename=filename,
                correlation_id=message.correlation_id
            )
            
            self.logger.info(
                "Invoice processing triggered",
                invoice_id=invoice_id,
                confidence=extracted_data.get("ocr_confidence", 0.0)
            )
            
        except Exception as e:
            self.logger.error(
                "Failed to trigger invoice processing",
                invoice_id=invoice_id,
                error=str(e)
            )
    
    async def on_invoice_processed(self, message: Message):
        """Handle invoice processing completion."""
        invoice_id = message.data.get("invoice_id")
        extracted_data = message.data.get("extracted_data", {})
        
        self.logger.info(
            "Invoice processed",
            invoice_id=invoice_id,
            correlation_id=message.correlation_id
        )
        
        # Update invoice with extracted data
        try:
            import sys
            import os
            from datetime import datetime
            sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
            from shared.database import get_async_session
            from shared.db_models import Invoice as DBInvoice, InvoiceStatus
            from sqlalchemy import select
            
            async with get_async_session() as db:
                # Fetch the invoice
                query = select(DBInvoice).where(DBInvoice.id == invoice_id)
                result = await db.execute(query)
                db_invoice = result.scalar_one_or_none()
                
                if db_invoice:
                    # Update invoice with extracted data
                    db_invoice.status = InvoiceStatus.EXTRACTED
                    db_invoice.vendor_name = extracted_data.get("vendor_name")
                    db_invoice.vendor_address = extracted_data.get("vendor_address")
                    db_invoice.invoice_number = extracted_data.get("invoice_number") or db_invoice.invoice_number
                    
                    # Parse dates
                    if extracted_data.get("invoice_date"):
                        try:
                            db_invoice.invoice_date = datetime.fromisoformat(extracted_data["invoice_date"])
                        except:
                            pass
                    
                    if extracted_data.get("due_date"):
                        try:
                            db_invoice.due_date = datetime.fromisoformat(extracted_data["due_date"])
                        except:
                            pass
                    
                    db_invoice.subtotal = extracted_data.get("subtotal")
                    db_invoice.tax_amount = extracted_data.get("tax_amount")
                    db_invoice.total_amount = extracted_data.get("total_amount")
                    db_invoice.currency = extracted_data.get("currency", "USD")
                    db_invoice.po_number = extracted_data.get("po_number")
                    db_invoice.payment_terms = extracted_data.get("payment_terms")
                    db_invoice.line_items = extracted_data.get("line_items", [])
                    
                    await db.commit()
                    
                    self.logger.info(
                        "Invoice updated with extracted data",
                        invoice_id=invoice_id,
                        vendor=extracted_data.get("vendor_name"),
                        total=extracted_data.get("total_amount")
                    )
                else:
                    self.logger.warning("Invoice not found for update", invoice_id=invoice_id)
                    
        except Exception as e:
            self.logger.error(
                "Failed to update invoice with extracted data",
                invoice_id=invoice_id,
                error=str(e)
            )
        
        # Trigger approval workflow
        try:
            import sys
            import os
            sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'services'))
            from approval_service import get_approval_service
            
            approval_service = get_approval_service()
            
            # Request approval with extracted invoice data
            approval_task = await approval_service.request_approval(
                invoice_id=invoice_id,
                invoice_data=extracted_data,
                correlation_id=message.correlation_id
            )
            
            self.logger.info(
                "Approval workflow triggered",
                invoice_id=invoice_id,
                task_id=approval_task.get("task_id"),
                approvers=len(approval_task.get("required_approvers", []))
            )
            
        except Exception as e:
            self.logger.error(
                "Failed to trigger approval workflow",
                invoice_id=invoice_id,
                error=str(e)
            )
    
    async def on_invoice_approved(self, message: Message):
        """Handle invoice approval."""
        invoice_id = message.data.get("invoice_id")
        approver = message.data.get("approver")
        
        self.logger.info(
            "Invoice approved",
            invoice_id=invoice_id,
            approver=approver,
            correlation_id=message.correlation_id
        )
        
        # Update invoice status
        # In production: await invoice_service.update_status(invoice_id, "approved")
        
        # Initiate payment if auto-payment enabled
        # In production: await payment_service.initiate_payment(invoice_id)
        
        # Sync to ERP
        # In production: await erp_service.sync_invoice(invoice_id)
    
    async def on_invoice_rejected(self, message: Message):
        """Handle invoice rejection."""
        invoice_id = message.data.get("invoice_id")
        reason = message.data.get("reason")
        
        self.logger.warning(
            "Invoice rejected",
            invoice_id=invoice_id,
            reason=reason,
            correlation_id=message.correlation_id
        )
        
        # Notify vendor
        # In production: await notification_service.notify_vendor(invoice_id, reason)
    
    async def on_invoice_paid(self, message: Message):
        """Handle invoice payment completion."""
        invoice_id = message.data.get("invoice_id")
        amount = message.data.get("amount")
        
        self.logger.info(
            "Invoice paid",
            invoice_id=invoice_id,
            amount=amount,
            correlation_id=message.correlation_id
        )
        
        # Update accounting system
        # In production: await accounting_service.record_payment(invoice_id, amount)


class PaymentEventHandler:
    """Handle payment-related events."""
    
    def __init__(self):
        self.logger = logger.bind(handler="PaymentEventHandler")
    
    async def on_payment_initiated(self, message: Message):
        """Handle payment initiation."""
        invoice_id = message.data.get("invoice_id")
        transaction_id = message.data.get("transaction_id")
        amount = message.data.get("amount")
        
        self.logger.info(
            "Payment initiated",
            invoice_id=invoice_id,
            transaction_id=transaction_id,
            amount=amount,
            correlation_id=message.correlation_id
        )
        
        # Monitor payment status
        # In production: await payment_monitor.track(transaction_id)
    
    async def on_payment_completed(self, message: Message):
        """Handle payment completion."""
        invoice_id = message.data.get("invoice_id")
        transaction_id = message.data.get("transaction_id")
        amount = message.data.get("amount")
        
        self.logger.info(
            "Payment completed",
            invoice_id=invoice_id,
            transaction_id=transaction_id,
            amount=amount,
            correlation_id=message.correlation_id
        )
        
        # Update invoice status
        # In production: await invoice_service.mark_paid(invoice_id, transaction_id)
        
        # Generate receipt
        # In production: await receipt_service.generate(transaction_id)
        
        # Send confirmation email
        # In production: await email_service.send_payment_confirmation(invoice_id)
    
    async def on_payment_failed(self, message: Message):
        """Handle payment failure."""
        invoice_id = message.data.get("invoice_id")
        transaction_id = message.data.get("transaction_id")
        error = message.data.get("error")
        
        self.logger.error(
            "Payment failed",
            invoice_id=invoice_id,
            transaction_id=transaction_id,
            error=error,
            correlation_id=message.correlation_id
        )
        
        # Retry logic
        if message.retry_count < message.max_retries:
            self.logger.info("Retrying payment", transaction_id=transaction_id)
            # In production: await payment_service.retry(transaction_id)
        else:
            # Alert finance team
            # In production: await alert_service.notify_finance_team(invoice_id, error)
            pass
    
    async def on_payment_refunded(self, message: Message):
        """Handle payment refund."""
        invoice_id = message.data.get("invoice_id")
        transaction_id = message.data.get("transaction_id")
        amount = message.data.get("amount")
        
        self.logger.info(
            "Payment refunded",
            invoice_id=invoice_id,
            transaction_id=transaction_id,
            amount=amount,
            correlation_id=message.correlation_id
        )
        
        # Update accounting records
        # In production: await accounting_service.record_refund(transaction_id, amount)


class ERPEventHandler:
    """Handle ERP synchronization events."""
    
    def __init__(self):
        self.logger = logger.bind(handler="ERPEventHandler")
    
    async def on_erp_sync_started(self, message: Message):
        """Handle ERP sync start."""
        invoice_id = message.data.get("invoice_id")
        provider = message.data.get("provider")
        
        self.logger.info(
            "ERP sync started",
            invoice_id=invoice_id,
            provider=provider,
            correlation_id=message.correlation_id
        )
    
    async def on_erp_sync_completed(self, message: Message):
        """Handle ERP sync completion."""
        invoice_id = message.data.get("invoice_id")
        erp_record_id = message.data.get("erp_record_id")
        provider = message.data.get("provider")
        
        self.logger.info(
            "ERP sync completed",
            invoice_id=invoice_id,
            erp_record_id=erp_record_id,
            provider=provider,
            correlation_id=message.correlation_id
        )
        
        # Update invoice with ERP reference
        # In production: await invoice_service.update_erp_id(invoice_id, erp_record_id)
    
    async def on_erp_sync_failed(self, message: Message):
        """Handle ERP sync failure."""
        invoice_id = message.data.get("invoice_id")
        error = message.data.get("error")
        provider = message.data.get("provider")
        
        self.logger.error(
            "ERP sync failed",
            invoice_id=invoice_id,
            error=error,
            provider=provider,
            correlation_id=message.correlation_id
        )
        
        # Schedule retry
        if message.retry_count < message.max_retries:
            # In production: await erp_service.schedule_retry(invoice_id, provider)
            pass
        else:
            # Alert administrators
            # In production: await alert_service.notify_admins(invoice_id, error)
            pass


class ApprovalEventHandler:
    """Handle approval workflow events."""
    
    def __init__(self):
        self.logger = logger.bind(handler="ApprovalEventHandler")
    
    async def on_approval_requested(self, message: Message):
        """Handle approval request."""
        invoice_id = message.data.get("invoice_id")
        required_approvers = message.data.get("required_approvers", [])
        
        self.logger.info(
            "Approval requested",
            invoice_id=invoice_id,
            approvers_count=len(required_approvers),
            correlation_id=message.correlation_id
        )
        
        # Send notifications to approvers
        # In production: await notification_service.notify_approvers(invoice_id, required_approvers)
    
    async def on_approval_assigned(self, message: Message):
        """Handle approval task assignment."""
        task_id = message.data.get("task_id")
        approver_id = message.data.get("approver_id")
        
        self.logger.info(
            "Approval assigned",
            task_id=task_id,
            approver_id=approver_id,
            correlation_id=message.correlation_id
        )
        
        # Send notification to specific approver
        # In production: await notification_service.notify_approver(task_id, approver_id)
    
    async def on_approval_completed(self, message: Message):
        """Handle approval completion."""
        task_id = message.data.get("task_id")
        invoice_id = message.data.get("invoice_id")
        decision = message.data.get("decision")
        
        self.logger.info(
            "Approval completed",
            task_id=task_id,
            invoice_id=invoice_id,
            decision=decision,
            correlation_id=message.correlation_id
        )
        
        # Check if all required approvals are complete
        # In production: await workflow_service.check_approval_completion(invoice_id)


class SystemEventHandler:
    """Handle system-level events."""
    
    def __init__(self):
        self.logger = logger.bind(handler="SystemEventHandler")
    
    async def on_system_error(self, message: Message):
        """Handle system errors."""
        component = message.data.get("component")
        error = message.data.get("error")
        severity = message.data.get("severity", "error")
        
        self.logger.error(
            "System error",
            component=component,
            error=error,
            severity=severity,
            correlation_id=message.correlation_id
        )
        
        # Send to monitoring system
        # In production: await monitoring_service.log_error(component, error, severity)
        
        # Alert if critical
        if severity == "critical":
            # In production: await alert_service.send_critical_alert(component, error)
            pass
    
    async def on_system_warning(self, message: Message):
        """Handle system warnings."""
        component = message.data.get("component")
        warning = message.data.get("warning")
        
        self.logger.warning(
            "System warning",
            component=component,
            warning=warning,
            correlation_id=message.correlation_id
        )


def register_all_handlers(message_queue):
    """Register all event handlers with the message queue."""
    
    # Invoice handlers
    invoice_handler = InvoiceEventHandler()
    message_queue.subscribe(EventType.INVOICE_UPLOADED, invoice_handler.on_invoice_uploaded)
    message_queue.subscribe(EventType.INVOICE_PROCESSED, invoice_handler.on_invoice_processed)
    message_queue.subscribe(EventType.INVOICE_APPROVED, invoice_handler.on_invoice_approved)
    message_queue.subscribe(EventType.INVOICE_REJECTED, invoice_handler.on_invoice_rejected)
    message_queue.subscribe(EventType.INVOICE_PAID, invoice_handler.on_invoice_paid)
    
    # Payment handlers
    payment_handler = PaymentEventHandler()
    message_queue.subscribe(EventType.PAYMENT_INITIATED, payment_handler.on_payment_initiated)
    message_queue.subscribe(EventType.PAYMENT_COMPLETED, payment_handler.on_payment_completed)
    message_queue.subscribe(EventType.PAYMENT_FAILED, payment_handler.on_payment_failed)
    message_queue.subscribe(EventType.PAYMENT_REFUNDED, payment_handler.on_payment_refunded)
    
    # ERP handlers
    erp_handler = ERPEventHandler()
    message_queue.subscribe(EventType.ERP_SYNC_STARTED, erp_handler.on_erp_sync_started)
    message_queue.subscribe(EventType.ERP_SYNC_COMPLETED, erp_handler.on_erp_sync_completed)
    message_queue.subscribe(EventType.ERP_SYNC_FAILED, erp_handler.on_erp_sync_failed)
    
    # Approval handlers
    approval_handler = ApprovalEventHandler()
    message_queue.subscribe(EventType.APPROVAL_REQUESTED, approval_handler.on_approval_requested)
    message_queue.subscribe(EventType.APPROVAL_ASSIGNED, approval_handler.on_approval_assigned)
    message_queue.subscribe(EventType.APPROVAL_COMPLETED, approval_handler.on_approval_completed)
    
    # System handlers
    system_handler = SystemEventHandler()
    message_queue.subscribe(EventType.SYSTEM_ERROR, system_handler.on_system_error)
    message_queue.subscribe(EventType.SYSTEM_WARNING, system_handler.on_system_warning)
    
    logger.info("All event handlers registered")
