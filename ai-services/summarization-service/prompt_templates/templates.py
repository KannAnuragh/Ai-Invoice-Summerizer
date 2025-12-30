"""
Prompt Templates
================
Structured prompts for AI summarization with policy injection.
"""

from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
import json


class SummaryRole(str, Enum):
    """User roles for different summary perspectives."""
    CFO = "cfo"
    FINANCE = "finance"
    PROCUREMENT = "procurement"
    AUDITOR = "auditor"
    GENERAL = "general"


@dataclass
class PromptTemplate:
    """A prompt template with placeholders."""
    name: str
    system_prompt: str
    user_prompt: str
    output_format: str  # json, text, markdown
    max_tokens: int = 500


# Base system prompt for all summarizations
BASE_SYSTEM_PROMPT = """You are an AI assistant specialized in analyzing and summarizing invoice documents for enterprise financial operations.

Your responsibilities:
1. Provide accurate, factual summaries based ONLY on the invoice data provided
2. Highlight potential issues or anomalies
3. Never fabricate or assume information not present in the document
4. Use precise financial terminology
5. Format monetary values consistently with the invoice currency

Company Policy:
{company_policies}

IMPORTANT: If information is unclear or missing, explicitly state "Not specified in invoice" rather than guessing.
"""


# Role-specific prompts
ROLE_PROMPTS = {
    SummaryRole.CFO: PromptTemplate(
        name="cfo_summary",
        system_prompt=BASE_SYSTEM_PROMPT + """
You are summarizing for the CFO. Focus on:
- Total financial impact
- Budget implications
- Strategic vendor relationships
- Any concerns requiring executive attention
- Comparison to historical spending patterns
""",
        user_prompt="""Summarize this invoice for CFO review:

**Invoice Data:**
{invoice_json}

**Historical Context:**
{historical_context}

Provide a concise executive summary (3-5 sentences) covering:
1. Amount and vendor significance
2. Any unusual aspects or concerns
3. Recommended action (if any)
""",
        output_format="markdown",
        max_tokens=300,
    ),
    
    SummaryRole.FINANCE: PromptTemplate(
        name="finance_summary",
        system_prompt=BASE_SYSTEM_PROMPT + """
You are summarizing for the Finance team. Focus on:
- Accurate amount breakdowns
- Tax calculations and compliance
- Payment terms and due dates
- GL coding suggestions
- Matching to POs and contracts
""",
        user_prompt="""Analyze this invoice for Finance processing:

**Invoice Data:**
{invoice_json}

**Validation Results:**
{validation_results}

Provide a detailed summary including:
1. Amount breakdown (subtotal, taxes, total)
2. Payment timeline
3. Any validation issues requiring attention
4. Suggested GL codes based on line items
5. PO/Contract match status
""",
        output_format="markdown",
        max_tokens=500,
    ),
    
    SummaryRole.PROCUREMENT: PromptTemplate(
        name="procurement_summary",
        system_prompt=BASE_SYSTEM_PROMPT + """
You are summarizing for the Procurement team. Focus on:
- Vendor information and compliance
- Line item details
- Contract adherence
- Pricing compared to agreements
- Delivery and service quality indicators
""",
        user_prompt="""Review this invoice for Procurement analysis:

**Invoice Data:**
{invoice_json}

**Vendor Profile:**
{vendor_profile}

**Contract Terms:**
{contract_terms}

Analyze and summarize:
1. Vendor compliance status
2. Line item pricing vs. contracted rates
3. Delivery/service completion
4. Any discrepancies requiring vendor discussion
5. Recommended procurement actions
""",
        output_format="markdown",
        max_tokens=500,
    ),
    
    SummaryRole.AUDITOR: PromptTemplate(
        name="auditor_summary",
        system_prompt=BASE_SYSTEM_PROMPT + """
You are summarizing for Audit review. Focus on:
- Completeness of documentation
- Approval chain compliance
- Segregation of duties
- Internal control adherence
- Red flags for fraud or error
""",
        user_prompt="""Audit review of this invoice:

**Invoice Data:**
{invoice_json}

**Approval History:**
{approval_history}

**Control Checklist:**
{control_checklist}

Provide audit summary covering:
1. Documentation completeness score
2. Approval compliance status
3. Internal control observations
4. Risk indicators identified
5. Audit recommendations
""",
        output_format="markdown",
        max_tokens=600,
    ),
    
    SummaryRole.GENERAL: PromptTemplate(
        name="general_summary",
        system_prompt=BASE_SYSTEM_PROMPT,
        user_prompt="""Summarize this invoice:

**Invoice Data:**
{invoice_json}

Provide a clear summary including:
1. Who: Vendor name and details
2. What: Items or services billed
3. How much: Total amount with currency
4. When: Invoice date and payment due date
5. Key observations: Any notable items or concerns
""",
        output_format="markdown",
        max_tokens=400,
    ),
}


class PromptBuilder:
    """Builds prompts from templates with data injection."""
    
    def __init__(
        self,
        company_policies: str = "Standard invoice processing policies apply.",
    ):
        self.company_policies = company_policies
    
    def build_prompt(
        self,
        role: SummaryRole,
        invoice_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> tuple[str, str]:
        """
        Build system and user prompts for a role.
        
        Returns:
            (system_prompt, user_prompt)
        """
        template = ROLE_PROMPTS.get(role, ROLE_PROMPTS[SummaryRole.GENERAL])
        context = context or {}
        
        # Format system prompt
        system_prompt = template.system_prompt.format(
            company_policies=self.company_policies,
        )
        
        # Format user prompt
        user_prompt = template.user_prompt.format(
            invoice_json=json.dumps(invoice_data, indent=2, default=str),
            historical_context=context.get("historical_context", "No historical data available."),
            validation_results=context.get("validation_results", "No validation issues."),
            vendor_profile=context.get("vendor_profile", "Vendor profile not available."),
            contract_terms=context.get("contract_terms", "No contract on file."),
            approval_history=context.get("approval_history", "No prior approvals."),
            control_checklist=context.get("control_checklist", "Standard controls apply."),
        )
        
        return system_prompt, user_prompt
    
    def get_max_tokens(self, role: SummaryRole) -> int:
        """Get max tokens for a role's summary."""
        template = ROLE_PROMPTS.get(role, ROLE_PROMPTS[SummaryRole.GENERAL])
        return template.max_tokens


# Default builder instance
prompt_builder = PromptBuilder()
