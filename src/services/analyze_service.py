"""
分析服务

整合分析引擎，提供情感分析、实体识别、事件提取等功能。
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import uuid
import asyncio

from ..analyzer.engine import AnalysisEngine
from ..analyzer.models import SentimentLabel, SentimentResult
from ..storage.repository import SentimentRepository


class AnalyzeService:
    """
    分析服务
    
    负责:
    - 情感分析
    - 实体识别
    - 事件提取
    - 主题聚类
    """
    
    def __init__(
        self,
        repository: SentimentRepository,
        analysis_engine: Optional[AnalysisEngine] = None,
    ):
        self.repository = repository
        self.engine = analysis_engine or AnalysisEngine()
        self._analysis_cache: Dict[str, Dict[str, Any]] = {}
    
    # ==================== 情感分析 ====================
    
    async def analyze_sentiment(
        self,
        texts: List[str],
        model: str = "default"
    ) -> List[Dict[str, Any]]:
        """
        批量情感分析
        
        Args:
            texts: 文本列表
            model: 分析模型
        
        Returns:
            情感分析结果列表
        """
        results = []
        
        for text in texts:
            # 检查缓存
            cached = self.repository.cache.get_cached_sentiment(text) if self.repository.cache else None
            
            if cached:
                results.append(cached)
            else:
                # 执行分析
                result = await self.engine.analyze_sentiment(text, model)
                
                # 格式化结果
                sentiment_data = {
                    "label": result.label.value if hasattr(result.label, "value") else result.label,
                    "score": result.score,
                    "confidence": result.confidence,
                    "model": result.model
                }
                
                # 缓存结果
                if self.repository.cache:
                    self.repository.cache.cache_sentiment(text, sentiment_data)
                
                results.append(sentiment_data)
        
        return results
    
    def analyze_sentiment_sync(
        self,
        texts: List[str],
        model: str = "default"
    ) -> List[Dict[str, Any]]:
        """同步情感分析"""
        return asyncio.run(self.analyze_sentiment(texts, model))
    
    async def analyze_document_sentiment(
        self,
        doc_id: str
    ) -> Dict[str, Any]:
        """
        分析文档情感
        
        Args:
            doc_id: 文档ID
        
        Returns:
            分析结果
        """
        # 获取文档
        doc = self.repository.get_raw_document(doc_id)
        if not doc:
            return {"error": f"Document not found: {doc_id}"}
        
        # 获取处理后的内容
        processed = self.repository.doc_repo.get_processed_document(doc_id)
        text = processed.get("normalized_content") if processed else doc.get("content", "")
        
        if not text:
            return {"error": "No content to analyze"}
        
        # 执行分析
        sentiment_results = await self.analyze_sentiment([text])
        
        # 保存结果
        result = {
            "doc_id": doc_id,
            "sentiment": sentiment_results[0] if sentiment_results else None,
            "analyzed_at": datetime.utcnow().isoformat()
        }
        
        self.repository.save_analysis_result(result)
        
        return result
    
    # ==================== 实体识别 ====================
    
    async def extract_entities(
        self,
        texts: List[str]
    ) -> List[List[Dict[str, Any]]]:
        """
        批量实体识别
        
        Args:
            texts: 文本列表
        
        Returns:
            实体列表的列表
        """
        results = []
        
        for text in texts:
            entities = await self.engine.extract_entities(text)
            
            entity_list = [
                {
                    "text": e.text,
                    "type": e.type.value if hasattr(e.type, "value") else e.type,
                    "start": e.start,
                    "end": e.end,
                    "confidence": e.confidence
                }
                for e in entities
            ]
            
            results.append(entity_list)
        
        return results
    
    def extract_entities_sync(
        self,
        texts: List[str]
    ) -> List[List[Dict[str, Any]]]:
        """同步实体识别"""
        return asyncio.run(self.extract_entities(texts))
    
    # ==================== 事件提取 ====================
    
    async def extract_events(
        self,
        texts: List[str],
        doc_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        批量事件提取
        
        Args:
            texts: 文本列表
            doc_ids: 文档ID列表 (可选)
        
        Returns:
            事件列表
        """
        all_events = []
        
        for i, text in enumerate(texts):
            events = self.engine.get_document_events(text)
            doc_id = doc_ids[i] if doc_ids else None
            
            for event in events:
                event_data = {
                    "event_id": str(uuid.uuid4()),
                    "doc_id": doc_id,
                    "type": event.type.value if hasattr(event.type, "value") else event.type,
                    "title": event.title,
                    "description": event.description,
                    "entities": event.entities,
                    "confidence": event.confidence,
                    "extracted_at": datetime.utcnow().isoformat()
                }
                
                # 保存事件
                self.repository.save_event(event_data)
                all_events.append(event_data)
        
        return all_events
    
    def extract_events_sync(
        self,
        texts: List[str],
        doc_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """同步事件提取"""
        return asyncio.run(self.extract_events(texts, doc_ids))
    
    # ==================== 主题聚类 ====================
    
    async def cluster_topics(
        self,
        texts: List[str],
        doc_ids: Optional[List[str]] = None,
        n_topics: int = 10
    ) -> List[Dict[str, Any]]:
        """
        主题聚类
        
        Args:
            texts: 文本列表
            doc_ids: 文档ID列表
            n_topics: 主题数量
        
        Returns:
            主题列表
        """
        topics = await self.engine.cluster_topics(texts, n_topics)
        
        topic_list = []
        for topic in topics:
            topic_data = {
                "topic_id": str(uuid.uuid4()),
                "keywords": topic.keywords,
                "label": topic.label,
                "document_count": topic.document_count,
                "relevance_score": topic.relevance_score,
                "created_at": datetime.utcnow().isoformat()
            }
            
            # 保存主题
            self.repository.doc_repo.upsert_topic(topic_data)
            topic_list.append(topic_data)
        
        return topic_list
    
    def cluster_topics_sync(
        self,
        texts: List[str],
        doc_ids: Optional[List[str]] = None,
        n_topics: int = 10
    ) -> List[Dict[str, Any]]:
        """同步主题聚类"""
        return asyncio.run(self.cluster_topics(texts, doc_ids, n_topics))
    
    # ==================== 完整分析 ====================
    
    async def analyze_document(
        self,
        doc_id: str,
        include_entities: bool = True,
        include_events: bool = True,
        include_topics: bool = False
    ) -> Dict[str, Any]:
        """
        完整文档分析
        
        Args:
            doc_id: 文档ID
            include_entities: 是否包含实体识别
            include_events: 是否包含事件提取
            include_topics: 是否包含主题聚类
        
        Returns:
            完整分析结果
        """
        # 获取文档
        doc = self.repository.get_raw_document(doc_id)
        if not doc:
            return {"error": f"Document not found: {doc_id}"}
        
        # 获取处理后的内容
        processed = self.repository.doc_repo.get_processed_document(doc_id)
        text = processed.get("normalized_content") if processed else doc.get("content", "")
        
        if not text:
            return {"error": "No content to analyze"}
        
        result = {
            "doc_id": doc_id,
            "analyzed_at": datetime.utcnow().isoformat()
        }
        
        # 情感分析
        sentiment_results = await self.analyze_sentiment([text])
        result["sentiment"] = sentiment_results[0] if sentiment_results else None
        
        # 实体识别
        if include_entities:
            entity_results = await self.extract_entities([text])
            result["entities"] = entity_results[0] if entity_results else []
        
        # 事件提取
        if include_events:
            event_results = await self.extract_events([text], [doc_id])
            result["events"] = event_results
        
        # 主题聚类 (需要批量处理)
        # result["topics"] = ...
        
        # 保存结果
        self.repository.save_analysis_result(result)
        
        return result
    
    async def analyze_batch(
        self,
        doc_ids: List[str],
        include_entities: bool = True,
        include_events: bool = True
    ) -> List[Dict[str, Any]]:
        """
        批量文档分析
        
        Args:
            doc_ids: 文档ID列表
            include_entities: 是否包含实体识别
            include_events: 是否包含事件提取
        
        Returns:
            分析结果列表
        """
        results = []
        
        for doc_id in doc_ids:
            result = await self.analyze_document(
                doc_id,
                include_entities=include_entities,
                include_events=include_events
            )
            results.append(result)
        
        return results
    
    # ==================== 统计分析 ====================
    
    def get_sentiment_distribution(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """获取情感分布统计"""
        return self.repository.get_sentiment_statistics(start_time, end_time)
    
    def get_trending_entities(
        self,
        entity_type: Optional[str] = None,
        days: int = 7,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """获取热门实体"""
        # 从分析结果中聚合
        start_time = datetime.utcnow() - timedelta(days=days)
        
        pipeline = [
            {"$match": {"analyzed_at": {"$gte": start_time}}},
            {"$unwind": "$entities"},
            {"$group": {
                "_id": {"text": "$entities.text", "type": "$entities.type"},
                "count": {"$sum": 1},
                "avg_confidence": {"$avg": "$entities.confidence"}
            }},
            {"$sort": {"count": -1}},
            {"$limit": limit}
        ]
        
        if entity_type:
            pipeline[0]["$match"]["entities.type"] = entity_type
        
        results = list(self.repository.doc_repo.client.db.analysis_results.aggregate(pipeline))
        
        return [
            {
                "text": r["_id"]["text"],
                "type": r["_id"]["type"],
                "count": r["count"],
                "avg_confidence": r["avg_confidence"]
            }
            for r in results
        ]
    
    def get_sentiment_trend(
        self,
        topic: Optional[str] = None,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """获取情感趋势"""
        start_time = datetime.utcnow() - timedelta(days=days)
        
        # 按日期分组统计
        pipeline = [
            {"$match": {"analyzed_at": {"$gte": start_time}}},
            {"$group": {
                "_id": {
                    "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$analyzed_at"}},
                    "label": "$sentiment.label"
                },
                "count": {"$sum": 1},
                "avg_score": {"$avg": "$sentiment.score"}
            }},
            {"$sort": {"_id.date": 1}}
        ]
        
        results = list(self.repository.doc_repo.client.db.analysis_results.aggregate(pipeline))
        
        # 格式化为趋势数据
        trend_data = {}
        for r in results:
            date = r["_id"]["date"]
            label = r["_id"]["label"]
            
            if date not in trend_data:
                trend_data[date] = {"date": date, "positive": 0, "negative": 0, "neutral": 0}
            
            trend_data[date][label] = r["count"]
            trend_data[date][f"{label}_avg_score"] = r["avg_score"]
        
        return list(trend_data.values())