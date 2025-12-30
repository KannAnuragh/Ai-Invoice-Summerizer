"""
PO Matching Engine
==================
Match invoices to Purchase Orders with variance detection.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
import difflib
import re

import structlog

logger = structlog.get_logger(__name__)


class MatchStatus(str, Enum):
    """PO matching status."""
    MATCHED = "matched"
    PARTIAL = "partial"
    MISMATCH = "mismatch"
    NO_PO = "no_po"
    PO_NOT_FOUND = "po_not_found"


class VarianceType(str, Enum):
    """Types of variances detected."""
    AMOUNT = "amount"
    QUANTITY = "quantity"
    PRICE = "price"
    TAX = "tax"
    VENDOR = "vendor"
    DATE = "date"
    LINE_ITEM = "line_item"


@dataclass
class POLineItem:
    """Purchase Order line item."""
    line_number: int
    description: str
    quantity: float
    unit_price: float
    total: float
    sku: Optional[str] = None
    category: Optional[str] = None


@dataclass
class PurchaseOrder:
    """Purchase Order model."""
    po_number: str
    vendor_id: str
    vendor_name: str
    order_date: str
    expected_delivery: Optional[str] = None
    currency: str = "USD"
    subtotal: float = 0.0
    tax_amount: float = 0.0
    total_amount: float = 0.0
    line_items: List[POLineItem] = field(default_factory=list)
    status: str = "open"  # open, partial, fulfilled, cancelled
    created_by: Optional[str] = None
    created_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "po_number": self.po_number,
            "vendor_id": self.vendor_id,
            "vendor_name": self.vendor_name,
            "order_date": self.order_date,
            "currency": self.currency,
            "subtotal": self.subtotal,
            "tax_amount": self.tax_amount,
            "total_amount": self.total_amount,
            "line_items_count": len(self.line_items),
            "status": self.status
        }


@dataclass
class Variance:
    """Detected variance between invoice and PO."""
    type: VarianceType
    field: str
    invoice_value: Any
    po_value: Any
    difference: Optional[float] = None
    percentage: Optional[float] = None
    severity: str = "info"  # info, warning, critical
    message: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "field": self.field,
            "invoice_value": self.invoice_value,
            "po_value": self.po_value,
            "difference": self.difference,
            "percentage": self.percentage,
            "severity": self.severity,
            "message": self.message
        }


@dataclass
class LineItemMatch:
    """Match result for a single line item."""
    invoice_line: int
    po_line: Optional[int]
    confidence: float
    variances: List[Variance] = field(default_factory=list)
    status: str = "matched"  # matched, partial, unmatched


@dataclass
class MatchResult:
    """Complete PO matching result."""
    invoice_id: str
    po_number: str
    status: MatchStatus
    overall_confidence: float
    header_variances: List[Variance]
    line_matches: List[LineItemMatch]
    unmatched_invoice_lines: List[int]
    unmatched_po_lines: List[int]
    total_variance_amount: float
    matched_at: str
    recommendation: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "invoice_id": self.invoice_id,
            "po_number": self.po_number,
            "status": self.status.value,
            "overall_confidence": self.overall_confidence,
            "header_variances": [v.to_dict() for v in self.header_variances],
            "line_match_count": len(self.line_matches),
            "unmatched_invoice_lines": len(self.unmatched_invoice_lines),
            "unmatched_po_lines": len(self.unmatched_po_lines),
            "total_variance_amount": self.total_variance_amount,
            "matched_at": self.matched_at,
            "recommendation": self.recommendation
        }


# Demo PO database
_po_database: Dict[str, PurchaseOrder] = {}


def _init_demo_pos():
    """Initialize demo POs for testing."""
    if _po_database:
        return
    
    _po_database["PO-2024-001"] = PurchaseOrder(
        po_number="PO-2024-001",
        vendor_id="v-001",
        vendor_name="Acme Corporation",
        order_date="2024-12-01",
        currency="USD",
        subtotal=10500,
        tax_amount=1680,
        total_amount=12180,
        line_items=[
            POLineItem(1, "Software License - Enterprise", 1, 8000, 8000),
            POLineItem(2, "Implementation Services", 10, 150, 1500),
            POLineItem(3, "Training Hours", 5, 200, 1000),
        ],
        status="open"
    )
    
    _po_database["PO-2024-002"] = PurchaseOrder(
        po_number="PO-2024-002",
        vendor_id="v-002",
        vendor_name="CloudServices Ltd",
        order_date="2024-11-15",
        currency="USD",
        subtotal=12000,
        tax_amount=0,
        total_amount=12000,
        line_items=[
            POLineItem(1, "Cloud Hosting Monthly", 1, 12000, 12000),
        ],
        status="open"
    )


_init_demo_pos()


class POMatchingEngine:
    """
    Purchase Order matching engine.
    
    Features:
    - Fuzzy PO number matching
    - Header field comparison (vendor, amounts, dates)
    - Line item matching with description similarity
    - Variance detection and severity classification
    - Match confidence scoring
    """
    
    def __init__(
        self,
        amount_tolerance_percent: float = 5.0,
        quantity_tolerance_percent: float = 10.0,
        price_tolerance_percent: float = 2.0,
        description_similarity_threshold: float = 0.7,
    ):
        self.amount_tolerance = amount_tolerance_percent / 100
        self.quantity_tolerance = quantity_tolerance_percent / 100
        self.price_tolerance = price_tolerance_percent / 100
        self.description_threshold = description_similarity_threshold
    
    def find_po(self, po_reference: str) -> Optional[PurchaseOrder]:
        """
        Find a PO by number with fuzzy matching.
        
        Handles variations like:
        - PO-2024-001, PO2024001, 2024-001
        """
        if not po_reference:
            return None
        
        # Normalize input
        normalized = self._normalize_po_number(po_reference)
        
        # Exact match first
        if normalized in _po_database:
            return _po_database[normalized]
        
        # Try original
        if po_reference in _po_database:
            return _po_database[po_reference]
        
        # Fuzzy match
        best_match = None
        best_score = 0.0
        
        for po_num, po in _po_database.items():
            score = difflib.SequenceMatcher(
                None,
                normalized.lower(),
                self._normalize_po_number(po_num).lower()
            ).ratio()
            
            if score > best_score and score > 0.8:
                best_score = score
                best_match = po
        
        return best_match
    
    def _normalize_po_number(self, po_ref: str) -> str:
        """Normalize PO number for comparison."""
        # Remove common prefixes/suffixes
        normalized = po_ref.upper().strip()
        normalized = re.sub(r'^(PO|P\.O\.|PURCHASE\s*ORDER)[:\s#-]*', 'PO-', normalized)
        normalized = re.sub(r'[^A-Z0-9-]', '', normalized)
        return normalized
    
    def match_invoice(
        self,
        invoice: Dict[str, Any],
        po_reference: Optional[str] = None,
    ) -> MatchResult:
        """
        Match an invoice to a Purchase Order.
        
        Args:
            invoice: Invoice data dictionary
            po_reference: Optional PO number (extracted from invoice if not provided)
            
        Returns:
            MatchResult with variances and confidence
        """
        invoice_id = invoice.get("id", "unknown")
        
        # Get PO reference from invoice if not provided
        if not po_reference:
            po_reference = invoice.get("po_number") or invoice.get("purchase_order")
        
        if not po_reference:
            return MatchResult(
                invoice_id=invoice_id,
                po_number="",
                status=MatchStatus.NO_PO,
                overall_confidence=0.0,
                header_variances=[],
                line_matches=[],
                unmatched_invoice_lines=[],
                unmatched_po_lines=[],
                total_variance_amount=0.0,
                matched_at=datetime.utcnow().isoformat(),
                recommendation="No PO reference found on invoice"
            )
        
        # Find the PO
        po = self.find_po(po_reference)
        
        if not po:
            return MatchResult(
                invoice_id=invoice_id,
                po_number=po_reference,
                status=MatchStatus.PO_NOT_FOUND,
                overall_confidence=0.0,
                header_variances=[],
                line_matches=[],
                unmatched_invoice_lines=[],
                unmatched_po_lines=[],
                total_variance_amount=0.0,
                matched_at=datetime.utcnow().isoformat(),
                recommendation=f"PO '{po_reference}' not found in system"
            )
        
        # Compare headers
        header_variances = self._compare_headers(invoice, po)
        
        # Match line items
        invoice_lines = invoice.get("line_items", [])
        line_matches, unmatched_inv, unmatched_po = self._match_line_items(
            invoice_lines,
            po.line_items
        )
        
        # Calculate overall result
        total_variance = sum(abs(v.difference or 0) for v in header_variances)
        for match in line_matches:
            total_variance += sum(abs(v.difference or 0) for v in match.variances)
        
        # Determine status
        critical_variances = [v for v in header_variances if v.severity == "critical"]
        if critical_variances:
            status = MatchStatus.MISMATCH
        elif unmatched_inv or unmatched_po or any(m.status != "matched" for m in line_matches):
            status = MatchStatus.PARTIAL
        else:
            status = MatchStatus.MATCHED
        
        # Calculate confidence
        confidence = self._calculate_confidence(
            header_variances,
            line_matches,
            len(invoice_lines),
            len(po.line_items)
        )
        
        # Generate recommendation
        recommendation = self._generate_recommendation(
            status,
            confidence,
            header_variances,
            line_matches,
            total_variance
        )
        
        logger.info(
            "PO matching completed",
            invoice_id=invoice_id,
            po_number=po.po_number,
            status=status.value,
            confidence=f"{confidence:.2%}",
            variance=total_variance
        )
        
        return MatchResult(
            invoice_id=invoice_id,
            po_number=po.po_number,
            status=status,
            overall_confidence=confidence,
            header_variances=header_variances,
            line_matches=line_matches,
            unmatched_invoice_lines=unmatched_inv,
            unmatched_po_lines=unmatched_po,
            total_variance_amount=total_variance,
            matched_at=datetime.utcnow().isoformat(),
            recommendation=recommendation
        )
    
    def _compare_headers(
        self,
        invoice: Dict[str, Any],
        po: PurchaseOrder
    ) -> List[Variance]:
        """Compare invoice header fields to PO."""
        variances = []
        
        # Vendor comparison
        inv_vendor = invoice.get("vendor", {}).get("name", "")
        if inv_vendor and po.vendor_name:
            similarity = difflib.SequenceMatcher(
                None, inv_vendor.lower(), po.vendor_name.lower()
            ).ratio()
            
            if similarity < 0.9:
                variances.append(Variance(
                    type=VarianceType.VENDOR,
                    field="vendor_name",
                    invoice_value=inv_vendor,
                    po_value=po.vendor_name,
                    severity="warning" if similarity > 0.7 else "critical",
                    message=f"Vendor name mismatch ({similarity:.0%} similar)"
                ))
        
        # Total amount comparison
        inv_total = invoice.get("total_amount", 0)
        if inv_total and po.total_amount:
            diff = inv_total - po.total_amount
            pct = abs(diff) / po.total_amount if po.total_amount else 0
            
            if pct > self.amount_tolerance:
                severity = "critical" if pct > 0.1 else "warning"
                variances.append(Variance(
                    type=VarianceType.AMOUNT,
                    field="total_amount",
                    invoice_value=inv_total,
                    po_value=po.total_amount,
                    difference=diff,
                    percentage=pct * 100,
                    severity=severity,
                    message=f"Total amount variance: ${diff:+,.2f} ({pct:.1%})"
                ))
        
        # Tax comparison
        inv_tax = invoice.get("tax_amount", 0)
        if abs((inv_tax or 0) - po.tax_amount) > 1:  # $1 tolerance
            diff = (inv_tax or 0) - po.tax_amount
            variances.append(Variance(
                type=VarianceType.TAX,
                field="tax_amount",
                invoice_value=inv_tax,
                po_value=po.tax_amount,
                difference=diff,
                severity="info",
                message=f"Tax variance: ${diff:+,.2f}"
            ))
        
        # Currency check
        inv_currency = invoice.get("currency", "USD")
        if inv_currency != po.currency:
            variances.append(Variance(
                type=VarianceType.AMOUNT,
                field="currency",
                invoice_value=inv_currency,
                po_value=po.currency,
                severity="critical",
                message=f"Currency mismatch: Invoice is {inv_currency}, PO is {po.currency}"
            ))
        
        return variances
    
    def _match_line_items(
        self,
        invoice_lines: List[Dict],
        po_lines: List[POLineItem]
    ) -> tuple:
        """Match invoice line items to PO lines."""
        matches = []
        matched_po_indices = set()
        unmatched_inv = []
        
        for inv_idx, inv_line in enumerate(invoice_lines):
            best_match = None
            best_score = 0.0
            best_po_idx = None
            
            for po_idx, po_line in enumerate(po_lines):
                if po_idx in matched_po_indices:
                    continue
                
                # Description similarity
                inv_desc = inv_line.get("description", "").lower()
                po_desc = po_line.description.lower()
                similarity = difflib.SequenceMatcher(None, inv_desc, po_desc).ratio()
                
                if similarity > best_score and similarity >= self.description_threshold:
                    best_score = similarity
                    best_match = po_line
                    best_po_idx = po_idx
            
            if best_match:
                matched_po_indices.add(best_po_idx)
                variances = self._compare_line_item(inv_line, best_match)
                
                status = "matched" if not variances else (
                    "partial" if all(v.severity == "info" for v in variances) else "mismatch"
                )
                
                matches.append(LineItemMatch(
                    invoice_line=inv_idx + 1,
                    po_line=best_match.line_number,
                    confidence=best_score,
                    variances=variances,
                    status=status
                ))
            else:
                unmatched_inv.append(inv_idx + 1)
        
        # Find unmatched PO lines
        unmatched_po = [
            po_lines[i].line_number
            for i in range(len(po_lines))
            if i not in matched_po_indices
        ]
        
        return matches, unmatched_inv, unmatched_po
    
    def _compare_line_item(
        self,
        inv_line: Dict,
        po_line: POLineItem
    ) -> List[Variance]:
        """Compare a single line item."""
        variances = []
        
        # Quantity
        inv_qty = inv_line.get("quantity", 0)
        if inv_qty and po_line.quantity:
            diff = inv_qty - po_line.quantity
            pct = abs(diff) / po_line.quantity
            
            if pct > self.quantity_tolerance:
                variances.append(Variance(
                    type=VarianceType.QUANTITY,
                    field="quantity",
                    invoice_value=inv_qty,
                    po_value=po_line.quantity,
                    difference=diff,
                    percentage=pct * 100,
                    severity="warning",
                    message=f"Quantity variance: {diff:+.0f}"
                ))
        
        # Unit price
        inv_price = inv_line.get("unit_price", 0)
        if inv_price and po_line.unit_price:
            diff = inv_price - po_line.unit_price
            pct = abs(diff) / po_line.unit_price
            
            if pct > self.price_tolerance:
                variances.append(Variance(
                    type=VarianceType.PRICE,
                    field="unit_price",
                    invoice_value=inv_price,
                    po_value=po_line.unit_price,
                    difference=diff,
                    percentage=pct * 100,
                    severity="warning" if pct < 0.1 else "critical",
                    message=f"Price variance: ${diff:+,.2f}"
                ))
        
        return variances
    
    def _calculate_confidence(
        self,
        header_variances: List[Variance],
        line_matches: List[LineItemMatch],
        inv_line_count: int,
        po_line_count: int
    ) -> float:
        """Calculate overall match confidence."""
        score = 1.0
        
        # Deduct for header variances
        for v in header_variances:
            if v.severity == "critical":
                score -= 0.3
            elif v.severity == "warning":
                score -= 0.1
        
        # Line item matching score
        if inv_line_count > 0:
            matched = len([m for m in line_matches if m.status == "matched"])
            line_score = matched / max(inv_line_count, po_line_count)
            score = min(score, line_score + 0.3)
        
        return max(0.0, min(1.0, score))
    
    def _generate_recommendation(
        self,
        status: MatchStatus,
        confidence: float,
        header_variances: List[Variance],
        line_matches: List[LineItemMatch],
        total_variance: float
    ) -> str:
        """Generate human-readable recommendation."""
        if status == MatchStatus.MATCHED and confidence > 0.9:
            return "Invoice matches PO. Ready for automatic approval."
        
        if status == MatchStatus.MATCHED:
            return "Invoice matches PO with minor variances. Review recommended."
        
        if status == MatchStatus.PARTIAL:
            issues = []
            if any(v.severity == "warning" for v in header_variances):
                issues.append("header field variances")
            if any(m.status != "matched" for m in line_matches):
                issues.append("line item discrepancies")
            return f"Partial match detected: {', '.join(issues)}. Manual review required."
        
        if status == MatchStatus.MISMATCH:
            critical = [v for v in header_variances if v.severity == "critical"]
            if critical:
                return f"Critical mismatch: {critical[0].message}. Approval blocked."
            return f"Significant variance (${total_variance:,.2f}). Escalation recommended."
        
        return "Unable to verify. Manual review required."


# Singleton instance
_po_matcher: Optional[POMatchingEngine] = None


def get_po_matcher() -> POMatchingEngine:
    """Get or create PO matching engine."""
    global _po_matcher
    if _po_matcher is None:
        _po_matcher = POMatchingEngine()
    return _po_matcher
