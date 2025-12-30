"""
Role-Based Summaries
====================
Generate summaries tailored to different user roles.
"""

from typing import Optional, Dict, Any
from dataclasses import dataclass
import structlog

from .prompt_templates import SummaryRole, prompt_builder
from .summarizer import GeminiSummarizer, SummaryResult, gemini_summarizer

logger = structlog.get_logger(__name__)


@dataclass
class RoleSummary:
    """A summary tailored for a specific role."""
    role: SummaryRole
    summary: str
    highlights: list[str]
    action_items: list[str]
    confidence: float


class RoleBasedSummarizer:
    """
    Generate summaries optimized for different organizational roles.
    
    Roles:
    - CFO: Executive summary with strategic focus
    - Finance: Detailed breakdown with GL codes
    - Procurement: Vendor and contract analysis
    - Auditor: Compliance and control focus
    - General: Basic informational summary
    """
    
    def __init__(
        self,
        summarizer: Optional[GeminiSummarizer] = None,
        company_policies: str = "Standard processing policies apply.",
    ):
        self.summarizer = summarizer or gemini_summarizer
        self.prompt_builder = prompt_builder
        self.prompt_builder.company_policies = company_policies
    
    def generate_summary(
        self,
        invoice_data: Dict[str, Any],
        role: SummaryRole = SummaryRole.GENERAL,
        context: Optional[Dict[str, Any]] = None,
    ) -> RoleSummary:
        """
        Generate a role-appropriate summary.
        
        Args:
            invoice_data: Extracted invoice data
            role: Target user role
            context: Additional context (vendor history, contracts, etc.)
            
        Returns:
            RoleSummary with tailored content
        """
        # Build prompts for role
        system_prompt, user_prompt = self.prompt_builder.build_prompt(
            role=role,
            invoice_data=invoice_data,
            context=context,
        )
        
        # Generate summary
        result = self.summarizer.summarize(
            invoice_data=invoice_data,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=self.prompt_builder.get_max_tokens(role),
        )
        
        # Extract structured elements
        highlights = self._extract_highlights(result.summary, role)
        action_items = self._extract_action_items(result.summary, role)
        
        return RoleSummary(
            role=role,
            summary=result.summary,
            highlights=highlights,
            action_items=action_items,
            confidence=result.confidence,
        )
    
    def generate_all_summaries(
        self,
        invoice_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[SummaryRole, RoleSummary]:
        """
        Generate summaries for all roles.
        Useful for pre-caching summaries.
        """
        summaries = {}
        
        for role in SummaryRole:
            try:
                summaries[role] = self.generate_summary(
                    invoice_data=invoice_data,
                    role=role,
                    context=context,
                )
            except Exception as e:
                logger.error(f"Failed to generate {role} summary", error=str(e))
        
        return summaries
    
    def _extract_highlights(
        self,
        summary: str,
        role: SummaryRole,
    ) -> list[str]:
        """Extract key highlights from summary text."""
        highlights = []
        
        # Look for bullet points
        lines = summary.split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith(("- ", "* ", "• ", "→ ")):
                highlights.append(line[2:].strip())
            elif line.startswith(("1.", "2.", "3.", "4.", "5.")):
                highlights.append(line[2:].strip())
        
        return highlights[:5]  # Max 5 highlights
    
    def _extract_action_items(
        self,
        summary: str,
        role: SummaryRole,
    ) -> list[str]:
        """Extract action items from summary text."""
        action_keywords = [
            "recommend", "should", "action", "review", "verify",
            "contact", "escalate", "approve", "reject", "follow up"
        ]
        
        actions = []
        sentences = summary.replace("\n", " ").split(".")
        
        for sentence in sentences:
            sentence_lower = sentence.lower()
            if any(kw in sentence_lower for kw in action_keywords):
                cleaned = sentence.strip()
                if cleaned and len(cleaned) > 10:
                    actions.append(cleaned)
        
        return actions[:3]  # Max 3 action items


# Default instance
role_summarizer = RoleBasedSummarizer()
