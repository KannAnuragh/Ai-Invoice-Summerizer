"""
Email Webhook Receiver
======================
Webhook endpoint for email services (SendGrid, Mailgun, etc.)
"""

import os
import hashlib
import hmac
from datetime import datetime
from typing import Optional, List, Dict, Any
from base64 import b64decode
import uuid

import structlog
from fastapi import APIRouter, HTTPException, Request, Header, BackgroundTasks
from pydantic import BaseModel

logger = structlog.get_logger(__name__)

router = APIRouter()


# Webhook secrets for verification
SENDGRID_WEBHOOK_SECRET = os.getenv("SENDGRID_WEBHOOK_SECRET", "")
MAILGUN_WEBHOOK_SECRET = os.getenv("MAILGUN_WEBHOOK_SECRET", "")


class EmailWebhookAttachment(BaseModel):
    """Attachment in webhook payload."""
    filename: str
    content_type: str
    content_base64: Optional[str] = None
    size: Optional[int] = None
    url: Optional[str] = None  # For services that provide download URL


class EmailWebhookPayload(BaseModel):
    """Generic email webhook payload."""
    message_id: Optional[str] = None
    from_email: str
    from_name: Optional[str] = None
    to_emails: List[str] = []
    subject: str
    text_body: Optional[str] = None
    html_body: Optional[str] = None
    attachments: List[EmailWebhookAttachment] = []
    received_at: Optional[str] = None
    # Provider-specific
    provider: str = "generic"
    raw_payload: Optional[Dict[str, Any]] = None


class WebhookResponse(BaseModel):
    """Webhook response."""
    status: str
    message: str
    invoices_created: int = 0
    invoice_ids: List[str] = []


def verify_sendgrid_signature(
    payload: bytes,
    signature: str,
    timestamp: str,
) -> bool:
    """Verify SendGrid webhook signature."""
    if not SENDGRID_WEBHOOK_SECRET:
        logger.warning("SendGrid webhook secret not configured")
        return True  # Skip verification in dev
    
    signed_payload = f"{timestamp}{payload.decode()}"
    expected = hmac.new(
        SENDGRID_WEBHOOK_SECRET.encode(),
        signed_payload.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected)


def verify_mailgun_signature(
    timestamp: str,
    token: str,
    signature: str,
) -> bool:
    """Verify Mailgun webhook signature."""
    if not MAILGUN_WEBHOOK_SECRET:
        logger.warning("Mailgun webhook secret not configured")
        return True  # Skip verification in dev
    
    expected = hmac.new(
        MAILGUN_WEBHOOK_SECRET.encode(),
        f"{timestamp}{token}".encode(),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected)


async def process_email_webhook(payload: EmailWebhookPayload) -> List[str]:
    """
    Process webhook payload and create invoices.
    
    Returns list of created invoice IDs.
    """
    invoice_ids = []
    
    # Filter valid attachments
    valid_extensions = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif"}
    
    for attachment in payload.attachments:
        ext = os.path.splitext(attachment.filename)[1].lower()
        if ext not in valid_extensions:
            logger.debug("Skipping attachment", filename=attachment.filename)
            continue
        
        try:
            # Decode content if base64
            content = None
            if attachment.content_base64:
                content = b64decode(attachment.content_base64)
            
            # Import to create invoice
            from routes.invoices import _invoices_db
            
            invoice_id = f"inv-{uuid.uuid4().hex[:8]}"
            invoice_number = f"INV-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
            
            # Detect vendor from email domain
            vendor_name = None
            if "@" in payload.from_email:
                domain = payload.from_email.split("@")[1].lower()
                # Simple vendor detection
                vendor_name = domain.split(".")[0].title()
            
            invoice = {
                "id": invoice_id,
                "document_id": str(uuid.uuid4()),
                "status": "uploaded",
                "vendor": {"name": vendor_name or "Pending Extraction..."},
                "invoice_number": invoice_number,
                "source_type": "email_webhook",
                "source_provider": payload.provider,
                "source_email": payload.from_email,
                "source_subject": payload.subject,
                "source_filename": attachment.filename,
                "source_size": attachment.size or (len(content) if content else 0),
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }
            
            _invoices_db[invoice_id] = invoice
            invoice_ids.append(invoice_id)
            
            logger.info(
                "Invoice created from webhook",
                invoice_id=invoice_id,
                filename=attachment.filename,
                provider=payload.provider
            )
            
            # TODO: Save attachment content and trigger OCR pipeline
            
        except Exception as e:
            logger.error(
                "Failed to process webhook attachment",
                filename=attachment.filename,
                error=str(e)
            )
    
    return invoice_ids


@router.post("/webhooks/email/sendgrid", response_model=WebhookResponse)
async def sendgrid_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_twilio_email_event_webhook_signature: Optional[str] = Header(None),
    x_twilio_email_event_webhook_timestamp: Optional[str] = Header(None),
) -> WebhookResponse:
    """
    SendGrid Inbound Parse webhook endpoint.
    
    Configure at: https://app.sendgrid.com/settings/parse
    """
    body = await request.body()
    
    # Verify signature
    if x_twilio_email_event_webhook_signature and x_twilio_email_event_webhook_timestamp:
        if not verify_sendgrid_signature(
            body,
            x_twilio_email_event_webhook_signature,
            x_twilio_email_event_webhook_timestamp
        ):
            raise HTTPException(status_code=401, detail="Invalid signature")
    
    # Parse form data
    form = await request.form()
    
    # Extract attachments
    attachments = []
    attachment_count = int(form.get("attachments", 0))
    
    for i in range(1, attachment_count + 1):
        attachment_info = form.get(f"attachment-info")
        attachment_file = form.get(f"attachment{i}")
        
        if attachment_file:
            content = await attachment_file.read()
            attachments.append(EmailWebhookAttachment(
                filename=attachment_file.filename,
                content_type=attachment_file.content_type,
                content_base64=content.hex(),  # Store as hex for now
                size=len(content)
            ))
    
    payload = EmailWebhookPayload(
        message_id=form.get("Message-ID"),
        from_email=form.get("from", ""),
        to_emails=[form.get("to", "")],
        subject=form.get("subject", ""),
        text_body=form.get("text"),
        html_body=form.get("html"),
        attachments=attachments,
        provider="sendgrid"
    )
    
    # Process in background
    invoice_ids = await process_email_webhook(payload)
    
    logger.info(
        "SendGrid webhook processed",
        from_email=payload.from_email,
        attachments=len(attachments),
        invoices=len(invoice_ids)
    )
    
    return WebhookResponse(
        status="processed",
        message=f"Created {len(invoice_ids)} invoices",
        invoices_created=len(invoice_ids),
        invoice_ids=invoice_ids
    )


@router.post("/webhooks/email/mailgun", response_model=WebhookResponse)
async def mailgun_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
) -> WebhookResponse:
    """
    Mailgun webhook endpoint for email receiving.
    
    Configure at: https://app.mailgun.com/app/receiving/routes
    """
    form = await request.form()
    
    # Verify signature
    timestamp = form.get("timestamp", "")
    token = form.get("token", "")
    signature = form.get("signature", "")
    
    if signature and not verify_mailgun_signature(timestamp, token, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # Extract attachments
    attachments = []
    attachment_count = int(form.get("attachment-count", 0))
    
    for i in range(1, attachment_count + 1):
        attachment_file = form.get(f"attachment-{i}")
        if attachment_file:
            content = await attachment_file.read()
            attachments.append(EmailWebhookAttachment(
                filename=attachment_file.filename,
                content_type=attachment_file.content_type,
                content_base64=content.hex(),
                size=len(content)
            ))
    
    payload = EmailWebhookPayload(
        message_id=form.get("Message-Id"),
        from_email=form.get("sender", form.get("from", "")),
        to_emails=[form.get("recipient", "")],
        subject=form.get("subject", ""),
        text_body=form.get("body-plain"),
        html_body=form.get("body-html"),
        attachments=attachments,
        provider="mailgun"
    )
    
    # Process
    invoice_ids = await process_email_webhook(payload)
    
    logger.info(
        "Mailgun webhook processed",
        from_email=payload.from_email,
        attachments=len(attachments),
        invoices=len(invoice_ids)
    )
    
    return WebhookResponse(
        status="processed",
        message=f"Created {len(invoice_ids)} invoices",
        invoices_created=len(invoice_ids),
        invoice_ids=invoice_ids
    )


@router.post("/webhooks/email/generic", response_model=WebhookResponse)
async def generic_email_webhook(
    payload: EmailWebhookPayload,
    background_tasks: BackgroundTasks,
) -> WebhookResponse:
    """
    Generic email webhook for custom integrations.
    
    Accepts standardized payload format.
    """
    invoice_ids = await process_email_webhook(payload)
    
    logger.info(
        "Generic webhook processed",
        from_email=payload.from_email,
        attachments=len(payload.attachments),
        invoices=len(invoice_ids)
    )
    
    return WebhookResponse(
        status="processed",
        message=f"Created {len(invoice_ids)} invoices",
        invoices_created=len(invoice_ids),
        invoice_ids=invoice_ids
    )
