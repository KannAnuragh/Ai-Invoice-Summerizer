"""
Storage Service
================
Handles file storage with support for local and cloud storage backends.
"""

import os
import shutil
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, BinaryIO
from pathlib import Path

import aiofiles
import structlog

logger = structlog.get_logger(__name__)


class StorageBackend(ABC):
    """Abstract base class for storage backends."""
    
    @abstractmethod
    async def save(self, key: str, content: bytes) -> str:
        """Save content and return the storage path."""
        pass
    
    @abstractmethod
    async def get(self, key: str) -> Optional[bytes]:
        """Retrieve content by key."""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete content by key."""
        pass
    
    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        pass


class LocalStorageBackend(StorageBackend):
    """
    Local filesystem storage backend.
    
    Organizes files by date: uploads/YYYY/MM/DD/document_id.ext
    """
    
    def __init__(self, base_path: str = "./uploads"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def _get_full_path(self, key: str) -> Path:
        """Get full filesystem path for a key."""
        return self.base_path / key
    
    async def save(self, key: str, content: bytes) -> str:
        """Save file to local filesystem."""
        full_path = self._get_full_path(key)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        async with aiofiles.open(full_path, "wb") as f:
            await f.write(content)
        
        logger.info("File saved", path=str(full_path), size=len(content))
        return str(full_path)
    
    async def get(self, key: str) -> Optional[bytes]:
        """Retrieve file from local filesystem."""
        full_path = self._get_full_path(key)
        
        if not full_path.exists():
            return None
        
        async with aiofiles.open(full_path, "rb") as f:
            return await f.read()
    
    async def delete(self, key: str) -> bool:
        """Delete file from local filesystem."""
        full_path = self._get_full_path(key)
        
        if not full_path.exists():
            return False
        
        full_path.unlink()
        logger.info("File deleted", path=str(full_path))
        return True
    
    async def exists(self, key: str) -> bool:
        """Check if file exists."""
        return self._get_full_path(key).exists()


class StorageService:
    """
    High-level storage service with organizational logic.
    """
    
    def __init__(self, backend: Optional[StorageBackend] = None):
        self.backend = backend or LocalStorageBackend()
    
    def generate_storage_key(
        self,
        document_id: str,
        filename: str,
        tenant_id: Optional[str] = None,
    ) -> str:
        """
        Generate a storage key for a document.
        
        Format: [tenant_id/]YYYY/MM/DD/document_id.ext
        """
        now = datetime.utcnow()
        ext = os.path.splitext(filename)[1].lower()
        
        parts = []
        if tenant_id:
            parts.append(tenant_id)
        parts.extend([
            now.strftime("%Y"),
            now.strftime("%m"),
            now.strftime("%d"),
            f"{document_id}{ext}"
        ])
        
        return "/".join(parts)
    
    async def store_document(
        self,
        document_id: str,
        filename: str,
        content: bytes,
        tenant_id: Optional[str] = None,
    ) -> dict:
        """
        Store a document and return storage metadata.
        """
        key = self.generate_storage_key(document_id, filename, tenant_id)
        path = await self.backend.save(key, content)
        
        return {
            "document_id": document_id,
            "storage_key": key,
            "storage_path": path,
            "size": len(content),
            "stored_at": datetime.utcnow().isoformat(),
        }
    
    async def retrieve_document(self, storage_key: str) -> Optional[bytes]:
        """Retrieve a document by its storage key."""
        return await self.backend.get(storage_key)
    
    async def delete_document(self, storage_key: str) -> bool:
        """Delete a document by its storage key."""
        return await self.backend.delete(storage_key)
    
    async def document_exists(self, storage_key: str) -> bool:
        """Check if a document exists."""
        return await self.backend.exists(storage_key)


# Default storage service instance
storage_service = StorageService()
