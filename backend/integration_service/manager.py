"""
Integration Manager
==================
Centralized manager for all payment and ERP integrations.
"""

from typing import Optional, Dict, Any, List
from enum import Enum

import structlog

from . import IntegrationProvider, IntegrationType
from .payment.stripe_integration import StripeIntegration
from .erp.quickbooks_integration import QuickBooksIntegration

logger = structlog.get_logger(__name__)


class IntegrationManager:
    """
    Manages all integration instances and provides unified interface.
    """
    
    def __init__(self, config: Dict[str, Dict[str, Any]]):
        """
        Initialize integration manager.
        
        Args:
            config: Dict mapping provider names to their configurations
                   e.g., {"stripe": {"api_key": "..."}, "quickbooks": {...}}
        """
        self.config = config
        self.integrations: Dict[IntegrationProvider, Any] = {}
        self.logger = logger.bind(component="IntegrationManager")
        
        self._init_integrations()
    
    def _init_integrations(self):
        """Initialize all configured integrations."""
        # Payment Gateways
        if IntegrationProvider.STRIPE in self.config:
            try:
                self.integrations[IntegrationProvider.STRIPE] = StripeIntegration(
                    self.config[IntegrationProvider.STRIPE]
                )
                self.logger.info("Stripe integration initialized")
            except Exception as e:
                self.logger.error("Failed to initialize Stripe", error=str(e))
        
        # ERP Systems
        if IntegrationProvider.QUICKBOOKS in self.config:
            try:
                self.integrations[IntegrationProvider.QUICKBOOKS] = QuickBooksIntegration(
                    self.config[IntegrationProvider.QUICKBOOKS]
                )
                self.logger.info("QuickBooks integration initialized")
            except Exception as e:
                self.logger.error("Failed to initialize QuickBooks", error=str(e))
        
        # Add more integrations here as needed
    
    def get_integration(self, provider: IntegrationProvider):
        """Get integration instance by provider."""
        return self.integrations.get(provider)
    
    def get_payment_integration(self, provider: IntegrationProvider):
        """Get payment gateway integration."""
        integration = self.get_integration(provider)
        if integration and hasattr(integration, 'create_payment'):
            return integration
        return None
    
    def get_erp_integration(self, provider: IntegrationProvider):
        """Get ERP integration."""
        integration = self.get_integration(provider)
        if integration and hasattr(integration, 'sync_invoice'):
            return integration
        return None
    
    async def test_all_connections(self) -> Dict[IntegrationProvider, bool]:
        """Test all integration connections."""
        results = {}
        for provider, integration in self.integrations.items():
            try:
                results[provider] = await integration.test_connection()
            except Exception as e:
                self.logger.error(f"Connection test failed for {provider}", error=str(e))
                results[provider] = False
        return results
    
    async def get_all_status(self) -> Dict[IntegrationProvider, Dict[str, Any]]:
        """Get status of all integrations."""
        statuses = {}
        for provider, integration in self.integrations.items():
            try:
                statuses[provider] = await integration.get_status()
            except Exception as e:
                self.logger.error(f"Failed to get status for {provider}", error=str(e))
                statuses[provider] = {"error": str(e)}
        return statuses
    
    def list_available_integrations(self) -> Dict[str, List[str]]:
        """List all available integrations by type."""
        return {
            "payment_gateways": [
                p.value for p in self.integrations.keys()
                if hasattr(self.integrations[p], 'create_payment')
            ],
            "erp_systems": [
                p.value for p in self.integrations.keys()
                if hasattr(self.integrations[p], 'sync_invoice')
            ]
        }


# Global integration manager instance
_integration_manager: Optional[IntegrationManager] = None


def init_integration_manager(config: Dict[str, Dict[str, Any]]) -> IntegrationManager:
    """Initialize global integration manager."""
    global _integration_manager
    _integration_manager = IntegrationManager(config)
    return _integration_manager


def get_integration_manager() -> IntegrationManager:
    """Get global integration manager instance."""
    if _integration_manager is None:
        # Initialize with empty config if not initialized
        return init_integration_manager({})
    return _integration_manager
