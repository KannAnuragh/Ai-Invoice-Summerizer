"""
File Validator
==============
Validates uploaded files for type, size, and security.
"""

import os
import hashlib
from typing import Tuple, Optional
from enum import Enum

import structlog

logger = structlog.get_logger(__name__)


class ValidationError(Exception):
    """File validation error."""
    pass


class FileType(str, Enum):
    """Supported file types."""
    PDF = "pdf"
    PNG = "png"
    JPEG = "jpeg"
    TIFF = "tiff"


# Magic bytes for file type detection
MAGIC_BYTES = {
    b"%PDF": FileType.PDF,
    b"\x89PNG": FileType.PNG,
    b"\xff\xd8\xff": FileType.JPEG,
    b"II*\x00": FileType.TIFF,  # Little-endian TIFF
    b"MM\x00*": FileType.TIFF,  # Big-endian TIFF
}

# File size limits
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
MIN_FILE_SIZE = 100  # 100 bytes (to catch empty/corrupt files)

# Allowed extensions
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif"}


def detect_file_type(content: bytes) -> Optional[FileType]:
    """
    Detect file type from magic bytes.
    More reliable than extension checking.
    """
    for magic, file_type in MAGIC_BYTES.items():
        if content.startswith(magic):
            return file_type
    return None


def validate_extension(filename: str) -> bool:
    """Check if file extension is allowed."""
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_EXTENSIONS


def validate_file_size(content: bytes) -> Tuple[bool, str]:
    """
    Validate file size.
    Returns (is_valid, message).
    """
    size = len(content)
    
    if size < MIN_FILE_SIZE:
        return False, f"File too small ({size} bytes). Minimum: {MIN_FILE_SIZE} bytes"
    
    if size > MAX_FILE_SIZE:
        return False, f"File too large ({size / (1024*1024):.1f} MB). Maximum: {MAX_FILE_SIZE / (1024*1024):.0f} MB"
    
    return True, "OK"


def compute_hash(content: bytes) -> str:
    """Compute SHA-256 hash for content."""
    return hashlib.sha256(content).hexdigest()


def validate_file(
    filename: str,
    content: bytes,
    check_magic_bytes: bool = True,
) -> Tuple[bool, str, Optional[FileType]]:
    """
    Full file validation.
    
    Returns:
        (is_valid, message, detected_type)
    """
    # Check extension
    if not validate_extension(filename):
        ext = os.path.splitext(filename)[1]
        return False, f"File type '{ext}' not allowed. Accepted: {', '.join(ALLOWED_EXTENSIONS)}", None
    
    # Check size
    size_valid, size_msg = validate_file_size(content)
    if not size_valid:
        return False, size_msg, None
    
    # Check magic bytes
    if check_magic_bytes:
        detected_type = detect_file_type(content)
        if detected_type is None:
            return False, "Unable to detect file type. File may be corrupted.", None
        
        # Verify extension matches detected type
        ext = os.path.splitext(filename)[1].lower()
        ext_type_map = {
            ".pdf": FileType.PDF,
            ".png": FileType.PNG,
            ".jpg": FileType.JPEG,
            ".jpeg": FileType.JPEG,
            ".tiff": FileType.TIFF,
            ".tif": FileType.TIFF,
        }
        expected_type = ext_type_map.get(ext)
        
        if expected_type and detected_type != expected_type:
            logger.warning(
                "File extension mismatch",
                filename=filename,
                extension=ext,
                detected_type=detected_type,
            )
            # Allow but log - some systems rename files
    else:
        detected_type = None
    
    return True, "File validation passed", detected_type


class FileValidator:
    """
    File validator with configurable limits.
    """
    
    def __init__(
        self,
        max_size: int = MAX_FILE_SIZE,
        allowed_extensions: set = ALLOWED_EXTENSIONS,
    ):
        self.max_size = max_size
        self.allowed_extensions = allowed_extensions
    
    def validate(self, filename: str, content: bytes) -> Tuple[bool, str]:
        """Validate a file."""
        is_valid, message, _ = validate_file(filename, content)
        return is_valid, message
    
    def get_file_info(self, filename: str, content: bytes) -> dict:
        """Get file information including hash and type."""
        is_valid, message, detected_type = validate_file(filename, content)
        
        return {
            "filename": filename,
            "size": len(content),
            "hash": compute_hash(content),
            "extension": os.path.splitext(filename)[1].lower(),
            "detected_type": detected_type.value if detected_type else None,
            "is_valid": is_valid,
            "validation_message": message,
        }
