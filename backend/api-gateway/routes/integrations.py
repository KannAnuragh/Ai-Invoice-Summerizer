"""
Integration API Routes
=====================
API endpoints for payment and ERP integrations.
"""

import os
import sys
from typing import Optional, List
from datetime import datetime

import structlog
from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel, Field

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from integration_service.manager import get_integration_manager
from integration_service import IntegrationProvider, PaymentStatus, SyncStatus

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])


# Request/Response Models
class PaymentRequest(BaseModel):
    """Payment creation request."""
    invoice_id: str
    amount: float = Field(gt=0)
    currency: str = "USD"
    customer_email: str
    provider: IntegrationProvider = IntegrationProvider.STRIPE
    metadata: Optional[dict] = None


class PaymentResponse(BaseModel):
    """Payment response."""
    transaction_id: str
    invoice_id: str
    amount: float
    currency: str
    status: str
    payment_method: str
    provider: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    client_secret: Optional[str] = None  # For frontend payment UI


class RefundRequest(BaseModel):
    """Refund request."""
    transaction_id: str
    amount: Optional[float] = None
    reason: Optional[str] = None
    provider: IntegrationProvider = IntegrationProvider.STRIPE


class SyncInvoiceRequest(BaseModel):
    """Invoice sync request."""
    invoice_id: str
    invoice_data: dict
    provider: IntegrationProvider = IntegrationProvider.QUICKBOOKS


class SyncResponse(BaseModel):
    """Sync response."""
    sync_id: str
    invoice_id: str
    provider: str
    status: str
    synced_at: datetime
    erp_record_id: Optional[str] = None
    error_message: Optional[str] = None


class IntegrationStatusResponse(BaseModel):
    """Integration status response."""
    provider: str
    enabled: bool
    configured: bool
    additional_info: dict


# Payment Endpoints

@router.post("/payment/create", response_model=PaymentResponse)
async def create_payment(request: PaymentRequest):
    """
    Create a payment transaction.
    
    Supported providers:
    - stripe: Stripe payment gateway
    - paypal: PayPal (placeholder)
    """
    manager = get_integration_manager()
    integration = manager.get_payment_integration(request.provider)
    
    if not integration:
        raise HTTPException(
            status_code=400,
            detail=f"Payment provider {request.provider} not configured"
        )
    
    try:
        transaction = await integration.create_payment(
            invoice_id=request.invoice_id,
            amount=request.amount,
            currency=request.currency,
            customer_email=request.customer_email,
            metadata=request.metadata
        )
        
        response = PaymentResponse(
            transaction_id=transaction.transaction_id,
            invoice_id=transaction.invoice_id,
            amount=transaction.amount,
            currency=transaction.currency,
            status=transaction.status.value,
            payment_method=transaction.payment_method,
            provider=transaction.provider.value,
            created_at=transaction.created_at,
            completed_at=transaction.completed_at,
            error_message=transaction.error_message
        )
        
        # Add client secret if available (for Stripe)
        if transaction.metadata and "client_secret" in transaction.metadata:
            response.client_secret = transaction.metadata["client_secret"]
        
        logger.info(
            "Payment created",
            transaction_id=transaction.transaction_id,
            provider=request.provider,
            amount=request.amount
        )
        
        return response
        
    except Exception as e:
        logger.error("Failed to create payment", error=str(e), provider=request.provider)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/payment/{transaction_id}", response_model=PaymentResponse)
async def get_payment_status(
    transaction_id: str,
    provider: IntegrationProvider = IntegrationProvider.STRIPE
):
    """Get payment transaction status."""
    manager = get_integration_manager()
    integration = manager.get_payment_integration(provider)
    
    if not integration:
        raise HTTPException(
            status_code=400,
            detail=f"Payment provider {provider} not configured"
        )
    
    try:
        transaction = await integration.get_payment_status(transaction_id)
        
        return PaymentResponse(
            transaction_id=transaction.transaction_id,
            invoice_id=transaction.invoice_id,
            amount=transaction.amount,
            currency=transaction.currency,
            status=transaction.status.value,
            payment_method=transaction.payment_method,
            provider=transaction.provider.value,
            created_at=transaction.created_at,
            completed_at=transaction.completed_at,
            error_message=transaction.error_message
        )
        
    except Exception as e:
        logger.error("Failed to get payment status", error=str(e))
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/payment/refund", response_model=PaymentResponse)
async def refund_payment(request: RefundRequest):
    """Refund a payment (full or partial)."""
    manager = get_integration_manager()
    integration = manager.get_payment_integration(request.provider)
    
    if not integration:
        raise HTTPException(
            status_code=400,
            detail=f"Payment provider {request.provider} not configured"
        )
    
    try:
        transaction = await integration.refund_payment(
            transaction_id=request.transaction_id,
            amount=request.amount,
            reason=request.reason
        )
        
        logger.info("Payment refunded", transaction_id=request.transaction_id)
        
        return PaymentResponse(
            transaction_id=transaction.transaction_id,
            invoice_id=transaction.invoice_id,
            amount=transaction.amount,
            currency=transaction.currency,
            status=transaction.status.value,
            payment_method=transaction.payment_method,
            provider=transaction.provider.value,
            created_at=transaction.created_at
        )
        
    except Exception as e:
        logger.error("Failed to refund payment", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ERP Endpoints

@router.post("/erp/sync-invoice", response_model=SyncResponse)
async def sync_invoice_to_erp(request: SyncInvoiceRequest):
    """
    Sync invoice to ERP system.
    
    Supported providers:
    - quickbooks: QuickBooks Online
    - sap: SAP (placeholder)
    - netsuite: NetSuite (placeholder)
    """
    manager = get_integration_manager()
    integration = manager.get_erp_integration(request.provider)
    
    if not integration:
        raise HTTPException(
            status_code=400,
            detail=f"ERP provider {request.provider} not configured"
        )
    
    try:
        result = await integration.sync_invoice(request.invoice_data)
        
        logger.info(
            "Invoice synced to ERP",
            invoice_id=request.invoice_id,
            provider=request.provider,
            erp_record_id=result.erp_record_id
        )
        
        return SyncResponse(
            sync_id=result.sync_id,
            invoice_id=result.invoice_id,
            provider=result.provider.value,
            status=result.status.value,
            synced_at=result.synced_at,
            erp_record_id=result.erp_record_id,
            error_message=result.error_message
        )
        
    except Exception as e:
        logger.error("Failed to sync invoice", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/erp/invoice/{erp_invoice_id}")
async def pull_invoice_from_erp(
    erp_invoice_id: str,
    provider: IntegrationProvider = IntegrationProvider.QUICKBOOKS
):
    """Pull invoice data from ERP system."""
    manager = get_integration_manager()
    integration = manager.get_erp_integration(provider)
    
    if not integration:
        raise HTTPException(
            status_code=400,
            detail=f"ERP provider {provider} not configured"
        )
    
    try:
        invoice_data = await integration.pull_invoice(erp_invoice_id)
        return invoice_data
        
    except Exception as e:
        logger.error("Failed to pull invoice", error=str(e))
        raise HTTPException(status_code=404, detail=str(e))


# Status and Management Endpoints

@router.get("/status")
async def get_integrations_status():
    """Get status of all integrations."""
    manager = get_integration_manager()
    statuses = await manager.get_all_status()
    
    return {
        "integrations": [
            {
                "provider": provider.value,
                **status
            }
            for provider, status in statuses.items()
        ],
        "available": manager.list_available_integrations()
    }


@router.get("/test")
async def test_all_integrations():
    """Test all integration connections."""
    manager = get_integration_manager()
    results = await manager.test_all_connections()
    
    return {
        "results": {
            provider.value: {
                "connected": connected,
                "status": "✅ Connected" if connected else "❌ Not connected"
            }
            for provider, connected in results.items()
        }
    }


@router.get("/providers")
async def list_providers():
    """List all available integration providers."""
    return {
        "payment_gateways": [
            {"id": IntegrationProvider.STRIPE.value, "name": "Stripe", "supported": True},
            {"id": IntegrationProvider.PAYPAL.value, "name": "PayPal", "supported": False},
            {"id": IntegrationProvider.SQUARE.value, "name": "Square", "supported": False},
        ],
        "erp_systems": [
            {"id": IntegrationProvider.QUICKBOOKS.value, "name": "QuickBooks Online", "supported": True},
            {"id": IntegrationProvider.XERO.value, "name": "Xero", "supported": False},
            {"id": IntegrationProvider.SAP.value, "name": "SAP", "supported": False},
            {"id": IntegrationProvider.NETSUITE.value, "name": "NetSuite", "supported": False},
        ]
    }
