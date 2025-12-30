"""
Configuration Management
========================
Centralized configuration using Pydantic Settings.
"""

import os
from typing import Optional
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application
    app_name: str = "AI Invoice Summarizer"
    app_version: str = "1.0.0"
    environment: str = "development"
    debug: bool = True
    
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "*"
    
    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/invoices"
    database_pool_size: int = 10
    database_max_overflow: int = 20
    sql_echo: bool = False
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_cache_ttl: int = 3600
    
    # Storage
    upload_dir: str = "./uploads"
    max_file_size_mb: int = 50
    allowed_extensions: str = ".pdf,.png,.jpg,.jpeg,.tiff,.tif"
    
    # Authentication
    jwt_secret_key: str = "dev-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 30
    
    # OAuth
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"
    frontend_url: str = "http://localhost:3000"
    
    # AI Services
    openai_api_key: Optional[str] = None
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "mistral"
    ocr_confidence_threshold: float = 0.85
    
    # OCR
    tesseract_path: Optional[str] = None
    ocr_languages: str = "eng"
    
    # Payment Integrations
    stripe_api_key: Optional[str] = None
    stripe_webhook_secret: Optional[str] = None
    
    # ERP Integrations
    quickbooks_client_id: Optional[str] = None
    quickbooks_client_secret: Optional[str] = None
    quickbooks_redirect_uri: str = "http://localhost:8000/integrations/quickbooks/callback"
    quickbooks_realm_id: Optional[str] = None
    quickbooks_refresh_token: Optional[str] = None
    quickbooks_env: str = "sandbox"
    
    # Workflow
    sla_warning_hours: int = 24
    sla_breach_hours: int = 48
    auto_approve_enabled: bool = False
    auto_approve_max_amount: float = 1000.0
    
    # Observability
    log_level: str = "INFO"
    log_format: str = "json"
    metrics_enabled: bool = True
    tracing_enabled: bool = False
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Convenience accessor
settings = get_settings()
