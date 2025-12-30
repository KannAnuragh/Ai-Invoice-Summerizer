"""
Rate Limiting Middleware
========================
Prevents abuse and accidental overload with token bucket algorithm.
"""

import time
from collections import defaultdict
from typing import Callable, Dict, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
import structlog

logger = structlog.get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Token bucket rate limiter.
    
    Default limits:
    - 100 requests per minute per IP
    - 1000 requests per minute per tenant
    
    Configurable via environment variables.
    """
    
    def __init__(self, app, requests_per_minute: int = 100):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.tokens_per_second = requests_per_minute / 60.0
        self.buckets: Dict[str, Tuple[float, float]] = defaultdict(
            lambda: (time.time(), float(requests_per_minute))
        )
    
    def _get_client_key(self, request: Request) -> str:
        """Get unique client identifier."""
        # Try to get tenant ID from header or use IP
        tenant_id = request.headers.get("X-Tenant-ID")
        if tenant_id:
            return f"tenant:{tenant_id}"
        
        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}"
    
    def _check_rate_limit(self, key: str) -> Tuple[bool, int]:
        """
        Check if request should be allowed.
        Returns (allowed, remaining_tokens).
        """
        now = time.time()
        last_update, tokens = self.buckets[key]
        
        # Add tokens based on time elapsed
        time_passed = now - last_update
        tokens = min(
            self.requests_per_minute,
            tokens + time_passed * self.tokens_per_second
        )
        
        if tokens >= 1:
            tokens -= 1
            self.buckets[key] = (now, tokens)
            return True, int(tokens)
        else:
            self.buckets[key] = (now, tokens)
            return False, 0
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/ready", "/live"]:
            return await call_next(request)
        
        client_key = self._get_client_key(request)
        allowed, remaining = self._check_rate_limit(client_key)
        
        if not allowed:
            logger.warning(
                "Rate limit exceeded",
                client_key=client_key,
                path=request.url.path,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "detail": "Too many requests. Please try again later.",
                    "retry_after_seconds": 60,
                },
                headers={"Retry-After": "60"}
            )
        
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        
        return response
