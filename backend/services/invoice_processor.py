"""
Invoice Processing Service
===========================
Orchestrates OCR, extraction, and event publishing for uploaded invoices.
"""

import os
import sys
from typing import Dict, Any, Optional
from pathlib import Path
import structlog

# Add paths for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logger = structlog.get_logger(__name__)


class InvoiceProcessor:
    """
    Service that processes uploaded invoices through the complete pipeline:
    1. OCR text extraction
    2. Field extraction
    3. Validation
    4. Event publishing
    """
    
    def __init__(self):
        self.logger = logger.bind(service="InvoiceProcessor")
    
    async def process_invoice(
        self,
        document_id: str,
        invoice_id: str,
        file_path: str,
        filename: str,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process an uploaded invoice document.
        
        Args:
            document_id: Document identifier
            invoice_id: Invoice identifier
            file_path: Path to uploaded file
            filename: Original filename
            correlation_id: Correlation ID for tracking
            
        Returns:
            Extraction results dictionary
        """
        self.logger.info(
            "Starting invoice processing",
            document_id=document_id,
            invoice_id=invoice_id,
            filename=filename
        )
        
        try:
            # Step 1: OCR - Extract text from document
            ocr_result = await self._perform_ocr(file_path, filename)
            
            # Step 2: Field Extraction - Extract structured fields
            extracted_data = await self._extract_fields(ocr_result)
            
            # Step 3: Enrich with metadata
            extracted_data["document_id"] = document_id
            extracted_data["invoice_id"] = invoice_id
            extracted_data["filename"] = filename
            extracted_data["ocr_confidence"] = ocr_result.get("overall_confidence", 0.0)
            extracted_data["processing_status"] = "completed"
            
            # Step 4: Publish INVOICE_PROCESSED event
            await self._publish_processed_event(
                invoice_id=invoice_id,
                document_id=document_id,
                extracted_data=extracted_data,
                correlation_id=correlation_id
            )
            
            self.logger.info(
                "Invoice processing completed",
                invoice_id=invoice_id,
                confidence=extracted_data.get("ocr_confidence")
            )
            
            return extracted_data
            
        except Exception as e:
            self.logger.error(
                "Invoice processing failed",
                invoice_id=invoice_id,
                error=str(e)
            )
            
            # Publish error event
            await self._publish_error_event(invoice_id, str(e))
            
            raise
    
    async def _perform_ocr(self, file_path: str, filename: str) -> Dict[str, Any]:
        """
        Perform OCR on the document.
        
        Args:
            file_path: Path to document file
            filename: Original filename
            
        Returns:
            OCR results dictionary
        """
        try:
            # Import OCR engine
            sys.path.insert(0, os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                'ai-services', 'ocr-service'
            ))
            from ocr_engine import get_ocr_engine
            
            ocr_engine = get_ocr_engine()
            
            # Determine file type
            file_ext = Path(filename).suffix.lower()
            
            if file_ext == '.pdf':
                # Process PDF (multiple pages)
                results = await ocr_engine.process_pdf(file_path)
                
                # Combine results from all pages
                full_text = "\n\n".join(r.full_text for r in results)
                overall_confidence = sum(r.overall_confidence for r in results) / len(results) if results else 0.0
                
                return {
                    "full_text": full_text,
                    "overall_confidence": overall_confidence,
                    "page_count": len(results),
                    "pages": [r.to_dict() for r in results]
                }
            else:
                # Process image (single page)
                result = await ocr_engine.process_image(file_path)
                
                return {
                    "full_text": result.full_text,
                    "overall_confidence": result.overall_confidence,
                    "page_count": 1,
                    "pages": [result.to_dict()]
                }
                
        except Exception as e:
            self.logger.error("OCR failed", error=str(e))
            
            # Return mock/fallback result
            return {
                "full_text": f"[OCR Error: {str(e)}]\nMock invoice text for development",
                "overall_confidence": 0.5,
                "page_count": 1,
                "pages": [],
                "ocr_error": str(e)
            }
    
    async def _extract_fields(self, ocr_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract structured fields from OCR text.
        
        Args:
            ocr_result: OCR results
            
        Returns:
            Extracted fields dictionary
        """
        try:
            # Import field extractor
            sys.path.insert(0, os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                'ai-services', 'extraction-service', 'field_extractors'
            ))
            from extractors import FieldExtractor
            
            extractor = FieldExtractor()
            text = ocr_result.get("full_text", "")
            
            # Extract all fields
            extraction_result = extractor.extract_all(text)
            
            # Build structured response
            extracted = {
                "vendor_name": self._get_field_value(extraction_result.fields, "vendor_name", "Unknown Vendor"),
                "vendor_address": self._get_field_value(extraction_result.fields, "vendor_address"),
                "invoice_number": self._get_field_value(extraction_result.fields, "invoice_number"),
                "invoice_date": self._get_field_value(extraction_result.fields, "invoice_date"),
                "due_date": self._get_field_value(extraction_result.fields, "due_date"),
                "po_number": self._get_field_value(extraction_result.fields, "po_number"),
                "subtotal": self._get_field_value(extraction_result.fields, "subtotal", 0.0),
                "tax_amount": self._get_field_value(extraction_result.fields, "tax_amount", 0.0),
                "total_amount": self._get_field_value(extraction_result.fields, "total_amount", 0.0),
                "currency": self._get_field_value(extraction_result.fields, "currency", "USD"),
                "line_items": self._get_field_value(extraction_result.fields, "line_items", []),
                "payment_terms": self._get_field_value(extraction_result.fields, "payment_terms"),
                "tax_id": self._get_field_value(extraction_result.fields, "tax_id"),
                "extraction_confidence": extraction_result.confidence,
                "extraction_warnings": extraction_result.warnings,
                "raw_text": text
            }
            
            return extracted
            
        except Exception as e:
            self.logger.error("Field extraction failed", error=str(e))
            
            # Return minimal extraction result
            return {
                "vendor_name": "Extraction Error",
                "invoice_number": "ERROR",
                "total_amount": 0.0,
                "currency": "USD",
                "extraction_confidence": 0.0,
                "extraction_error": str(e),
                "raw_text": ocr_result.get("full_text", "")
            }
    
    def _get_field_value(
        self,
        fields: Dict[str, Any],
        field_name: str,
        default: Any = None
    ) -> Any:
        """Get value from extraction fields dict."""
        field = fields.get(field_name)
        if field and hasattr(field, 'value'):
            return field.value
        return default
    
    async def _publish_processed_event(
        self,
        invoice_id: str,
        document_id: str,
        extracted_data: Dict[str, Any],
        correlation_id: Optional[str] = None
    ):
        """
        Publish INVOICE_PROCESSED event to message queue.
        
        Args:
            invoice_id: Invoice identifier
            document_id: Document identifier
            extracted_data: Extracted fields and metadata
            correlation_id: Correlation ID for tracking
        """
        try:
            from shared.event_publishers import publish_invoice_processed
            
            success = await publish_invoice_processed(
                invoice_id=invoice_id,
                extracted_data=extracted_data
            )
            
            if success:
                self.logger.info(
                    "INVOICE_PROCESSED event published",
                    invoice_id=invoice_id,
                    correlation_id=correlation_id or document_id
                )
            else:
                self.logger.warning(
                    "Failed to publish INVOICE_PROCESSED event",
                    invoice_id=invoice_id
                )
                
        except Exception as e:
            self.logger.error(
                "Error publishing INVOICE_PROCESSED event",
                invoice_id=invoice_id,
                error=str(e)
            )
    
    async def _publish_error_event(self, invoice_id: str, error: str):
        """Publish system error event for processing failure."""
        try:
            from shared.event_publishers import publish_system_error
            
            await publish_system_error(
                component="invoice-processor",
                error=f"Invoice processing failed: {error}",
                severity="error",
                details={"invoice_id": invoice_id}
            )
        except Exception as e:
            self.logger.error(
                "Failed to publish error event",
                invoice_id=invoice_id,
                error=str(e)
            )


# Singleton instance
_processor: Optional[InvoiceProcessor] = None


def get_invoice_processor() -> InvoiceProcessor:
    """Get or create invoice processor instance."""
    global _processor
    if _processor is None:
        _processor = InvoiceProcessor()
    return _processor
