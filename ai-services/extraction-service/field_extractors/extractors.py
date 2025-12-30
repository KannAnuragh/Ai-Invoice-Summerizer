"""
Field Extractors
================
Extract structured fields from OCR text using patterns and AI.
"""

import re
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from dataclasses import dataclass
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ExtractedField:
    """An extracted field with confidence and location."""
    field_name: str
    value: Any
    raw_value: str
    confidence: float
    extraction_method: str  # regex, ai, layout
    position: Optional[Dict[str, int]] = None  # Bounding box if available


@dataclass
class ExtractionResult:
    """Complete extraction result for a document."""
    success: bool
    fields: Dict[str, ExtractedField]
    raw_text: str
    confidence: float
    warnings: List[str]
    errors: List[str]


class FieldExtractor:
    """
    Extract invoice fields using regex patterns and heuristics.
    
    Fields extracted:
    - Invoice number
    - Invoice date
    - Due date
    - Vendor name
    - Vendor address
    - Tax ID
    - Subtotal
    - Tax amount
    - Total amount
    - PO number
    - Payment terms
    """
    
    # Regex patterns for common invoice fields
    PATTERNS = {
        "invoice_number": [
            r"invoice\s*#?\s*:?\s*([A-Z0-9][-A-Z0-9]{3,20})",
            r"inv\s*#?\s*:?\s*([A-Z0-9][-A-Z0-9]{3,20})",
            r"invoice\s*number\s*:?\s*([A-Z0-9][-A-Z0-9]{3,20})",
            r"bill\s*#?\s*:?\s*([A-Z0-9][-A-Z0-9]{3,20})",
        ],
        "po_number": [
            r"p\.?o\.?\s*#?\s*:?\s*([A-Z0-9][-A-Z0-9]{3,20})",
            r"purchase\s*order\s*#?\s*:?\s*([A-Z0-9][-A-Z0-9]{3,20})",
            r"order\s*#?\s*:?\s*([A-Z0-9][-A-Z0-9]{3,20})",
        ],
        "date": [
            r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",  # MM/DD/YYYY or DD-MM-YYYY
            r"(\d{4}[/-]\d{1,2}[/-]\d{1,2})",    # YYYY-MM-DD
            r"(\w+\s+\d{1,2},?\s+\d{4})",         # Month DD, YYYY
            r"(\d{1,2}\s+\w+\s+\d{4})",           # DD Month YYYY
        ],
        "amount": [
            r"\$\s*([\d,]+\.?\d*)",               # $1,234.56
            r"([\d,]+\.?\d*)\s*(?:USD|EUR|GBP|INR)",  # 1234.56 USD
            r"(?:total|amount|due)\s*:?\s*\$?\s*([\d,]+\.?\d*)",
        ],
        "tax_id": [
            r"(?:tax\s*id|tin|gst|vat)\s*:?\s*([A-Z0-9]{5,20})",
            r"(?:ein|ssn)\s*:?\s*(\d{2}-\d{7})",
        ],
        "email": [
            r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)",
        ],
        "phone": [
            r"(?:tel|phone|ph)\s*:?\s*([\d\s\-\(\)\.]+)",
            r"(\+?\d{1,3}[\s\-\.]?\(?\d{2,4}\)?[\s\-\.]?\d{3,4}[\s\-\.]?\d{3,4})",
        ],
    }
    
    def __init__(self):
        self._compiled_patterns = {}
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Pre-compile regex patterns for performance."""
        for field, patterns in self.PATTERNS.items():
            self._compiled_patterns[field] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]
    
    def extract_field(
        self,
        text: str,
        field_name: str,
    ) -> Optional[ExtractedField]:
        """
        Extract a single field from text.
        
        Tries multiple patterns and returns the first match.
        """
        patterns = self._compiled_patterns.get(field_name, [])
        
        for pattern in patterns:
            match = pattern.search(text)
            if match:
                raw_value = match.group(1) if match.groups() else match.group(0)
                return ExtractedField(
                    field_name=field_name,
                    value=self._normalize_value(field_name, raw_value),
                    raw_value=raw_value,
                    confidence=0.8,  # Regex matches have moderate confidence
                    extraction_method="regex",
                )
        
        return None
    
    def _normalize_value(self, field_name: str, raw_value: str) -> Any:
        """Normalize extracted value based on field type."""
        if field_name in ["amount", "subtotal", "tax_amount", "total_amount"]:
            # Remove currency symbols and convert to float
            cleaned = re.sub(r"[^\d.]", "", raw_value.replace(",", ""))
            try:
                return float(cleaned)
            except ValueError:
                return raw_value
        
        return raw_value.strip()
    
    def extract_all(self, text: str) -> ExtractionResult:
        """
        Extract all fields from text.
        """
        fields = {}
        warnings = []
        
        # Extract standard fields
        for field_name in self.PATTERNS.keys():
            result = self.extract_field(text, field_name)
            if result:
                fields[field_name] = result
        
        # Extract dates with context
        dates = self._extract_dates_with_context(text)
        if "invoice_date" in dates:
            fields["invoice_date"] = dates["invoice_date"]
        if "due_date" in dates:
            fields["due_date"] = dates["due_date"]
        
        # Extract amounts with context
        amounts = self._extract_amounts_with_context(text)
        for amt_name, amt_field in amounts.items():
            fields[amt_name] = amt_field
        
        # Calculate overall confidence
        if fields:
            avg_confidence = sum(f.confidence for f in fields.values()) / len(fields)
        else:
            avg_confidence = 0.0
            warnings.append("No fields extracted")
        
        return ExtractionResult(
            success=bool(fields),
            fields=fields,
            raw_text=text,
            confidence=avg_confidence,
            warnings=warnings,
            errors=[],
        )
    
    def _extract_dates_with_context(
        self,
        text: str,
    ) -> Dict[str, ExtractedField]:
        """Extract dates with contextual labels."""
        dates = {}
        
        # Invoice date patterns
        invoice_date_patterns = [
            r"(?:invoice\s*date|date\s*of\s*invoice)\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
            r"(?:invoice\s*date|date)\s*:?\s*(\w+\s+\d{1,2},?\s+\d{4})",
        ]
        
        for pattern in invoice_date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                dates["invoice_date"] = ExtractedField(
                    field_name="invoice_date",
                    value=match.group(1),
                    raw_value=match.group(1),
                    confidence=0.85,
                    extraction_method="regex_contextual",
                )
                break
        
        # Due date patterns
        due_date_patterns = [
            r"(?:due\s*date|payment\s*due)\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
            r"(?:due|payable)\s*(?:by|on)\s*:?\s*(\w+\s+\d{1,2},?\s+\d{4})",
        ]
        
        for pattern in due_date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                dates["due_date"] = ExtractedField(
                    field_name="due_date",
                    value=match.group(1),
                    raw_value=match.group(1),
                    confidence=0.85,
                    extraction_method="regex_contextual",
                )
                break
        
        return dates
    
    def _extract_amounts_with_context(
        self,
        text: str,
    ) -> Dict[str, ExtractedField]:
        """Extract amounts with contextual labels."""
        amounts = {}
        
        amount_patterns = {
            "subtotal": [
                r"sub\s*-?\s*total\s*:?\s*\$?\s*([\d,]+\.?\d*)",
            ],
            "tax_amount": [
                r"(?:tax|vat|gst)\s*(?:amount)?\s*:?\s*\$?\s*([\d,]+\.?\d*)",
            ],
            "total_amount": [
                r"(?:grand\s*)?total\s*(?:amount|due)?\s*:?\s*\$?\s*([\d,]+\.?\d*)",
                r"amount\s*due\s*:?\s*\$?\s*([\d,]+\.?\d*)",
                r"balance\s*due\s*:?\s*\$?\s*([\d,]+\.?\d*)",
            ],
        }
        
        for field_name, patterns in amount_patterns.items():
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    raw_value = match.group(1)
                    cleaned = re.sub(r"[^\d.]", "", raw_value.replace(",", ""))
                    try:
                        value = float(cleaned)
                    except ValueError:
                        value = raw_value
                    
                    amounts[field_name] = ExtractedField(
                        field_name=field_name,
                        value=value,
                        raw_value=raw_value,
                        confidence=0.85,
                        extraction_method="regex_contextual",
                    )
                    break
        
        return amounts


# Default extractor instance
field_extractor = FieldExtractor()
