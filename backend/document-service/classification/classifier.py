"""
Document Classification
=======================
Classifies documents by type (invoice, receipt, credit note, etc.)
"""

from enum import Enum
from typing import Optional, List, Tuple
from dataclasses import dataclass
import structlog

logger = structlog.get_logger(__name__)


class DocumentType(str, Enum):
    """Types of financial documents."""
    INVOICE = "invoice"
    CREDIT_NOTE = "credit_note"
    DEBIT_NOTE = "debit_note"
    RECEIPT = "receipt"
    PURCHASE_ORDER = "purchase_order"
    STATEMENT = "statement"
    UNKNOWN = "unknown"


@dataclass
class ClassificationResult:
    """Result of document classification."""
    document_type: DocumentType
    confidence: float  # 0.0 to 1.0
    alternative_types: List[Tuple[DocumentType, float]]  # Other possible types
    keywords_found: List[str]


class DocumentClassifier:
    """
    Classifies documents based on content analysis.
    
    Uses keyword matching and layout analysis to determine document type.
    In production, could use ML models for better accuracy.
    """
    
    # Keywords associated with each document type
    TYPE_KEYWORDS = {
        DocumentType.INVOICE: [
            "invoice", "invoice number", "invoice #", "inv #", "bill to",
            "due date", "payment due", "total due", "amount due",
            "tax invoice", "proforma invoice", "remit to"
        ],
        DocumentType.CREDIT_NOTE: [
            "credit note", "credit memo", "credit memorandum",
            "refund", "credit adjustment", "adjustment note"
        ],
        DocumentType.DEBIT_NOTE: [
            "debit note", "debit memo", "debit memorandum",
            "charge back", "additional charge"
        ],
        DocumentType.RECEIPT: [
            "receipt", "payment received", "paid", "thank you for your payment",
            "transaction id", "confirmation", "amount paid"
        ],
        DocumentType.PURCHASE_ORDER: [
            "purchase order", "po number", "po #", "order confirmation",
            "requisition", "ship to", "deliver to"
        ],
        DocumentType.STATEMENT: [
            "statement", "account statement", "balance due",
            "previous balance", "current charges", "aging"
        ],
    }
    
    def __init__(self, min_confidence: float = 0.3):
        self.min_confidence = min_confidence
    
    def classify(self, text: str) -> ClassificationResult:
        """
        Classify document based on extracted text.
        
        Args:
            text: Extracted text from OCR
            
        Returns:
            ClassificationResult with type and confidence
        """
        text_lower = text.lower()
        scores = {}
        keywords_found = {}
        
        for doc_type, keywords in self.TYPE_KEYWORDS.items():
            matched_keywords = []
            score = 0
            
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    matched_keywords.append(keyword)
                    # Weight by keyword length (longer = more specific)
                    score += len(keyword.split())
            
            if matched_keywords:
                # Normalize score
                max_possible = sum(len(k.split()) for k in keywords)
                scores[doc_type] = score / max_possible if max_possible > 0 else 0
                keywords_found[doc_type] = matched_keywords
        
        if not scores:
            return ClassificationResult(
                document_type=DocumentType.UNKNOWN,
                confidence=0.0,
                alternative_types=[],
                keywords_found=[]
            )
        
        # Get best match
        sorted_types = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        best_type, best_score = sorted_types[0]
        
        # If best score is below threshold, mark as unknown
        if best_score < self.min_confidence:
            return ClassificationResult(
                document_type=DocumentType.UNKNOWN,
                confidence=best_score,
                alternative_types=sorted_types[:3],
                keywords_found=keywords_found.get(best_type, [])
            )
        
        return ClassificationResult(
            document_type=best_type,
            confidence=best_score,
            alternative_types=sorted_types[1:4],  # Top 3 alternatives
            keywords_found=keywords_found.get(best_type, [])
        )
    
    def classify_by_layout(self, layout_info: dict) -> Optional[DocumentType]:
        """
        Classify document based on layout features.
        
        Uses positional information about fields to improve classification.
        This is a placeholder for more sophisticated layout analysis.
        """
        # Layout-based classification would analyze:
        # - Position of header elements
        # - Table structure
        # - Footer information
        # - Overall document structure
        return None


# Default classifier instance
document_classifier = DocumentClassifier()
