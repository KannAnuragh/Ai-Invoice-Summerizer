"""
Approvals Routes
================
Workflow approval management endpoints.
"""

from datetime import datetime, timedelta
from typing import Optional, List
from enum import Enum

from fastapi import APIRouter, HTTPException, Query, Path
from pydantic import BaseModel
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter()


class ApprovalStatus(str, Enum):
    """Approval task status."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"
    EXPIRED = "expired"


class ApprovalAction(str, Enum):
    """Available approval actions."""
    APPROVE = "approve"
    REJECT = "reject"
    ESCALATE = "escalate"
    REQUEST_INFO = "request_info"
    DELEGATE = "delegate"


class ApprovalTask(BaseModel):
    """Approval task in the queue."""
    id: str
    invoice_id: str
    invoice_number: Optional[str] = None
    vendor_name: Optional[str] = None
    amount: float
    currency: str = "USD"
    status: str = "pending"
    priority: str = "normal"
    assigned_to: Optional[str] = None
    due_date: Optional[str] = None
    due_in: Optional[str] = None
    sla_status: str = "on_track"
    created_at: str
    risk_score: Optional[float] = None


class ApprovalQueueResponse(BaseModel):
    """Approval queue response."""
    tasks: List[ApprovalTask]
    total: int
    page: int
    page_size: int


class ApprovalStatsResponse(BaseModel):
    """Approval statistics."""
    pending: int
    warning: int
    breached: int
    total_amount: float
    high_risk: int
    approved_today: int
    rejected_today: int


class ApprovalActionRequest(BaseModel):
    """Approval action request."""
    action: ApprovalAction
    comment: Optional[str] = None
    delegate_to: Optional[str] = None


# In-memory storage for demo
_approval_tasks: dict = {}


def _create_demo_approvals():
    """Create demo approval tasks."""
    if _approval_tasks:
        return
    
    now = datetime.utcnow()
    
    demo_tasks = [
        {
            "id": "apr-001",
            "invoice_id": "inv-001",
            "invoice_number": "INV-2024-0247",
            "vendor_name": "Acme Corporation",
            "amount": 12500,
            "currency": "USD",
            "status": "pending",
            "priority": "normal",
            "assigned_to": "You",
            "due_date": (now + timedelta(days=2)).isoformat(),
            "due_in": "2 days",
            "sla_status": "on_track",
            "created_at": now.isoformat(),
            "risk_score": 0.15,
        },
        {
            "id": "apr-002",
            "invoice_id": "inv-002",
            "invoice_number": "INV-2024-0244",
            "vendor_name": "CloudServices Ltd",
            "amount": 15000,
            "currency": "USD",
            "status": "pending",
            "priority": "high",
            "assigned_to": "You",
            "due_date": (now + timedelta(hours=4)).isoformat(),
            "due_in": "4 hours",
            "sla_status": "warning",
            "created_at": (now - timedelta(days=1)).isoformat(),
            "risk_score": 0.45,
        },
        {
            "id": "apr-003",
            "invoice_id": "inv-004",
            "invoice_number": "INV-2024-0240",
            "vendor_name": "Unknown Vendor",
            "amount": 45000,
            "currency": "USD",
            "status": "pending",
            "priority": "urgent",
            "assigned_to": "You",
            "due_date": (now - timedelta(hours=2)).isoformat(),
            "due_in": "Overdue",
            "sla_status": "breached",
            "created_at": (now - timedelta(days=3)).isoformat(),
            "risk_score": 0.75,
        },
    ]
    
    for task in demo_tasks:
        _approval_tasks[task["id"]] = task


# Initialize demo data
_create_demo_approvals()


@router.get("/approvals/queue", response_model=ApprovalQueueResponse)
async def get_approval_queue(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    assigned_to: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
) -> ApprovalQueueResponse:
    """
    Get pending approval tasks for the current user.
    """
    tasks = list(_approval_tasks.values())
    
    # Filter
    if status:
        tasks = [t for t in tasks if t.get("status") == status]
    if assigned_to:
        tasks = [t for t in tasks if t.get("assigned_to") == assigned_to]
    if priority:
        tasks = [t for t in tasks if t.get("priority") == priority]
    
    # Only pending tasks
    tasks = [t for t in tasks if t.get("status") == "pending"]
    
    # Sort by priority and due date
    priority_order = {"urgent": 0, "high": 1, "normal": 2}
    tasks.sort(key=lambda x: (priority_order.get(x.get("priority", "normal"), 2), x.get("due_date", "")))
    
    total = len(tasks)
    start = (page - 1) * page_size
    end = start + page_size
    
    return ApprovalQueueResponse(
        tasks=[ApprovalTask(**t) for t in tasks[start:end]],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/approvals/stats", response_model=ApprovalStatsResponse)
async def get_approval_stats() -> ApprovalStatsResponse:
    """
    Get approval statistics for dashboard.
    """
    tasks = list(_approval_tasks.values())
    pending_tasks = [t for t in tasks if t.get("status") == "pending"]
    
    return ApprovalStatsResponse(
        pending=len(pending_tasks),
        warning=len([t for t in pending_tasks if t.get("sla_status") == "warning"]),
        breached=len([t for t in pending_tasks if t.get("sla_status") == "breached"]),
        total_amount=sum(t.get("amount", 0) for t in pending_tasks),
        high_risk=len([t for t in pending_tasks if (t.get("risk_score") or 0) > 0.5]),
        approved_today=0,
        rejected_today=0,
    )


@router.get("/approvals/{task_id}")
async def get_approval_task(
    task_id: str = Path(..., description="Approval task ID")
) -> ApprovalTask:
    """
    Get details of a specific approval task.
    """
    if task_id not in _approval_tasks:
        raise HTTPException(status_code=404, detail="Approval task not found")
    
    return ApprovalTask(**_approval_tasks[task_id])


@router.post("/approvals/{task_id}/action")
async def process_approval_action(
    task_id: str = Path(..., description="Approval task ID"),
    request: ApprovalActionRequest = None,
) -> dict:
    """
    Process an approval action (approve, reject, escalate, etc.).
    """
    if task_id not in _approval_tasks:
        raise HTTPException(status_code=404, detail="Approval task not found")
    
    task = _approval_tasks[task_id]
    
    if task["status"] != "pending":
        raise HTTPException(status_code=400, detail="Task is no longer pending")
    
    action = request.action if request else ApprovalAction.APPROVE
    
    # Process action
    if action == ApprovalAction.APPROVE:
        task["status"] = "approved"
    elif action == ApprovalAction.REJECT:
        task["status"] = "rejected"
    elif action == ApprovalAction.ESCALATE:
        task["status"] = "escalated"
        task["priority"] = "urgent"
    elif action == ApprovalAction.DELEGATE:
        task["assigned_to"] = request.delegate_to if request else None
    
    task["updated_at"] = datetime.utcnow().isoformat()
    _approval_tasks[task_id] = task
    
    logger.info(
        "Approval action processed",
        task_id=task_id,
        action=action,
        comment=request.comment if request else None,
    )
    
    # Publish approval events
    try:
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'services'))
        from approval_service import get_approval_service, ApprovalDecision
        
        approval_service = get_approval_service()
        
        if action == ApprovalAction.APPROVE:
            await approval_service.process_approval_decision(
                task_id=task_id,
                invoice_id=task["invoice_id"],
                approver_id="current_user",  # TODO: Get from auth
                decision=ApprovalDecision.APPROVED,
                comments=request.comment if request else None
            )
        elif action == ApprovalAction.REJECT:
            await approval_service.process_approval_decision(
                task_id=task_id,
                invoice_id=task["invoice_id"],
                approver_id="current_user",
                decision=ApprovalDecision.REJECTED,
                comments=request.comment if request else None
            )
        elif action == ApprovalAction.ESCALATE:
            await approval_service.escalate_approval(
                task_id=task_id,
                invoice_id=task["invoice_id"],
                reason=request.comment if request else "Escalated by user",
                escalate_to=request.delegate_to if request and request.delegate_to else None
            )
    except Exception as e:
        logger.warning("Failed to publish approval events", error=str(e))
    
    return {
        "success": True,
        "task_id": task_id,
        "action": action,
        "new_status": task["status"],
        "message": f"Invoice {task['invoice_number']} has been {task['status']}"
    }
