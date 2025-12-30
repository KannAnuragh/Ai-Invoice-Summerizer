"""
Invoices Routes
===============
CRUD operations for invoice management.
"""

from datetime import datetime
from typing import Optional, List
from enum import Enum
import uuid

from fastapi import APIRouter, HTTPException, Query, Path
from pydantic import BaseModel, Field
import structlog

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


# In-memory storage for demo (replace with database)
_invoices_db: dict = {}


def _create_demo_invoices():
    """Create demo invoices for testing."""
    if _invoices_db:
        return
    
    demo_invoices = [
        {
            "id": "inv-001",
            "document_id": "doc-001",
            "status": "pending",
            "vendor": {"id": "v-001", "name": "Acme Corporation", "address": "123 Business Ave"},
            "vendor_confidence": 0.95,
            "invoice_number": "INV-2024-0247",
            "invoice_number_confidence": 0.98,
            "invoice_date": "2024-12-22",
            "date_confidence": 0.92,
            "due_date": "2025-01-21",
            "due_date_confidence": 0.88,
            "currency": "USD",
            "subtotal": 10500,
            "tax_amount": 2000,
            "total_amount": 12500,
            "amount_confidence": 0.96,
            "line_items": [
                {"description": "Software License - Enterprise", "quantity": 1, "unit_price": 8000, "total": 8000},
                {"description": "Implementation Services", "quantity": 10, "unit_price": 150, "total": 1500},
                {"description": "Training (per hour)", "quantity": 5, "unit_price": 200, "total": 1000},
            ],
            "confidence": 0.92,
            "risk_score": 0.15,
            "anomalies": [],
            "summary": "Invoice from Acme Corporation for software licensing and implementation services. Total amount $12,500 USD with standard NET30 payment terms.",
            "created_at": "2024-12-22T10:00:00Z",
            "updated_at": "2024-12-22T10:00:00Z",
        },
        {
            "id": "inv-002",
            "document_id": "doc-002",
            "status": "review",
            "vendor": {"id": "v-002", "name": "CloudServices Ltd"},
            "vendor_confidence": 0.72,
            "invoice_number": "INV-2024-0244",
            "invoice_number_confidence": 0.88,
            "invoice_date": "2024-12-20",
            "date_confidence": 0.85,
            "due_date": "2025-01-19",
            "due_date_confidence": 0.80,
            "currency": "USD",
            "subtotal": 13500,
            "tax_amount": 1500,
            "total_amount": 15000,
            "amount_confidence": 0.90,
            "line_items": [
                {"description": "Cloud Hosting (Monthly)", "quantity": 1, "unit_price": 12000, "total": 12000},
                {"description": "Support Premium", "quantity": 1, "unit_price": 1500, "total": 1500},
            ],
            "confidence": 0.72,
            "risk_score": 0.45,
            "anomalies": ["Amount 50% higher than historical average"],
            "summary": "Cloud hosting invoice requires review due to amount deviation from typical billing.",
            "created_at": "2024-12-20T14:30:00Z",
            "updated_at": "2024-12-20T14:30:00Z",
        },
        {
            "id": "inv-003",
            "document_id": "doc-003",
            "status": "approved",
            "vendor": {"id": "v-003", "name": "Office Depot"},
            "vendor_confidence": 0.98,
            "invoice_number": "INV-2024-0245",
            "invoice_number_confidence": 0.99,
            "invoice_date": "2024-12-21",
            "date_confidence": 0.95,
            "due_date": "2025-01-20",
            "due_date_confidence": 0.95,
            "currency": "USD",
            "subtotal": 2100,
            "tax_amount": 240,
            "total_amount": 2340,
            "amount_confidence": 0.98,
            "line_items": [
                {"description": "Office Supplies", "quantity": 1, "unit_price": 1200, "total": 1200},
                {"description": "Printer Cartridges", "quantity": 3, "unit_price": 300, "total": 900},
            ],
            "confidence": 0.95,
            "risk_score": 0.08,
            "anomalies": [],
            "summary": "Standard office supplies order from verified vendor. Auto-approved based on low risk score.",
            "created_at": "2024-12-21T09:15:00Z",
            "updated_at": "2024-12-21T09:15:00Z",
        },
    ]
    
    for inv in demo_invoices:
        _invoices_db[inv["id"]] = inv


# Initialize demo data
_create_demo_invoices()


@router.get("/invoices", response_model=InvoiceListResponse)
async def list_invoices(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, alias="page_size", description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status"),
    search: Optional[str] = Query(None, description="Search by invoice number or vendor"),
    vendor_id: Optional[str] = Query(None, description="Filter by vendor"),
) -> InvoiceListResponse:
    """
    List invoices with pagination and filtering.
    """
    all_invoices = list(_invoices_db.values())
    
    # Apply filters
    if status:
        all_invoices = [i for i in all_invoices if i.get("status") == status]
    if vendor_id:
        all_invoices = [i for i in all_invoices if i.get("vendor", {}).get("id") == vendor_id]
    if search:
        search_lower = search.lower()
        all_invoices = [
            i for i in all_invoices 
            if search_lower in (i.get("invoice_number") or "").lower()
            or search_lower in (i.get("vendor", {}).get("name") or "").lower()
        ]
    
    # Sort by created_at desc
    all_invoices.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    
    total = len(all_invoices)
    start = (page - 1) * limit
    end = start + limit
    items = all_invoices[start:end]
    
    return InvoiceListResponse(
        invoices=[Invoice(**i) for i in items],
        total=total,
        page=page,
        page_size=limit,
        has_more=end < total
    )


@router.get("/invoices/{invoice_id}", response_model=Invoice)
async def get_invoice(
    invoice_id: str = Path(..., description="Invoice ID")
) -> Invoice:
    """
    Get a single invoice by ID.
    """
    if invoice_id not in _invoices_db:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    return Invoice(**_invoices_db[invoice_id])


class InvoiceUpdateRequest(BaseModel):
    """Update request body."""
    data: Optional[dict] = None
    status: Optional[str] = None


@router.patch("/invoices/{invoice_id}")
async def update_invoice(
    invoice_id: str = Path(..., description="Invoice ID"),
    request: InvoiceUpdateRequest = None,
) -> Invoice:
    """
    Update invoice data or status.
    Used for human corrections and status transitions.
    """
    if invoice_id not in _invoices_db:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    invoice = _invoices_db[invoice_id]
    
    if request and request.data:
        # Merge field updates
        for key, value in request.data.items():
            if key in invoice or key in ["vendor_name", "invoice_number", "invoice_date", "due_date", "total_amount"]:
                invoice[key] = value
    
    if request and request.status:
        invoice["status"] = request.status
    
    invoice["updated_at"] = datetime.utcnow().isoformat()
    _invoices_db[invoice_id] = invoice
    
    logger.info("Invoice updated", invoice_id=invoice_id, status=request.status if request else None)
    
    return Invoice(**invoice)


@router.get("/invoices/{invoice_id}/summary")
async def get_invoice_summary(
    invoice_id: str = Path(..., description="Invoice ID"),
    role: str = Query("finance", description="Role-based summary (cfo, finance, procurement, auditor)")
) -> dict:
    """
    Get AI-generated summary for an invoice.
    Summary content varies based on user role.
    """
    if invoice_id not in _invoices_db:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    invoice = _invoices_db[invoice_id]
    
    # Role-based summary templates
    summaries = {
        "cfo": f"**Executive Summary**: Invoice {invoice.get('invoice_number', 'N/A')} from {invoice.get('vendor', {}).get('name', 'Unknown')} for ${invoice.get('total_amount', 0):,.2f}. Risk level: {'Low' if invoice.get('risk_score', 0) < 0.3 else 'Medium' if invoice.get('risk_score', 0) < 0.6 else 'High'}. Recommended action: Review and approve.",
        "finance": f"""**Finance Analysis**:
- Vendor: {invoice.get('vendor', {}).get('name', 'Unknown')}
- Invoice #: {invoice.get('invoice_number', 'N/A')}
- Amount: ${invoice.get('total_amount', 0):,.2f} ({invoice.get('currency', 'USD')})
- Tax: ${invoice.get('tax_amount', 0):,.2f}
- Due Date: {invoice.get('due_date', 'N/A')}
- Confidence: {(invoice.get('confidence', 0) * 100):.0f}%
""",
        "procurement": f"**Procurement Review**: Invoice from {invoice.get('vendor', {}).get('name', 'Unknown')} for {len(invoice.get('line_items', []))} line items totaling ${invoice.get('total_amount', 0):,.2f}. Verify pricing against contracted rates.",
        "auditor": f"**Audit Notes**: Invoice {invoice.get('invoice_number', 'N/A')} processed with {(invoice.get('confidence', 0) * 100):.0f}% extraction confidence. Risk score: {(invoice.get('risk_score', 0) * 100):.0f}%. Anomalies detected: {len(invoice.get('anomalies', []))}.",
    }
    
    return {
        "invoice_id": invoice_id,
        "role": role,
        "summary": summaries.get(role, invoice.get("summary", "Summary pending processing...")),
        "generated_at": datetime.utcnow().isoformat()
    }


@router.get("/invoices/{invoice_id}/audit-trail")
async def get_audit_trail(
    invoice_id: str = Path(..., description="Invoice ID")
) -> dict:
    """
    Get complete audit trail for an invoice.
    Shows all actions taken on the invoice.
    """
    if invoice_id not in _invoices_db:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    invoice = _invoices_db[invoice_id]
    
    return {
        "invoice_id": invoice_id,
        "events": [
            {"action": "uploaded", "timestamp": invoice.get("created_at"), "user": "system", "details": "Invoice uploaded"},
            {"action": "processed", "timestamp": invoice.get("created_at"), "user": "system", "details": "OCR and extraction completed"},
            {"action": "validated", "timestamp": invoice.get("updated_at"), "user": "system", "details": f"Risk score: {invoice.get('risk_score', 0):.2f}"},
        ]
    }
