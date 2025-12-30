"""
SLA Manager
===========
Monitors invoice processing SLAs and handles escalations.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import structlog

logger = structlog.get_logger(__name__)


class SLAStatus(str, Enum):
    """SLA status levels."""
    ON_TRACK = "on_track"
    WARNING = "warning"
    BREACHED = "breached"
    EXPIRED = "expired"


class EscalationLevel(str, Enum):
    """Escalation levels."""
    NONE = "none"
    REMINDER = "reminder"
    MANAGER = "manager"
    DIRECTOR = "director"
    EXECUTIVE = "executive"


@dataclass
class SLAConfig:
    """SLA configuration for invoice processing."""
    processing_hours: int = 24  # Time to process new invoices
    review_hours: int = 48  # Time to complete review
    approval_hours: int = 72  # Time to approve
    warning_threshold: float = 0.75  # Warn at 75% of deadline
    
    # Escalation timing
    first_reminder_hours: int = 4
    manager_escalation_hours: int = 8
    director_escalation_hours: int = 24


@dataclass
class SLARecord:
    """SLA tracking record for an invoice."""
    invoice_id: str
    created_at: datetime
    deadline: datetime
    status: SLAStatus = SLAStatus.ON_TRACK
    current_escalation: EscalationLevel = EscalationLevel.NONE
    reminder_count: int = 0
    last_reminder_at: Optional[datetime] = None
    breached_at: Optional[datetime] = None
    assigned_to: Optional[str] = None


class SLAManager:
    """
    Manages SLA tracking and escalations.
    
    Features:
    - Deadline tracking
    - Warning notifications
    - Automated escalation
    - SLA reporting
    """
    
    def __init__(self, config: Optional[SLAConfig] = None):
        self.config = config or SLAConfig()
        self._records: Dict[str, SLARecord] = {}
    
    def create_sla(
        self,
        invoice_id: str,
        stage: str = "processing",
        assigned_to: Optional[str] = None,
    ) -> SLARecord:
        """
        Create SLA record for an invoice.
        
        Args:
            invoice_id: Invoice identifier
            stage: Current processing stage
            assigned_to: Assigned user
        """
        now = datetime.utcnow()
        
        # Determine deadline based on stage
        if stage == "processing":
            hours = self.config.processing_hours
        elif stage == "review":
            hours = self.config.review_hours
        elif stage == "approval":
            hours = self.config.approval_hours
        else:
            hours = 24
        
        deadline = now + timedelta(hours=hours)
        
        record = SLARecord(
            invoice_id=invoice_id,
            created_at=now,
            deadline=deadline,
            assigned_to=assigned_to,
        )
        
        self._records[invoice_id] = record
        
        logger.info(
            "SLA created",
            invoice_id=invoice_id,
            stage=stage,
            deadline=deadline.isoformat(),
        )
        
        return record
    
    def check_sla(self, invoice_id: str) -> Optional[SLARecord]:
        """
        Check and update SLA status for an invoice.
        """
        record = self._records.get(invoice_id)
        if not record:
            return None
        
        now = datetime.utcnow()
        time_to_deadline = record.deadline - now
        total_time = record.deadline - record.created_at
        
        if time_to_deadline.total_seconds() <= 0:
            # Breached
            if record.status != SLAStatus.BREACHED:
                record.status = SLAStatus.BREACHED
                record.breached_at = now
                logger.warning("SLA breached", invoice_id=invoice_id)
        elif time_to_deadline < total_time * (1 - self.config.warning_threshold):
            # Warning zone
            if record.status == SLAStatus.ON_TRACK:
                record.status = SLAStatus.WARNING
                logger.info("SLA warning", invoice_id=invoice_id)
        
        return record
    
    def get_escalation_action(
        self,
        invoice_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Determine if escalation is needed and return action.
        """
        record = self.check_sla(invoice_id)
        if not record:
            return None
        
        now = datetime.utcnow()
        hours_elapsed = (now - record.created_at).total_seconds() / 3600
        
        action = None
        
        if record.status == SLAStatus.BREACHED:
            if record.current_escalation.value < EscalationLevel.EXECUTIVE.value:
                action = {
                    "type": "escalate",
                    "level": EscalationLevel.EXECUTIVE,
                    "reason": "SLA breached",
                    "invoice_id": invoice_id,
                }
                record.current_escalation = EscalationLevel.EXECUTIVE
        
        elif record.status == SLAStatus.WARNING:
            if hours_elapsed >= self.config.director_escalation_hours:
                if record.current_escalation.value < EscalationLevel.DIRECTOR.value:
                    action = {
                        "type": "escalate",
                        "level": EscalationLevel.DIRECTOR,
                        "reason": "SLA warning - director escalation",
                        "invoice_id": invoice_id,
                    }
                    record.current_escalation = EscalationLevel.DIRECTOR
            
            elif hours_elapsed >= self.config.manager_escalation_hours:
                if record.current_escalation.value < EscalationLevel.MANAGER.value:
                    action = {
                        "type": "escalate",
                        "level": EscalationLevel.MANAGER,
                        "reason": "SLA warning - manager escalation",
                        "invoice_id": invoice_id,
                    }
                    record.current_escalation = EscalationLevel.MANAGER
            
            elif hours_elapsed >= self.config.first_reminder_hours:
                if record.reminder_count < 3:  # Max 3 reminders
                    action = {
                        "type": "reminder",
                        "level": EscalationLevel.REMINDER,
                        "reason": "SLA warning - reminder",
                        "invoice_id": invoice_id,
                    }
                    record.reminder_count += 1
                    record.last_reminder_at = now
        
        return action
    
    def complete_sla(self, invoice_id: str) -> Optional[Dict[str, Any]]:
        """
        Mark SLA as completed and return metrics.
        """
        record = self._records.get(invoice_id)
        if not record:
            return None
        
        now = datetime.utcnow()
        processing_time = now - record.created_at
        
        metrics = {
            "invoice_id": invoice_id,
            "processing_time_hours": processing_time.total_seconds() / 3600,
            "was_breached": record.status == SLAStatus.BREACHED,
            "escalation_level": record.current_escalation.value,
            "reminder_count": record.reminder_count,
        }
        
        # Remove completed record
        del self._records[invoice_id]
        
        return metrics
    
    def get_all_at_risk(self) -> List[SLARecord]:
        """Get all invoices at risk of SLA breach."""
        at_risk = []
        
        for record in self._records.values():
            self.check_sla(record.invoice_id)
            if record.status in [SLAStatus.WARNING, SLAStatus.BREACHED]:
                at_risk.append(record)
        
        # Sort by deadline (most urgent first)
        at_risk.sort(key=lambda r: r.deadline)
        
        return at_risk
    
    def get_sla_stats(self) -> Dict[str, Any]:
        """Get SLA statistics for dashboard."""
        total = len(self._records)
        
        if total == 0:
            return {
                "total_active": 0,
                "on_track": 0,
                "warning": 0,
                "breached": 0,
                "compliance_rate": 1.0,
            }
        
        # Update all statuses
        for invoice_id in self._records:
            self.check_sla(invoice_id)
        
        on_track = sum(1 for r in self._records.values() if r.status == SLAStatus.ON_TRACK)
        warning = sum(1 for r in self._records.values() if r.status == SLAStatus.WARNING)
        breached = sum(1 for r in self._records.values() if r.status == SLAStatus.BREACHED)
        
        return {
            "total_active": total,
            "on_track": on_track,
            "warning": warning,
            "breached": breached,
            "compliance_rate": on_track / total if total else 1.0,
        }


# Default manager instance
sla_manager = SLAManager()
