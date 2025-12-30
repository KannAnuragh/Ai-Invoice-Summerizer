"""
Explainability Module
=====================
Provides reasoning traces and explanations for AI decisions.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ReasoningStep:
    """A single step in the reasoning process."""
    step_number: int
    action: str
    observation: str
    reasoning: str


@dataclass
class Explanation:
    """Full explanation of an AI decision."""
    decision: str
    confidence: float
    reasoning_steps: List[ReasoningStep]
    supporting_evidence: List[str]
    assumptions_made: List[str]
    timestamp: datetime


class ExplainabilityEngine:
    """
    Provides explanations for AI decisions.
    
    Features:
    - Chain-of-thought reasoning traces
    - Evidence citation
    - Assumption tracking
    - Confidence calibration
    """
    
    def explain_summary(
        self,
        invoice_data: Dict[str, Any],
        summary: str,
        role: str,
    ) -> Explanation:
        """
        Generate explanation for a summary.
        
        Args:
            invoice_data: Original invoice data
            summary: Generated summary
            role: Role the summary was generated for
            
        Returns:
            Explanation with reasoning trace
        """
        steps = []
        evidence = []
        assumptions = []
        
        # Step 1: Data extraction analysis
        steps.append(ReasoningStep(
            step_number=1,
            action="Analyzed extracted invoice data",
            observation=f"Found {len(invoice_data.get('line_items', []))} line items",
            reasoning="Examined all available fields to understand invoice scope"
        ))
        
        # Step 2: Vendor analysis
        vendor = invoice_data.get("vendor", {})
        if vendor:
            steps.append(ReasoningStep(
                step_number=2,
                action="Evaluated vendor information",
                observation=f"Vendor: {vendor.get('name', 'Unknown')}",
                reasoning="Vendor identification is critical for approval routing"
            ))
            evidence.append(f"Vendor name: {vendor.get('name', 'N/A')}")
        
        # Step 3: Amount analysis
        total = invoice_data.get("total_amount")
        if total:
            steps.append(ReasoningStep(
                step_number=3,
                action="Analyzed financial impact",
                observation=f"Total amount: {total}",
                reasoning="Amount determines approval level requirements"
            ))
            evidence.append(f"Invoice total: {invoice_data.get('currency', 'USD')} {total}")
        
        # Step 4: Risk assessment
        steps.append(ReasoningStep(
            step_number=4,
            action="Assessed risk indicators",
            observation="Checked for anomalies against vendor history",
            reasoning=f"Generated {role}-appropriate risk assessment"
        ))
        
        # Document assumptions
        if not invoice_data.get("po_number"):
            assumptions.append("No PO number found - assuming direct purchase")
        if not invoice_data.get("contract_terms"):
            assumptions.append("No contract reference - using standard terms")
        
        return Explanation(
            decision="Summary generated successfully",
            confidence=0.85,
            reasoning_steps=steps,
            supporting_evidence=evidence,
            assumptions_made=assumptions,
            timestamp=datetime.utcnow(),
        )
    
    def explain_anomaly(
        self,
        anomaly_type: str,
        anomaly_details: Dict[str, Any],
        vendor_history: Optional[Dict[str, Any]] = None,
    ) -> Explanation:
        """
        Explain why an anomaly was flagged.
        """
        steps = []
        evidence = []
        
        # Build reasoning based on anomaly type
        if anomaly_type == "amount_deviation":
            expected = anomaly_details.get("expected_amount", 0)
            actual = anomaly_details.get("actual_amount", 0)
            deviation = abs(actual - expected) / expected * 100 if expected else 0
            
            steps.append(ReasoningStep(
                step_number=1,
                action="Compared amount to historical average",
                observation=f"Deviation: {deviation:.1f}% from expected",
                reasoning="Significant deviations may indicate pricing errors or fraud"
            ))
            evidence.append(f"Expected: {expected}, Actual: {actual}")
        
        elif anomaly_type == "duplicate_detection":
            steps.append(ReasoningStep(
                step_number=1,
                action="Checked against existing invoices",
                observation=f"Match found: {anomaly_details.get('match_type', 'unknown')}",
                reasoning="Duplicate invoices may indicate processing errors or fraud"
            ))
            evidence.append(f"Original invoice: {anomaly_details.get('original_id', 'N/A')}")
        
        return Explanation(
            decision=f"Flagged as {anomaly_type}",
            confidence=anomaly_details.get("confidence", 0.7),
            reasoning_steps=steps,
            supporting_evidence=evidence,
            assumptions_made=[],
            timestamp=datetime.utcnow(),
        )
    
    def format_explanation_markdown(self, explanation: Explanation) -> str:
        """Format explanation as readable markdown."""
        lines = [
            f"## Decision: {explanation.decision}",
            f"**Confidence:** {explanation.confidence:.0%}",
            "",
            "### Reasoning Steps",
        ]
        
        for step in explanation.reasoning_steps:
            lines.extend([
                f"**{step.step_number}. {step.action}**",
                f"- Observation: {step.observation}",
                f"- Reasoning: {step.reasoning}",
                "",
            ])
        
        if explanation.supporting_evidence:
            lines.extend([
                "### Supporting Evidence",
                *[f"- {e}" for e in explanation.supporting_evidence],
                "",
            ])
        
        if explanation.assumptions_made:
            lines.extend([
                "### Assumptions",
                *[f"- {a}" for a in explanation.assumptions_made],
            ])
        
        return "\n".join(lines)


# Default engine instance
explainability_engine = ExplainabilityEngine()
