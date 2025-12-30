"""
Approval Service
================
Handles approval workflow with event publishing.
"""

import os
import sys
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from enum import Enum
import structlog

# Add paths for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logger = structlog.get_logger(__name__)


class ApprovalDecision(str, Enum):
    """Approval decision types."""
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"
    DELEGATED = "delegated"


class ApprovalService:
    """
    Service for managing invoice approval workflows with event publishing.
    
    Features:
    - Automatic approval routing based on rules
    - Event publishing for all approval actions
    - SLA tracking and escalation
    - Multi-level approval support
    """
    
    def __init__(self):
        self.logger = logger.bind(service="ApprovalService")
    
    async def request_approval(
        self,
        invoice_id: str,
        invoice_data: Dict[str, Any],
        required_approvers: Optional[List[str]] = None,
        due_date: Optional[datetime] = None,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Request approval for an invoice.
        
        Args:
            invoice_id: Invoice identifier
            invoice_data: Invoice details
            required_approvers: List of approver IDs/emails
            due_date: Approval deadline
            correlation_id: Correlation ID for tracking
            
        Returns:
            Approval task details
        """
        self.logger.info(
            "Requesting invoice approval",
            invoice_id=invoice_id,
            amount=invoice_data.get("total_amount"),
            vendor=invoice_data.get("vendor_name")
        )
        
        try:
            # Determine approvers based on rules if not specified
            if not required_approvers:
                required_approvers = await self._determine_approvers(invoice_data)
            
            # Calculate due date if not specified (default: 2 business days)
            if not due_date:
                due_date = datetime.utcnow() + timedelta(days=2)
            
            # Create approval task
            task_id = f"task-{invoice_id}-{datetime.utcnow().timestamp()}"
            
            approval_task = {
                "task_id": task_id,
                "invoice_id": invoice_id,
                "invoice_number": invoice_data.get("invoice_number"),
                "vendor_name": invoice_data.get("vendor_name"),
                "amount": invoice_data.get("total_amount"),
                "currency": invoice_data.get("currency", "USD"),
                "required_approvers": required_approvers,
                "due_date": due_date.isoformat(),
                "status": "pending",
                "created_at": datetime.utcnow().isoformat()
            }
            
            # Publish APPROVAL_REQUESTED event
            await self._publish_approval_requested(
                invoice_id=invoice_id,
                task_id=task_id,
                required_approvers=required_approvers,
                due_date=due_date.isoformat(),
                invoice_data=invoice_data,
                correlation_id=correlation_id
            )
            
            # Assign to first approver
            if required_approvers:
                await self._assign_approval_task(
                    task_id=task_id,
                    invoice_id=invoice_id,
                    approver_id=required_approvers[0],
                    correlation_id=correlation_id
                )
            
            self.logger.info(
                "Approval requested successfully",
                invoice_id=invoice_id,
                task_id=task_id,
                approvers=len(required_approvers)
            )
            
            return approval_task
            
        except Exception as e:
            self.logger.error(
                "Failed to request approval",
                invoice_id=invoice_id,
                error=str(e)
            )
            
            # Publish error event
            await self._publish_error_event(invoice_id, str(e))
            raise
    
    async def process_approval_decision(
        self,
        task_id: str,
        invoice_id: str,
        approver_id: str,
        decision: ApprovalDecision,
        comments: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process an approval decision.
        
        Args:
            task_id: Approval task ID
            invoice_id: Invoice identifier
            approver_id: Approver identifier
            decision: Approval decision
            comments: Optional comments
            correlation_id: Correlation ID for tracking
            
        Returns:
            Decision result
        """
        self.logger.info(
            "Processing approval decision",
            task_id=task_id,
            invoice_id=invoice_id,
            approver=approver_id,
            decision=decision.value
        )
        
        try:
            result = {
                "task_id": task_id,
                "invoice_id": invoice_id,
                "approver_id": approver_id,
                "decision": decision.value,
                "comments": comments,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Publish APPROVAL_COMPLETED event
            await self._publish_approval_completed(
                task_id=task_id,
                invoice_id=invoice_id,
                approver_id=approver_id,
                decision=decision.value,
                comments=comments,
                correlation_id=correlation_id
            )
            
            # Publish invoice-level events based on decision
            if decision == ApprovalDecision.APPROVED:
                await self._publish_invoice_approved(
                    invoice_id=invoice_id,
                    approver=approver_id,
                    comments=comments,
                    correlation_id=correlation_id
                )
            elif decision == ApprovalDecision.REJECTED:
                await self._publish_invoice_rejected(
                    invoice_id=invoice_id,
                    rejector=approver_id,
                    reason=comments or "Rejected by approver",
                    correlation_id=correlation_id
                )
            
            self.logger.info(
                "Approval decision processed",
                task_id=task_id,
                decision=decision.value
            )
            
            return result
            
        except Exception as e:
            self.logger.error(
                "Failed to process approval decision",
                task_id=task_id,
                error=str(e)
            )
            raise
    
    async def escalate_approval(
        self,
        task_id: str,
        invoice_id: str,
        reason: str,
        escalate_to: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Escalate an approval task.
        
        Args:
            task_id: Approval task ID
            invoice_id: Invoice identifier
            reason: Escalation reason
            escalate_to: User to escalate to
            correlation_id: Correlation ID for tracking
            
        Returns:
            Escalation result
        """
        self.logger.info(
            "Escalating approval",
            task_id=task_id,
            invoice_id=invoice_id,
            reason=reason
        )
        
        try:
            # Publish escalation as APPROVAL_ASSIGNED event
            if escalate_to:
                await self._assign_approval_task(
                    task_id=task_id,
                    invoice_id=invoice_id,
                    approver_id=escalate_to,
                    correlation_id=correlation_id,
                    reason=f"Escalated: {reason}"
                )
            
            return {
                "task_id": task_id,
                "invoice_id": invoice_id,
                "status": "escalated",
                "escalated_to": escalate_to,
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(
                "Failed to escalate approval",
                task_id=task_id,
                error=str(e)
            )
            raise
    
    async def _determine_approvers(
        self,
        invoice_data: Dict[str, Any]
    ) -> List[str]:
        """
        Determine required approvers based on invoice amount and rules.
        
        Args:
            invoice_data: Invoice details
            
        Returns:
            List of approver IDs
        """
        amount = invoice_data.get("total_amount", 0.0)
        risk_score = invoice_data.get("risk_score", 0.0)
        
        approvers = []
        
        # Amount-based routing
        if amount < 500:
            # Auto-approve or single approver
            approvers = ["auto-approve"]
        elif amount < 5000:
            # Department manager
            approvers = ["manager@company.com"]
        elif amount < 50000:
            # Manager + Finance
            approvers = ["manager@company.com", "finance@company.com"]
        else:
            # Manager + Finance + Director
            approvers = ["manager@company.com", "finance@company.com", "director@company.com"]
        
        # Risk-based escalation
        if risk_score > 0.7:
            approvers.append("risk-team@company.com")
        
        return approvers
    
    async def _assign_approval_task(
        self,
        task_id: str,
        invoice_id: str,
        approver_id: str,
        correlation_id: Optional[str] = None,
        reason: Optional[str] = None
    ):
        """Publish APPROVAL_ASSIGNED event."""
        try:
            from shared.event_publishers import publish_approval_assigned
            
            success = await publish_approval_assigned(
                task_id=task_id,
                invoice_id=invoice_id,
                approver_id=approver_id
            )
            
            if success:
                self.logger.info(
                    "APPROVAL_ASSIGNED event published",
                    task_id=task_id,
                    approver=approver_id
                )
            
        except Exception as e:
            self.logger.error(
                "Failed to publish APPROVAL_ASSIGNED event",
                task_id=task_id,
                error=str(e)
            )
    
    async def _publish_approval_requested(
        self,
        invoice_id: str,
        task_id: str,
        required_approvers: List[str],
        due_date: str,
        invoice_data: Dict[str, Any],
        correlation_id: Optional[str] = None
    ):
        """Publish APPROVAL_REQUESTED event."""
        try:
            from shared.event_publishers import publish_approval_requested
            
            success = await publish_approval_requested(
                invoice_id=invoice_id,
                required_approvers=required_approvers,
                due_date=due_date
            )
            
            if success:
                self.logger.info(
                    "APPROVAL_REQUESTED event published",
                    invoice_id=invoice_id,
                    task_id=task_id
                )
            
        except Exception as e:
            self.logger.error(
                "Failed to publish APPROVAL_REQUESTED event",
                invoice_id=invoice_id,
                error=str(e)
            )
    
    async def _publish_approval_completed(
        self,
        task_id: str,
        invoice_id: str,
        approver_id: str,
        decision: str,
        comments: Optional[str],
        correlation_id: Optional[str] = None
    ):
        """Publish APPROVAL_COMPLETED event."""
        try:
            from shared.event_publishers import publish_approval_completed
            
            success = await publish_approval_completed(
                task_id=task_id,
                invoice_id=invoice_id,
                approver_id=approver_id,
                decision=decision,
                comments=comments
            )
            
            if success:
                self.logger.info(
                    "APPROVAL_COMPLETED event published",
                    task_id=task_id,
                    decision=decision
                )
            
        except Exception as e:
            self.logger.error(
                "Failed to publish APPROVAL_COMPLETED event",
                task_id=task_id,
                error=str(e)
            )
    
    async def _publish_invoice_approved(
        self,
        invoice_id: str,
        approver: str,
        comments: Optional[str],
        correlation_id: Optional[str] = None
    ):
        """Publish INVOICE_APPROVED event."""
        try:
            from shared.event_publishers import publish_invoice_approved
            
            success = await publish_invoice_approved(
                invoice_id=invoice_id,
                approver=approver,
                comments=comments
            )
            
            if success:
                self.logger.info(
                    "INVOICE_APPROVED event published",
                    invoice_id=invoice_id
                )
            
        except Exception as e:
            self.logger.error(
                "Failed to publish INVOICE_APPROVED event",
                invoice_id=invoice_id,
                error=str(e)
            )
    
    async def _publish_invoice_rejected(
        self,
        invoice_id: str,
        rejector: str,
        reason: str,
        correlation_id: Optional[str] = None
    ):
        """Publish INVOICE_REJECTED event."""
        try:
            from shared.event_publishers import publish_invoice_rejected
            
            success = await publish_invoice_rejected(
                invoice_id=invoice_id,
                rejector=rejector,
                reason=reason
            )
            
            if success:
                self.logger.info(
                    "INVOICE_REJECTED event published",
                    invoice_id=invoice_id
                )
            
        except Exception as e:
            self.logger.error(
                "Failed to publish INVOICE_REJECTED event",
                invoice_id=invoice_id,
                error=str(e)
            )
    
    async def _publish_error_event(self, invoice_id: str, error: str):
        """Publish system error event."""
        try:
            from shared.event_publishers import publish_system_error
            
            await publish_system_error(
                component="approval-service",
                error=f"Approval processing failed: {error}",
                severity="error",
                details={"invoice_id": invoice_id}
            )
        except Exception as e:
            self.logger.error(
                "Failed to publish error event",
                invoice_id=invoice_id,
                error=str(e)
            )


# Singleton instance
_approval_service: Optional[ApprovalService] = None


def get_approval_service() -> ApprovalService:
    """Get or create approval service instance."""
    global _approval_service
    if _approval_service is None:
        _approval_service = ApprovalService()
    return _approval_service
