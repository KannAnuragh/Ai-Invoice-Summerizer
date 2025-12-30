"""
Authentication Middleware
=========================
JWT-based authentication and authorization.
"""

import os
from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import structlog

logger = structlog.get_logger(__name__)

# Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Bearer token extractor
security = HTTPBearer(auto_error=False)


class TokenPayload(BaseModel):
    """JWT token payload."""
    sub: str  # User ID
    email: str
    role: str
    tenant_id: Optional[str] = None
    exp: datetime


class CurrentUser(BaseModel):
    """Authenticated user context."""
    id: str
    email: str
    role: str
    tenant_id: Optional[str] = None
    permissions: list[str] = []


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def create_access_token(
    user_id: str,
    email: str,
    role: str,
    tenant_id: Optional[str] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a new JWT access token."""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {
        "sub": user_id,
        "email": email,
        "role": role,
        "tenant_id": tenant_id,
        "exp": expire,
    }
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[TokenPayload]:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return TokenPayload(**payload)
    except JWTError as e:
        logger.warning("Token decode failed", error=str(e))
        return None


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[CurrentUser]:
    """
    Dependency to get the current authenticated user.
    Returns None if no valid token is provided.
    """
    if not credentials:
        return None
    
    token_payload = decode_token(credentials.credentials)
    if not token_payload:
        return None
    
    # Define role-based permissions
    permissions_map = {
        "admin": ["read", "write", "delete", "approve", "admin"],
        "approver": ["read", "write", "approve"],
        "viewer": ["read"],
    }
    
    return CurrentUser(
        id=token_payload.sub,
        email=token_payload.email,
        role=token_payload.role,
        tenant_id=token_payload.tenant_id,
        permissions=permissions_map.get(token_payload.role, []),
    )


async def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> CurrentUser:
    """
    Dependency that requires authentication.
    Raises 401 if not authenticated.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token_payload = decode_token(credentials.credentials)
    if not token_payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    permissions_map = {
        "admin": ["read", "write", "delete", "approve", "admin"],
        "approver": ["read", "write", "approve"],
        "viewer": ["read"],
    }
    
    return CurrentUser(
        id=token_payload.sub,
        email=token_payload.email,
        role=token_payload.role,
        tenant_id=token_payload.tenant_id,
        permissions=permissions_map.get(token_payload.role, []),
    )


def require_permission(permission: str):
    """
    Dependency factory for permission-based authorization.
    
    Usage:
        @router.delete("/invoices/{id}", dependencies=[Depends(require_permission("delete"))])
    """
    async def check_permission(user: CurrentUser = Depends(require_auth)) -> CurrentUser:
        if permission not in user.permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required",
            )
        return user
    
    return check_permission
