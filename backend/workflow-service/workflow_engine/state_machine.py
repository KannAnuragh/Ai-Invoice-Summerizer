"""
Workflow State Machine
======================
Invoice lifecycle state management.
"""

from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import structlog

logger = structlog.get_logger(__name__)


class InvoiceState(str, Enum):
    """Invoice lifecycle states."""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    OCR_COMPLETE = "ocr_complete"
    EXTRACTED = "extracted"
    VALIDATED = "validated"
    REVIEW_PENDING = "review_pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PAYMENT_PENDING = "payment_pending"
    PAID = "paid"
    ARCHIVED = "archived"
    ERROR = "error"


class TransitionAction(str, Enum):
    """Actions that trigger state transitions."""
    UPLOAD = "upload"
    START_PROCESSING = "start_processing"
    COMPLETE_OCR = "complete_ocr"
    COMPLETE_EXTRACTION = "complete_extraction"
    VALIDATE = "validate"
    REQUEST_REVIEW = "request_review"
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_PAYMENT = "request_payment"
    CONFIRM_PAYMENT = "confirm_payment"
    ARCHIVE = "archive"
    REPORT_ERROR = "report_error"
    RETRY = "retry"


@dataclass
class StateTransition:
    """A state transition record."""
    from_state: InvoiceState
    to_state: InvoiceState
    action: TransitionAction
    timestamp: datetime
    actor: Optional[str] = None
    comment: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowState:
    """Current workflow state for an invoice."""
    invoice_id: str
    current_state: InvoiceState
    history: List[StateTransition] = field(default_factory=list)
    assigned_to: Optional[str] = None
    due_date: Optional[datetime] = None
    sla_status: str = "on_track"
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


class StateMachine:
    """
    Invoice workflow state machine.
    
    Manages state transitions and enforces valid paths.
    """
    
    # Valid state transitions
    TRANSITIONS = {
        InvoiceState.UPLOADED: {
            TransitionAction.START_PROCESSING: InvoiceState.PROCESSING,
            TransitionAction.REPORT_ERROR: InvoiceState.ERROR,
        },
        InvoiceState.PROCESSING: {
            TransitionAction.COMPLETE_OCR: InvoiceState.OCR_COMPLETE,
            TransitionAction.REPORT_ERROR: InvoiceState.ERROR,
        },
        InvoiceState.OCR_COMPLETE: {
            TransitionAction.COMPLETE_EXTRACTION: InvoiceState.EXTRACTED,
            TransitionAction.REPORT_ERROR: InvoiceState.ERROR,
        },
        InvoiceState.EXTRACTED: {
            TransitionAction.VALIDATE: InvoiceState.VALIDATED,
            TransitionAction.REPORT_ERROR: InvoiceState.ERROR,
        },
        InvoiceState.VALIDATED: {
            TransitionAction.REQUEST_REVIEW: InvoiceState.REVIEW_PENDING,
            TransitionAction.APPROVE: InvoiceState.APPROVED,  # Auto-approve path
        },
        InvoiceState.REVIEW_PENDING: {
            TransitionAction.APPROVE: InvoiceState.APPROVED,
            TransitionAction.REJECT: InvoiceState.REJECTED,
        },
        InvoiceState.APPROVED: {
            TransitionAction.REQUEST_PAYMENT: InvoiceState.PAYMENT_PENDING,
        },
        InvoiceState.PAYMENT_PENDING: {
            TransitionAction.CONFIRM_PAYMENT: InvoiceState.PAID,
            TransitionAction.REPORT_ERROR: InvoiceState.ERROR,
        },
        InvoiceState.PAID: {
            TransitionAction.ARCHIVE: InvoiceState.ARCHIVED,
        },
        InvoiceState.REJECTED: {
            TransitionAction.ARCHIVE: InvoiceState.ARCHIVED,
            TransitionAction.RETRY: InvoiceState.UPLOADED,  # Allow re-upload
        },
        InvoiceState.ERROR: {
            TransitionAction.RETRY: InvoiceState.UPLOADED,
            TransitionAction.ARCHIVE: InvoiceState.ARCHIVED,
        },
    }
    
    def __init__(self):
        self._workflows: Dict[str, WorkflowState] = {}
        self._hooks: Dict[InvoiceState, List[Callable]] = {}
    
    def create_workflow(
        self,
        invoice_id: str,
        initial_state: InvoiceState = InvoiceState.UPLOADED,
    ) -> WorkflowState:
        """Create a new workflow for an invoice."""
        workflow = WorkflowState(
            invoice_id=invoice_id,
            current_state=initial_state,
        )
        self._workflows[invoice_id] = workflow
        
        logger.info(
            "Workflow created",
            invoice_id=invoice_id,
            state=initial_state,
        )
        
        return workflow
    
    def get_workflow(self, invoice_id: str) -> Optional[WorkflowState]:
        """Get workflow state for an invoice."""
        return self._workflows.get(invoice_id)
    
    def can_transition(
        self,
        invoice_id: str,
        action: TransitionAction,
    ) -> bool:
        """Check if a transition is valid."""
        workflow = self._workflows.get(invoice_id)
        if not workflow:
            return False
        
        valid_actions = self.TRANSITIONS.get(workflow.current_state, {})
        return action in valid_actions
    
    def transition(
        self,
        invoice_id: str,
        action: TransitionAction,
        actor: Optional[str] = None,
        comment: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> WorkflowState:
        """
        Execute a state transition.
        
        Raises:
            ValueError: If transition is not valid
        """
        workflow = self._workflows.get(invoice_id)
        if not workflow:
            raise ValueError(f"No workflow found for invoice {invoice_id}")
        
        valid_actions = self.TRANSITIONS.get(workflow.current_state, {})
        
        if action not in valid_actions:
            raise ValueError(
                f"Invalid transition: {workflow.current_state} -> {action}. "
                f"Valid actions: {list(valid_actions.keys())}"
            )
        
        # Record transition
        from_state = workflow.current_state
        to_state = valid_actions[action]
        
        transition = StateTransition(
            from_state=from_state,
            to_state=to_state,
            action=action,
            timestamp=datetime.utcnow(),
            actor=actor,
            comment=comment,
            metadata=metadata or {},
        )
        
        workflow.history.append(transition)
        workflow.current_state = to_state
        workflow.updated_at = datetime.utcnow()
        
        logger.info(
            "State transition",
            invoice_id=invoice_id,
            from_state=from_state,
            to_state=to_state,
            action=action,
            actor=actor,
        )
        
        # Execute hooks
        self._execute_hooks(to_state, workflow)
        
        return workflow
    
    def register_hook(
        self,
        state: InvoiceState,
        hook: Callable[[WorkflowState], None],
    ) -> None:
        """Register a hook to be called when entering a state."""
        if state not in self._hooks:
            self._hooks[state] = []
        self._hooks[state].append(hook)
    
    def _execute_hooks(
        self,
        state: InvoiceState,
        workflow: WorkflowState,
    ) -> None:
        """Execute hooks for entering a state."""
        hooks = self._hooks.get(state, [])
        for hook in hooks:
            try:
                hook(workflow)
            except Exception as e:
                logger.error(
                    "Hook execution failed",
                    state=state,
                    error=str(e),
                )
    
    def get_available_actions(
        self,
        invoice_id: str,
    ) -> List[TransitionAction]:
        """Get available actions for an invoice."""
        workflow = self._workflows.get(invoice_id)
        if not workflow:
            return []
        
        valid_actions = self.TRANSITIONS.get(workflow.current_state, {})
        return list(valid_actions.keys())


# Default state machine instance
state_machine = StateMachine()
