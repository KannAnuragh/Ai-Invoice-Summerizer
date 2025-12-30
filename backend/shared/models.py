"""
Shared Pydantic Models
======================
Data models used across multiple services.
"""

from datetime import datetime
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict


# ============== Enums ==============

class InvoiceStatus(str, Enum):
    """Invoice lifecycle states."""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    OCR_COMPLETE = "ocr_complete"
    EXTRACTED = "extracted"
    VALIDATED = "validated"
    REVIEW_PENDING = "review_pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PAID = "paid"
    ARCHIVED = "archived"


class DocumentType(str, Enum):
    """Type of financial document."""
    INVOICE = "invoice"
    CREDIT_NOTE = "credit_note"
    DEBIT_NOTE = "debit_note"
    RECEIPT = "receipt"
    PURCHASE_ORDER = "purchase_order"
    UNKNOWN = "unknown"


class RiskLevel(str, Enum):
    """Risk assessment levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ============== Base Models ==============

class TimestampMixin(BaseModel):
    """Mixin for created/updated timestamps."""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class TenantMixin(BaseModel):
    """Mixin for multi-tenant models."""
    tenant_id: str


# ============== Invoice Models ==============

class LineItem(BaseModel):
    """Invoice line item."""
    model_config = ConfigDict(from_attributes=True)
    
    line_number: int = 1
    description: str
    quantity: float = 1.0
    unit: Optional[str] = None
    unit_price: float
    discount: float = 0.0
    tax_rate: float = 0.0
    tax_amount: float = 0.0
    total: float
    gl_code: Optional[str] = None
    cost_center: Optional[str] = None


class Address(BaseModel):
    """Postal address."""
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None


class VendorInfo(BaseModel):
    """Vendor information extracted from invoice."""
    name: str
    tax_id: Optional[str] = None
    address: Optional[Address] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    bank_account: Optional[str] = None


class InvoiceData(BaseModel):
    """Extracted invoice data."""
    model_config = ConfigDict(from_attributes=True)
    
    # Vendor
    vendor: Optional[VendorInfo] = None
    vendor_id: Optional[str] = None  # Matched vendor profile
    
    # Invoice identifiers
    invoice_number: Optional[str] = None
    po_number: Optional[str] = None
    contract_number: Optional[str] = None
    
    # Dates
    invoice_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    delivery_date: Optional[datetime] = None
    
    # Amounts
    currency: str = "USD"
    subtotal: Optional[float] = None
    discount_amount: Optional[float] = None
    tax_amount: Optional[float] = None
    shipping_amount: Optional[float] = None
    total_amount: Optional[float] = None
    
    # Line items
    line_items: List[LineItem] = []
    
    # Payment
    payment_terms: Optional[str] = None
    payment_method: Optional[str] = None
    bank_details: Optional[str] = None
    
    # Additional
    notes: Optional[str] = None
    language: str = "en"


class Invoice(TimestampMixin):
    """Full invoice model."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    document_id: str
    tenant_id: str
    
    # Status
    status: InvoiceStatus = InvoiceStatus.UPLOADED
    document_type: DocumentType = DocumentType.INVOICE
    
    # Extracted data
    data: Optional[InvoiceData] = None
    
    # AI outputs
    confidence_score: Optional[float] = None
    risk_score: Optional[float] = None
    risk_level: RiskLevel = RiskLevel.LOW
    anomalies: List[str] = []
    summary: Optional[str] = None
    
    # Processing metadata
    ocr_confidence: Optional[float] = None
    extraction_confidence: Optional[float] = None
    processing_time_ms: Optional[int] = None
    
    # Files
    original_filename: Optional[str] = None
    storage_path: Optional[str] = None
    file_hash: Optional[str] = None
    
    # Workflow
    assigned_to: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None


# ============== User Models ==============

class User(TimestampMixin):
    """System user."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    email: str
    name: str
    role: str
    tenant_id: str
    department: Optional[str] = None
    approval_limit: Optional[float] = None
    active: bool = True


# ============== Vendor Models ==============

class Vendor(TimestampMixin):
    """Vendor profile."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    tenant_id: str
    name: str
    tax_id: Optional[str] = None
    address: Optional[Address] = None
    payment_terms: str = "NET30"
    currency: str = "USD"
    risk_level: RiskLevel = RiskLevel.LOW
    auto_approve_threshold: Optional[float] = None
    default_gl_code: Optional[str] = None
    contact_email: Optional[str] = None
    active: bool = True


# ============== Event Models ==============

class InvoiceEvent(BaseModel):
    """Event emitted for invoice processing."""
    event_type: str
    invoice_id: str
    document_id: str
    tenant_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    data: dict = {}
