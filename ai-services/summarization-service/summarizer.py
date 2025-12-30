"""
Ollama Summarizer
=================
AI summarization using Ollama local LLM.
"""

import os
from typing import Optional, Dict, Any
from dataclasses import dataclass
import json
import structlog
import httpx

logger = structlog.get_logger(__name__)


@dataclass
class SummaryResult:
    """Result of AI summarization."""
    success: bool
    summary: str
    role: str
    confidence: float
    tokens_used: int
    reasoning_trace: Optional[str] = None
    error: Optional[str] = None


class OllamaSummarizer:
    """
    Invoice summarization using Ollama local LLM.
    
    Features:
    - Role-based summaries
    - Explainable reasoning
    - Hallucination prevention
    - Structured output
        - No API keys required (local model)
    """
    
    def __init__(
        self,
        ollama_url: Optional[str] = None,
        model: str = "mistral",
    ):
        """
        Initialize Ollama summarizer.
        
        Args:
            ollama_url: Ollama server URL (default: http://localhost:11434)
            model: Ollama model name (default: mistral)
        """
        self.ollama_url = ollama_url or os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.model = model or os.getenv("OLLAMA_MODEL", "mistral")
        logger.info(
            "Initialized Ollama summarizer",
            url=self.ollama_url,
            model=self.model,
        )
    
    def summarize(
        self,
        invoice_data: Dict[str, Any],
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 500,
    ) -> SummaryResult:
        """
        Generate an AI summary of invoice data using Ollama.
        
        Args:
            invoice_data: Extracted invoice data
            system_prompt: System context and instructions
            user_prompt: Formatted user prompt with data
            max_tokens: Maximum response tokens
            
        Returns:
            SummaryResult with generated summary
        """
        try:
            # Combine prompts
            full_prompt = f"{system_prompt}\n\n{user_prompt}"
            
            # Call Ollama API (synchronous)
            response = httpx.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": full_prompt,
                    "stream": False,
                    "num_ctx": 4096,
                    "num_predict": max_tokens,
                    "temperature": 0.3,
                    "top_p": 0.9,
                    "top_k": 40,
                },
                timeout=60.0,
            )
            
            if response.status_code != 200:
                logger.error(
                    "Ollama API error",
                    status=response.status_code,
                    response=response.text,
                )
                return self._fallback_summary(invoice_data)
            
            result = response.json()
            summary = result.get("response", "").strip()
            
            if not summary:
                logger.warning("Ollama returned empty response")
                return self._fallback_summary(invoice_data)
            
            logger.info(
                "Summary generated from Ollama",
                model=self.model,
                tokens=len(summary.split()),
            )
            
            return SummaryResult(
                success=True,
                summary=summary,
                role="ai",
                confidence=0.85,
                tokens_used=len(summary.split()),
                    except httpx.ConnectError:
                        logger.warning(
                            "Ollama not available, using fallback",
                            url=self.ollama_url,
                        )
                        return self._fallback_summary(invoice_data)
            
            )
            
        except Exception as e:
            logger.error("Summarization failed", error=str(e), exc_info=True)
            return self._fallback_summary(invoice_data)
    
    def _fallback_summary(self, invoice_data: Dict[str, Any]) -> SummaryResult:
        """
        Generate a simple template-based summary when Ollama is unavailable.
        """
        # Extract key fields
        vendor = invoice_data.get("vendor", {}).get("name", "Unknown Vendor")
        invoice_number = invoice_data.get("invoice_number", "N/A")
        total = invoice_data.get("total_amount", 0)
        currency = invoice_data.get("currency", "USD")
        invoice_date = invoice_data.get("invoice_date", "N/A")
        due_date = invoice_data.get("due_date", "N/A")
        
        # Count line items
        line_items = invoice_data.get("line_items", [])
        item_count = len(line_items)
        
        summary = f"""## Invoice Summary

**Vendor:** {vendor}
**Invoice #:** {invoice_number}
**Date:** {invoice_date}
**Due Date:** {due_date}

**Amount:** {currency} {total:,.2f}
**Line Items:** {item_count}

*Note: AI summary unavailable. This is a template-based summary.*
"""
        
        return SummaryResult(
            success=True,
            summary=summary,
            role="template",
            confidence=1.0,
            tokens_used=0,
        )
    
    def summarize_with_explanation(
        self,
        invoice_data: Dict[str, Any],
        system_prompt: str,
        user_prompt: str,
    ) -> SummaryResult:
        """
        Generate summary with chain-of-thought reasoning.
        Useful for explaining why certain things were flagged.
        """
        # Add explanation request to prompt
        explanation_prompt = user_prompt + """

    Additionally, provide your detailed reasoning process:
1. What key information did you identify?
2. Why did you highlight certain aspects?
3. What concerns or risks did you identify?
4. What are your recommendations?

Format your response as:
## Summary
[Your summary here]

## Reasoning
[Your explanation here]
"""
        
        result = self.summarize(
            invoice_data,
            system_prompt,
            explanation_prompt,
            max_tokens=800,
        )
        
        # Extract reasoning if present
        if result.success and "## Reasoning" in result.summary:
            parts = result.summary.split("## Reasoning")
            result.summary = parts[0].replace("## Summary", "").strip()
            result.reasoning_trace = parts[1].strip() if len(parts) > 1 else None
        
        return result


# Default summarizer instance
ollama_summarizer = OllamaSummarizer()

# Backwards compatibility alias
GeminiSummarizer = OllamaSummarizer
gemini_summarizer = ollama_summarizer
