"""
Stripe Payment Gateway Integration
==================================
Integration with Stripe for payment processing.
"""

import os
from typing import Optional, Dict, Any, List
from datetime import datetime
import asyncio

import structlog

from .. import (
    PaymentGatewayIntegration,
    PaymentTransaction,
    PaymentStatus,
    IntegrationProvider
)

logger = structlog.get_logger(__name__)

# Try to import Stripe SDK
try:
    import stripe
    STRIPE_AVAILABLE = True
except ImportError:
    STRIPE_AVAILABLE = False
    logger.warning("Stripe SDK not installed, using mock mode")


class StripeIntegration(PaymentGatewayIntegration):
    """
    Stripe payment gateway integration.
    
    Features:
    - Create payment intents
    - Check payment status
    - Process refunds
    - Webhook handling for real-time updates
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key") or os.getenv("STRIPE_API_KEY")
        self.webhook_secret = config.get("webhook_secret") or os.getenv("STRIPE_WEBHOOK_SECRET")
        
        if STRIPE_AVAILABLE and self.api_key:
            stripe.api_key = self.api_key
            self.enabled = True
        else:
            self.enabled = False
            self.logger.warning("Stripe integration disabled (missing API key or SDK)")
    
    async def test_connection(self) -> bool:
        """Test Stripe API connection."""
        if not self.enabled:
            return False
        
        try:
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, stripe.Account.retrieve)
            self.logger.info("Stripe connection successful")
            return True
        except Exception as e:
            self.logger.error("Stripe connection failed", error=str(e))
            return False
    
    async def get_status(self) -> Dict[str, Any]:
        """Get Stripe integration status."""
        return {
            "provider": IntegrationProvider.STRIPE,
            "enabled": self.enabled,
            "sdk_available": STRIPE_AVAILABLE,
            "configured": bool(self.api_key),
            "webhook_configured": bool(self.webhook_secret)
        }
    
    async def create_payment(
        self,
        invoice_id: str,
        amount: float,
        currency: str,
        customer_email: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PaymentTransaction:
        """Create a Stripe payment intent."""
        if not self.enabled:
            return self._mock_payment(invoice_id, amount, currency)
        
        try:
            # Convert amount to cents (Stripe uses smallest currency unit)
            amount_cents = int(amount * 100)
            
            # Prepare metadata
            payment_metadata = {
                "invoice_id": invoice_id,
                "customer_email": customer_email,
                **(metadata or {})
            }
            
            # Create payment intent
            loop = asyncio.get_event_loop()
            intent = await loop.run_in_executor(
                None,
                lambda: stripe.PaymentIntent.create(
                    amount=amount_cents,
                    currency=currency.lower(),
                    metadata=payment_metadata,
                    receipt_email=customer_email
                )
            )
            
            # Map Stripe status to our status
            status_map = {
                "requires_payment_method": PaymentStatus.PENDING,
                "requires_confirmation": PaymentStatus.PENDING,
                "requires_action": PaymentStatus.PENDING,
                "processing": PaymentStatus.PROCESSING,
                "succeeded": PaymentStatus.SUCCEEDED,
                "canceled": PaymentStatus.CANCELLED,
            }
            
            transaction = PaymentTransaction(
                transaction_id=intent.id,
                invoice_id=invoice_id,
                amount=amount,
                currency=currency,
                status=status_map.get(intent.status, PaymentStatus.PENDING),
                payment_method="stripe",
                provider=IntegrationProvider.STRIPE,
                created_at=datetime.fromtimestamp(intent.created),
                metadata={
                    "client_secret": intent.client_secret,
                    "stripe_status": intent.status
                }
            )
            
            self.logger.info(
                "Payment created",
                transaction_id=transaction.transaction_id,
                amount=amount,
                currency=currency
            )
            
            return transaction
            
        except Exception as e:
            self.logger.error("Failed to create payment", error=str(e))
            return PaymentTransaction(
                transaction_id=f"failed_{invoice_id}",
                invoice_id=invoice_id,
                amount=amount,
                currency=currency,
                status=PaymentStatus.FAILED,
                payment_method="stripe",
                provider=IntegrationProvider.STRIPE,
                created_at=datetime.now(),
                error_message=str(e)
            )
    
    async def get_payment_status(self, transaction_id: str) -> PaymentTransaction:
        """Get Stripe payment intent status."""
        if not self.enabled:
            return self._mock_payment_status(transaction_id)
        
        try:
            loop = asyncio.get_event_loop()
            intent = await loop.run_in_executor(
                None,
                lambda: stripe.PaymentIntent.retrieve(transaction_id)
            )
            
            status_map = {
                "requires_payment_method": PaymentStatus.PENDING,
                "requires_confirmation": PaymentStatus.PENDING,
                "requires_action": PaymentStatus.PENDING,
                "processing": PaymentStatus.PROCESSING,
                "succeeded": PaymentStatus.SUCCEEDED,
                "canceled": PaymentStatus.CANCELLED,
            }
            
            return PaymentTransaction(
                transaction_id=intent.id,
                invoice_id=intent.metadata.get("invoice_id", "unknown"),
                amount=intent.amount / 100.0,
                currency=intent.currency.upper(),
                status=status_map.get(intent.status, PaymentStatus.PENDING),
                payment_method="stripe",
                provider=IntegrationProvider.STRIPE,
                created_at=datetime.fromtimestamp(intent.created),
                completed_at=datetime.now() if intent.status == "succeeded" else None,
                metadata={"stripe_status": intent.status}
            )
            
        except Exception as e:
            self.logger.error("Failed to get payment status", error=str(e))
            raise
    
    async def refund_payment(
        self,
        transaction_id: str,
        amount: Optional[float] = None,
        reason: Optional[str] = None
    ) -> PaymentTransaction:
        """Refund a Stripe payment."""
        if not self.enabled:
            return self._mock_refund(transaction_id)
        
        try:
            refund_data = {"payment_intent": transaction_id}
            if amount:
                refund_data["amount"] = int(amount * 100)
            if reason:
                refund_data["reason"] = reason
            
            loop = asyncio.get_event_loop()
            refund = await loop.run_in_executor(
                None,
                lambda: stripe.Refund.create(**refund_data)
            )
            
            return PaymentTransaction(
                transaction_id=refund.id,
                invoice_id=refund.metadata.get("invoice_id", "unknown"),
                amount=(refund.amount / 100.0) if refund.amount else 0,
                currency=refund.currency.upper() if refund.currency else "USD",
                status=PaymentStatus.REFUNDED,
                payment_method="stripe",
                provider=IntegrationProvider.STRIPE,
                created_at=datetime.fromtimestamp(refund.created),
                metadata={"original_payment": transaction_id, "refund_status": refund.status}
            )
            
        except Exception as e:
            self.logger.error("Failed to refund payment", error=str(e))
            raise
    
    async def list_payments(
        self,
        invoice_id: Optional[str] = None,
        limit: int = 100
    ) -> List[PaymentTransaction]:
        """List Stripe payment intents."""
        if not self.enabled:
            return []
        
        try:
            loop = asyncio.get_event_loop()
            intents_data = await loop.run_in_executor(
                None,
                lambda: stripe.PaymentIntent.list(limit=limit)
            )
            
            transactions = []
            for intent in intents_data.data:
                if invoice_id and intent.metadata.get("invoice_id") != invoice_id:
                    continue
                
                status_map = {
                    "requires_payment_method": PaymentStatus.PENDING,
                    "requires_confirmation": PaymentStatus.PENDING,
                    "requires_action": PaymentStatus.PENDING,
                    "processing": PaymentStatus.PROCESSING,
                    "succeeded": PaymentStatus.SUCCEEDED,
                    "canceled": PaymentStatus.CANCELLED,
                }
                
                transactions.append(PaymentTransaction(
                    transaction_id=intent.id,
                    invoice_id=intent.metadata.get("invoice_id", "unknown"),
                    amount=intent.amount / 100.0,
                    currency=intent.currency.upper(),
                    status=status_map.get(intent.status, PaymentStatus.PENDING),
                    payment_method="stripe",
                    provider=IntegrationProvider.STRIPE,
                    created_at=datetime.fromtimestamp(intent.created),
                    metadata={"stripe_status": intent.status}
                ))
            
            return transactions
            
        except Exception as e:
            self.logger.error("Failed to list payments", error=str(e))
            return []
    
    # Mock methods for when Stripe is not configured
    def _mock_payment(self, invoice_id: str, amount: float, currency: str) -> PaymentTransaction:
        """Mock payment creation."""
        return PaymentTransaction(
            transaction_id=f"mock_stripe_{invoice_id}",
            invoice_id=invoice_id,
            amount=amount,
            currency=currency,
            status=PaymentStatus.SUCCEEDED,
            payment_method="stripe_mock",
            provider=IntegrationProvider.STRIPE,
            created_at=datetime.now(),
            completed_at=datetime.now(),
            metadata={"mock": True}
        )
    
    def _mock_payment_status(self, transaction_id: str) -> PaymentTransaction:
        """Mock payment status check."""
        return PaymentTransaction(
            transaction_id=transaction_id,
            invoice_id="mock_invoice",
            amount=1000.0,
            currency="USD",
            status=PaymentStatus.SUCCEEDED,
            payment_method="stripe_mock",
            provider=IntegrationProvider.STRIPE,
            created_at=datetime.now(),
            completed_at=datetime.now(),
            metadata={"mock": True}
        )
    
    def _mock_refund(self, transaction_id: str) -> PaymentTransaction:
        """Mock refund."""
        return PaymentTransaction(
            transaction_id=f"refund_{transaction_id}",
            invoice_id="mock_invoice",
            amount=1000.0,
            currency="USD",
            status=PaymentStatus.REFUNDED,
            payment_method="stripe_mock",
            provider=IntegrationProvider.STRIPE,
            created_at=datetime.now(),
            metadata={"mock": True, "original_payment": transaction_id}
        )
