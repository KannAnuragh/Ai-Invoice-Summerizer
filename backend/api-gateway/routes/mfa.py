"""
MFA (Multi-Factor Authentication)
=================================
TOTP-based MFA for enhanced security.
"""

import os
import hmac
import struct
import time
import secrets
import hashlib
from datetime import datetime
from typing import Optional, Dict, List
from base64 import b32encode, b32decode

import structlog
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

logger = structlog.get_logger(__name__)

router = APIRouter()


# MFA storage (use database in production)
_mfa_secrets: Dict[str, Dict] = {}
_backup_codes: Dict[str, List[str]] = {}


class MFASetupResponse(BaseModel):
    """MFA setup response."""
    secret: str
    qr_uri: str
    backup_codes: List[str]


class MFAVerifyRequest(BaseModel):
    """MFA verification request."""
    code: str


class MFAStatusResponse(BaseModel):
    """MFA status response."""
    enabled: bool
    verified: bool
    backup_codes_remaining: int


def generate_totp_secret() -> str:
    """Generate a random TOTP secret."""
    # 20 bytes = 160 bits, standard for TOTP
    return b32encode(secrets.token_bytes(20)).decode("utf-8").rstrip("=")


def generate_backup_codes(count: int = 10) -> List[str]:
    """Generate backup codes for MFA recovery."""
    codes = []
    for _ in range(count):
        # 8 character alphanumeric codes
        code = secrets.token_hex(4).upper()
        codes.append(f"{code[:4]}-{code[4:]}")
    return codes


def get_totp_uri(secret: str, email: str, issuer: str = "AI Invoice Summarizer") -> str:
    """
    Generate otpauth:// URI for QR code generation.
    
    This URI can be scanned by authenticator apps like Google Authenticator,
    Authy, or Microsoft Authenticator.
    """
    from urllib.parse import quote
    
    label = quote(f"{issuer}:{email}")
    issuer_param = quote(issuer)
    
    return f"otpauth://totp/{label}?secret={secret}&issuer={issuer_param}&algorithm=SHA1&digits=6&period=30"


def compute_totp(secret: str, time_step: int = 30, digits: int = 6) -> str:
    """
    Compute TOTP code using HMAC-SHA1.
    
    Implements RFC 6238 TOTP algorithm.
    """
    # Decode base32 secret (add padding if needed)
    secret_padded = secret + "=" * ((8 - len(secret) % 8) % 8)
    key = b32decode(secret_padded.upper())
    
    # Get current time counter
    counter = int(time.time()) // time_step
    
    # Pack counter as big-endian 8-byte integer
    counter_bytes = struct.pack(">Q", counter)
    
    # Compute HMAC-SHA1
    hmac_hash = hmac.new(key, counter_bytes, hashlib.sha1).digest()
    
    # Dynamic truncation
    offset = hmac_hash[-1] & 0x0F
    code_int = struct.unpack(">I", hmac_hash[offset:offset+4])[0] & 0x7FFFFFFF
    
    # Get last N digits
    code = code_int % (10 ** digits)
    
    return str(code).zfill(digits)


def verify_totp(secret: str, code: str, window: int = 1) -> bool:
    """
    Verify a TOTP code with time window tolerance.
    
    Args:
        secret: Base32-encoded TOTP secret
        code: 6-digit code to verify
        window: Number of time steps to check before/after current
        
    Returns:
        True if code is valid
    """
    # Remove spaces and hyphens
    code = code.replace(" ", "").replace("-", "")
    
    if len(code) != 6 or not code.isdigit():
        return False
    
    current_time = int(time.time())
    
    # Check current and adjacent time windows
    for offset in range(-window, window + 1):
        check_time = current_time + (offset * 30)
        expected = compute_totp(secret, time_step=30)
        
        # Temporarily compute for different time
        counter = check_time // 30
        secret_padded = secret + "=" * ((8 - len(secret) % 8) % 8)
        key = b32decode(secret_padded.upper())
        counter_bytes = struct.pack(">Q", counter)
        hmac_hash = hmac.new(key, counter_bytes, hashlib.sha1).digest()
        offset_byte = hmac_hash[-1] & 0x0F
        code_int = struct.unpack(">I", hmac_hash[offset_byte:offset_byte+4])[0] & 0x7FFFFFFF
        expected = str(code_int % 1000000).zfill(6)
        
        if hmac.compare_digest(code, expected):
            return True
    
    return False


@router.post("/auth/mfa/setup", response_model=MFASetupResponse)
async def setup_mfa(
    user_id: str,  # In production, get from session
    email: str,
) -> MFASetupResponse:
    """
    Initialize MFA setup for a user.
    
    Returns secret and QR code URI for authenticator app.
    """
    # Check if already enabled
    if user_id in _mfa_secrets and _mfa_secrets[user_id].get("verified"):
        raise HTTPException(
            status_code=400,
            detail="MFA already enabled. Disable first to reconfigure."
        )
    
    # Generate new secret
    secret = generate_totp_secret()
    backup_codes = generate_backup_codes()
    
    # Store (unverified until first successful verification)
    _mfa_secrets[user_id] = {
        "secret": secret,
        "verified": False,
        "created_at": datetime.utcnow().isoformat()
    }
    _backup_codes[user_id] = backup_codes
    
    # Generate QR code URI
    qr_uri = get_totp_uri(secret, email)
    
    logger.info("MFA setup initiated", user_id=user_id[:8])
    
    return MFASetupResponse(
        secret=secret,
        qr_uri=qr_uri,
        backup_codes=backup_codes
    )


@router.post("/auth/mfa/verify")
async def verify_mfa_setup(
    user_id: str,
    request: MFAVerifyRequest,
) -> Dict:
    """
    Verify MFA setup with first TOTP code.
    
    This confirms the user has correctly configured their authenticator.
    """
    if user_id not in _mfa_secrets:
        raise HTTPException(status_code=400, detail="MFA not set up")
    
    mfa_data = _mfa_secrets[user_id]
    
    if mfa_data.get("verified"):
        raise HTTPException(status_code=400, detail="MFA already verified")
    
    # Verify the code
    if not verify_totp(mfa_data["secret"], request.code):
        raise HTTPException(status_code=400, detail="Invalid code")
    
    # Mark as verified
    mfa_data["verified"] = True
    mfa_data["verified_at"] = datetime.utcnow().isoformat()
    
    logger.info("MFA verified", user_id=user_id[:8])
    
    return {"status": "mfa_enabled", "message": "MFA successfully enabled"}


@router.post("/auth/mfa/check")
async def check_mfa_code(
    user_id: str,
    request: MFAVerifyRequest,
) -> Dict:
    """
    Verify MFA code during login.
    
    Also accepts backup codes.
    """
    code = request.code.replace(" ", "").replace("-", "")
    
    # Check if MFA is enabled
    if user_id not in _mfa_secrets:
        raise HTTPException(status_code=400, detail="MFA not enabled")
    
    mfa_data = _mfa_secrets[user_id]
    
    if not mfa_data.get("verified"):
        raise HTTPException(status_code=400, detail="MFA not verified")
    
    # Try TOTP first
    if verify_totp(mfa_data["secret"], code):
        logger.info("MFA check passed (TOTP)", user_id=user_id[:8])
        return {"status": "verified", "method": "totp"}
    
    # Try backup codes
    if user_id in _backup_codes:
        formatted_code = code.upper()
        if len(formatted_code) == 8:
            formatted_code = f"{formatted_code[:4]}-{formatted_code[4:]}"
        
        if formatted_code in _backup_codes[user_id]:
            # Remove used backup code
            _backup_codes[user_id].remove(formatted_code)
            logger.info("MFA check passed (backup code)", user_id=user_id[:8])
            return {
                "status": "verified",
                "method": "backup_code",
                "remaining_backup_codes": len(_backup_codes[user_id])
            }
    
    logger.warning("MFA check failed", user_id=user_id[:8])
    raise HTTPException(status_code=401, detail="Invalid MFA code")


@router.get("/auth/mfa/status", response_model=MFAStatusResponse)
async def get_mfa_status(user_id: str) -> MFAStatusResponse:
    """Get MFA status for a user."""
    if user_id not in _mfa_secrets:
        return MFAStatusResponse(
            enabled=False,
            verified=False,
            backup_codes_remaining=0
        )
    
    mfa_data = _mfa_secrets[user_id]
    backup_count = len(_backup_codes.get(user_id, []))
    
    return MFAStatusResponse(
        enabled=True,
        verified=mfa_data.get("verified", False),
        backup_codes_remaining=backup_count
    )


@router.post("/auth/mfa/disable")
async def disable_mfa(
    user_id: str,
    request: MFAVerifyRequest,
) -> Dict:
    """
    Disable MFA (requires current MFA code).
    """
    if user_id not in _mfa_secrets:
        raise HTTPException(status_code=400, detail="MFA not enabled")
    
    # Verify current code before disabling
    mfa_data = _mfa_secrets[user_id]
    if not verify_totp(mfa_data["secret"], request.code):
        raise HTTPException(status_code=401, detail="Invalid MFA code")
    
    # Remove MFA
    del _mfa_secrets[user_id]
    if user_id in _backup_codes:
        del _backup_codes[user_id]
    
    logger.info("MFA disabled", user_id=user_id[:8])
    
    return {"status": "mfa_disabled"}


@router.post("/auth/mfa/regenerate-backup-codes")
async def regenerate_backup_codes(
    user_id: str,
    request: MFAVerifyRequest,
) -> Dict:
    """
    Regenerate backup codes (requires MFA code).
    """
    if user_id not in _mfa_secrets:
        raise HTTPException(status_code=400, detail="MFA not enabled")
    
    mfa_data = _mfa_secrets[user_id]
    
    # Verify current code
    if not verify_totp(mfa_data["secret"], request.code):
        raise HTTPException(status_code=401, detail="Invalid MFA code")
    
    # Generate new backup codes
    new_codes = generate_backup_codes()
    _backup_codes[user_id] = new_codes
    
    logger.info("Backup codes regenerated", user_id=user_id[:8])
    
    return {"backup_codes": new_codes}
