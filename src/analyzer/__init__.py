"""
Analyzer module for Guzi Sentiment System.
Provides sentiment analysis, entity recognition, event extraction, and topic clustering.
"""

from .models import (
    SentimentResult,
    SentimentLabel,
    Entity,
    EntityType,
    Event,
    EventType,
    Topic,
    AnalysisResult,
)
from .sentiment_analyzer import (
    SentimentAnalyzerBase,
    RuleBasedSentimentAnalyzer,
    LLMSentimentAnalyzer,
    HybridSentimentAnalyzer,
    create_sentiment_analyzer,
)
from .entity_recognizer import EntityRecognizer
from .event_extractor import EventExtractor
from .topic_cluster import TopicCluster, HierarchicalTopicCluster
from .engine import AnalysisEngine, AnalysisEngineBuilder

__all__ = [
    # Models
    "SentimentResult",
    "SentimentLabel",
    "Entity",
    "EntityType",
    "Event",
    "EventType",
    "Topic",
    "AnalysisResult",
    # Sentiment
    "SentimentAnalyzerBase",
    "RuleBasedSentimentAnalyzer",
    "LLMSentimentAnalyzer",
    "HybridSentimentAnalyzer",
    "create_sentiment_analyzer",
    # Entity
    "EntityRecognizer",
    # Event
    "EventExtractor",
    # Topic
    "TopicCluster",
    "HierarchicalTopicCluster",
    # Engine
    "AnalysisEngine",
    "AnalysisEngineBuilder",
]