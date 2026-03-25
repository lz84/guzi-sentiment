"""
Analysis engine for comprehensive document analysis.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid

from .models import (
    AnalysisResult,
    SentimentResult,
    Entity,
    Event,
    Topic,
    SentimentLabel,
)
from .sentiment_analyzer import (
    SentimentAnalyzerBase,
    create_sentiment_analyzer,
)
from .entity_recognizer import EntityRecognizer
from .event_extractor import EventExtractor
from .topic_cluster import TopicCluster

logger = logging.getLogger(__name__)


class AnalysisEngine:
    """
    Main analysis engine that orchestrates all analysis components.
    
    Components:
    - Sentiment Analyzer
    - Entity Recognizer
    - Event Extractor
    - Topic Clusterer
    """
    
    def __init__(
        self,
        sentiment_analyzer: Optional[SentimentAnalyzerBase] = None,
        entity_recognizer: Optional[EntityRecognizer] = None,
        event_extractor: Optional[EventExtractor] = None,
        topic_clusterer: Optional[TopicCluster] = None,
        llm_client: Optional[Any] = None,
    ):
        """
        Initialize analysis engine.
        
        Args:
            sentiment_analyzer: Custom sentiment analyzer
            entity_recognizer: Custom entity recognizer
            event_extractor: Custom event extractor
            topic_clusterer: Custom topic clusterer
            llm_client: LLM client for advanced analysis
        """
        self.llm_client = llm_client
        
        # Initialize components
        self.sentiment_analyzer = sentiment_analyzer or create_sentiment_analyzer(
            method="rule"
        )
        
        self.entity_recognizer = entity_recognizer or EntityRecognizer(
            llm_client=llm_client,
        )
        
        self.event_extractor = event_extractor or EventExtractor(
            llm_client=llm_client,
        )
        
        self.topic_clusterer = topic_clusterer or TopicCluster()
        
        # Statistics
        self._stats = {
            "documents_analyzed": 0,
            "total_entities": 0,
            "total_events": 0,
        }
    
    async def analyze(self, doc_id: str, text: str) -> AnalysisResult:
        """
        Analyze a single document.
        
        Args:
            doc_id: Document ID
            text: Document text
            
        Returns:
            AnalysisResult with all analysis components
        """
        result = AnalysisResult(doc_id=doc_id)
        
        try:
            # 1. Sentiment analysis
            result.sentiment = self.sentiment_analyzer.analyze(text)
            
            # 2. Entity recognition
            result.entities = self.entity_recognizer.recognize(text)
            
            # 3. Event extraction
            entity_texts = [e.text for e in result.entities]
            result.events = self.event_extractor.extract(text, entity_texts)
            
            # 4. Keyword extraction
            keywords = self.topic_clusterer.extract_keywords(text)
            result.keywords = [kw for kw, _ in keywords[:10]]
            
            # Update stats
            self._stats["documents_analyzed"] += 1
            self._stats["total_entities"] += len(result.entities)
            self._stats["total_events"] += len(result.events)
            
        except Exception as e:
            logger.error(f"Analysis failed for {doc_id}: {e}")
            result.metadata["error"] = str(e)
        
        return result
    
    async def analyze_batch(
        self, documents: List[tuple]
    ) -> List[AnalysisResult]:
        """
        Analyze multiple documents.
        
        Args:
            documents: List of (doc_id, text) tuples
            
        Returns:
            List of AnalysisResult
        """
        results = []
        
        for doc_id, text in documents:
            result = await self.analyze(doc_id, text)
            results.append(result)
        
        return results
    
    def cluster_topics(
        self, documents: List[tuple]
    ) -> List[Topic]:
        """
        Cluster documents by topics.
        
        Args:
            documents: List of (doc_id, text) tuples
            
        Returns:
            List of Topic objects
        """
        return self.topic_clusterer.cluster(documents)
    
    def get_document_sentiment(self, text: str) -> SentimentResult:
        """Quick sentiment analysis."""
        return self.sentiment_analyzer.analyze(text)
    
    def get_document_entities(self, text: str) -> List[Entity]:
        """Quick entity recognition."""
        return self.entity_recognizer.recognize(text)
    
    def get_document_events(self, text: str) -> List[Event]:
        """Quick event extraction."""
        return self.event_extractor.extract(text)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get engine statistics."""
        return {
            **self._stats,
            "topic_stats": self.topic_clusterer.get_stats(),
        }
    
    def reset_stats(self):
        """Reset statistics."""
        self._stats = {
            "documents_analyzed": 0,
            "total_entities": 0,
            "total_events": 0,
        }


class AnalysisEngineBuilder:
    """Builder for creating analysis engines."""
    
    def __init__(self):
        self._llm_client = None
        self._sentiment_method = "rule"
        self._use_spacy = False
        self._spacy_model = None
    
    def with_llm(self, llm_client: Any) -> "AnalysisEngineBuilder":
        """Set LLM client."""
        self._llm_client = llm_client
        return self
    
    def with_sentiment_method(self, method: str) -> "AnalysisEngineBuilder":
        """Set sentiment analysis method."""
        self._sentiment_method = method
        return self
    
    def with_spacy(self, model: str = "zh_core_web_sm") -> "AnalysisEngineBuilder":
        """Enable spaCy NER."""
        self._use_spacy = True
        self._spacy_model = model
        return self
    
    def build(self) -> AnalysisEngine:
        """Build the analysis engine."""
        sentiment_analyzer = create_sentiment_analyzer(
            method=self._sentiment_method,
            llm_client=self._llm_client,
        )
        
        entity_recognizer = EntityRecognizer(
            spacy_model=self._spacy_model if self._use_spacy else None,
            llm_client=self._llm_client,
            use_spacy=self._use_spacy,
        )
        
        event_extractor = EventExtractor(
            llm_client=self._llm_client,
        )
        
        topic_clusterer = TopicCluster(
            llm_client=self._llm_client,
        )
        
        return AnalysisEngine(
            sentiment_analyzer=sentiment_analyzer,
            entity_recognizer=entity_recognizer,
            event_extractor=event_extractor,
            topic_clusterer=topic_clusterer,
            llm_client=self._llm_client,
        )