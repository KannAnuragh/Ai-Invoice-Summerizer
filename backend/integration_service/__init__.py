"""
Integration Service - Payment Gateway & ERP Integrations
========================================================
Provides connectors for payment processing and ERP system synchronization.
"""

from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime
from abc import ABC, abstractmethod
from dataclasses import dataclass
import structlog

logger = structlog.get_logger(__name__)


class IntegrationType(str, Enum):
    """Types of integrations supported."""
    PAYMENT_GATEWAY = "payment_gateway"
    ERP_SYSTEM = "erp_system"
    ACCOUNTING_SOFTWARE = "accounting_software"


class IntegrationProvider(str, Enum):
    """Supported integration providers."""
    # Payment Gateways
    STRIPE = "stripe"
    PAYPAL = "paypal"
    SQUARE = "square"
    AUTHORIZE_NET = "authorize_net"
    
    # ERP Systems
    SAP = "sap"
    ORACLE_ERP = "oracle_erp"
    MICROSOFT_DYNAMICS = "microsoft_dynamics"
    NETSUITE = "netsuite"
    
    # Accounting Software
    QUICKBOOKS = "quickbooks"
    XERO = "xero"
    SAGE = "sage"
    FRESHBOOKS = "freshbooks"


class PaymentStatus(str, Enum):
    """Payment transaction status."""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class SyncStatus(str, Enum):
    """ERP synchronization status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class PaymentTransaction:
    """Payment transaction details."""
    transaction_id: str
    invoice_id: str
    amount: float
    currency: str
    status: PaymentStatus
    payment_method: str
    provider: IntegrationProvider
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ERPSyncResult:
    """ERP synchronization result."""
    sync_id: str
    invoice_id: str
    provider: IntegrationProvider
    status: SyncStatus
    synced_at: datetime
    erp_record_id: Optional[str] = None
    error_message: Optional[str] = None
    synced_fields: Optional[List[str]] = None


class BaseIntegration(ABC):
    """Base class for all integrations."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logger.bind(integration=self.__class__.__name__)
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """Test if integration is properly configured and accessible."""
        pass
    
    @abstractmethod
    async def get_status(self) -> Dict[str, Any]:
        """Get integration status and health."""
        pass


class PaymentGatewayIntegration(BaseIntegration):
    """Base class for payment gateway integrations."""
    
    @abstractmethod
    async def create_payment(
        self,
        invoice_id: str,
        amount: float,
        currency: str,
        customer_email: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PaymentTransaction:
        """Create a payment transaction."""
        pass
    
    @abstractmethod
    async def get_payment_status(self, transaction_id: str) -> PaymentTransaction:
        """Get payment transaction status."""
        pass
    
    @abstractmethod
    async def refund_payment(
        self,
        transaction_id: str,
        amount: Optional[float] = None,
        reason: Optional[str] = None
    ) -> PaymentTransaction:
        """Refund a payment (full or partial)."""
        pass
    
    @abstractmethod
    async def list_payments(
        self,
        invoice_id: Optional[str] = None,
        limit: int = 100
    ) -> List[PaymentTransaction]:
        """List payment transactions."""
        pass


class ERPIntegration(BaseIntegration):
    """Base class for ERP system integrations."""
    
    @abstractmethod
    async def sync_invoice(
        self,
        invoice_data: Dict[str, Any]
    ) -> ERPSyncResult:
        """Sync invoice to ERP system."""
        pass
    
    @abstractmethod
    async def sync_vendor(
        self,
        vendor_data: Dict[str, Any]
    ) -> ERPSyncResult:
        """Sync vendor to ERP system."""
        pass
    
    @abstractmethod
    async def get_sync_status(self, sync_id: str) -> ERPSyncResult:
        """Get synchronization status."""
        pass
    
    @abstractmethod
    async def pull_invoice(self, erp_invoice_id: str) -> Dict[str, Any]:
        """Pull invoice data from ERP system."""
        pass
    
    @abstractmethod
    async def pull_vendor(self, erp_vendor_id: str) -> Dict[str, Any]:
        """Pull vendor data from ERP system."""
        pass
