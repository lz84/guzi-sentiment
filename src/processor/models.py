"""
Data models for processor module.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional
from enum import Enum


class ProcessingStatus(Enum):
    """Processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ContentType(Enum):
    """Content type."""
    TEXT = "text"
    HTML = "html"
    MARKDOWN = "markdown"
    JSON = "json"


@dataclass
class RawDocument:
    """Raw document from data collection."""
    doc_id: str
    source: str
    platform: str
    content: str
    content_type: ContentType = ContentType.TEXT
    author: str = ""
    published_at: Optional[datetime] = None
    url: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    collected_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "source": self.source,
            "platform": self.platform,
            "content": self.content,
            "content_type": self.content_type.value,
            "author": self.author,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "url": self.url,
            "metadata": self.metadata,
            "collected_at": self.collected_at.isoformat() if self.collected_at else None,
        }


@dataclass
class ProcessedDocument:
    """Processed document after cleaning, deduplication, and normalization."""
    doc_id: str
    raw_doc_id: str
    source: str
    platform: str
    original_content: str
    cleaned_content: str
    normalized_content: str
    content_hash: str = ""
    language: str = "zh"
    word_count: int = 0
    processing_steps: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    processed_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "raw_doc_id": self.raw_doc_id,
            "source": self.source,
            "platform": self.platform,
            "original_content": self.original_content,
            "cleaned_content": self.cleaned_content,
            "normalized_content": self.normalized_content,
            "content_hash": self.content_hash,
            "language": self.language,
            "word_count": self.word_count,
            "processing_steps": self.processing_steps,
            "metadata": self.metadata,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
        }


@dataclass
class ProcessingResult:
    """Result of processing operation."""
    success: bool
    documents_processed: int = 0
    documents_failed: int = 0
    processing_time_ms: float = 0.0
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "documents_processed": self.documents_processed,
            "documents_failed": self.documents_failed,
            "processing_time_ms": self.processing_time_ms,
            "errors": self.errors,
            "metadata": self.metadata,
        }


@dataclass
class DeduplicationResult:
    """Result of deduplication operation."""
    total_documents: int = 0
    unique_documents: int = 0
    duplicate_documents: int = 0
    duplicate_groups: List[List[str]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_documents": self.total_documents,
            "unique_documents": self.unique_documents,
            "duplicate_documents": self.duplicate_documents,
            "duplicate_groups": self.duplicate_groups,
        }