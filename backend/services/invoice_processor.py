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
    3. AI Summarization
    4. Validation
    5. Event publishing
    """
    
    def __init__(self):
        self.logger = logger.bind(service="InvoiceProcessor")
        self._summarizer = None
    
    def _get_summarizer(self):
        """Get or initialize the AI summarizer."""
        if self._summarizer is None:
            try:
                project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                summarizer_path = os.path.join(project_root, 'ai-services', 'summarization-service')
                if summarizer_path not in sys.path:
                    sys.path.insert(0, summarizer_path)
                from summarizer import OllamaSummarizer
                # Use qwen2.5 model which is available in Ollama
                self._summarizer = OllamaSummarizer(model="qwen2.5:0.5b")
                self.logger.info("AI Summarizer initialized")
            except Exception as e:
                self.logger.warning("Failed to initialize summarizer", error=str(e))
        return self._summarizer
    
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
            # Step 1: Update status to processing
            await self._update_invoice_status(invoice_id, "processing")
            
            # Step 2: OCR - Extract text from document
            ocr_result = await self._perform_ocr(file_path, filename)
            
            # Step 3: Field Extraction - Extract structured fields
            extracted_data = await self._extract_fields(ocr_result)
            
            # Step 4: Enrich with metadata
            extracted_data["document_id"] = document_id
            extracted_data["invoice_id"] = invoice_id
            extracted_data["filename"] = filename
            extracted_data["ocr_confidence"] = ocr_result.get("overall_confidence", 0.0)
            extracted_data["processing_status"] = "completed"
            
            # Step 5: Generate AI Summary
            summary = await self._generate_summary(extracted_data)
            extracted_data["summary"] = summary
            
            # Step 6: Update database with extracted data and summary
            await self._update_invoice_with_data(invoice_id, extracted_data)
            
            # Step 7: Publish INVOICE_PROCESSED event
            await self._publish_processed_event(
                invoice_id=invoice_id,
                document_id=document_id,
                extracted_data=extracted_data,
                correlation_id=correlation_id
            )
            
            self.logger.info(
                "Invoice processing completed",
                invoice_id=invoice_id,
                confidence=extracted_data.get("ocr_confidence"),
                has_summary=bool(summary)
            )
            
            return extracted_data
            
        except Exception as e:
            self.logger.error(
                "Invoice processing failed",
                invoice_id=invoice_id,
                error=str(e)
            )
            
            # Update status to error
            await self._update_invoice_status(invoice_id, "uploaded")
            
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
            # Import OCR engine - go to project root then into ai-services
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            ocr_path = os.path.join(project_root, 'ai-services', 'ocr-service')
            if ocr_path not in sys.path:
                sys.path.insert(0, ocr_path)
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
            # Import field extractor - go to project root then into ai-services
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            extractor_path = os.path.join(project_root, 'ai-services', 'extraction-service', 'field_extractors')
            if extractor_path not in sys.path:
                sys.path.insert(0, extractor_path)
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
    
    async def _generate_summary(self, extracted_data: Dict[str, Any]) -> str:
        """
        Generate an AI summary of the invoice using Ollama.
        
        Args:
            extracted_data: Extracted invoice fields
            
        Returns:
            Summary string
        """
        try:
            summarizer = self._get_summarizer()
            if not summarizer:
                return self._generate_fallback_summary(extracted_data)
            
            # Prepare invoice data for summarization
            invoice_data = {
                "vendor": {"name": extracted_data.get("vendor_name", "Unknown")},
                "invoice_number": extracted_data.get("invoice_number", "N/A"),
                "invoice_date": extracted_data.get("invoice_date", "N/A"),
                "due_date": extracted_data.get("due_date", "N/A"),
                "total_amount": extracted_data.get("total_amount", 0),
                "subtotal": extracted_data.get("subtotal", 0),
                "tax_amount": extracted_data.get("tax_amount", 0),
                "currency": extracted_data.get("currency", "USD"),
                "line_items": extracted_data.get("line_items", []),
                "po_number": extracted_data.get("po_number"),
                "payment_terms": extracted_data.get("payment_terms"),
            }
            
            system_prompt = """You are an AI assistant that summarizes invoices concisely for business users.
Focus on: vendor name, total amount, due date, key line items, and any notable information.
Keep summaries brief (2-4 sentences). Use professional language."""
            
            user_prompt = f"""Summarize this invoice:

Vendor: {invoice_data['vendor']['name']}
Invoice Number: {invoice_data['invoice_number']}
Date: {invoice_data['invoice_date']}
Due Date: {invoice_data['due_date']}
Total: {invoice_data['currency']} {invoice_data['total_amount']:,.2f}
Tax: {invoice_data['currency']} {invoice_data['tax_amount']:,.2f}
Line Items: {len(invoice_data['line_items'])} items
PO Number: {invoice_data.get('po_number', 'N/A')}
Payment Terms: {invoice_data.get('payment_terms', 'N/A')}

Provide a concise business summary."""
            
            result = summarizer.summarize(
                invoice_data=invoice_data,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=200,
            )
            
            if result.success:
                self.logger.info("AI summary generated", confidence=result.confidence)
                return result.summary
            else:
                self.logger.warning("AI summary failed", error=result.error)
                return self._generate_fallback_summary(extracted_data)
                
        except Exception as e:
            self.logger.error("Summary generation failed", error=str(e))
            return self._generate_fallback_summary(extracted_data)
    
    def _generate_fallback_summary(self, extracted_data: Dict[str, Any]) -> str:
        """Generate a template-based summary when AI is unavailable."""
        vendor = extracted_data.get("vendor_name", "Unknown Vendor")
        invoice_num = extracted_data.get("invoice_number", "N/A")
        total = extracted_data.get("total_amount", 0)
        currency = extracted_data.get("currency", "USD")
        due_date = extracted_data.get("due_date", "N/A")
        line_items = extracted_data.get("line_items", [])
        
        return f"Invoice {invoice_num} from {vendor} for {currency} {total:,.2f}. Due: {due_date}. Contains {len(line_items)} line items."
    
    async def _update_invoice_status(self, invoice_id: str, status: str):
        """Update invoice status in database."""
        try:
            sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
            from shared.database import get_async_session
            from shared.db_models import Invoice as DBInvoice, InvoiceStatus
            from sqlalchemy import select
            
            async with get_async_session() as db:
                query = select(DBInvoice).where(DBInvoice.id == invoice_id)
                result = await db.execute(query)
                db_invoice = result.scalar_one_or_none()
                
                if db_invoice:
                    if status == "processing":
                        db_invoice.status = InvoiceStatus.PROCESSING
                    elif status == "extracted":
                        db_invoice.status = InvoiceStatus.EXTRACTED
                    elif status == "uploaded":
                        db_invoice.status = InvoiceStatus.UPLOADED
                    
                    await db.commit()
                    self.logger.info("Invoice status updated", invoice_id=invoice_id, status=status)
        except Exception as e:
            self.logger.error("Failed to update invoice status", invoice_id=invoice_id, error=str(e))
    
    async def _update_invoice_with_data(self, invoice_id: str, extracted_data: Dict[str, Any]):
        """Update invoice with extracted data in database."""
        try:
            from datetime import datetime
            sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
            from shared.database import get_async_session
            from shared.db_models import Invoice as DBInvoice, InvoiceStatus
            from sqlalchemy import select
            
            async with get_async_session() as db:
                query = select(DBInvoice).where(DBInvoice.id == invoice_id)
                result = await db.execute(query)
                db_invoice = result.scalar_one_or_none()
                
                if db_invoice:
                    # Update status
                    db_invoice.status = InvoiceStatus.EXTRACTED
                    
                    # Update vendor info
                    db_invoice.vendor_name = extracted_data.get("vendor_name")
                    db_invoice.vendor_address = extracted_data.get("vendor_address")
                    
                    # Update invoice details
                    if extracted_data.get("invoice_number"):
                        db_invoice.invoice_number = extracted_data["invoice_number"]
                    
                    # Parse and set dates
                    if extracted_data.get("invoice_date"):
                        try:
                            if isinstance(extracted_data["invoice_date"], str):
                                db_invoice.invoice_date = datetime.fromisoformat(extracted_data["invoice_date"])
                            elif isinstance(extracted_data["invoice_date"], datetime):
                                db_invoice.invoice_date = extracted_data["invoice_date"]
                        except:
                            pass
                    
                    if extracted_data.get("due_date"):
                        try:
                            if isinstance(extracted_data["due_date"], str):
                                db_invoice.due_date = datetime.fromisoformat(extracted_data["due_date"])
                            elif isinstance(extracted_data["due_date"], datetime):
                                db_invoice.due_date = extracted_data["due_date"]
                        except:
                            pass
                    
                    # Update financial data
                    db_invoice.subtotal = extracted_data.get("subtotal")
                    db_invoice.tax_amount = extracted_data.get("tax_amount")
                    db_invoice.total_amount = extracted_data.get("total_amount")
                    db_invoice.currency = extracted_data.get("currency", "USD")
                    
                    # Update additional fields
                    db_invoice.po_number = extracted_data.get("po_number")
                    db_invoice.payment_terms = extracted_data.get("payment_terms")
                    db_invoice.line_items = extracted_data.get("line_items", [])
                    
                    # Update AI summary
                    if extracted_data.get("summary"):
                        db_invoice.summary = extracted_data["summary"]
                    
                    # Update confidence score
                    db_invoice.confidence = extracted_data.get("extraction_confidence")
                    
                    await db.commit()
                    
                    self.logger.info(
                        "Invoice updated with extracted data",
                        invoice_id=invoice_id,
                        vendor=extracted_data.get("vendor_name"),
                        total=extracted_data.get("total_amount"),
                        has_summary=bool(extracted_data.get("summary"))
                    )
                else:
                    self.logger.warning("Invoice not found for update", invoice_id=invoice_id)
                    
        except Exception as e:
            self.logger.error(
                "Failed to update invoice with extracted data",
                invoice_id=invoice_id,
                error=str(e)
            )
    
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
