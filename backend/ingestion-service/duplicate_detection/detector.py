"""
Duplicate Detection
===================
Detects duplicate invoices using multiple strategies.
"""

import hashlib
from typing import Optional, List, Dict, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from difflib import SequenceMatcher

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class DuplicateMatch:
    """Represents a potential duplicate match."""
    original_id: str
    match_type: str  # exact_hash, fuzzy_vendor, similar_amount
    confidence: float  # 0.0 to 1.0
    details: dict


class DuplicateDetector:
    """
    Multi-strategy duplicate detection.
    
    Strategies:
    1. Exact hash match - Same file uploaded twice
    2. Vendor + Invoice Number - Same invoice from same vendor
    3. Similar amounts - Potential duplicate within time window
    """
    
    def __init__(
        self,
        hash_window_days: int = 90,
        similarity_threshold: float = 0.85,
    ):
        self.hash_window_days = hash_window_days
        self.similarity_threshold = similarity_threshold
        
        # In-memory storage (replace with database in production)
        self._hash_index: Dict[str, List[dict]] = {}
        self._vendor_index: Dict[str, List[dict]] = {}
    
    def compute_content_hash(self, content: bytes) -> str:
        """Compute SHA-256 hash of file content."""
        return hashlib.sha256(content).hexdigest()
    
    def _string_similarity(self, a: str, b: str) -> float:
        """Calculate string similarity ratio."""
        if not a or not b:
            return 0.0
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()
    
    def _amount_similarity(self, a: float, b: float, tolerance: float = 0.01) -> float:
        """Calculate amount similarity (1.0 if within tolerance)."""
        if a == 0 and b == 0:
            return 1.0
        if a == 0 or b == 0:
            return 0.0
        
        diff_ratio = abs(a - b) / max(a, b)
        if diff_ratio <= tolerance:
            return 1.0
        elif diff_ratio <= 0.1:
            return 0.8
        elif diff_ratio <= 0.2:
            return 0.5
        return 0.0
    
    def check_hash_duplicate(
        self,
        content_hash: str,
        tenant_id: str,
    ) -> Optional[DuplicateMatch]:
        """
        Check for exact content hash match.
        Returns match if same file was uploaded before.
        """
        key = f"{tenant_id}:{content_hash}"
        
        if key in self._hash_index:
            matches = self._hash_index[key]
            if matches:
                oldest = matches[0]
                return DuplicateMatch(
                    original_id=oldest["document_id"],
                    match_type="exact_hash",
                    confidence=1.0,
                    details={
                        "message": "Exact duplicate file detected",
                        "original_upload_date": oldest["upload_date"],
                    }
                )
        
        return None
    
    def check_vendor_invoice_duplicate(
        self,
        vendor_name: str,
        vendor_id: Optional[str],
        invoice_number: str,
        tenant_id: str,
    ) -> Optional[DuplicateMatch]:
        """
        Check for same invoice number from same vendor.
        """
        if not invoice_number:
            return None
        
        # Build key from vendor identifier
        vendor_key = vendor_id or vendor_name
        if not vendor_key:
            return None
        
        key = f"{tenant_id}:{vendor_key}:{invoice_number}"
        
        if key in self._vendor_index:
            matches = self._vendor_index[key]
            if matches:
                original = matches[0]
                return DuplicateMatch(
                    original_id=original["document_id"],
                    match_type="vendor_invoice_number",
                    confidence=0.95,
                    details={
                        "message": "Same invoice number from same vendor",
                        "vendor": vendor_name,
                        "invoice_number": invoice_number,
                        "original_date": original.get("invoice_date"),
                    }
                )
        
        return None
    
    def check_similar_invoice(
        self,
        vendor_name: str,
        amount: float,
        invoice_date: Optional[datetime],
        tenant_id: str,
    ) -> Optional[DuplicateMatch]:
        """
        Check for similar invoices from same vendor with same amount.
        Useful for catching re-submissions of the same invoice.
        """
        if not vendor_name or amount <= 0:
            return None
        
        # Look for invoices from same vendor in past 7 days
        # This is a simplified version - production should use database queries
        vendor_key = f"{tenant_id}:{vendor_name.lower()}"
        
        if vendor_key in self._vendor_index:
            now = datetime.utcnow()
            for record in self._vendor_index.get(vendor_key, []):
                record_date = record.get("upload_date")
                if record_date:
                    # Skip if older than 7 days
                    if isinstance(record_date, str):
                        record_date = datetime.fromisoformat(record_date)
                    if (now - record_date).days > 7:
                        continue
                
                # Check amount similarity
                record_amount = record.get("amount", 0)
                if self._amount_similarity(amount, record_amount) > 0.95:
                    return DuplicateMatch(
                        original_id=record["document_id"],
                        match_type="similar_amount",
                        confidence=0.7,
                        details={
                            "message": "Similar invoice from same vendor within 7 days",
                            "vendor": vendor_name,
                            "amount": amount,
                            "original_amount": record_amount,
                        }
                    )
        
        return None
    
    def register_document(
        self,
        document_id: str,
        tenant_id: str,
        content_hash: str,
        vendor_name: Optional[str] = None,
        vendor_id: Optional[str] = None,
        invoice_number: Optional[str] = None,
        amount: Optional[float] = None,
    ) -> None:
        """
        Register a document in the duplicate detection index.
        Call after successful upload/validation.
        """
        now = datetime.utcnow().isoformat()
        
        record = {
            "document_id": document_id,
            "upload_date": now,
            "amount": amount,
            "invoice_number": invoice_number,
        }
        
        # Index by hash
        hash_key = f"{tenant_id}:{content_hash}"
        if hash_key not in self._hash_index:
            self._hash_index[hash_key] = []
        self._hash_index[hash_key].append(record)
        
        # Index by vendor + invoice number
        if vendor_name and invoice_number:
            vendor_key = f"{tenant_id}:{vendor_id or vendor_name}:{invoice_number}"
            if vendor_key not in self._vendor_index:
                self._vendor_index[vendor_key] = []
            self._vendor_index[vendor_key].append(record)
        
        # Index by vendor name for similarity checks
        if vendor_name:
            vendor_name_key = f"{tenant_id}:{vendor_name.lower()}"
            if vendor_name_key not in self._vendor_index:
                self._vendor_index[vendor_name_key] = []
            self._vendor_index[vendor_name_key].append(record)
        
        logger.debug("Document registered for duplicate detection", document_id=document_id)
    
    def check_all(
        self,
        content_hash: str,
        tenant_id: str,
        vendor_name: Optional[str] = None,
        vendor_id: Optional[str] = None,
        invoice_number: Optional[str] = None,
        amount: Optional[float] = None,
    ) -> List[DuplicateMatch]:
        """
        Run all duplicate detection checks.
        Returns list of potential matches, sorted by confidence.
        """
        matches = []
        
        # Check exact hash
        hash_match = self.check_hash_duplicate(content_hash, tenant_id)
        if hash_match:
            matches.append(hash_match)
        
        # Check vendor + invoice number
        if vendor_name and invoice_number:
            vendor_match = self.check_vendor_invoice_duplicate(
                vendor_name, vendor_id, invoice_number, tenant_id
            )
            if vendor_match:
                matches.append(vendor_match)
        
        # Check similar amount
        if vendor_name and amount:
            similar_match = self.check_similar_invoice(
                vendor_name, amount, None, tenant_id
            )
            if similar_match:
                matches.append(similar_match)
        
        # Sort by confidence
        matches.sort(key=lambda m: m.confidence, reverse=True)
        
        return matches


# Singleton instance
duplicate_detector = DuplicateDetector()
