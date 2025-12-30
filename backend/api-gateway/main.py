"""
AI Invoice Summarizer - API Gateway
====================================
Single entry point for all client requests.
Handles authentication, authorization, routing, and rate limiting.
"""

import os
import sys
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Add parent to path for shared imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Add api-gateway to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from routes import upload, invoices, approvals, admin, health
from routes import oauth, mfa
from middleware.logging import LoggingMiddleware
from middleware.rate_limit import RateLimitMiddleware

# Import metrics and tracing
try:
    from shared.metrics import get_metrics
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False

try:
    from shared.tracing import get_tracer, tracing_middleware_helper
    TRACING_AVAILABLE = True
except ImportError:
    TRACING_AVAILABLE = False

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan handler for startup/shutdown events."""
    # Startup
    logger.info("Starting API Gateway", version="2.0.0")
    
    # Initialize database (optional - fallback to in-memory if fails)
    try:
        from shared.database import init_db, close_db
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.warning("Database initialization failed, using in-memory storage", error=str(e))
    
    # Initialize integrations
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from integration_service.manager import init_integration_manager
        from integration_service import IntegrationProvider
        
        # Build integration config from environment
        integration_config = {}
        
        # Stripe configuration
        stripe_api_key = os.getenv("STRIPE_API_KEY")
        if stripe_api_key:
            integration_config[IntegrationProvider.STRIPE] = {
                "api_key": stripe_api_key,
                "webhook_secret": os.getenv("STRIPE_WEBHOOK_SECRET")
            }
        
        # QuickBooks configuration
        qb_client_id = os.getenv("QUICKBOOKS_CLIENT_ID")
        if qb_client_id:
            integration_config[IntegrationProvider.QUICKBOOKS] = {
                "client_id": qb_client_id,
                "client_secret": os.getenv("QUICKBOOKS_CLIENT_SECRET"),
                "redirect_uri": os.getenv("QUICKBOOKS_REDIRECT_URI"),
                "realm_id": os.getenv("QUICKBOOKS_REALM_ID"),
                "refresh_token": os.getenv("QUICKBOOKS_REFRESH_TOKEN"),
                "environment": os.getenv("QUICKBOOKS_ENV", "sandbox")
            }
        
        init_integration_manager(integration_config)
        logger.info("Integration manager initialized", integrations=list(integration_config.keys()))
    except Exception as e:
        logger.warning("Integration manager initialization failed", error=str(e))
    
    # Initialize metrics
    if METRICS_AVAILABLE:
        try:
            get_metrics()
            logger.info("Prometheus metrics initialized")
        except Exception as e:
            logger.warning("Metrics initialization failed", error=str(e))
    
    # Initialize tracing
    if TRACING_AVAILABLE:
        try:
            get_tracer()
            logger.info("OpenTelemetry tracing initialized")
        except Exception as e:
            logger.warning("Tracing initialization failed", error=str(e))
    
    # Initialize message queue
    try:
        from shared.message_queue import init_message_queue, get_message_queue
        from shared.event_handlers import register_all_handlers
        
        redis_url = os.getenv("REDIS_URL")
        await init_message_queue(redis_url)
        
        queue = get_message_queue()
        
        # Register all event handlers
        register_all_handlers(queue)
        
        # Start consuming messages
        await queue.start_consumers()
        
        logger.info("Message queue initialized with event handlers")
    except Exception as e:
        logger.warning("Message queue initialization failed", error=str(e))
    
    yield
    
    # Shutdown
    try:
        from shared.message_queue import get_message_queue
        queue = get_message_queue()
        if queue:
            await queue.disconnect()
    except:
        pass
    
    try:
        await close_db()
    except:
        pass
    logger.info("Shutting down API Gateway")


# Initialize FastAPI application
app = FastAPI(
    title="AI Invoice Summarizer API",
    description="Enterprise invoice processing with AI-powered summarization",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom Middleware
app.add_middleware(LoggingMiddleware)
app.add_middleware(RateLimitMiddleware)


# Metrics middleware
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """Track request metrics."""
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    
    if METRICS_AVAILABLE:
        get_metrics().record_http_request(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code,
            duration=duration
        )
    
    return response


# === Health & Core Routes ===
app.include_router(health.router, tags=["Health"])
app.include_router(upload.router, prefix="/api/v1", tags=["Upload"])

# Use database-backed invoices routes if available, fallback to in-memory
try:
    from routes import invoices_db
    app.include_router(invoices_db.router, prefix="/api/v1", tags=["Invoices"])
    logger.info("Using database-backed invoice routes")
except ImportError:
    app.include_router(invoices.router, prefix="/api/v1", tags=["Invoices"])
    logger.warning("Using in-memory invoice routes")

app.include_router(approvals.router, prefix="/api/v1", tags=["Approvals"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])

# === Integration Routes ===
try:
    from routes import integrations
    app.include_router(integrations.router, tags=["Integrations"])
    logger.info("Integration routes loaded")
except ImportError as e:
    logger.warning("Integration routes not available", error=str(e))

# === Authentication Routes ===
app.include_router(oauth.router, tags=["Authentication"])
app.include_router(mfa.router, tags=["MFA"])


# === Metrics Endpoint ===
@app.get("/metrics", include_in_schema=False)
async def prometheus_metrics():
    """Prometheus metrics endpoint."""
    if not METRICS_AVAILABLE:
        return Response(
            content="# Metrics not available\n",
            media_type="text/plain"
        )
    
    metrics = get_metrics()
    return Response(
        content=metrics.get_metrics(),
        media_type=metrics.get_content_type()
    )


# === PO Matching Route ===
@app.post("/api/v1/invoices/{invoice_id}/match-po", tags=["Validation"])
async def match_invoice_to_po(invoice_id: str, po_number: str = None):
    """
    Match an invoice to a Purchase Order.
    
    Returns variance analysis and match confidence.
    """
    try:
        from validation_service.po_matching import get_po_matcher
        from routes.invoices import _invoices_db
    except ImportError:
        # Fallback import path
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from validation_service.po_matching import get_po_matcher
        from routes.invoices import _invoices_db
    
    if invoice_id not in _invoices_db:
        return JSONResponse(status_code=404, content={"detail": "Invoice not found"})
    
    invoice = _invoices_db[invoice_id]
    matcher = get_po_matcher()
    result = matcher.match_invoice(invoice, po_number)
    
    return result.to_dict()


# === Email Ingestion Routes ===
try:
    from ingestion_service.email.webhook_receiver import router as webhook_router
    app.include_router(webhook_router, prefix="/api/v1", tags=["Email Ingestion"])
except ImportError:
    logger.warning("Email webhook routes not available")


# === Error Handlers ===
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler for unhandled errors."""
    # Record error metric
    if METRICS_AVAILABLE:
        get_metrics().record_error(
            error_type=type(exc).__name__,
            component="api_gateway"
        )
    
    logger.error(
        "Unhandled exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error_id": request.state.trace_id if hasattr(request.state, 'trace_id') else None
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("ENV", "development") == "development",
    )
