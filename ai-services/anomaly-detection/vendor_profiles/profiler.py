"""
Vendor Profiling
================
Build and maintain vendor behavioral profiles for anomaly detection.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from statistics import mean, stdev
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class VendorStatistics:
    """Statistical profile of a vendor."""
    total_invoices: int = 0
    total_amount: float = 0.0
    average_amount: float = 0.0
    std_deviation: float = 0.0
    min_amount: float = 0.0
    max_amount: float = 0.0
    average_payment_days: int = 30
    invoice_frequency_days: float = 30.0
    last_invoice_date: Optional[datetime] = None
    first_invoice_date: Optional[datetime] = None


@dataclass
class VendorProfile:
    """Complete vendor profile including history and statistics."""
    vendor_id: str
    vendor_name: str
    statistics: VendorStatistics
    common_categories: List[str] = field(default_factory=list)
    payment_terms_history: List[str] = field(default_factory=list)
    currency: str = "USD"
    risk_level: str = "normal"
    is_verified: bool = False
    notes: List[str] = field(default_factory=list)


class VendorProfiler:
    """
    Build and manage vendor profiles for anomaly detection.
    
    Tracks:
    - Invoice amounts and frequency
    - Payment patterns
    - Spending categories
    - Historical behavior
    """
    
    def __init__(self):
        # In-memory storage (replace with database in production)
        self._profiles: Dict[str, VendorProfile] = {}
        self._invoice_history: Dict[str, List[Dict]] = {}
    
    def get_profile(self, vendor_id: str) -> Optional[VendorProfile]:
        """Get existing vendor profile."""
        return self._profiles.get(vendor_id)
    
    def create_or_update_profile(
        self,
        vendor_id: str,
        vendor_name: str,
        invoice_data: Dict[str, Any],
    ) -> VendorProfile:
        """
        Update vendor profile with new invoice data.
        
        Args:
            vendor_id: Unique vendor identifier
            vendor_name: Vendor display name
            invoice_data: Extracted invoice data
            
        Returns:
            Updated VendorProfile
        """
        # Get or create history
        if vendor_id not in self._invoice_history:
            self._invoice_history[vendor_id] = []
        
        # Add invoice to history
        invoice_record = {
            "amount": invoice_data.get("total_amount", 0),
            "date": invoice_data.get("invoice_date", datetime.utcnow()),
            "payment_terms": invoice_data.get("payment_terms"),
            "currency": invoice_data.get("currency", "USD"),
        }
        self._invoice_history[vendor_id].append(invoice_record)
        
        # Calculate statistics
        stats = self._calculate_statistics(vendor_id)
        
        # Get or create profile
        if vendor_id in self._profiles:
            profile = self._profiles[vendor_id]
            profile.statistics = stats
        else:
            profile = VendorProfile(
                vendor_id=vendor_id,
                vendor_name=vendor_name,
                statistics=stats,
                currency=invoice_data.get("currency", "USD"),
            )
        
        # Update payment terms history
        if invoice_data.get("payment_terms"):
            if invoice_data["payment_terms"] not in profile.payment_terms_history:
                profile.payment_terms_history.append(invoice_data["payment_terms"])
        
        self._profiles[vendor_id] = profile
        
        return profile
    
    def _calculate_statistics(self, vendor_id: str) -> VendorStatistics:
        """Calculate statistics from invoice history."""
        history = self._invoice_history.get(vendor_id, [])
        
        if not history:
            return VendorStatistics()
        
        amounts = [inv["amount"] for inv in history if inv.get("amount")]
        dates = [inv["date"] for inv in history if inv.get("date")]
        
        stats = VendorStatistics(
            total_invoices=len(history),
            total_amount=sum(amounts) if amounts else 0,
        )
        
        if amounts:
            stats.average_amount = mean(amounts)
            stats.min_amount = min(amounts)
            stats.max_amount = max(amounts)
            if len(amounts) > 1:
                stats.std_deviation = stdev(amounts)
        
        if dates and len(dates) > 1:
            # Sort dates
            sorted_dates = sorted(d for d in dates if d)
            stats.first_invoice_date = sorted_dates[0]
            stats.last_invoice_date = sorted_dates[-1]
            
            # Calculate average frequency
            if len(sorted_dates) > 1:
                total_days = (sorted_dates[-1] - sorted_dates[0]).days
                stats.invoice_frequency_days = total_days / (len(sorted_dates) - 1)
        
        return stats
    
    def check_anomaly(
        self,
        vendor_id: str,
        invoice_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Check if invoice is anomalous compared to vendor history.
        
        Returns dict with anomaly flags and scores.
        """
        profile = self.get_profile(vendor_id)
        
        if not profile or profile.statistics.total_invoices < 3:
            return {
                "is_anomaly": False,
                "reason": "Insufficient history for comparison",
                "confidence": 0.0,
            }
        
        stats = profile.statistics
        amount = invoice_data.get("total_amount", 0)
        
        anomalies = []
        
        # Check amount deviation
        if stats.std_deviation > 0:
            z_score = abs(amount - stats.average_amount) / stats.std_deviation
            if z_score > 2:
                anomalies.append({
                    "type": "amount_deviation",
                    "severity": "high" if z_score > 3 else "medium",
                    "detail": f"Z-score: {z_score:.2f}",
                })
        
        # Check against historical range
        if amount > stats.max_amount * 1.5:
            anomalies.append({
                "type": "exceeds_historical_max",
                "severity": "medium",
                "detail": f"Amount {amount} exceeds max {stats.max_amount}",
            })
        
        # Check timing
        if stats.last_invoice_date:
            days_since_last = (datetime.utcnow() - stats.last_invoice_date).days
            expected_days = stats.invoice_frequency_days
            
            if days_since_last < expected_days * 0.3:
                anomalies.append({
                    "type": "unusual_timing",
                    "severity": "low",
                    "detail": f"Only {days_since_last} days since last invoice",
                })
        
        return {
            "is_anomaly": len(anomalies) > 0,
            "anomalies": anomalies,
            "confidence": min(0.9, 0.5 + len(anomalies) * 0.2),
            "vendor_stats": {
                "total_invoices": stats.total_invoices,
                "average_amount": stats.average_amount,
                "std_deviation": stats.std_deviation,
            }
        }
    
    def get_vendor_summary(self, vendor_id: str) -> Optional[str]:
        """Get human-readable vendor summary."""
        profile = self.get_profile(vendor_id)
        
        if not profile:
            return None
        
        stats = profile.statistics
        
        return f"""**Vendor Profile: {profile.vendor_name}**
- Total Invoices: {stats.total_invoices}
- Average Amount: {profile.currency} {stats.average_amount:,.2f}
- Amount Range: {profile.currency} {stats.min_amount:,.2f} - {stats.max_amount:,.2f}
- Invoice Frequency: Every {stats.invoice_frequency_days:.0f} days
- Risk Level: {profile.risk_level}
- Verified: {'Yes' if profile.is_verified else 'No'}
"""


# Default profiler instance
vendor_profiler = VendorProfiler()
