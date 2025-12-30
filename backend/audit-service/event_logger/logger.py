"""
Audit Event Logger
==================
Immutable audit logging for compliance.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json
import hashlib
import structlog

logger = structlog.get_logger(__name__)


class AuditEventType(str, Enum):
    """Types of auditable events."""
    # Document events
    DOCUMENT_UPLOADED = "document.uploaded"
    DOCUMENT_PROCESSED = "document.processed"
    DOCUMENT_DELETED = "document.deleted"
    
    # Invoice events
    INVOICE_CREATED = "invoice.created"
    INVOICE_UPDATED = "invoice.updated"
    INVOICE_EXTRACTED = "invoice.extracted"
    INVOICE_VALIDATED = "invoice.validated"
    
    # Workflow events
    WORKFLOW_STARTED = "workflow.started"
    WORKFLOW_TRANSITIONED = "workflow.transitioned"
    REVIEW_REQUESTED = "workflow.review_requested"
    APPROVED = "workflow.approved"
    REJECTED = "workflow.rejected"
    ESCALATED = "workflow.escalated"
    
    # User events
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    USER_ACTION = "user.action"
    
    # System events
    SYSTEM_ERROR = "system.error"
    CONFIG_CHANGED = "system.config_changed"
    RULE_UPDATED = "system.rule_updated"


@dataclass
class AuditEvent:
    """An immutable audit event."""
    id: str
    event_type: AuditEventType
    timestamp: datetime
    actor: str  # User ID or "system"
    tenant_id: str
    resource_type: str  # invoice, document, user, etc.
    resource_id: str
    action: str
    details: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    checksum: Optional[str] = None  # For integrity verification
    
    def compute_checksum(self) -> str:
        """Compute SHA-256 checksum for integrity."""
        data = {
            "id": self.id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "actor": self.actor,
            "tenant_id": self.tenant_id,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "action": self.action,
            "details": self.details,
        }
        content = json.dumps(data, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()


class AuditLogger:
    """
    Immutable audit logger for enterprise compliance.
    
    Features:
    - Append-only logging
    - Integrity checksums
    - Search and filtering
    - Retention policies
    """
    
    def __init__(self, retention_days: int = 2555):  # 7 years default
        self._events: List[AuditEvent] = []
        self.retention_days = retention_days
        self._event_counter = 0
    
    def log(
        self,
        event_type: AuditEventType,
        actor: str,
        tenant_id: str,
        resource_type: str,
        resource_id: str,
        action: str,
        details: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        """
        Log an audit event.
        
        Events are immutable once logged.
        """
        self._event_counter += 1
        event_id = f"AE-{datetime.utcnow().strftime('%Y%m%d')}-{self._event_counter:08d}"
        
        event = AuditEvent(
            id=event_id,
            event_type=event_type,
            timestamp=datetime.utcnow(),
            actor=actor,
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            details=details or {},
            metadata=metadata or {},
        )
        
        # Compute integrity checksum
        event.checksum = event.compute_checksum()
        
        # Append (immutable)
        self._events.append(event)
        
        logger.info(
            "Audit event logged",
            event_id=event_id,
            event_type=event_type.value,
            actor=actor,
            resource=f"{resource_type}:{resource_id}",
        )
        
        return event
    
    def query(
        self,
        tenant_id: Optional[str] = None,
        event_type: Optional[AuditEventType] = None,
        actor: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """
        Query audit events with filters.
        """
        results = self._events
        
        if tenant_id:
            results = [e for e in results if e.tenant_id == tenant_id]
        if event_type:
            results = [e for e in results if e.event_type == event_type]
        if actor:
            results = [e for e in results if e.actor == actor]
        if resource_type:
            results = [e for e in results if e.resource_type == resource_type]
        if resource_id:
            results = [e for e in results if e.resource_id == resource_id]
        if from_date:
            results = [e for e in results if e.timestamp >= from_date]
        if to_date:
            results = [e for e in results if e.timestamp <= to_date]
        
        # Sort by timestamp descending (most recent first)
        results.sort(key=lambda e: e.timestamp, reverse=True)
        
        return results[:limit]
    
    def get_resource_history(
        self,
        resource_type: str,
        resource_id: str,
    ) -> List[AuditEvent]:
        """Get complete history for a resource."""
        return self.query(
            resource_type=resource_type,
            resource_id=resource_id,
            limit=1000,
        )
    
    def get_user_activity(
        self,
        actor: str,
        from_date: Optional[datetime] = None,
    ) -> List[AuditEvent]:
        """Get all activity for a user."""
        return self.query(
            actor=actor,
            from_date=from_date,
            limit=1000,
        )
    
    def verify_integrity(self, event: AuditEvent) -> bool:
        """Verify event integrity using checksum."""
        computed = event.compute_checksum()
        return computed == event.checksum
    
    def export_for_compliance(
        self,
        tenant_id: str,
        from_date: datetime,
        to_date: datetime,
    ) -> str:
        """Export audit log in compliance-ready JSON format."""
        events = self.query(
            tenant_id=tenant_id,
            from_date=from_date,
            to_date=to_date,
            limit=100000,
        )
        
        export_data = {
            "export_date": datetime.utcnow().isoformat(),
            "tenant_id": tenant_id,
            "date_range": {
                "from": from_date.isoformat(),
                "to": to_date.isoformat(),
            },
            "event_count": len(events),
            "events": [
                {
                    "id": e.id,
                    "type": e.event_type.value,
                    "timestamp": e.timestamp.isoformat(),
                    "actor": e.actor,
                    "resource": f"{e.resource_type}:{e.resource_id}",
                    "action": e.action,
                    "details": e.details,
                    "checksum": e.checksum,
                }
                for e in events
            ]
        }
        
        return json.dumps(export_data, indent=2)


# Default logger instance
audit_logger = AuditLogger()
