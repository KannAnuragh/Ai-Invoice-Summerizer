"""
Logging Middleware
==================
Request/response logging with trace IDs for observability.
"""

import uuid
import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import structlog

logger = structlog.get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for structured request/response logging.
    
    Features:
    - Generates unique trace IDs for each request
    - Logs request method, path, and timing
    - Attaches trace ID to response headers
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate trace ID
        trace_id = str(uuid.uuid4())[:8]
        request.state.trace_id = trace_id
        
        # Start timing
        start_time = time.perf_counter()
        
        # Log incoming request
        logger.info(
            "Request started",
            trace_id=trace_id,
            method=request.method,
            path=request.url.path,
            query=str(request.query_params) if request.query_params else None,
            client_ip=request.client.host if request.client else None,
        )
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            # Log response
            logger.info(
                "Request completed",
                trace_id=trace_id,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2),
            )
            
            # Attach trace ID to response headers
            response.headers["X-Trace-ID"] = trace_id
            response.headers["X-Response-Time-Ms"] = str(round(duration_ms, 2))
            
            return response
            
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            logger.error(
                "Request failed",
                trace_id=trace_id,
                method=request.method,
                path=request.url.path,
                error=str(e),
                duration_ms=round(duration_ms, 2),
            )
            raise
