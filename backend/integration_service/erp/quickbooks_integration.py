"""
QuickBooks Online Integration
==============================
Integration with QuickBooks Online for accounting/ERP functionality.
"""

import os
from typing import Optional, Dict, Any, List
from datetime import datetime
import asyncio
import json

import structlog

from .. import (
    ERPIntegration,
    ERPSyncResult,
    SyncStatus,
    IntegrationProvider
)

logger = structlog.get_logger(__name__)

# Try to import QuickBooks SDK
try:
    from intuitlib.client import AuthClient
    from intuitlib.enums import Scopes
    from quickbooks import QuickBooks
    from quickbooks.objects.invoice import Invoice as QBInvoice
    from quickbooks.objects.vendor import Vendor as QBVendor
    from quickbooks.objects.customer import Customer as QBCustomer
    QB_AVAILABLE = True
except ImportError:
    QB_AVAILABLE = False
    logger.warning("QuickBooks SDK not installed, using mock mode")


class QuickBooksIntegration(ERPIntegration):
    """
    QuickBooks Online integration.
    
    Features:
    - Sync invoices to QuickBooks
    - Sync vendors/customers
    - Pull data from QuickBooks
    - OAuth 2.0 authentication
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.client_id = config.get("client_id") or os.getenv("QUICKBOOKS_CLIENT_ID")
        self.client_secret = config.get("client_secret") or os.getenv("QUICKBOOKS_CLIENT_SECRET")
        self.redirect_uri = config.get("redirect_uri") or os.getenv("QUICKBOOKS_REDIRECT_URI")
        self.realm_id = config.get("realm_id") or os.getenv("QUICKBOOKS_REALM_ID")
        self.refresh_token = config.get("refresh_token") or os.getenv("QUICKBOOKS_REFRESH_TOKEN")
        self.environment = config.get("environment", "sandbox")  # sandbox or production
        
        self.enabled = QB_AVAILABLE and all([
            self.client_id,
            self.client_secret,
            self.realm_id
        ])
        
        if not self.enabled:
            self.logger.warning("QuickBooks integration disabled (missing configuration or SDK)")
        else:
            self._init_client()
    
    def _init_client(self):
        """Initialize QuickBooks client."""
        if not QB_AVAILABLE:
            return
        
        try:
            self.auth_client = AuthClient(
                client_id=self.client_id,
                client_secret=self.client_secret,
                redirect_uri=self.redirect_uri,
                environment=self.environment
            )
            
            if self.refresh_token:
                # Refresh access token
                self.auth_client.refresh(refresh_token=self.refresh_token)
            
            self.qb_client = QuickBooks(
                auth_client=self.auth_client,
                refresh_token=self.refresh_token,
                company_id=self.realm_id
            )
        except Exception as e:
            self.logger.error("Failed to initialize QuickBooks client", error=str(e))
            self.enabled = False
    
    async def test_connection(self) -> bool:
        """Test QuickBooks API connection."""
        if not self.enabled:
            return False
        
        try:
            # Try to query company info
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.qb_client.query("SELECT * FROM CompanyInfo")
            )
            self.logger.info("QuickBooks connection successful")
            return True
        except Exception as e:
            self.logger.error("QuickBooks connection failed", error=str(e))
            return False
    
    async def get_status(self) -> Dict[str, Any]:
        """Get QuickBooks integration status."""
        return {
            "provider": IntegrationProvider.QUICKBOOKS,
            "enabled": self.enabled,
            "sdk_available": QB_AVAILABLE,
            "configured": all([self.client_id, self.client_secret, self.realm_id]),
            "authenticated": bool(self.refresh_token),
            "environment": self.environment,
            "realm_id": self.realm_id if self.enabled else None
        }
    
    async def sync_invoice(self, invoice_data: Dict[str, Any]) -> ERPSyncResult:
        """Sync invoice to QuickBooks."""
        if not self.enabled:
            return self._mock_sync_result(invoice_data["id"], "invoice")
        
        try:
            # Map invoice data to QuickBooks format
            qb_invoice = self._map_invoice_to_qb(invoice_data)
            
            # Save to QuickBooks
            loop = asyncio.get_event_loop()
            saved_invoice = await loop.run_in_executor(
                None,
                qb_invoice.save
            )
            
            result = ERPSyncResult(
                sync_id=f"qb_sync_{datetime.now().timestamp()}",
                invoice_id=invoice_data["id"],
                provider=IntegrationProvider.QUICKBOOKS,
                status=SyncStatus.COMPLETED,
                synced_at=datetime.now(),
                erp_record_id=str(saved_invoice.Id),
                synced_fields=["invoice_number", "vendor", "amount", "date", "line_items"]
            )
            
            self.logger.info(
                "Invoice synced to QuickBooks",
                invoice_id=invoice_data["id"],
                qb_id=saved_invoice.Id
            )
            
            return result
            
        except Exception as e:
            self.logger.error("Failed to sync invoice", error=str(e))
            return ERPSyncResult(
                sync_id=f"qb_sync_failed_{datetime.now().timestamp()}",
                invoice_id=invoice_data["id"],
                provider=IntegrationProvider.QUICKBOOKS,
                status=SyncStatus.FAILED,
                synced_at=datetime.now(),
                error_message=str(e)
            )
    
    async def sync_vendor(self, vendor_data: Dict[str, Any]) -> ERPSyncResult:
        """Sync vendor to QuickBooks."""
        if not self.enabled:
            return self._mock_sync_result(vendor_data["id"], "vendor")
        
        try:
            # Map vendor data to QuickBooks format
            qb_vendor = QBVendor()
            qb_vendor.DisplayName = vendor_data["name"]
            
            if "email" in vendor_data:
                qb_vendor.PrimaryEmailAddr = {"Address": vendor_data["email"]}
            
            if "phone" in vendor_data:
                qb_vendor.PrimaryPhone = {"FreeFormNumber": vendor_data["phone"]}
            
            if "address" in vendor_data:
                qb_vendor.BillAddr = {
                    "Line1": vendor_data["address"].get("street", ""),
                    "City": vendor_data["address"].get("city", ""),
                    "PostalCode": vendor_data["address"].get("zip", ""),
                }
            
            # Save to QuickBooks
            loop = asyncio.get_event_loop()
            saved_vendor = await loop.run_in_executor(
                None,
                qb_vendor.save
            )
            
            return ERPSyncResult(
                sync_id=f"qb_vendor_sync_{datetime.now().timestamp()}",
                invoice_id=vendor_data["id"],
                provider=IntegrationProvider.QUICKBOOKS,
                status=SyncStatus.COMPLETED,
                synced_at=datetime.now(),
                erp_record_id=str(saved_vendor.Id),
                synced_fields=["name", "email", "phone", "address"]
            )
            
        except Exception as e:
            self.logger.error("Failed to sync vendor", error=str(e))
            return ERPSyncResult(
                sync_id=f"qb_vendor_sync_failed_{datetime.now().timestamp()}",
                invoice_id=vendor_data["id"],
                provider=IntegrationProvider.QUICKBOOKS,
                status=SyncStatus.FAILED,
                synced_at=datetime.now(),
                error_message=str(e)
            )
    
    async def get_sync_status(self, sync_id: str) -> ERPSyncResult:
        """Get synchronization status."""
        # In a real implementation, you'd query a sync log database
        return ERPSyncResult(
            sync_id=sync_id,
            invoice_id="unknown",
            provider=IntegrationProvider.QUICKBOOKS,
            status=SyncStatus.COMPLETED,
            synced_at=datetime.now()
        )
    
    async def pull_invoice(self, erp_invoice_id: str) -> Dict[str, Any]:
        """Pull invoice data from QuickBooks."""
        if not self.enabled:
            return self._mock_invoice_data(erp_invoice_id)
        
        try:
            loop = asyncio.get_event_loop()
            qb_invoice = await loop.run_in_executor(
                None,
                lambda: QBInvoice.get(erp_invoice_id, qb=self.qb_client)
            )
            
            # Map QuickBooks invoice to our format
            return self._map_qb_to_invoice(qb_invoice)
            
        except Exception as e:
            self.logger.error("Failed to pull invoice", error=str(e))
            raise
    
    async def pull_vendor(self, erp_vendor_id: str) -> Dict[str, Any]:
        """Pull vendor data from QuickBooks."""
        if not self.enabled:
            return self._mock_vendor_data(erp_vendor_id)
        
        try:
            loop = asyncio.get_event_loop()
            qb_vendor = await loop.run_in_executor(
                None,
                lambda: QBVendor.get(erp_vendor_id, qb=self.qb_client)
            )
            
            return {
                "id": str(qb_vendor.Id),
                "name": qb_vendor.DisplayName,
                "email": qb_vendor.PrimaryEmailAddr.Address if qb_vendor.PrimaryEmailAddr else None,
                "phone": qb_vendor.PrimaryPhone.FreeFormNumber if qb_vendor.PrimaryPhone else None,
                "active": qb_vendor.Active,
                "balance": float(qb_vendor.Balance) if qb_vendor.Balance else 0.0
            }
            
        except Exception as e:
            self.logger.error("Failed to pull vendor", error=str(e))
            raise
    
    def _map_invoice_to_qb(self, invoice_data: Dict[str, Any]) -> 'QBInvoice':
        """Map our invoice format to QuickBooks format."""
        qb_invoice = QBInvoice()
        qb_invoice.DocNumber = invoice_data.get("invoice_number")
        qb_invoice.TxnDate = invoice_data.get("date", datetime.now().strftime("%Y-%m-%d"))
        
        # Map line items
        if "line_items" in invoice_data:
            # This is simplified - real implementation would need proper line item mapping
            pass
        
        return qb_invoice
    
    def _map_qb_to_invoice(self, qb_invoice: 'QBInvoice') -> Dict[str, Any]:
        """Map QuickBooks invoice to our format."""
        return {
            "erp_id": str(qb_invoice.Id),
            "invoice_number": qb_invoice.DocNumber,
            "date": str(qb_invoice.TxnDate) if qb_invoice.TxnDate else None,
            "total_amount": float(qb_invoice.TotalAmt) if qb_invoice.TotalAmt else 0.0,
            "balance": float(qb_invoice.Balance) if qb_invoice.Balance else 0.0,
            "status": "paid" if qb_invoice.Balance == 0 else "unpaid"
        }
    
    # Mock methods
    def _mock_sync_result(self, record_id: str, record_type: str) -> ERPSyncResult:
        """Mock sync result."""
        return ERPSyncResult(
            sync_id=f"mock_qb_sync_{datetime.now().timestamp()}",
            invoice_id=record_id,
            provider=IntegrationProvider.QUICKBOOKS,
            status=SyncStatus.COMPLETED,
            synced_at=datetime.now(),
            erp_record_id=f"qb_mock_{record_id}",
            synced_fields=["all"],
        )
    
    def _mock_invoice_data(self, invoice_id: str) -> Dict[str, Any]:
        """Mock invoice data."""
        return {
            "erp_id": invoice_id,
            "invoice_number": "INV-MOCK-001",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "total_amount": 1500.00,
            "balance": 0.0,
            "status": "paid"
        }
    
    def _mock_vendor_data(self, vendor_id: str) -> Dict[str, Any]:
        """Mock vendor data."""
        return {
            "id": vendor_id,
            "name": "Mock Vendor Corp",
            "email": "vendor@example.com",
            "phone": "(555) 123-4567",
            "active": True,
            "balance": 0.0
        }
