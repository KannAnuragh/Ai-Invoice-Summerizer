"""
OCR Engine - Tesseract Integration
==================================
Production OCR implementation using Tesseract with confidence scoring.
"""

import os
import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum
import asyncio
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

# Try to import pytesseract, graceful fallback if not available
try:
    import pytesseract
    from PIL import Image
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    logger.warning("pytesseract not installed, OCR will use mock mode")


class OCRLanguage(str, Enum):
    """Supported OCR languages."""
    ENGLISH = "eng"
    GERMAN = "deu"
    FRENCH = "fra"
    SPANISH = "spa"
    ITALIAN = "ita"
    PORTUGUESE = "por"
    DUTCH = "nld"
    CHINESE_SIMPLIFIED = "chi_sim"
    CHINESE_TRADITIONAL = "chi_tra"
    JAPANESE = "jpn"
    KOREAN = "kor"
    ARABIC = "ara"
    HINDI = "hin"


@dataclass
class BoundingBox:
    """Bounding box for text region."""
    left: int
    top: int
    width: int
    height: int
    
    @property
    def right(self) -> int:
        return self.left + self.width
    
    @property
    def bottom(self) -> int:
        return self.top + self.height
    
    def to_dict(self) -> Dict[str, int]:
        return {
            "left": self.left,
            "top": self.top,
            "width": self.width,
            "height": self.height
        }


@dataclass
class OCRWord:
    """Single word extracted by OCR."""
    text: str
    confidence: float  # 0.0 - 1.0
    bbox: BoundingBox
    line_num: int
    block_num: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "confidence": self.confidence,
            "bbox": self.bbox.to_dict(),
            "line_num": self.line_num,
            "block_num": self.block_num
        }


@dataclass
class OCRLine:
    """Line of text with words."""
    text: str
    words: List[OCRWord]
    confidence: float
    bbox: BoundingBox
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "words": [w.to_dict() for w in self.words],
            "confidence": self.confidence,
            "bbox": self.bbox.to_dict()
        }


@dataclass
class OCRBlock:
    """Block of text (paragraph/section)."""
    lines: List[OCRLine]
    block_type: str  # text, table, image
    confidence: float
    bbox: BoundingBox
    
    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)


@dataclass
class OCRResult:
    """Complete OCR result for a document page."""
    page_num: int
    full_text: str
    blocks: List[OCRBlock]
    words: List[OCRWord]
    overall_confidence: float
    language: str
    processing_time_ms: float
    image_width: int
    image_height: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "page_num": self.page_num,
            "full_text": self.full_text,
            "overall_confidence": self.overall_confidence,
            "language": self.language,
            "processing_time_ms": self.processing_time_ms,
            "word_count": len(self.words),
            "block_count": len(self.blocks),
            "image_dimensions": {
                "width": self.image_width,
                "height": self.image_height
            }
        }


class TesseractOCREngine:
    """
    Production OCR engine using Tesseract.
    
    Features:
    - Multi-language support
    - Word-level confidence scores
    - Bounding box extraction
    - Layout analysis
    """
    
    def __init__(
        self,
        tesseract_cmd: Optional[str] = None,
        default_language: str = "eng",
        psm: int = 3,  # Page segmentation mode: 3 = auto
        oem: int = 3,  # OCR Engine mode: 3 = LSTM only
    ):
        self.default_language = default_language
        self.psm = psm
        self.oem = oem
        
        # Configure Tesseract path if provided
        if tesseract_cmd:
            if TESSERACT_AVAILABLE:
                pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        elif os.getenv("TESSERACT_PATH"):
            if TESSERACT_AVAILABLE:
                pytesseract.pytesseract.tesseract_cmd = os.getenv("TESSERACT_PATH")
        
        self._validate_tesseract()
    
    def _validate_tesseract(self) -> None:
        """Validate Tesseract installation."""
        if not TESSERACT_AVAILABLE:
            logger.warning("Tesseract Python bindings not available")
            return
            
        try:
            version = pytesseract.get_tesseract_version()
            logger.info("Tesseract initialized", version=str(version))
        except Exception as e:
            logger.warning("Tesseract not found", error=str(e))
    
    def _get_tesseract_config(self, language: str) -> str:
        """Build Tesseract configuration string."""
        config_parts = [
            f"--psm {self.psm}",
            f"--oem {self.oem}",
        ]
        return " ".join(config_parts)
    
    async def process_image(
        self,
        image_path: str,
        language: Optional[str] = None,
        page_num: int = 1,
    ) -> OCRResult:
        """
        Process a single image and extract text with confidence scores.
        
        Args:
            image_path: Path to image file
            language: OCR language code (default: eng)
            page_num: Page number for multi-page documents
            
        Returns:
            OCRResult with full text, words, and confidence scores
        """
        import time
        start_time = time.time()
        
        lang = language or self.default_language
        
        if not TESSERACT_AVAILABLE:
            # Return mock result for development
            return self._mock_ocr_result(image_path, page_num, lang)
        
        # Run OCR in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            self._process_image_sync,
            image_path,
            lang,
            page_num,
        )
        
        processing_time = (time.time() - start_time) * 1000
        result.processing_time_ms = processing_time
        
        logger.info(
            "OCR completed",
            page=page_num,
            words=len(result.words),
            confidence=f"{result.overall_confidence:.2%}",
            time_ms=f"{processing_time:.1f}"
        )
        
        return result
    
    def _process_image_sync(
        self,
        image_path: str,
        language: str,
        page_num: int,
    ) -> OCRResult:
        """Synchronous OCR processing."""
        image = Image.open(image_path)
        width, height = image.size
        
        config = self._get_tesseract_config(language)
        
        # Get detailed data with bounding boxes and confidence
        data = pytesseract.image_to_data(
            image,
            lang=language,
            config=config,
            output_type=pytesseract.Output.DICT
        )
        
        # Parse OCR data into structured format
        words = []
        current_line_words = []
        current_line_num = -1
        lines = []
        
        for i in range(len(data["text"])):
            text = data["text"][i].strip()
            conf = data["conf"][i]
            
            # Skip empty or low-confidence results
            if not text or conf == -1:
                continue
            
            # Normalize confidence to 0-1 range
            confidence = max(0, min(conf, 100)) / 100.0
            
            bbox = BoundingBox(
                left=data["left"][i],
                top=data["top"][i],
                width=data["width"][i],
                height=data["height"][i]
            )
            
            word = OCRWord(
                text=text,
                confidence=confidence,
                bbox=bbox,
                line_num=data["line_num"][i],
                block_num=data["block_num"][i]
            )
            words.append(word)
            
            # Group words into lines
            if data["line_num"][i] != current_line_num:
                if current_line_words:
                    lines.append(self._create_line(current_line_words))
                current_line_words = [word]
                current_line_num = data["line_num"][i]
            else:
                current_line_words.append(word)
        
        # Add last line
        if current_line_words:
            lines.append(self._create_line(current_line_words))
        
        # Build full text
        full_text = pytesseract.image_to_string(image, lang=language, config=config)
        
        # Calculate overall confidence
        if words:
            overall_confidence = sum(w.confidence for w in words) / len(words)
        else:
            overall_confidence = 0.0
        
        # Create blocks (simplified - one block for now)
        blocks = []
        if lines:
            block_bbox = BoundingBox(
                left=min(l.bbox.left for l in lines),
                top=min(l.bbox.top for l in lines),
                width=max(l.bbox.right for l in lines) - min(l.bbox.left for l in lines),
                height=max(l.bbox.bottom for l in lines) - min(l.bbox.top for l in lines)
            )
            blocks.append(OCRBlock(
                lines=lines,
                block_type="text",
                confidence=overall_confidence,
                bbox=block_bbox
            ))
        
        return OCRResult(
            page_num=page_num,
            full_text=full_text.strip(),
            blocks=blocks,
            words=words,
            overall_confidence=overall_confidence,
            language=language,
            processing_time_ms=0,  # Will be set by caller
            image_width=width,
            image_height=height
        )
    
    def _create_line(self, words: List[OCRWord]) -> OCRLine:
        """Create an OCRLine from a list of words."""
        text = " ".join(w.text for w in words)
        confidence = sum(w.confidence for w in words) / len(words) if words else 0
        
        bbox = BoundingBox(
            left=min(w.bbox.left for w in words),
            top=min(w.bbox.top for w in words),
            width=max(w.bbox.right for w in words) - min(w.bbox.left for w in words),
            height=max(w.bbox.bottom for w in words) - min(w.bbox.top for w in words)
        )
        
        return OCRLine(
            text=text,
            words=words,
            confidence=confidence,
            bbox=bbox
        )
    
    def _mock_ocr_result(
        self,
        image_path: str,
        page_num: int,
        language: str
    ) -> OCRResult:
        """Generate mock OCR result for development/testing."""
        mock_text = """
INVOICE

Acme Corporation
123 Business Avenue
San Francisco, CA 94102

Invoice Number: INV-2024-0001
Invoice Date: December 22, 2024
Due Date: January 21, 2025

Bill To:
Customer Company Inc.
456 Client Street
New York, NY 10001

Description                    Qty    Unit Price    Total
---------------------------------------------------------
Software License              1      $8,000.00     $8,000.00
Implementation Services       10     $150.00       $1,500.00
Training Hours               5      $200.00       $1,000.00

                              Subtotal:           $10,500.00
                              Tax (16%):          $1,680.00
                              Total Due:          $12,180.00

Payment Terms: NET 30
        """
        
        # Create mock words with high confidence
        words = []
        for i, word in enumerate(mock_text.split()):
            words.append(OCRWord(
                text=word,
                confidence=0.95,
                bbox=BoundingBox(left=10 + (i % 10) * 80, top=10 + (i // 10) * 20, width=70, height=18),
                line_num=i // 10,
                block_num=0
            ))
        
        return OCRResult(
            page_num=page_num,
            full_text=mock_text.strip(),
            blocks=[],
            words=words,
            overall_confidence=0.95,
            language=language,
            processing_time_ms=50.0,
            image_width=2480,
            image_height=3508
        )
    
    async def process_pdf(
        self,
        pdf_path: str,
        language: Optional[str] = None,
    ) -> List[OCRResult]:
        """
        Process a PDF document, converting pages to images and running OCR.
        
        Args:
            pdf_path: Path to PDF file
            language: OCR language code
            
        Returns:
            List of OCRResult, one per page
        """
        try:
            from pdf2image import convert_from_path
        except ImportError:
            logger.error("pdf2image not installed, cannot process PDF")
            return []
        
        # Convert PDF pages to images
        images = convert_from_path(pdf_path, dpi=300)
        
        results = []
        for i, image in enumerate(images):
            # Save temporary image
            temp_path = f"/tmp/ocr_page_{i}.png"
            image.save(temp_path, "PNG")
            
            # Process page
            result = await self.process_image(temp_path, language, page_num=i + 1)
            results.append(result)
            
            # Cleanup
            os.remove(temp_path)
        
        return results


# Singleton instance
_ocr_engine: Optional[TesseractOCREngine] = None


def get_ocr_engine() -> TesseractOCREngine:
    """Get or create OCR engine instance."""
    global _ocr_engine
    if _ocr_engine is None:
        _ocr_engine = TesseractOCREngine()
    return _ocr_engine
