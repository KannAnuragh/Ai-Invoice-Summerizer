"""
Upload Routes
=============
Handles invoice file uploads with validation and storage.
"""

import os
import uuid
import hashlib
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
import structlog
import aiofiles
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from shared.database import get_db

logger = structlog.get_logger(__name__)

router = APIRouter()

# Allowed file types and size limits
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")


class UploadResponse(BaseModel):
    """Response model for file upload."""
    document_id: str
    invoice_id: str
    filename: str
    content_type: str
    size: int
    hash: str
    status: str
    message: str


class UploadError(BaseModel):
    """Error response for upload failures."""
    error: str
    detail: str


def validate_file_extension(filename: str) -> bool:
    """Check if file extension is allowed."""
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_EXTENSIONS


def compute_file_hash(content: bytes) -> str:
    """Compute SHA-256 hash for duplicate detection."""
    return hashlib.sha256(content).hexdigest()


async def save_file_async(path: str, content: bytes) -> None:
    """Save file content asynchronously."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    async with aiofiles.open(path, "wb") as f:
        await f.write(content)


async def create_invoice_record(document_id: str, filename: str, file_size: int, file_hash: str, db) -> dict:
    """Create a new invoice record in the database."""
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from shared.db_models import Invoice as DBInvoice, InvoiceStatus
    
    invoice_id = f"inv-{uuid.uuid4().hex[:8]}"
    invoice_number = f"INV-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
    
    db_invoice = DBInvoice(
        id=invoice_id,
        document_id=document_id,
        status=InvoiceStatus.UPLOADED,
        vendor_name="Pending Extraction...",
        invoice_number=invoice_number,
        currency="USD",
        line_items=[],
        anomalies=[],
        source_filename=filename,
        source_size=file_size,
        file_hash=file_hash,
    )
    
    db.add(db_invoice)
    await db.commit()
    await db.refresh(db_invoice)
    
    return {
        "id": db_invoice.id,
        "document_id": db_invoice.document_id,
        "status": db_invoice.status.value,
        "invoice_number": db_invoice.invoice_number,
        "created_at": db_invoice.created_at.isoformat() if db_invoice.created_at else None,
    }


@router.post("/invoices/upload", response_model=UploadResponse)
async def upload_invoice(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    vendor_id: Optional[str] = None,
    notes: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> UploadResponse:
    """
    Upload an invoice document for processing.
    
    Accepts PDF, PNG, JPG, JPEG, TIFF files up to 50MB.
    Returns a document_id for tracking the processing status.
    """
    # Validate file extension
    if not validate_file_extension(file.filename or ""):
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Accepted: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Read file content
    content = await file.read()
    file_size = len(content)
    
    # Validate file size
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB"
        )
    
    if file_size == 0:
        raise HTTPException(status_code=400, detail="Empty file not allowed")
    
    # Generate document ID and compute hash
    document_id = str(uuid.uuid4())
    file_hash = compute_file_hash(content)
    
    # Determine storage path
    date_prefix = datetime.utcnow().strftime("%Y/%m/%d")
    ext = os.path.splitext(file.filename or "document")[1].lower()
    storage_path = os.path.join(UPLOAD_DIR, date_prefix, f"{document_id}{ext}")
    
    # Save file asynchronously
    await save_file_async(storage_path, content)
    
    # Create invoice record
    invoice = await create_invoice_record(document_id, file.filename or "unknown", file_size, file_hash, db)
    
    logger.info(
        "Invoice uploaded successfully",
        document_id=document_id,
        invoice_id=invoice["id"],
        filename=file.filename,
        size=file_size,
        hash=file_hash[:16],
        vendor_id=vendor_id,
    )
    
    # Trigger invoice processing in background
    async def process_invoice_task():
        """Background task to process invoice"""
        try:
            # Import processor
            import sys
            import os
            sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'services'))
            from invoice_processor import get_invoice_processor
            
            processor = get_invoice_processor()
            
            # Process the invoice
            await processor.process_invoice(
                document_id=document_id,
                invoice_id=invoice["id"],
                file_path=storage_path,
                filename=file.filename or "unknown",
                correlation_id=document_id
            )
            logger.info("Invoice processing completed", invoice_id=invoice["id"])
        except Exception as e:
            logger.error("Invoice processing failed", invoice_id=invoice["id"], error=str(e))
    
    # Schedule the background task
    background_tasks.add_task(process_invoice_task)
    logger.info("Invoice processing scheduled", invoice_id=invoice["id"])
    
    # Also publish to message queue (if available)
    try:
        from shared.message_queue import get_message_queue, Message, EventType, MessagePriority
        
        queue = get_message_queue()
        if queue:
            await queue.publish(Message(
                event_type=EventType.INVOICE_UPLOADED,
                data={
                    "document_id": document_id,
                    "invoice_id": invoice["id"],
                    "filename": file.filename,
                    "size": file_size,
                    "hash": file_hash,
                    "storage_path": storage_path,
                    "vendor_id": vendor_id,
                    "notes": notes
                },
                priority=MessagePriority.HIGH,
                correlation_id=document_id
            ))
            logger.info("Invoice upload event published", invoice_id=invoice["id"])
    except Exception as e:
        logger.warning("Failed to publish upload event", error=str(e))
    
    return UploadResponse(
        document_id=document_id,
        invoice_id=invoice["id"],
        filename=file.filename or "unknown",
        content_type=file.content_type or "application/octet-stream",
        size=file_size,
        hash=file_hash,
        status="uploaded",
        message="Invoice uploaded successfully. Processing will begin shortly."
    )


@router.post("/invoices/upload/batch")
async def upload_batch(
    files: list[UploadFile] = File(...),
) -> dict:
    """
    Upload multiple invoice documents in a single request.
    Maximum 20 files per batch.
    """
    if len(files) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 files per batch")
    
    results = []
    for file in files:
        try:
            # Reuse single upload logic
            if not validate_file_extension(file.filename or ""):
                results.append({
                    "filename": file.filename,
                    "status": "failed",
                    "error": "Invalid file type"
                })
                continue
                
            content = await file.read()
            file_size = len(content)
            
            if file_size > MAX_FILE_SIZE or file_size == 0:
                results.append({
                    "filename": file.filename,
                    "status": "failed",
                    "error": "Invalid file size"
                })
                continue
            
            document_id = str(uuid.uuid4())
            file_hash = compute_file_hash(content)
            date_prefix = datetime.utcnow().strftime("%Y/%m/%d")
            ext = os.path.splitext(file.filename or "document")[1].lower()
            storage_path = os.path.join(UPLOAD_DIR, date_prefix, f"{document_id}{ext}")
            
            await save_file_async(storage_path, content)
            
            # Create invoice record
            invoice = create_invoice_record(document_id, file.filename or "unknown", file_size)
            
            results.append({
                "filename": file.filename,
                "document_id": document_id,
                "invoice_id": invoice["id"],
                "status": "uploaded",
                "hash": file_hash
            })
            
        except Exception as e:
            logger.error("Batch upload error", filename=file.filename, error=str(e))
            results.append({
                "filename": file.filename,
                "status": "failed",
                "error": str(e)
            })
    
    return {
        "total": len(files),
        "successful": sum(1 for r in results if r.get("status") == "uploaded"),
        "failed": sum(1 for r in results if r.get("status") == "failed"),
        "results": results
    }
