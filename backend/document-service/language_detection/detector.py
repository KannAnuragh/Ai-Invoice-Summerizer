"""
Language Detection
==================
Detects the language of invoice documents for proper OCR and processing.
"""

from typing import Optional, List, Tuple
from dataclasses import dataclass
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class LanguageDetectionResult:
    """Result of language detection."""
    primary_language: str  # ISO 639-1 code (en, es, de, etc.)
    confidence: float
    secondary_languages: List[Tuple[str, float]]
    ocr_language_code: str  # Tesseract language code


# Mapping from ISO 639-1 to Tesseract language codes
ISO_TO_TESSERACT = {
    "en": "eng",
    "es": "spa",
    "de": "deu",
    "fr": "fra",
    "it": "ita",
    "pt": "por",
    "nl": "nld",
    "pl": "pol",
    "ru": "rus",
    "ja": "jpn",
    "zh": "chi_sim",
    "ko": "kor",
    "ar": "ara",
    "hi": "hin",
    "th": "tha",
    "vi": "vie",
}

# Common words for language detection
LANGUAGE_INDICATORS = {
    "en": ["invoice", "total", "amount", "date", "payment", "due", "bill", "tax"],
    "es": ["factura", "total", "importe", "fecha", "pago", "vencimiento", "iva"],
    "de": ["rechnung", "gesamt", "betrag", "datum", "zahlung", "fällig", "mwst"],
    "fr": ["facture", "total", "montant", "date", "paiement", "échéance", "tva"],
    "it": ["fattura", "totale", "importo", "data", "pagamento", "scadenza", "iva"],
    "pt": ["fatura", "total", "valor", "data", "pagamento", "vencimento", "iva"],
}


class LanguageDetector:
    """
    Detects language of document text.
    
    Uses keyword matching and character analysis.
    In production, could use libraries like langdetect or fasttext.
    """
    
    def __init__(self, default_language: str = "en"):
        self.default_language = default_language
    
    def detect(self, text: str) -> LanguageDetectionResult:
        """
        Detect language from text content.
        
        Args:
            text: Extracted text from document
            
        Returns:
            LanguageDetectionResult with detected language
        """
        if not text or len(text.strip()) < 20:
            return LanguageDetectionResult(
                primary_language=self.default_language,
                confidence=0.0,
                secondary_languages=[],
                ocr_language_code=ISO_TO_TESSERACT.get(self.default_language, "eng")
            )
        
        text_lower = text.lower()
        scores = {}
        
        for lang, keywords in LANGUAGE_INDICATORS.items():
            matches = sum(1 for kw in keywords if kw in text_lower)
            if matches > 0:
                scores[lang] = matches / len(keywords)
        
        if not scores:
            return LanguageDetectionResult(
                primary_language=self.default_language,
                confidence=0.1,
                secondary_languages=[],
                ocr_language_code=ISO_TO_TESSERACT.get(self.default_language, "eng")
            )
        
        sorted_langs = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        primary = sorted_langs[0]
        
        return LanguageDetectionResult(
            primary_language=primary[0],
            confidence=primary[1],
            secondary_languages=sorted_langs[1:3],
            ocr_language_code=ISO_TO_TESSERACT.get(primary[0], "eng")
        )
    
    def get_ocr_languages(self, lang_result: LanguageDetectionResult) -> str:
        """
        Get Tesseract language string for OCR.
        
        Returns combined language codes for multi-language documents.
        Example: "eng+deu" for English+German
        """
        languages = [lang_result.ocr_language_code]
        
        # Add secondary languages if confidence is reasonable
        for lang, conf in lang_result.secondary_languages:
            if conf > 0.3:
                tesseract_code = ISO_TO_TESSERACT.get(lang)
                if tesseract_code and tesseract_code not in languages:
                    languages.append(tesseract_code)
        
        return "+".join(languages[:3])  # Max 3 languages


# Default detector instance
language_detector = LanguageDetector()
