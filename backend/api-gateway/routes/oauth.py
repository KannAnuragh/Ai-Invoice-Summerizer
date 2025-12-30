"""
Google OAuth2 SSO Authentication
================================
Enterprise SSO integration with Google OAuth2.
"""

import os
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from urllib.parse import urlencode

import httpx
import structlog
from fastapi import APIRouter, HTTPException, Request, Response, Depends
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

logger = structlog.get_logger(__name__)

router = APIRouter()


# Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Google OAuth endpoints
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

# Session storage (use Redis in production)
_oauth_states: Dict[str, Dict[str, Any]] = {}
_sessions: Dict[str, Dict[str, Any]] = {}


class GoogleUser(BaseModel):
    """Google user profile."""
    id: str
    email: str
    verified_email: bool
    name: str
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    picture: Optional[str] = None
    locale: Optional[str] = None
    hd: Optional[str] = None  # Hosted domain (for Google Workspace)


class AuthResponse(BaseModel):
    """Authentication response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: GoogleUser
    is_new_user: bool = False


class SessionInfo(BaseModel):
    """Session information."""
    user_id: str
    email: str
    name: str
    picture: Optional[str] = None
    roles: list = []
    expires_at: str


def _generate_state() -> str:
    """Generate secure random state for OAuth flow."""
    return secrets.token_urlsafe(32)


def _generate_session_token() -> str:
    """Generate secure session token."""
    return secrets.token_urlsafe(48)


@router.get("/auth/google/login")
async def google_login(
    request: Request,
    redirect_uri: Optional[str] = None,
) -> RedirectResponse:
    """
    Initiate Google OAuth2 login flow.
    
    Redirects user to Google consent screen.
    """
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=500,
            detail="Google OAuth not configured. Set GOOGLE_CLIENT_ID environment variable."
        )
    
    # Generate state for CSRF protection
    state = _generate_state()
    
    # Store state with metadata
    _oauth_states[state] = {
        "created_at": datetime.utcnow().isoformat(),
        "redirect_uri": redirect_uri or FRONTEND_URL,
        "ip": request.client.host if request.client else None,
    }
    
    # Build authorization URL
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",  # Get refresh token
        "prompt": "select_account",  # Always show account picker
    }
    
    auth_url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
    
    logger.info("OAuth login initiated", state=state[:8])
    
    return RedirectResponse(url=auth_url)


@router.get("/auth/google/callback")
async def google_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
) -> RedirectResponse:
    """
    Handle Google OAuth2 callback.
    
    Exchanges authorization code for tokens and creates session.
    """
    # Handle errors from Google
    if error:
        logger.warning("OAuth error from Google", error=error)
        return RedirectResponse(url=f"{FRONTEND_URL}/login?error={error}")
    
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")
    
    # Validate state (CSRF protection)
    if state not in _oauth_states:
        logger.warning("Invalid OAuth state", state=state[:8])
        raise HTTPException(status_code=400, detail="Invalid state")
    
    state_data = _oauth_states.pop(state)
    redirect_uri = state_data.get("redirect_uri", FRONTEND_URL)
    
    # Check state age (max 10 minutes)
    created = datetime.fromisoformat(state_data["created_at"])
    if datetime.utcnow() - created > timedelta(minutes=10):
        raise HTTPException(status_code=400, detail="State expired")
    
    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": GOOGLE_REDIRECT_URI,
            }
        )
        
        if token_response.status_code != 200:
            logger.error("Token exchange failed", status=token_response.status_code)
            return RedirectResponse(url=f"{FRONTEND_URL}/login?error=token_exchange_failed")
        
        tokens = token_response.json()
        access_token = tokens.get("access_token")
        
        # Get user info
        userinfo_response = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        if userinfo_response.status_code != 200:
            logger.error("Failed to get user info", status=userinfo_response.status_code)
            return RedirectResponse(url=f"{FRONTEND_URL}/login?error=userinfo_failed")
        
        user_data = userinfo_response.json()
    
    # Create user object
    user = GoogleUser(**user_data)
    
    # Create session
    session_token = _generate_session_token()
    session_expires = datetime.utcnow() + timedelta(hours=24)
    
    _sessions[session_token] = {
        "user_id": user.id,
        "email": user.email,
        "name": user.name,
        "picture": user.picture,
        "google_access_token": access_token,
        "refresh_token": tokens.get("refresh_token"),
        "expires_at": session_expires.isoformat(),
        "roles": _get_user_roles(user),
        "created_at": datetime.utcnow().isoformat(),
    }
    
    logger.info("OAuth login successful", email=user.email, user_id=user.id[:8])
    
    # Redirect to frontend with session token
    callback_url = f"{redirect_uri}/auth/callback?token={session_token}"
    return RedirectResponse(url=callback_url)


@router.get("/auth/session", response_model=SessionInfo)
async def get_session(
    request: Request,
) -> SessionInfo:
    """
    Get current session information.
    
    Requires valid session token in Authorization header or cookie.
    """
    token = _extract_token(request)
    
    if not token or token not in _sessions:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    session = _sessions[token]
    
    # Check expiration
    expires_at = datetime.fromisoformat(session["expires_at"])
    if datetime.utcnow() > expires_at:
        del _sessions[token]
        raise HTTPException(status_code=401, detail="Session expired")
    
    return SessionInfo(
        user_id=session["user_id"],
        email=session["email"],
        name=session["name"],
        picture=session.get("picture"),
        roles=session.get("roles", []),
        expires_at=session["expires_at"]
    )


@router.post("/auth/logout")
async def logout(request: Request) -> Dict[str, str]:
    """
    Log out and invalidate session.
    """
    token = _extract_token(request)
    
    if token and token in _sessions:
        email = _sessions[token].get("email", "unknown")
        del _sessions[token]
        logger.info("User logged out", email=email)
    
    return {"status": "logged_out"}


@router.post("/auth/refresh")
async def refresh_session(request: Request) -> Dict[str, Any]:
    """
    Refresh session using Google refresh token.
    """
    token = _extract_token(request)
    
    if not token or token not in _sessions:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    session = _sessions[token]
    refresh_token = session.get("refresh_token")
    
    if not refresh_token:
        raise HTTPException(status_code=400, detail="No refresh token available")
    
    # Refresh Google token
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            }
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=401, detail="Token refresh failed")
        
        tokens = response.json()
    
    # Update session
    session["google_access_token"] = tokens.get("access_token")
    session["expires_at"] = (datetime.utcnow() + timedelta(hours=24)).isoformat()
    
    return {
        "status": "refreshed",
        "expires_at": session["expires_at"]
    }


def _extract_token(request: Request) -> Optional[str]:
    """Extract session token from request."""
    # Try Authorization header first
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    
    # Try cookie
    return request.cookies.get("session_token")


def _get_user_roles(user: GoogleUser) -> list:
    """
    Determine user roles based on email/domain.
    
    In production, this would query a database.
    """
    roles = ["viewer"]  # Default role
    
    # Check for admin domains (customize for your organization)
    if user.hd:  # Google Workspace domain
        roles.append("user")
        
        # Auto-assign roles based on domain
        admin_domains = os.getenv("ADMIN_DOMAINS", "").split(",")
        if user.hd in admin_domains:
            roles.append("admin")
    
    # Check for specific admin emails
    admin_emails = os.getenv("ADMIN_EMAILS", "").split(",")
    if user.email in admin_emails:
        roles.append("admin")
    
    return roles


# Dependency for protected routes
async def require_auth(request: Request) -> SessionInfo:
    """
    Dependency to require authentication.
    
    Usage:
        @router.get("/protected")
        async def protected_route(session: SessionInfo = Depends(require_auth)):
            return {"user": session.email}
    """
    token = _extract_token(request)
    
    if not token or token not in _sessions:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    session = _sessions[token]
    
    # Check expiration
    expires_at = datetime.fromisoformat(session["expires_at"])
    if datetime.utcnow() > expires_at:
        del _sessions[token]
        raise HTTPException(status_code=401, detail="Session expired")
    
    return SessionInfo(
        user_id=session["user_id"],
        email=session["email"],
        name=session["name"],
        picture=session.get("picture"),
        roles=session.get("roles", []),
        expires_at=session["expires_at"]
    )


def require_role(*required_roles: str):
    """
    Dependency factory to require specific roles.
    
    Usage:
        @router.get("/admin")
        async def admin_route(session: SessionInfo = Depends(require_role("admin"))):
            return {"admin": True}
    """
    async def check_role(session: SessionInfo = Depends(require_auth)) -> SessionInfo:
        user_roles = set(session.roles)
        if not user_roles.intersection(required_roles):
            raise HTTPException(
                status_code=403,
                detail=f"Required roles: {', '.join(required_roles)}"
            )
        return session
    
    return check_role
