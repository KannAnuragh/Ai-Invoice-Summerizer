"""Email ingestion package."""

from .email_handler import EmailHandler, EmailIngestionService, ParsedEmail
from .webhook_receiver import router as webhook_router

__all__ = [
    "EmailHandler",
    "EmailIngestionService", 
    "ParsedEmail",
    "webhook_router",
]
