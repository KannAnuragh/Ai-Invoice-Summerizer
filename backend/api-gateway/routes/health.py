"""
Health Check Endpoints
======================
Provides health and readiness probes for monitoring.
"""

from fastapi import APIRouter, Response
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    timestamp: str
    version: str
    services: dict


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Basic health check endpoint.
    Returns the current status of the API Gateway.
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        version="1.0.0",
        services={
            "api_gateway": "up",
            "database": "pending",  # Will be updated when DB is connected
            "redis": "pending",
        }
    )


@router.get("/ready")
async def readiness_check() -> dict:
    """
    Readiness probe for Kubernetes.
    Checks if the service is ready to accept traffic.
    """
    # TODO: Add actual dependency checks
    return {"ready": True}


@router.get("/live")
async def liveness_check() -> Response:
    """
    Liveness probe for Kubernetes.
    Simple check that the service is running.
    """
    return Response(status_code=200)
