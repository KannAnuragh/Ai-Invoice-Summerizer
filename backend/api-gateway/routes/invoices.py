"""
Invoices Routes
===============
CRUD operations for invoice management.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
import sys
import os

from fastapi import APIRouter, HTTPException, Query, Path, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
import structlog

# Ensure shared package is importable when running directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from shared.database import get_db
from shared.db_models import Invoice as DBInvoice, InvoiceStatus as DBInvoiceStatus

logger = structlog.get_logger(__name__)

router = APIRouter()


class InvoiceStatus(str, Enum):
    """Invoice lifecycle states."""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    EXTRACTED = "extracted"
    VALIDATED = "validated"
    REVIEW_PENDING = "review_pending"
    PENDING = "pending"
    REVIEW = "review"
    APPROVED = "approved"
    REJECTED = "rejected"
    PAID = "paid"
    ARCHIVED = "archived"


class LineItem(BaseModel):
    """Invoice line item."""
    description: str
    quantity: float
    unit_price: float
    total: float
    tax_rate: Optional[float] = None


class Vendor(BaseModel):
    """Vendor information."""
    id: Optional[str] = None
    name: Optional[str] = None
    address: Optional[str] = None
    tax_id: Optional[str] = None


class Invoice(BaseModel):
    """Invoice with flattened structure for frontend."""
    id: str
    document_id: Optional[str] = None
    status: str
    
    # Vendor info
    vendor: Optional[Vendor] = None
    
    # Invoice fields
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    due_date: Optional[str] = None
    
    # Amounts
    currency: str = "USD"
    subtotal: Optional[float] = None
    tax_amount: Optional[float] = None
    total_amount: Optional[float] = None
    
    # Line items
    line_items: List[LineItem] = Field(default_factory=list)
    
    # Other fields
    po_number: Optional[str] = None
    payment_terms: Optional[str] = None
    
    # Risk assessment only (no confidence)
    risk_score: Optional[float] = None
    anomalies: List[str] = Field(default_factory=list)
    
    # Summary
    summary: Optional[str] = None
    
    # Metadata
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    created_by: Optional[str] = None


class InvoiceListResponse(BaseModel):
    """Paginated invoice list response."""
    invoices: List[Invoice]
    total: int
    page: int
    page_size: int
    has_more: bool


class InvoiceUpdateRequest(BaseModel):
    """Update request body."""
    data: Optional[Dict[str, Any]] = None
    status: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_date(value: Any) -> Optional[datetime]:
    """Parse ISO date strings to datetime when possible."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _decimal_to_float(value: Any) -> Optional[float]:
    """Safely convert Decimal/None to float."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _db_invoice_to_dict(db_invoice: DBInvoice) -> dict:
    """Convert database invoice to dictionary for response models."""
    return {
        "id": db_invoice.id,
        "document_id": db_invoice.document_id,
        "status": db_invoice.status.value if hasattr(db_invoice.status, "value") else str(db_invoice.status),
        "vendor": {
            "id": db_invoice.vendor_id,
            "name": db_invoice.vendor_name or "Unknown",
            "address": db_invoice.vendor_address,
        } if db_invoice.vendor_id or db_invoice.vendor_name else None,
        "invoice_number": db_invoice.invoice_number,
        "invoice_date": db_invoice.invoice_date.isoformat() if db_invoice.invoice_date else None,
        "due_date": db_invoice.due_date.isoformat() if db_invoice.due_date else None,
        "currency": db_invoice.currency or "USD",
        "subtotal": _decimal_to_float(db_invoice.subtotal),
        "tax_amount": _decimal_to_float(db_invoice.tax_amount),
        "total_amount": _decimal_to_float(db_invoice.total_amount),
        "line_items": db_invoice.line_items or [],
        "po_number": db_invoice.po_number,
        "payment_terms": db_invoice.payment_terms,
        "risk_score": _decimal_to_float(db_invoice.risk_score),
        "anomalies": db_invoice.anomalies or [],
        "summary": db_invoice.summary,
        "created_at": db_invoice.created_at.isoformat() if db_invoice.created_at else None,
        "updated_at": db_invoice.updated_at.isoformat() if db_invoice.updated_at else None,
        "created_by": db_invoice.created_by,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/invoices", response_model=InvoiceListResponse)
async def list_invoices(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status"),
    search: Optional[str] = Query(None, description="Search by invoice number or vendor"),
    vendor_id: Optional[str] = Query(None, description="Filter by vendor"),
    db: AsyncSession = Depends(get_db),
) -> InvoiceListResponse:
    """List invoices with pagination and filtering."""
    query = select(DBInvoice)

    if status:
        query = query.where(DBInvoice.status == status)
    if vendor_id:
        query = query.where(DBInvoice.vendor_id == vendor_id)
    if search:
        pattern = f"%{search}%"
        query = query.where(
            or_(
                DBInvoice.invoice_number.ilike(pattern),
                DBInvoice.vendor_name.ilike(pattern),
            )
        )

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    paged_query = (
        query.order_by(DBInvoice.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    result = await db.execute(paged_query)
    db_invoices = result.scalars().all()

    invoices = [Invoice(**_db_invoice_to_dict(inv)) for inv in db_invoices]

    return InvoiceListResponse(
        invoices=invoices,
        total=total,
        page=page,
        page_size=limit,
        has_more=page * limit < total,
    )


@router.get("/invoices/{invoice_id}", response_model=Invoice)
async def get_invoice(
    invoice_id: str = Path(..., description="Invoice ID"),
    db: AsyncSession = Depends(get_db),
) -> Invoice:
    """Get a single invoice by ID."""
    query = select(DBInvoice).where(DBInvoice.id == invoice_id)
    result = await db.execute(query)
    db_invoice = result.scalar_one_or_none()

    if not db_invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    return Invoice(**_db_invoice_to_dict(db_invoice))


@router.patch("/invoices/{invoice_id}", response_model=Invoice)
async def update_invoice(
    invoice_id: str = Path(..., description="Invoice ID"),
    request: InvoiceUpdateRequest = None,
    db: AsyncSession = Depends(get_db),
) -> Invoice:
    """Update invoice data or status for human corrections."""
    query = select(DBInvoice).where(DBInvoice.id == invoice_id)
    result = await db.execute(query)
    db_invoice = result.scalar_one_or_none()

    if not db_invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    allowed_fields = {
        "vendor_id",
        "vendor_name",
        "vendor_address",
        "invoice_number",
        "invoice_date",
        "due_date",
        "currency",
        "subtotal",
        "tax_amount",
        "total_amount",
        "line_items",
        "po_number",
        "payment_terms",
        "risk_score",
        "anomalies",
        "summary",
        "document_id",
    }

    updated = False

    if request and request.data:
        for key, value in request.data.items():
            if key not in allowed_fields:
                continue
            if key in {"invoice_date", "due_date"}:
                parsed_date = _parse_date(value)
                if parsed_date:
                    setattr(db_invoice, key, parsed_date)
                    updated = True
                continue
            setattr(db_invoice, key, value)
            updated = True

    if request and request.status:
        try:
            db_invoice.status = DBInvoiceStatus(request.status)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status value")
        updated = True

    if updated:
        db_invoice.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(db_invoice)

    return Invoice(**_db_invoice_to_dict(db_invoice))


@router.get("/invoices/{invoice_id}/summary")
async def get_invoice_summary(
    invoice_id: str = Path(..., description="Invoice ID"),
    role: str = Query("finance", description="User role requesting summary"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Generate a simple role-based summary for an invoice."""
    query = select(DBInvoice).where(DBInvoice.id == invoice_id)
    result = await db.execute(query)
    db_invoice = result.scalar_one_or_none()

    if not db_invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    vendor_name = db_invoice.vendor_name or "Unknown vendor"
    amount = _decimal_to_float(db_invoice.total_amount) or 0.0
    currency = db_invoice.currency or "USD"
    invoice_number = db_invoice.invoice_number or "N/A"
    due_date = db_invoice.due_date.isoformat() if db_invoice.due_date else "N/A"
    risk_score = _decimal_to_float(db_invoice.risk_score)

    base_summary = (
        f"Invoice {invoice_number} from {vendor_name} for {currency} {amount:,.2f}. "
        f"Due: {due_date}."
    )

    role_summaries = {
        "finance": (
            f"Finance: {base_summary} "
            f"Tax: {_decimal_to_float(db_invoice.tax_amount) or 0.0:,.2f}."
        ),
        "procurement": (
            f"Procurement: {base_summary} "
            f"Line items: {len(db_invoice.line_items or [])}."
        ),
        "auditor": (
            f"Audit: {base_summary} "
            f"Risk score: {risk_score:.2f}" if risk_score is not None else base_summary
        ),
    }

    return {
        "invoice_id": invoice_id,
        "role": role,
        "summary": role_summaries.get(role, base_summary),
        "generated_at": datetime.utcnow().isoformat(),
    }


@router.get("/invoices/{invoice_id}/audit-trail")
async def get_audit_trail(
    invoice_id: str = Path(..., description="Invoice ID"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return basic audit trail derived from invoice timestamps."""
    query = select(DBInvoice).where(DBInvoice.id == invoice_id)
    result = await db.execute(query)
    db_invoice = result.scalar_one_or_none()

    if not db_invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    events = [
        {
            "action": "uploaded",
            "timestamp": db_invoice.created_at.isoformat() if db_invoice.created_at else None,
            "user": db_invoice.created_by or "system",
            "details": "Invoice uploaded",
        }
    ]

    if db_invoice.updated_at and db_invoice.updated_at != db_invoice.created_at:
        events.append(
            {
                "action": "updated",
                "timestamp": db_invoice.updated_at.isoformat(),
                "user": db_invoice.updated_by or db_invoice.created_by or "system",
                "details": "Invoice updated",
            }
        )

    events.append(
        {
            "action": "status",
            "timestamp": db_invoice.updated_at.isoformat() if db_invoice.updated_at else None,
            "user": db_invoice.updated_by or db_invoice.created_by or "system",
            "details": f"Status: {db_invoice.status}",
        }
    )

    return {
        "invoice_id": invoice_id,
        "events": events,
    }
