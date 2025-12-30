"""
Data Normalization
==================
Standardizes extracted data for consistency.
"""

import re
from typing import Optional, Any
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
import structlog

logger = structlog.get_logger(__name__)


class CurrencyNormalizer:
    """Normalize currency values."""
    
    # Currency symbol mapping
    SYMBOLS = {
        "$": "USD",
        "€": "EUR",
        "£": "GBP",
        "₹": "INR",
        "¥": "JPY",
        "₩": "KRW",
        "₽": "RUB",
        "R$": "BRL",
        "C$": "CAD",
        "A$": "AUD",
    }
    
    @staticmethod
    def normalize_amount(value: Any) -> Optional[Decimal]:
        """
        Convert various amount formats to Decimal.
        
        Handles:
        - "1,234.56" -> 1234.56
        - "1.234,56" (European) -> 1234.56
        - "$1,234.56" -> 1234.56
        """
        if value is None:
            return None
        
        if isinstance(value, (int, float, Decimal)):
            return Decimal(str(value))
        
        # Remove currency symbols
        cleaned = re.sub(r"[^\d.,\-]", "", str(value))
        
        if not cleaned:
            return None
        
        # Detect format (European vs US)
        # If last separator is comma and has 2 digits after, it's decimal
        if re.match(r".*,\d{2}$", cleaned):
            # European format: 1.234,56
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            # US format: 1,234.56
            cleaned = cleaned.replace(",", "")
        
        try:
            return Decimal(cleaned)
        except InvalidOperation:
            logger.warning("Could not normalize amount", value=value)
            return None
    
    @classmethod
    def detect_currency(cls, text: str) -> str:
        """Detect currency from text."""
        text_upper = text.upper()
        
        # Check for currency codes
        for code in ["USD", "EUR", "GBP", "INR", "JPY", "CAD", "AUD"]:
            if code in text_upper:
                return code
        
        # Check for symbols
        for symbol, code in cls.SYMBOLS.items():
            if symbol in text:
                return code
        
        return "USD"  # Default


class DateNormalizer:
    """Normalize date values."""
    
    # Common date formats
    FORMATS = [
        "%m/%d/%Y",      # 01/31/2024
        "%d/%m/%Y",      # 31/01/2024
        "%Y-%m-%d",      # 2024-01-31
        "%m-%d-%Y",      # 01-31-2024
        "%d-%m-%Y",      # 31-01-2024
        "%B %d, %Y",     # January 31, 2024
        "%b %d, %Y",     # Jan 31, 2024
        "%d %B %Y",      # 31 January 2024
        "%d %b %Y",      # 31 Jan 2024
        "%m/%d/%y",      # 01/31/24
        "%d/%m/%y",      # 31/01/24
    ]
    
    @classmethod
    def normalize(cls, value: Any) -> Optional[date]:
        """
        Convert various date formats to date object.
        """
        if value is None:
            return None
        
        if isinstance(value, datetime):
            return value.date()
        
        if isinstance(value, date):
            return value
        
        date_str = str(value).strip()
        
        for fmt in cls.FORMATS:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        
        logger.warning("Could not parse date", value=value)
        return None
    
    @staticmethod
    def to_iso(d: Optional[date]) -> Optional[str]:
        """Convert date to ISO format string."""
        if d is None:
            return None
        return d.isoformat()


class TextNormalizer:
    """Normalize text values."""
    
    @staticmethod
    def clean_whitespace(text: str) -> str:
        """Normalize whitespace in text."""
        return " ".join(text.split())
    
    @staticmethod
    def normalize_company_name(name: str) -> str:
        """
        Normalize company name for matching.
        
        - Removes common suffixes (Inc., LLC, Ltd, etc.)
        - Converts to uppercase
        - Removes punctuation
        """
        if not name:
            return ""
        
        name = name.upper()
        
        # Remove common suffixes
        suffixes = [
            r"\s+INC\.?$",
            r"\s+LLC\.?$",
            r"\s+LTD\.?$",
            r"\s+LIMITED$",
            r"\s+CORP\.?$",
            r"\s+CORPORATION$",
            r"\s+CO\.?$",
            r"\s+COMPANY$",
            r"\s+PVT\.?$",
            r"\s+PRIVATE$",
        ]
        
        for suffix in suffixes:
            name = re.sub(suffix, "", name)
        
        # Remove punctuation
        name = re.sub(r"[^\w\s]", "", name)
        
        return " ".join(name.split())
    
    @staticmethod
    def extract_address_parts(address: str) -> dict:
        """
        Parse address into components.
        This is a simplified parser - production should use
        a proper address parsing library.
        """
        parts = {
            "street": None,
            "city": None,
            "state": None,
            "postal_code": None,
            "country": None,
        }
        
        # Extract postal code (US ZIP or similar)
        zip_match = re.search(r"\b(\d{5}(?:-\d{4})?)\b", address)
        if zip_match:
            parts["postal_code"] = zip_match.group(1)
        
        return parts


class DataNormalizer:
    """Combined normalizer for invoice data."""
    
    def __init__(self):
        self.currency = CurrencyNormalizer()
        self.date = DateNormalizer()
        self.text = TextNormalizer()
    
    def normalize_invoice_data(self, raw_data: dict) -> dict:
        """
        Normalize all invoice data fields.
        
        Args:
            raw_data: Dictionary of extracted fields
            
        Returns:
            Normalized dictionary
        """
        normalized = {}
        
        # Amounts
        for field in ["subtotal", "tax_amount", "total_amount", "discount_amount"]:
            if field in raw_data:
                normalized[field] = self.currency.normalize_amount(raw_data[field])
        
        # Dates
        for field in ["invoice_date", "due_date", "delivery_date"]:
            if field in raw_data:
                normalized[field] = self.date.to_iso(
                    self.date.normalize(raw_data[field])
                )
        
        # Text fields
        for field in ["invoice_number", "po_number", "vendor_name"]:
            if field in raw_data:
                normalized[field] = self.text.clean_whitespace(str(raw_data[field]))
        
        # Currency
        if "currency" not in normalized and "total_amount" in raw_data:
            normalized["currency"] = self.currency.detect_currency(
                str(raw_data.get("total_amount", ""))
            )
        
        return normalized


# Default normalizer instance
data_normalizer = DataNormalizer()
