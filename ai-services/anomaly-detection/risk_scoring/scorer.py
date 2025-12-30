"""
Risk Scoring
============
Calculate composite risk scores for invoices.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
import structlog

logger = structlog.get_logger(__name__)


class RiskLevel(str, Enum):
    """Risk classification levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskFactor(str, Enum):
    """Types of risk factors evaluated."""
    AMOUNT_DEVIATION = "amount_deviation"
    NEW_VENDOR = "new_vendor"
    UNUSUAL_TIMING = "unusual_timing"
    DUPLICATE_SUSPECTED = "duplicate_suspected"
    MISSING_PO = "missing_po"
    ROUND_AMOUNT = "round_amount"
    RUSH_PAYMENT = "rush_payment"
    THRESHOLD_SPLITTING = "threshold_splitting"
    VENDOR_RISK = "vendor_risk"
    UNUSUAL_CATEGORY = "unusual_category"


@dataclass
class RiskIndicator:
    """A single risk indicator."""
    factor: RiskFactor
    weight: float  # 0.0 to 1.0
    score: float  # 0.0 to 1.0
    description: str
    evidence: Optional[str] = None


@dataclass
class RiskAssessment:
    """Complete risk assessment for an invoice."""
    overall_score: float  # 0.0 to 1.0
    level: RiskLevel
    indicators: List[RiskIndicator]
    recommendations: List[str]
    requires_review: bool


class RiskScorer:
    """
    Calculate risk scores for invoices.
    
    Risk Factors:
    - Amount deviation from historical average
    - New or unusual vendor
    - Timing anomalies
    - Missing documentation
    - Suspicious patterns (round amounts, threshold splitting)
    """
    
    # Default weights for risk factors
    FACTOR_WEIGHTS = {
        RiskFactor.AMOUNT_DEVIATION: 0.20,
        RiskFactor.NEW_VENDOR: 0.15,
        RiskFactor.UNUSUAL_TIMING: 0.10,
        RiskFactor.DUPLICATE_SUSPECTED: 0.25,
        RiskFactor.MISSING_PO: 0.10,
        RiskFactor.ROUND_AMOUNT: 0.05,
        RiskFactor.RUSH_PAYMENT: 0.10,
        RiskFactor.THRESHOLD_SPLITTING: 0.20,
        RiskFactor.VENDOR_RISK: 0.15,
        RiskFactor.UNUSUAL_CATEGORY: 0.05,
    }
    
    # Thresholds for risk levels
    LEVEL_THRESHOLDS = {
        RiskLevel.LOW: 0.3,
        RiskLevel.MEDIUM: 0.5,
        RiskLevel.HIGH: 0.7,
        RiskLevel.CRITICAL: 1.0,
    }
    
    def __init__(
        self,
        custom_weights: Optional[Dict[RiskFactor, float]] = None,
        review_threshold: float = 0.5,
    ):
        self.weights = {**self.FACTOR_WEIGHTS}
        if custom_weights:
            self.weights.update(custom_weights)
        self.review_threshold = review_threshold
    
    def assess(
        self,
        invoice_data: Dict[str, Any],
        vendor_history: Optional[Dict[str, Any]] = None,
        company_config: Optional[Dict[str, Any]] = None,
    ) -> RiskAssessment:
        """
        Perform complete risk assessment.
        
        Args:
            invoice_data: Extracted invoice data
            vendor_history: Historical data for this vendor
            company_config: Company-specific thresholds
            
        Returns:
            RiskAssessment with scores and recommendations
        """
        indicators = []
        vendor_history = vendor_history or {}
        company_config = company_config or {}
        
        # Check each risk factor
        indicators.append(self._check_amount_deviation(invoice_data, vendor_history))
        indicators.append(self._check_new_vendor(vendor_history))
        indicators.append(self._check_missing_po(invoice_data))
        indicators.append(self._check_round_amount(invoice_data))
        indicators.append(self._check_rush_payment(invoice_data))
        indicators.append(self._check_threshold_splitting(invoice_data, company_config))
        
        # Remove None indicators
        indicators = [i for i in indicators if i is not None]
        
        # Calculate weighted score
        if indicators:
            total_weight = sum(self.weights.get(i.factor, 0.1) for i in indicators)
            weighted_score = sum(
                i.score * self.weights.get(i.factor, 0.1) for i in indicators
            ) / total_weight
        else:
            weighted_score = 0.0
        
        # Determine risk level
        level = RiskLevel.LOW
        for lvl, threshold in sorted(self.LEVEL_THRESHOLDS.items(), key=lambda x: x[1]):
            if weighted_score <= threshold:
                level = lvl
                break
        
        # Generate recommendations
        recommendations = self._generate_recommendations(indicators, level)
        
        return RiskAssessment(
            overall_score=round(weighted_score, 3),
            level=level,
            indicators=indicators,
            recommendations=recommendations,
            requires_review=weighted_score >= self.review_threshold,
        )
    
    def _check_amount_deviation(
        self,
        invoice_data: Dict[str, Any],
        vendor_history: Dict[str, Any],
    ) -> Optional[RiskIndicator]:
        """Check if amount deviates from historical average."""
        amount = invoice_data.get("total_amount", 0)
        avg_amount = vendor_history.get("average_invoice_amount", 0)
        
        if not avg_amount or not amount:
            return None
        
        deviation = abs(amount - avg_amount) / avg_amount
        
        if deviation > 0.5:  # More than 50% deviation
            return RiskIndicator(
                factor=RiskFactor.AMOUNT_DEVIATION,
                weight=self.weights[RiskFactor.AMOUNT_DEVIATION],
                score=min(deviation, 1.0),
                description=f"Amount {deviation:.0%} different from average",
                evidence=f"Invoice: {amount}, Avg: {avg_amount}",
            )
        
        return None
    
    def _check_new_vendor(
        self,
        vendor_history: Dict[str, Any],
    ) -> Optional[RiskIndicator]:
        """Check if vendor is new or has limited history."""
        invoice_count = vendor_history.get("total_invoices", 0)
        
        if invoice_count < 3:
            return RiskIndicator(
                factor=RiskFactor.NEW_VENDOR,
                weight=self.weights[RiskFactor.NEW_VENDOR],
                score=0.7 if invoice_count == 0 else 0.4,
                description="New or limited vendor history",
                evidence=f"Only {invoice_count} prior invoices",
            )
        
        return None
    
    def _check_missing_po(
        self,
        invoice_data: Dict[str, Any],
    ) -> Optional[RiskIndicator]:
        """Check for missing PO number."""
        if not invoice_data.get("po_number"):
            amount = invoice_data.get("total_amount", 0)
            
            # Higher concern for larger amounts without PO
            if amount > 1000:
                return RiskIndicator(
                    factor=RiskFactor.MISSING_PO,
                    weight=self.weights[RiskFactor.MISSING_PO],
                    score=0.6,
                    description="No PO number for significant amount",
                    evidence=f"Amount: {amount}",
                )
        
        return None
    
    def _check_round_amount(
        self,
        invoice_data: Dict[str, Any],
    ) -> Optional[RiskIndicator]:
        """Check for suspiciously round amounts."""
        amount = invoice_data.get("total_amount", 0)
        
        if amount >= 1000 and amount % 1000 == 0:
            return RiskIndicator(
                factor=RiskFactor.ROUND_AMOUNT,
                weight=self.weights[RiskFactor.ROUND_AMOUNT],
                score=0.3,
                description="Exact round amount",
                evidence=f"Amount: {amount}",
            )
        
        return None
    
    def _check_rush_payment(
        self,
        invoice_data: Dict[str, Any],
    ) -> Optional[RiskIndicator]:
        """Check for rush payment requests."""
        payment_terms = str(invoice_data.get("payment_terms", "")).lower()
        
        rush_indicators = ["immediate", "due upon receipt", "urgent", "asap", "net 0"]
        
        if any(ind in payment_terms for ind in rush_indicators):
            return RiskIndicator(
                factor=RiskFactor.RUSH_PAYMENT,
                weight=self.weights[RiskFactor.RUSH_PAYMENT],
                score=0.5,
                description="Rush payment requested",
                evidence=f"Terms: {invoice_data.get('payment_terms')}",
            )
        
        return None
    
    def _check_threshold_splitting(
        self,
        invoice_data: Dict[str, Any],
        company_config: Dict[str, Any],
    ) -> Optional[RiskIndicator]:
        """Check for threshold splitting (amounts just below approval limits)."""
        amount = invoice_data.get("total_amount", 0)
        thresholds = company_config.get("approval_thresholds", [1000, 5000, 10000, 25000])
        
        for threshold in thresholds:
            # Check if amount is 5-15% below a threshold
            if threshold * 0.85 <= amount < threshold * 0.98:
                return RiskIndicator(
                    factor=RiskFactor.THRESHOLD_SPLITTING,
                    weight=self.weights[RiskFactor.THRESHOLD_SPLITTING],
                    score=0.6,
                    description=f"Amount suspiciously close to {threshold} threshold",
                    evidence=f"Amount: {amount}, Threshold: {threshold}",
                )
        
        return None
    
    def _generate_recommendations(
        self,
        indicators: List[RiskIndicator],
        level: RiskLevel,
    ) -> List[str]:
        """Generate recommendations based on risk indicators."""
        recommendations = []
        
        for indicator in indicators:
            if indicator.factor == RiskFactor.AMOUNT_DEVIATION:
                recommendations.append("Verify pricing with vendor or check for volume changes")
            elif indicator.factor == RiskFactor.NEW_VENDOR:
                recommendations.append("Complete vendor verification before payment")
            elif indicator.factor == RiskFactor.MISSING_PO:
                recommendations.append("Obtain retroactive PO approval")
            elif indicator.factor == RiskFactor.DUPLICATE_SUSPECTED:
                recommendations.append("Confirm this is not a duplicate payment")
            elif indicator.factor == RiskFactor.THRESHOLD_SPLITTING:
                recommendations.append("Review for potential threshold avoidance")
        
        if level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            recommendations.append("Consider escalation to management review")
        
        return recommendations


# Default scorer instance
risk_scorer = RiskScorer()
