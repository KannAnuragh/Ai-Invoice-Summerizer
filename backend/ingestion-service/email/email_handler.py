"""
Email Ingestion Handler
=======================
IMAP-based email polling for invoice attachment extraction.
"""

import os
import email
import imaplib
import asyncio
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from email.header import decode_header
import mimetypes

import structlog

logger = structlog.get_logger(__name__)


# Configuration
IMAP_HOST = os.getenv("IMAP_HOST", "imap.gmail.com")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
IMAP_USER = os.getenv("IMAP_USER", "")
IMAP_PASSWORD = os.getenv("IMAP_PASSWORD", "")
IMAP_FOLDER = os.getenv("IMAP_FOLDER", "INBOX")
IMAP_PROCESSED_FOLDER = os.getenv("IMAP_PROCESSED_FOLDER", "Processed")

# Allowed attachment types
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif"}
MAX_ATTACHMENT_SIZE = 50 * 1024 * 1024  # 50MB


@dataclass
class EmailAttachment:
    """Extracted email attachment."""
    filename: str
    content_type: str
    content: bytes
    size: int


@dataclass
class ParsedEmail:
    """Parsed email with metadata and attachments."""
    message_id: str
    from_address: str
    from_name: Optional[str]
    to_addresses: List[str]
    subject: str
    date: datetime
    body_text: Optional[str]
    body_html: Optional[str]
    attachments: List[EmailAttachment]
    raw_headers: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "from_address": self.from_address,
            "from_name": self.from_name,
            "to_addresses": self.to_addresses,
            "subject": self.subject,
            "date": self.date.isoformat(),
            "attachment_count": len(self.attachments),
            "attachments": [
                {"filename": a.filename, "size": a.size, "content_type": a.content_type}
                for a in self.attachments
            ]
        }


@dataclass 
class IngestionResult:
    """Result of email ingestion."""
    email_id: str
    message_id: str
    from_address: str
    subject: str
    processed_attachments: List[Dict[str, Any]]
    skipped_attachments: List[Dict[str, str]]
    vendor_detected: Optional[str]
    status: str
    error: Optional[str] = None


class EmailHandler:
    """
    IMAP email handler for invoice ingestion.
    
    Features:
    - IMAP SSL connection
    - Attachment extraction with type filtering
    - Vendor detection from sender
    - Automatic email organization (move to processed folder)
    """
    
    def __init__(
        self,
        host: str = IMAP_HOST,
        port: int = IMAP_PORT,
        username: str = IMAP_USER,
        password: str = IMAP_PASSWORD,
        folder: str = IMAP_FOLDER,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.folder = folder
        self._connection: Optional[imaplib.IMAP4_SSL] = None
    
    def connect(self) -> None:
        """Establish IMAP connection."""
        if not self.username or not self.password:
            raise ValueError("IMAP credentials not configured")
        
        self._connection = imaplib.IMAP4_SSL(self.host, self.port)
        self._connection.login(self.username, self.password)
        self._connection.select(self.folder)
        
        logger.info("IMAP connected", host=self.host, folder=self.folder)
    
    def disconnect(self) -> None:
        """Close IMAP connection."""
        if self._connection:
            try:
                self._connection.close()
                self._connection.logout()
            except Exception:
                pass
            self._connection = None
    
    def _decode_header_value(self, value: str) -> str:
        """Decode MIME-encoded header value."""
        if not value:
            return ""
        
        decoded_parts = decode_header(value)
        result = []
        
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                result.append(part.decode(encoding or "utf-8", errors="replace"))
            else:
                result.append(part)
        
        return " ".join(result)
    
    def _parse_email_address(self, addr_str: str) -> Tuple[Optional[str], str]:
        """Parse email address into name and address."""
        if not addr_str:
            return None, ""
        
        addr_str = self._decode_header_value(addr_str)
        
        # Simple parsing (use email.utils.parseaddr for production)
        if "<" in addr_str and ">" in addr_str:
            name = addr_str.split("<")[0].strip().strip('"')
            address = addr_str.split("<")[1].split(">")[0].strip()
            return name if name else None, address
        
        return None, addr_str.strip()
    
    def _extract_body(self, msg: email.message.Message) -> Tuple[Optional[str], Optional[str]]:
        """Extract text and HTML body from email."""
        text_body = None
        html_body = None
        
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))
                
                # Skip attachments
                if "attachment" in content_disposition:
                    continue
                
                if content_type == "text/plain" and not text_body:
                    try:
                        text_body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                    except Exception:
                        pass
                elif content_type == "text/html" and not html_body:
                    try:
                        html_body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                    except Exception:
                        pass
        else:
            content_type = msg.get_content_type()
            try:
                payload = msg.get_payload(decode=True)
                if payload:
                    decoded = payload.decode("utf-8", errors="replace")
                    if content_type == "text/html":
                        html_body = decoded
                    else:
                        text_body = decoded
            except Exception:
                pass
        
        return text_body, html_body
    
    def _extract_attachments(self, msg: email.message.Message) -> List[EmailAttachment]:
        """Extract invoice attachments from email."""
        attachments = []
        
        for part in msg.walk():
            content_disposition = str(part.get("Content-Disposition", ""))
            
            if "attachment" not in content_disposition and "inline" not in content_disposition:
                # Check if it's a file part anyway
                filename = part.get_filename()
                if not filename:
                    continue
            
            filename = part.get_filename()
            if not filename:
                continue
            
            filename = self._decode_header_value(filename)
            
            # Check extension
            ext = os.path.splitext(filename)[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                logger.debug("Skipping attachment", filename=filename, reason="invalid_extension")
                continue
            
            # Get content
            try:
                content = part.get_payload(decode=True)
                if not content:
                    continue
                
                if len(content) > MAX_ATTACHMENT_SIZE:
                    logger.warning("Attachment too large", filename=filename, size=len(content))
                    continue
                
                content_type = part.get_content_type() or mimetypes.guess_type(filename)[0] or "application/octet-stream"
                
                attachments.append(EmailAttachment(
                    filename=filename,
                    content_type=content_type,
                    content=content,
                    size=len(content)
                ))
                
                logger.debug("Attachment extracted", filename=filename, size=len(content))
                
            except Exception as e:
                logger.error("Failed to extract attachment", filename=filename, error=str(e))
        
        return attachments
    
    def parse_email(self, raw_email: bytes) -> ParsedEmail:
        """Parse raw email bytes into structured format."""
        msg = email.message_from_bytes(raw_email)
        
        # Parse headers
        message_id = msg.get("Message-ID", "")
        from_name, from_address = self._parse_email_address(msg.get("From", ""))
        to_addresses = [self._parse_email_address(addr)[1] for addr in msg.get("To", "").split(",")]
        subject = self._decode_header_value(msg.get("Subject", ""))
        
        # Parse date
        date_str = msg.get("Date", "")
        try:
            from email.utils import parsedate_to_datetime
            date = parsedate_to_datetime(date_str)
        except Exception:
            date = datetime.utcnow()
        
        # Extract body and attachments
        text_body, html_body = self._extract_body(msg)
        attachments = self._extract_attachments(msg)
        
        return ParsedEmail(
            message_id=message_id,
            from_address=from_address,
            from_name=from_name,
            to_addresses=to_addresses,
            subject=subject,
            date=date,
            body_text=text_body,
            body_html=html_body,
            attachments=attachments
        )
    
    def fetch_unread_emails(self, limit: int = 50) -> List[Tuple[str, ParsedEmail]]:
        """
        Fetch unread emails with invoice attachments.
        
        Returns list of (email_uid, parsed_email) tuples.
        """
        if not self._connection:
            self.connect()
        
        # Search for unread emails
        status, messages = self._connection.search(None, "UNSEEN")
        if status != "OK":
            logger.error("IMAP search failed", status=status)
            return []
        
        email_ids = messages[0].split()
        
        if not email_ids:
            return []
        
        # Limit number of emails to process
        email_ids = email_ids[:limit]
        
        results = []
        
        for email_id in email_ids:
            try:
                # Fetch email
                status, data = self._connection.fetch(email_id, "(RFC822)")
                if status != "OK":
                    continue
                
                raw_email = data[0][1]
                parsed = self.parse_email(raw_email)
                
                # Only include emails with valid attachments
                if parsed.attachments:
                    results.append((email_id.decode(), parsed))
                    logger.info(
                        "Email fetched",
                        message_id=parsed.message_id[:20],
                        from_addr=parsed.from_address,
                        attachments=len(parsed.attachments)
                    )
            
            except Exception as e:
                logger.error("Failed to fetch email", email_id=email_id, error=str(e))
        
        return results
    
    def mark_as_read(self, email_uid: str) -> None:
        """Mark email as read."""
        if self._connection:
            self._connection.store(email_uid.encode(), "+FLAGS", "\\Seen")
    
    def move_to_processed(self, email_uid: str) -> None:
        """Move email to processed folder."""
        if not self._connection:
            return
        
        try:
            # Copy to processed folder
            self._connection.copy(email_uid.encode(), IMAP_PROCESSED_FOLDER)
            # Mark for deletion from inbox
            self._connection.store(email_uid.encode(), "+FLAGS", "\\Deleted")
            self._connection.expunge()
        except Exception as e:
            logger.error("Failed to move email", email_uid=email_uid, error=str(e))
    
    def detect_vendor_from_email(self, parsed_email: ParsedEmail) -> Optional[str]:
        """
        Detect vendor from email sender domain.
        
        This would query the vendor database in production.
        """
        # Extract domain from email address
        if "@" in parsed_email.from_address:
            domain = parsed_email.from_address.split("@")[1].lower()
            
            # Known vendor mappings (would be a database lookup)
            vendor_domains = {
                "acme.com": "Acme Corporation",
                "cloudservices.com": "CloudServices Ltd",
                "officedepot.com": "Office Depot",
            }
            
            return vendor_domains.get(domain)
        
        return None


class EmailIngestionService:
    """
    High-level email ingestion service.
    
    Coordinates email fetching, attachment processing, and invoice creation.
    """
    
    def __init__(self):
        self.email_handler = EmailHandler()
    
    async def process_inbox(self) -> List[IngestionResult]:
        """
        Process all unread emails with invoice attachments.
        
        Returns list of ingestion results.
        """
        results = []
        
        try:
            # Fetch emails (run in thread pool)
            loop = asyncio.get_event_loop()
            emails = await loop.run_in_executor(
                None,
                self.email_handler.fetch_unread_emails
            )
            
            for email_uid, parsed_email in emails:
                result = await self._process_email(email_uid, parsed_email)
                results.append(result)
            
        except Exception as e:
            logger.error("Email ingestion failed", error=str(e))
        finally:
            self.email_handler.disconnect()
        
        return results
    
    async def _process_email(
        self,
        email_uid: str,
        parsed_email: ParsedEmail
    ) -> IngestionResult:
        """Process a single email and create invoices."""
        processed = []
        skipped = []
        
        # Detect vendor
        vendor = self.email_handler.detect_vendor_from_email(parsed_email)
        
        for attachment in parsed_email.attachments:
            try:
                # Save attachment to temporary location
                import tempfile
                
                with tempfile.NamedTemporaryFile(
                    suffix=os.path.splitext(attachment.filename)[1],
                    delete=False
                ) as tmp:
                    tmp.write(attachment.content)
                    tmp_path = tmp.name
                
                # Import upload route to create invoice
                from routes.invoices import _invoices_db
                import uuid
                
                invoice_id = f"inv-{uuid.uuid4().hex[:8]}"
                invoice_number = f"INV-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
                
                invoice = {
                    "id": invoice_id,
                    "document_id": str(uuid.uuid4()),
                    "status": "uploaded",
                    "vendor": {"name": vendor or "Pending Extraction..."},
                    "invoice_number": invoice_number,
                    "source_type": "email",
                    "source_email": parsed_email.from_address,
                    "source_subject": parsed_email.subject,
                    "source_filename": attachment.filename,
                    "source_size": attachment.size,
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat(),
                }
                
                _invoices_db[invoice_id] = invoice
                
                processed.append({
                    "filename": attachment.filename,
                    "invoice_id": invoice_id,
                    "size": attachment.size
                })
                
                logger.info(
                    "Invoice created from email",
                    invoice_id=invoice_id,
                    filename=attachment.filename,
                    vendor=vendor
                )
                
                # Cleanup temp file
                os.unlink(tmp_path)
                
            except Exception as e:
                logger.error(
                    "Failed to process attachment",
                    filename=attachment.filename,
                    error=str(e)
                )
                skipped.append({
                    "filename": attachment.filename,
                    "reason": str(e)
                })
        
        # Mark email as processed
        self.email_handler.mark_as_read(email_uid)
        
        return IngestionResult(
            email_id=email_uid,
            message_id=parsed_email.message_id,
            from_address=parsed_email.from_address,
            subject=parsed_email.subject,
            processed_attachments=processed,
            skipped_attachments=skipped,
            vendor_detected=vendor,
            status="processed" if processed else "skipped"
        )
