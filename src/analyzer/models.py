"""
Data models for analyzer module.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional
from enum import Enum


class SentimentLabel(Enum):
    """Sentiment labels."""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class EntityType(Enum):
    """Entity types."""
    PERSON = "PERSON"
    ORGANIZATION = "ORGANIZATION"
    LOCATION = "LOCATION"
    DATE = "DATE"
    MONEY = "MONEY"
    PERCENT = "PERCENT"
    EVENT = "EVENT"
    PRODUCT = "PRODUCT"
    LAW = "LAW"
    GPE = "GPE"  # Geo-political entity


class EventType(Enum):
    """Event types."""
    ELECTION = "election"
    POLICY = "policy"
    ECONOMIC = "economic"
    SOCIAL = "social"
    SCANDAL = "scandal"
    DISASTER = "disaster"
    BREAKTHROUGH = "breakthrough"
    UNKNOWN = "unknown"


@dataclass
class SentimentResult:
    """Sentiment analysis result."""
    label: SentimentLabel
    score: float  # -1 to 1
    confidence: float  # 0 to 1
    model: str = ""
    analyzed_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label.value,
            "score": self.score,
            "confidence": self.confidence,
            "model": self.model,
            "analyzed_at": self.analyzed_at.isoformat() if self.analyzed_at else None,
        }


@dataclass
class Entity:
    """Named entity."""
    text: str
    type: EntityType
    start: int = 0
    end: int = 0
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "type": self.type.value,
            "start": self.start,
            "end": self.end,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


@dataclass
class Event:
    """Extracted event."""
    event_id: str
    type: EventType
    title: str
    description: str = ""
    entities: List[str] = field(default_factory=list)
    sentiment: Optional[SentimentResult] = None
    impact: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    extracted_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "type": self.type.value,
            "title": self.title,
            "description": self.description,
            "entities": self.entities,
            "sentiment": self.sentiment.to_dict() if self.sentiment else None,
            "impact": self.impact,
            "confidence": self.confidence,
            "extracted_at": self.extracted_at.isoformat() if self.extracted_at else None,
        }


@dataclass
class Topic:
    """Topic/cluster information."""
    topic_id: str
    keywords: List[str]
    label: str = ""
    document_count: int = 0
    relevance_score: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic_id": self.topic_id,
            "keywords": self.keywords,
            "label": self.label,
            "document_count": self.document_count,
            "relevance_score": self.relevance_score,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


@dataclass
class AnalysisResult:
    """Complete analysis result for a document."""
    doc_id: str
    sentiment: Optional[SentimentResult] = None
    entities: List[Entity] = field(default_factory=list)
    events: List[Event] = field(default_factory=list)
    topics: List[Topic] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    language: str = "zh"
    analyzed_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "sentiment": self.sentiment.to_dict() if self.sentiment else None,
            "entities": [e.to_dict() for e in self.entities],
            "events": [e.to_dict() for e in self.events],
            "topics": [t.to_dict() for t in self.topics],
            "keywords": self.keywords,
            "language": self.language,
            "analyzed_at": self.analyzed_at.isoformat() if self.analyzed_at else None,
            "metadata": self.metadata,
        }