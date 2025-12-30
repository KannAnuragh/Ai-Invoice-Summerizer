"""
Admin Routes
============
Administrative endpoints for system configuration and management.
"""

from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query, Path
from pydantic import BaseModel
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter()


# ============== Vendor Management ==============

class VendorProfile(BaseModel):
    """Vendor configuration profile."""
    id: str
    name: str
    tax_id: Optional[str] = None
    address: Optional[str] = None
    payment_terms: str = "NET30"
    currency: str = "USD"
    risk_level: str = "normal"  # low, normal, high
    auto_approve_threshold: Optional[float] = None
    default_gl_code: Optional[str] = None
    active: bool = True
    created_at: datetime
    updated_at: datetime


_vendors_db: dict = {}


@router.get("/vendors", response_model=List[VendorProfile])
async def list_vendors(
    active_only: bool = Query(True, description="Only show active vendors"),
    search: Optional[str] = Query(None, description="Search by name"),
) -> List[VendorProfile]:
    """List all vendor profiles."""
    vendors = list(_vendors_db.values())
    
    if active_only:
        vendors = [v for v in vendors if v.get("active", True)]
    if search:
        vendors = [v for v in vendors if search.lower() in v.get("name", "").lower()]
    
    return [VendorProfile(**v) for v in vendors]


@router.post("/vendors", response_model=VendorProfile)
async def create_vendor(vendor: VendorProfile) -> VendorProfile:
    """Create a new vendor profile."""
    if vendor.id in _vendors_db:
        raise HTTPException(status_code=409, detail="Vendor ID already exists")
    
    vendor_dict = vendor.model_dump()
    vendor_dict["created_at"] = datetime.utcnow()
    vendor_dict["updated_at"] = datetime.utcnow()
    _vendors_db[vendor.id] = vendor_dict
    
    logger.info("Vendor created", vendor_id=vendor.id, name=vendor.name)
    return VendorProfile(**vendor_dict)


@router.put("/vendors/{vendor_id}", response_model=VendorProfile)
async def update_vendor(
    vendor_id: str = Path(...),
    vendor: VendorProfile = ...,
) -> VendorProfile:
    """Update a vendor profile."""
    if vendor_id not in _vendors_db:
        raise HTTPException(status_code=404, detail="Vendor not found")
    
    vendor_dict = vendor.model_dump()
    vendor_dict["updated_at"] = datetime.utcnow()
    vendor_dict["created_at"] = _vendors_db[vendor_id]["created_at"]
    _vendors_db[vendor_id] = vendor_dict
    
    logger.info("Vendor updated", vendor_id=vendor_id)
    return VendorProfile(**vendor_dict)


# ============== Approval Rules ==============

class ApprovalRule(BaseModel):
    """Approval workflow rule definition."""
    id: str
    name: str
    description: Optional[str] = None
    conditions: dict  # JSON conditions
    actions: List[str]  # Required approvers or auto-actions
    priority: int = 0
    active: bool = True


_approval_rules: dict = {}


@router.get("/approval-rules", response_model=List[ApprovalRule])
async def list_approval_rules() -> List[ApprovalRule]:
    """List all approval rules."""
    return [ApprovalRule(**r) for r in _approval_rules.values()]


@router.post("/approval-rules", response_model=ApprovalRule)
async def create_approval_rule(rule: ApprovalRule) -> ApprovalRule:
    """Create a new approval rule."""
    if rule.id in _approval_rules:
        raise HTTPException(status_code=409, detail="Rule ID already exists")
    
    _approval_rules[rule.id] = rule.model_dump()
    logger.info("Approval rule created", rule_id=rule.id, name=rule.name)
    return rule


# ============== System Configuration ==============

class SystemConfig(BaseModel):
    """System-wide configuration settings."""
    ocr_confidence_threshold: float = 0.85
    auto_approve_enabled: bool = False
    auto_approve_max_amount: float = 1000.0
    duplicate_detection_enabled: bool = True
    duplicate_hash_window_days: int = 90
    sla_warning_hours: int = 24
    sla_breach_hours: int = 48
    summary_language: str = "en"
    retention_days: int = 2555  # 7 years


_system_config = SystemConfig()


@router.get("/config", response_model=SystemConfig)
async def get_system_config() -> SystemConfig:
    """Get current system configuration."""
    return _system_config


@router.put("/config", response_model=SystemConfig)
async def update_system_config(config: SystemConfig) -> SystemConfig:
    """Update system configuration."""
    global _system_config
    _system_config = config
    logger.info("System config updated", config=config.model_dump())
    return _system_config


# ============== User Management ==============

class User(BaseModel):
    """System user."""
    id: str
    email: str
    name: str
    role: str  # admin, approver, viewer
    department: Optional[str] = None
    approval_limit: Optional[float] = None
    active: bool = True


_users_db: dict = {}


@router.get("/users", response_model=List[User])
async def list_users(
    role: Optional[str] = Query(None, description="Filter by role"),
    active_only: bool = Query(True),
) -> List[User]:
    """List all users."""
    users = list(_users_db.values())
    
    if role:
        users = [u for u in users if u.get("role") == role]
    if active_only:
        users = [u for u in users if u.get("active", True)]
    
    return [User(**u) for u in users]


@router.post("/users", response_model=User)
async def create_user(user: User) -> User:
    """Create a new user."""
    if user.id in _users_db:
        raise HTTPException(status_code=409, detail="User ID already exists")
    
    _users_db[user.id] = user.model_dump()
    logger.info("User created", user_id=user.id, email=user.email, role=user.role)
    return user
