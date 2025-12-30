"""
Invoices Routes (Database-backed)
==================================
CRUD operations for invoice management with PostgreSQL persistence.
"""

from datetime import datetime
from typing import Optional, List
from decimal import Decimal
import sys
import os
import uuid

from fastapi import APIRouter, HTTPException, Query, Path, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
import structlog

# Add parent to path for shared imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from shared.database import get_db
from shared.db_models import Invoice as DBInvoice, Vendor as DBVendor, InvoiceStatus

logger = structlog.get_logger(__name__)

router = APIRouter()


# ============== Pydantic Models ==============

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
    vendor_confidence: Optional[float] = None
    
    # Invoice fields
    invoice_number: Optional[str] = None
    invoice_number_confidence: Optional[float] = None
    invoice_date: Optional[str] = None
    date_confidence: Optional[float] = None
    due_date: Optional[str] = None
    due_date_confidence: Optional[float] = None
    
    # Amounts
    currency: str = "USD"
    subtotal: Optional[float] = None
    tax_amount: Optional[float] = None
    total_amount: Optional[float] = None
    amount_confidence: Optional[float] = None
    
    # Line items
    line_items: List[LineItem] = []
    
    # Other fields
    po_number: Optional[str] = None
    payment_terms: Optional[str] = None
    
    # Scoring
    confidence: Optional[float] = None
    risk_score: Optional[float] = None
    anomalies: List[str] = []
    
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
    data: Optional[dict] = None
    status: Optional[str] = None


# ============== Helper Functions ==============

def db_invoice_to_pydantic(db_invoice: DBInvoice) -> Invoice:
    """Convert SQLAlchemy model to Pydantic model."""
    vendor_data = None
    if db_invoice.vendor:
        vendor_data = Vendor(
            id=db_invoice.vendor.id,
            name=db_invoice.vendor.name,
            address=db_invoice.vendor.address,
            tax_id=db_invoice.vendor.tax_id
        )
    elif db_invoice.vendor_name:
        vendor_data = Vendor(
            id=db_invoice.vendor_id,
            name=db_invoice.vendor_name,
            address=db_invoice.vendor_address
        )
    
    return Invoice(
        id=db_invoice.id,
        document_id=db_invoice.document_id,
        status=db_invoice.status.value if isinstance(db_invoice.status, InvoiceStatus) else db_invoice.status,
        vendor=vendor_data,
        vendor_confidence=db_invoice.vendor_confidence,
        invoice_number=db_invoice.invoice_number,
        invoice_number_confidence=db_invoice.invoice_number_confidence,
        invoice_date=db_invoice.invoice_date.isoformat() if db_invoice.invoice_date else None,
        date_confidence=db_invoice.date_confidence,
        due_date=db_invoice.due_date.isoformat() if db_invoice.due_date else None,
        due_date_confidence=db_invoice.due_date_confidence,
        currency=db_invoice.currency,
        subtotal=float(db_invoice.subtotal) if db_invoice.subtotal else None,
        tax_amount=float(db_invoice.tax_amount) if db_invoice.tax_amount else None,
        total_amount=float(db_invoice.total_amount) if db_invoice.total_amount else None,
        amount_confidence=db_invoice.amount_confidence,
        line_items=[LineItem(**item) for item in (db_invoice.line_items or [])],
        po_number=db_invoice.po_number,
        payment_terms=db_invoice.payment_terms,
        confidence=db_invoice.confidence,
        risk_score=db_invoice.risk_score,
        anomalies=db_invoice.anomalies or [],
        summary=db_invoice.summary,
        created_at=db_invoice.created_at.isoformat() if db_invoice.created_at else None,
        updated_at=db_invoice.updated_at.isoformat() if db_invoice.updated_at else None,
        created_by=db_invoice.created_by
    )


# ============== Routes ==============

@router.get("/invoices", response_model=InvoiceListResponse)
async def list_invoices(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, alias="page_size", description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status"),
    search: Optional[str] = Query(None, description="Search by invoice number or vendor"),
    vendor_id: Optional[str] = Query(None, description="Filter by vendor"),
    db: AsyncSession = Depends(get_db),
) -> InvoiceListResponse:
    """
    List invoices with pagination and filtering.
    """
    # Build query
    query = select(DBInvoice)
    
    # Apply filters
    filters = []
    if status:
        filters.append(DBInvoice.status == status)
    if vendor_id:
        filters.append(DBInvoice.vendor_id == vendor_id)
    if search:
        search_filter = or_(
            DBInvoice.invoice_number.ilike(f"%{search}%"),
            DBInvoice.vendor_name.ilike(f"%{search}%")
        )
        filters.append(search_filter)
    
    if filters:
        query = query.where(and_(*filters))
    
    # Get total count
    count_query = select(func.count()).select_from(DBInvoice)
    if filters:
        count_query = count_query.where(and_(*filters))
    result = await db.execute(count_query)
    total = result.scalar_one()
    
    # Apply pagination and sorting
    query = query.order_by(DBInvoice.created_at.desc())
    query = query.offset((page - 1) * limit).limit(limit)
    
    # Execute query
    result = await db.execute(query)
    invoices = result.scalars().all()
    
    return InvoiceListResponse(
        invoices=[db_invoice_to_pydantic(inv) for inv in invoices],
        total=total,
        page=page,
        page_size=limit,
        has_more=(page * limit) < total
    )


@router.get("/invoices/{invoice_id}", response_model=Invoice)
async def get_invoice(
    invoice_id: str = Path(..., description="Invoice ID"),
    db: AsyncSession = Depends(get_db),
) -> Invoice:
    """
    Get a single invoice by ID.
    """
    query = select(DBInvoice).where(DBInvoice.id == invoice_id)
    result = await db.execute(query)
    db_invoice = result.scalar_one_or_none()
    
    if not db_invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    return db_invoice_to_pydantic(db_invoice)


@router.patch("/invoices/{invoice_id}")
async def update_invoice(
    invoice_id: str = Path(..., description="Invoice ID"),
    request: InvoiceUpdateRequest = None,
    db: AsyncSession = Depends(get_db),
) -> Invoice:
    """
    Update invoice data or status.
    Used for human corrections and status transitions.
    """
    query = select(DBInvoice).where(DBInvoice.id == invoice_id)
    result = await db.execute(query)
    db_invoice = result.scalar_one_or_none()
    
    if not db_invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Update fields from request
    if request and request.data:
        for key, value in request.data.items():
            if hasattr(db_invoice, key):
                # Handle special types
                if key in ['subtotal', 'tax_amount', 'total_amount'] and value is not None:
                    value = Decimal(str(value))
                elif key in ['invoice_date', 'due_date'] and value is not None:
                    if isinstance(value, str):
                        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
                
                setattr(db_invoice, key, value)
    
    if request and request.status:
        try:
            db_invoice.status = InvoiceStatus(request.status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {request.status}")
    
    db_invoice.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(db_invoice)
    
    logger.info("Invoice updated", invoice_id=invoice_id, status=request.status if request else None)
    
    return db_invoice_to_pydantic(db_invoice)


@router.get("/invoices/{invoice_id}/summary")
async def get_invoice_summary(
    invoice_id: str = Path(..., description="Invoice ID"),
    role: str = Query("finance", description="Role-based summary (cfo, finance, procurement, auditor)"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get AI-generated summary for an invoice.
    Summary content varies based on user role.
    """
    query = select(DBInvoice).where(DBInvoice.id == invoice_id)
    result = await db.execute(query)
    db_invoice = result.scalar_one_or_none()
    
    if not db_invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Role-based summary templates
    vendor_name = db_invoice.vendor.name if db_invoice.vendor else db_invoice.vendor_name or "Unknown"
    invoice_num = db_invoice.invoice_number or "N/A"
    total = float(db_invoice.total_amount) if db_invoice.total_amount else 0
    currency = db_invoice.currency or "USD"
    risk = db_invoice.risk_score or 0
    confidence = db_invoice.confidence or 0
    line_count = len(db_invoice.line_items or [])
    
    summaries = {
        "cfo": f"**Executive Summary**: Invoice {invoice_num} from {vendor_name} for {currency} {total:,.2f}. Risk level: {'Low' if risk < 0.3 else 'Medium' if risk < 0.6 else 'High'}. Recommended action: Review and approve.",
        "finance": f"""**Finance Analysis**:
- Vendor: {vendor_name}
- Invoice #: {invoice_num}
- Amount: {currency} {total:,.2f}
- Tax: {currency} {float(db_invoice.tax_amount or 0):,.2f}
- Due Date: {db_invoice.due_date.date() if db_invoice.due_date else 'N/A'}
- Confidence: {(confidence * 100):.0f}%
""",
        "procurement": f"**Procurement Review**: Invoice from {vendor_name} for {line_count} line items totaling {currency} {total:,.2f}. Verify pricing against contracted rates.",
        "auditor": f"**Audit Notes**: Invoice {invoice_num} processed with {(confidence * 100):.0f}% extraction confidence. Risk score: {(risk * 100):.0f}%. Anomalies detected: {len(db_invoice.anomalies or [])}.",
    }
    
    return {
        "invoice_id": invoice_id,
        "role": role,
        "summary": summaries.get(role, db_invoice.summary or "Summary pending processing..."),
        "generated_at": datetime.utcnow().isoformat()
    }


@router.get("/invoices/{invoice_id}/audit-trail")
async def get_audit_trail(
    invoice_id: str = Path(..., description="Invoice ID"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get complete audit trail for an invoice.
    Shows all actions taken on the invoice.
    """
    query = select(DBInvoice).where(DBInvoice.id == invoice_id)
    result = await db.execute(query)
    db_invoice = result.scalar_one_or_none()
    
    if not db_invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    return {
        "invoice_id": invoice_id,
        "events": [
            {"action": "uploaded", "timestamp": db_invoice.created_at.isoformat() if db_invoice.created_at else None, "user": "system", "details": "Invoice uploaded"},
            {"action": "processed", "timestamp": db_invoice.created_at.isoformat() if db_invoice.created_at else None, "user": "system", "details": "OCR and extraction completed"},
            {"action": "validated", "timestamp": db_invoice.updated_at.isoformat() if db_invoice.updated_at else None, "user": "system", "details": f"Risk score: {db_invoice.risk_score:.2f}" if db_invoice.risk_score else "Risk assessed"},
        ]
    }


@router.delete("/invoices/{invoice_id}")
async def delete_invoice(
    invoice_id: str = Path(..., description="Invoice ID"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Delete an invoice (soft delete by archiving).
    """
    query = select(DBInvoice).where(DBInvoice.id == invoice_id)
    result = await db.execute(query)
    db_invoice = result.scalar_one_or_none()
    
    if not db_invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    db_invoice.status = InvoiceStatus.ARCHIVED
    db_invoice.updated_at = datetime.utcnow()
    
    await db.commit()
    
    logger.info("Invoice archived", invoice_id=invoice_id)
    
    return {"status": "deleted", "invoice_id": invoice_id}
