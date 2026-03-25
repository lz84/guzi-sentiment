"""
Topic clustering for grouping documents by topics.
"""

import re
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from collections import Counter, defaultdict
import uuid

from .models import Topic

logger = logging.getLogger(__name__)


class TopicCluster:
    """
    Cluster documents by topics using keyword extraction and clustering.
    
    Features:
    - Keyword extraction
    - Topic clustering
    - Topic labeling
    """
    
    # Stop words for Chinese and English
    STOP_WORDS = {
        "zh": set([
            "的", "了", "是", "在", "我", "有", "和", "就", "不", "人", "都", "一", "一个",
            "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好",
            "自己", "这", "那", "什么", "他", "她", "它", "们", "这个", "那个", "可以", "因为",
        ]),
        "en": set([
            "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would", "could", "should",
            "this", "that", "these", "those", "it", "its", "they", "them", "their",
            "i", "me", "my", "we", "us", "our", "you", "your", "he", "him", "his",
            "she", "her", "in", "on", "at", "to", "for", "of", "with", "by", "from",
        ]),
    }
    
    def __init__(
        self,
        min_cluster_size: int = 2,
        max_topics: int = 20,
        keyword_threshold: float = 0.01,
        llm_client: Optional[Any] = None,
    ):
        """
        Initialize topic clusterer.
        
        Args:
            min_cluster_size: Minimum documents per cluster
            max_topics: Maximum number of topics
            keyword_threshold: Minimum frequency for keywords
            llm_client: Optional LLM client for labeling
        """
        self.min_cluster_size = min_cluster_size
        self.max_topics = max_topics
        self.keyword_threshold = keyword_threshold
        self.llm_client = llm_client
        
        # Storage
        self._topics: Dict[str, Topic] = {}
        self._document_topics: Dict[str, str] = {}  # doc_id -> topic_id
    
    def extract_keywords(self, text: str, top_n: int = 10) -> List[Tuple[str, int]]:
        """
        Extract keywords from text.
        
        Args:
            text: Text to extract keywords from
            top_n: Number of top keywords to return
            
        Returns:
            List of (keyword, count) tuples
        """
        # Detect language
        chinese_ratio = len(re.findall(r"[\u4e00-\u9fa5]", text)) / max(len(text), 1)
        lang = "zh" if chinese_ratio > 0.3 else "en"
        
        # Tokenize
        if lang == "zh":
            # Simple character-based tokenization for Chinese
            tokens = re.findall(r"[\u4e00-\u9fa5]{2,}", text)
        else:
            # Word-based tokenization for English
            tokens = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
        
        # Remove stop words
        stop_words = self.STOP_WORDS.get(lang, set())
        tokens = [t for t in tokens if t not in stop_words]
        
        # Count frequencies
        counter = Counter(tokens)
        
        # Get top keywords
        return counter.most_common(top_n)
    
    def cluster(self, documents: List[Tuple[str, str]]) -> List[Topic]:
        """
        Cluster documents by topics.
        
        Args:
            documents: List of (doc_id, text) tuples
            
        Returns:
            List of Topic objects
        """
        # Extract keywords for each document
        doc_keywords: Dict[str, List[Tuple[str, int]]] = {}
        all_keywords: Counter = Counter()
        
        for doc_id, text in documents:
            keywords = self.extract_keywords(text)
            doc_keywords[doc_id] = keywords
            for keyword, count in keywords:
                all_keywords[keyword] += count
        
        # Get significant keywords
        total_docs = len(documents)
        min_count = max(2, int(total_docs * self.keyword_threshold))
        significant_keywords = [
            kw for kw, count in all_keywords.most_common(100)
            if count >= min_count
        ]
        
        # Build keyword-document index
        keyword_docs: Dict[str, List[str]] = defaultdict(list)
        for doc_id, keywords in doc_keywords.items():
            keyword_set = {kw for kw, _ in keywords}
            for kw in significant_keywords:
                if kw in keyword_set:
                    keyword_docs[kw].append(doc_id)
        
        # Create topics from keyword clusters
        topics = []
        used_docs = set()
        
        for keyword, doc_ids in sorted(
            keyword_docs.items(),
            key=lambda x: len(x[1]),
            reverse=True
        ):
            if len(doc_ids) < self.min_cluster_size:
                continue
            
            # Find unique docs for this topic
            unique_docs = [d for d in doc_ids if d not in used_docs]
            if len(unique_docs) < self.min_cluster_size:
                continue
            
            # Create topic
            topic = Topic(
                topic_id=f"topic_{uuid.uuid4().hex[:8]}",
                keywords=[keyword],
                label=keyword,
                document_count=len(unique_docs),
                relevance_score=len(unique_docs) / total_docs,
            )
            
            topics.append(topic)
            
            # Mark docs as used
            used_docs.update(unique_docs)
            
            # Store document-topic mapping
            for doc_id in unique_docs:
                self._document_topics[doc_id] = topic.topic_id
            
            # Stop if max topics reached
            if len(topics) >= self.max_topics:
                break
        
        # Store topics
        for topic in topics:
            self._topics[topic.topic_id] = topic
        
        return topics
    
    def get_document_topic(self, doc_id: str) -> Optional[Topic]:
        """Get topic for a document."""
        topic_id = self._document_topics.get(doc_id)
        if topic_id:
            return self._topics.get(topic_id)
        return None
    
    def get_topic_documents(self, topic_id: str) -> List[str]:
        """Get documents for a topic."""
        return [
            doc_id for doc_id, tid in self._document_topics.items()
            if tid == topic_id
        ]
    
    def label_topic(self, topic: Topic, documents: List[str]) -> str:
        """
        Generate a label for a topic using LLM.
        
        Args:
            topic: Topic to label
            documents: Sample documents from the topic
            
        Returns:
            Generated label
        """
        if not self.llm_client:
            return topic.keywords[0] if topic.keywords else "Unknown"
        
        try:
            sample = " ".join(documents[:5])[:500]
            prompt = f"""为以下文档集合生成一个简洁的主题标签（2-5个字）：

关键词：{', '.join(topic.keywords)}

文档示例：
{sample}

只返回标签，不要其他内容。"""

            label = self.llm_client.generate(prompt).strip()
            return label[:10]  # Limit length
            
        except Exception as e:
            logger.error(f"Topic labeling failed: {e}")
            return topic.keywords[0] if topic.keywords else "Unknown"
    
    def get_stats(self) -> Dict[str, Any]:
        """Get clustering statistics."""
        return {
            "total_topics": len(self._topics),
            "total_documents_clustered": len(self._document_topics),
            "topics": [
                {
                    "id": t.topic_id,
                    "label": t.label,
                    "keywords": t.keywords,
                    "document_count": t.document_count,
                }
                for t in self._topics.values()
            ],
        }
    
    def clear(self):
        """Clear all stored data."""
        self._topics.clear()
        self._document_topics.clear()


class HierarchicalTopicCluster(TopicCluster):
    """
    Hierarchical topic clustering with multiple levels.
    """
    
    def __init__(self, levels: int = 2, **kwargs):
        """
        Initialize hierarchical clusterer.
        
        Args:
            levels: Number of hierarchy levels
            **kwargs: Arguments for base TopicCluster
        """
        super().__init__(**kwargs)
        self.levels = levels
        self._hierarchy: Dict[str, List[str]] = {}  # parent_id -> [child_ids]
    
    def cluster_hierarchical(
        self, documents: List[Tuple[str, str]]
    ) -> Dict[int, List[Topic]]:
        """
        Cluster documents hierarchically.
        
        Args:
            documents: List of (doc_id, text) tuples
            
        Returns:
            Dict mapping level to list of topics
        """
        result = {}
        
        # Level 0: Coarse clustering
        level_0_topics = self.cluster(documents)
        result[0] = level_0_topics
        
        # Additional levels
        for level in range(1, self.levels):
            level_topics = []
            
            for parent_topic in result[level - 1]:
                # Get documents for this parent
                parent_docs = [
                    (doc_id, text) for doc_id, text in documents
                    if self._document_topics.get(doc_id) == parent_topic.topic_id
                ]
                
                if len(parent_docs) >= self.min_cluster_size * 2:
                    # Sub-cluster
                    clusterer = TopicCluster(
                        min_cluster_size=self.min_cluster_size,
                        max_topics=5,
                    )
                    sub_topics = clusterer.cluster(parent_docs)
                    
                    for sub_topic in sub_topics:
                        sub_topic.topic_id = f"{parent_topic.topic_id}_{sub_topic.topic_id}"
                        level_topics.append(sub_topic)
                        
                        # Store hierarchy
                        if parent_topic.topic_id not in self._hierarchy:
                            self._hierarchy[parent_topic.topic_id] = []
                        self._hierarchy[parent_topic.topic_id].append(sub_topic.topic_id)
            
            if level_topics:
                result[level] = level_topics
            else:
                break
        
        return result