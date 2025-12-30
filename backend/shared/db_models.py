"""
SQLAlchemy Database Models
===========================
ORM models for PostgreSQL database.
"""

from datetime import datetime
from typing import Optional, List

from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, JSON, ForeignKey, Enum as SQLEnum, Numeric, Index
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func
import enum

Base = declarative_base()


class InvoiceStatus(str, enum.Enum):
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


class ApprovalStatus(str, enum.Enum):
    """Approval task status."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"
    EXPIRED = "expired"


class RiskLevel(str, enum.Enum):
    """Risk classification."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Vendor(Base):
    """Vendor master data."""
    __tablename__ = "vendors"
    
    id = Column(String(50), primary_key=True)
    name = Column(String(255), nullable=False, index=True)
    tax_id = Column(String(50))
    address = Column(Text)
    email = Column(String(255))
    phone = Column(String(50))
    payment_terms = Column(String(50), default="NET30")
    currency = Column(String(3), default="USD")
    risk_level = Column(String(20), default="normal")
    auto_approve_threshold = Column(Numeric(12, 2))
    default_gl_code = Column(String(50))
    active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    
    # Statistics
    total_invoices = Column(Integer, default=0)
    total_amount = Column(Numeric(15, 2), default=0)
    average_amount = Column(Numeric(12, 2), default=0)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    invoices = relationship("Invoice", back_populates="vendor")


class Invoice(Base):
    """Invoice records."""
    __tablename__ = "invoices"
    
    id = Column(String(50), primary_key=True)
    document_id = Column(String(50), unique=True, index=True)
    status = Column(SQLEnum(InvoiceStatus), default=InvoiceStatus.UPLOADED, index=True)
    
    # Vendor information
    vendor_id = Column(String(50), ForeignKey("vendors.id"), index=True)
    vendor_name = Column(String(255))
    vendor_address = Column(Text)
    vendor_confidence = Column(Float)
    
    # Invoice fields
    invoice_number = Column(String(100), index=True)
    invoice_number_confidence = Column(Float)
    invoice_date = Column(DateTime)
    date_confidence = Column(Float)
    due_date = Column(DateTime)
    due_date_confidence = Column(Float)
    
    # Amounts
    currency = Column(String(3), default="USD")
    subtotal = Column(Numeric(15, 2))
    tax_amount = Column(Numeric(15, 2))
    total_amount = Column(Numeric(15, 2), index=True)
    amount_confidence = Column(Float)
    
    # Line items (stored as JSON)
    line_items = Column(JSON, default=list)
    
    # Other fields
    po_number = Column(String(100))
    payment_terms = Column(String(100))
    
    # Scoring
    confidence = Column(Float)
    risk_score = Column(Float, index=True)
    anomalies = Column(JSON, default=list)
    
    # Summary
    summary = Column(Text)
    
    # Source file information
    source_filename = Column(String(255))
    source_size = Column(Integer)
    file_hash = Column(String(64), index=True)
    
    # Metadata
    created_at = Column(DateTime, server_default=func.now(), index=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    created_by = Column(String(100))
    updated_by = Column(String(100))
    
    # Relationships
    vendor = relationship("Vendor", back_populates="invoices")
    approval_tasks = relationship("ApprovalTask", back_populates="invoice", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_invoice_vendor_date', 'vendor_id', 'invoice_date'),
        Index('idx_invoice_status_created', 'status', 'created_at'),
    )


class ApprovalTask(Base):
    """Approval workflow tasks."""
    __tablename__ = "approval_tasks"
    
    id = Column(String(50), primary_key=True)
    invoice_id = Column(String(50), ForeignKey("invoices.id"), nullable=False, index=True)
    status = Column(SQLEnum(ApprovalStatus), default=ApprovalStatus.PENDING, index=True)
    priority = Column(String(20), default="normal", index=True)  # normal, high, urgent
    
    # Assignment
    assigned_to = Column(String(100), index=True)
    assigned_role = Column(String(50))
    
    # SLA
    due_date = Column(DateTime, index=True)
    sla_status = Column(String(20), default="on_track")  # on_track, warning, breached
    
    # Action tracking
    action_taken = Column(String(50))  # approve, reject, escalate, delegate
    approved_by = Column(String(100))
    approved_at = Column(DateTime)
    rejection_reason = Column(Text)
    comments = Column(Text)
    delegated_to = Column(String(100))
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    invoice = relationship("Invoice", back_populates="approval_tasks")
    
    __table_args__ = (
        Index('idx_approval_status_due', 'status', 'due_date'),
        Index('idx_approval_assigned', 'assigned_to', 'status'),
    )


class User(Base):
    """System users."""
    __tablename__ = "users"
    
    id = Column(String(50), primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, index=True)  # admin, approver, viewer
    department = Column(String(100))
    approval_limit = Column(Numeric(15, 2))
    active = Column(Boolean, default=True)
    
    # OAuth info
    google_id = Column(String(255), unique=True)
    picture_url = Column(String(500))
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    last_login = Column(DateTime)


class ApprovalRule(Base):
    """Approval workflow rules."""
    __tablename__ = "approval_rules"
    
    id = Column(String(50), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    conditions = Column(JSON, nullable=False)  # JSON conditions
    actions = Column(JSON, nullable=False)  # Required approvers or auto-actions
    priority = Column(Integer, default=0)
    active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class SystemConfig(Base):
    """System-wide configuration."""
    __tablename__ = "system_config"
    
    id = Column(Integer, primary_key=True)
    ocr_confidence_threshold = Column(Float, default=0.85)
    auto_approve_enabled = Column(Boolean, default=False)
    auto_approve_max_amount = Column(Numeric(12, 2), default=1000.0)
    duplicate_detection_enabled = Column(Boolean, default=True)
    duplicate_hash_window_days = Column(Integer, default=90)
    sla_warning_hours = Column(Integer, default=24)
    sla_breach_hours = Column(Integer, default=48)
    summary_language = Column(String(10), default="en")
    retention_days = Column(Integer, default=2555)  # 7 years
    
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class AuditLog(Base):
    """Immutable audit trail."""
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(50), nullable=False, index=True)
    entity_type = Column(String(50))  # invoice, approval, user, etc.
    entity_id = Column(String(50), index=True)
    user_id = Column(String(100))
    action = Column(String(100), nullable=False)
    details = Column(JSON)
    ip_address = Column(String(50))
    user_agent = Column(Text)
    
    created_at = Column(DateTime, server_default=func.now(), index=True)
    
    __table_args__ = (
        Index('idx_audit_entity', 'entity_type', 'entity_id'),
        Index('idx_audit_user_time', 'user_id', 'created_at'),
    )
