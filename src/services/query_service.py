"""
查询服务

提供对话式数据查询和语义搜索功能。
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import re

from ..storage.repository import SentimentRepository


class QueryService:
    """
    查询服务
    
    负责:
    - 自然语言查询解析
    - 语义搜索
    - 数据聚合和统计
    """
    
    # 时间范围表达式
    TIME_EXPRESSIONS = {
        "今天": timedelta(days=0),
        "昨天": timedelta(days=1),
        "本周": timedelta(weeks=1),
        "上周": timedelta(weeks=2),
        "本月": timedelta(days=30),
        "上月": timedelta(days=60),
        "最近三天": timedelta(days=3),
        "最近一周": timedelta(weeks=1),
        "最近一个月": timedelta(days=30),
        "past_day": timedelta(days=1),
        "past_week": timedelta(weeks=1),
        "past_month": timedelta(days=30),
        "1d": timedelta(days=1),
        "7d": timedelta(weeks=1),
        "30d": timedelta(days=30),
    }
    
    def __init__(
        self,
        repository: SentimentRepository,
        llm_client: Optional[Any] = None
    ):
        self.repository = repository
        self.llm_client = llm_client
    
    # ==================== 自然语言查询 ====================
    
    async def query(self, query_text: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        自然语言查询
        
        Args:
            query_text: 查询文本
            context: 查询上下文
        
        Returns:
            查询结果
        """
        # 解析查询意图
        intent = await self._parse_intent(query_text)
        
        # 根据意图执行查询
        if intent["type"] == "sentiment":
            return await self._query_sentiment(intent)
        elif intent["type"] == "events":
            return await self._query_events(intent)
        elif intent["type"] == "documents":
            return await self._query_documents(intent)
        elif intent["type"] == "statistics":
            return await self._query_statistics(intent)
        elif intent["type"] == "search":
            return await self._semantic_search(intent)
        else:
            return {
                "success": False,
                "error": f"Unknown query type: {intent['type']}",
                "query": query_text
            }
    
    async def _parse_intent(self, query_text: str) -> Dict[str, Any]:
        """
        解析查询意图
        
        支持的意图类型:
        - sentiment: 情感查询
        - events: 事件查询
        - documents: 文档查询
        - statistics: 统计查询
        - search: 语义搜索
        """
        query_lower = query_text.lower()
        
        intent = {
            "type": "search",
            "params": {},
            "original_query": query_text
        }
        
        # 解析时间范围
        time_range = self._parse_time_range(query_text)
        if time_range:
            intent["params"]["time_range"] = time_range
        
        # 解析情感标签
        if "负面" in query_text or "negative" in query_lower:
            intent["params"]["sentiment"] = "negative"
            if "情感" in query_text or "情绪" in query_text:
                intent["type"] = "sentiment"
        elif "正面" in query_text or "positive" in query_lower:
            intent["params"]["sentiment"] = "positive"
            if "情感" in query_text or "情绪" in query_text:
                intent["type"] = "sentiment"
        
        # 解析事件查询
        if "事件" in query_text or "event" in query_lower:
            intent["type"] = "events"
            
            # 解析事件类型
            event_types = ["选举", "政策", "经济", "社会", "丑闻", "灾难", "突破"]
            for et in event_types:
                if et in query_text:
                    intent["params"]["event_type"] = et
                    break
        
        # 解析统计查询
        if "统计" in query_text or "多少" in query_text or "数量" in query_text:
            intent["type"] = "statistics"
        
        # 解析文档查询
        if "文档" in query_text or "内容" in query_text or "文章" in query_text:
            intent["type"] = "documents"
        
        # 如果没有明确类型，使用语义搜索
        if intent["type"] == "search":
            intent["params"]["query_text"] = query_text
        
        return intent
    
    def _parse_time_range(self, query_text: str) -> Optional[Dict[str, datetime]]:
        """解析时间范围"""
        end_time = datetime.utcnow()
        
        for expr, delta in self.TIME_EXPRESSIONS.items():
            if expr in query_text:
                start_time = end_time - delta
                return {
                    "start": start_time,
                    "end": end_time
                }
        
        # 尝试解析具体日期
        date_patterns = [
            (r"(\d{4})-(\d{2})-(\d{2})", "%Y-%m-%d"),
            (r"(\d{2})/(\d{2})", "%m/%d"),
        ]
        
        for pattern, date_format in date_patterns:
            match = re.search(pattern, query_text)
            if match:
                try:
                    date_str = match.group(0)
                    parsed_date = datetime.strptime(date_str, date_format)
                    
                    # 如果只有月日，补充年份
                    if date_format == "%m/%d":
                        parsed_date = parsed_date.replace(year=end_time.year)
                    
                    return {
                        "start": parsed_date.replace(hour=0, minute=0, second=0),
                        "end": parsed_date.replace(hour=23, minute=59, second=59)
                    }
                except ValueError:
                    continue
        
        return None
    
    # ==================== 查询执行 ====================
    
    async def _query_sentiment(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """情感查询"""
        params = intent["params"]
        time_range = params.get("time_range", {})
        
        start_time = time_range.get("start")
        end_time = time_range.get("end")
        
        stats = self.repository.get_sentiment_statistics(start_time, end_time)
        
        sentiment = params.get("sentiment")
        if sentiment:
            docs = self.repository.find_by_sentiment(sentiment, limit=50)
            return {
                "success": True,
                "type": "sentiment",
                "stats": stats,
                "documents": docs[:10],
                "total": len(docs)
            }
        
        return {
            "success": True,
            "type": "sentiment",
            "stats": stats
        }
    
    async def _query_events(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """事件查询"""
        params = intent["params"]
        time_range = params.get("time_range", {})
        
        start_time = time_range.get("start")
        end_time = time_range.get("end")
        event_type = params.get("event_type")
        
        events = self.repository.find_events(
            event_type=event_type,
            start_time=start_time,
            end_time=end_time,
            limit=100
        )
        
        return {
            "success": True,
            "type": "events",
            "events": events[:20],
            "total": len(events),
            "event_type": event_type
        }
    
    async def _query_documents(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """文档查询"""
        params = intent["params"]
        time_range = params.get("time_range", {})
        
        start_time = time_range.get("start")
        end_time = time_range.get("end")
        
        docs = self.repository.find_documents(
            start_time=start_time,
            end_time=end_time,
            limit=100
        )
        
        return {
            "success": True,
            "type": "documents",
            "documents": docs[:20],
            "total": len(docs)
        }
    
    async def _query_statistics(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """统计查询"""
        stats = self.repository.get_statistics()
        
        params = intent["params"]
        time_range = params.get("time_range", {})
        
        start_time = time_range.get("start")
        end_time = time_range.get("end")
        
        sentiment_stats = self.repository.get_sentiment_statistics(start_time, end_time)
        
        return {
            "success": True,
            "type": "statistics",
            "overall": stats,
            "sentiment": sentiment_stats,
            "time_range": {
                "start": start_time.isoformat() if start_time else None,
                "end": end_time.isoformat() if end_time else None
            }
        }
    
    async def _semantic_search(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """语义搜索"""
        query_text = intent["params"].get("query_text", intent["original_query"])
        sentiment = intent["params"].get("sentiment")
        
        try:
            results = self.repository.semantic_search(
                query=query_text,
                n_results=20,
                sentiment=sentiment
            )
            
            return {
                "success": True,
                "type": "search",
                "query": query_text,
                "results": results,
                "total": len(results)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "query": query_text
            }
    
    # ==================== 结构化查询 ====================
    
    def find_documents_by_keywords(
        self,
        keywords: List[str],
        platform: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """按关键词查找文档"""
        # 使用 MongoDB 文本搜索
        collection = self.repository.doc_repo.client.get_collection("raw_documents")
        
        query = {}
        
        if keywords:
            query["$text"] = {"$search": " ".join(keywords)}
        
        if platform:
            query["platform"] = platform
        
        if start_time or end_time:
            query["collected_at"] = {}
            if start_time:
                query["collected_at"]["$gte"] = start_time
            if end_time:
                query["collected_at"]["$lte"] = end_time
        
        cursor = collection.find(query).sort("collected_at", -1).limit(limit)
        return list(cursor)
    
    def find_similar_documents(
        self,
        doc_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """查找相似文档"""
        return self.repository.find_similar_documents(doc_id, limit)
    
    def get_document_timeline(
        self,
        topic: Optional[str] = None,
        platform: Optional[str] = None,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """获取文档时间线"""
        start_time = datetime.utcnow() - timedelta(days=days)
        
        pipeline = [
            {"$match": {
                "collected_at": {"$gte": start_time}
            }},
            {"$group": {
                "_id": {
                    "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$collected_at"}},
                    "platform": "$platform"
                },
                "count": {"$sum": 1}
            }},
            {"$sort": {"_id.date": 1}}
        ]
        
        if topic:
            pipeline[0]["$match"]["$text"] = {"$search": topic}
        
        if platform:
            pipeline[0]["$match"]["platform"] = platform
        
        collection = self.repository.doc_repo.client.get_collection("raw_documents")
        results = list(collection.aggregate(pipeline))
        
        return [
            {
                "date": r["_id"]["date"],
                "platform": r["_id"]["platform"],
                "count": r["count"]
            }
            for r in results
        ]
    
    # ==================== 聚合查询 ====================
    
    def get_platform_distribution(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, int]:
        """获取平台分布"""
        pipeline = [
            {"$match": {}},
            {"$group": {
                "_id": "$platform",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}}
        ]
        
        if start_time or end_time:
            pipeline[0]["$match"]["collected_at"] = {}
            if start_time:
                pipeline[0]["$match"]["collected_at"]["$gte"] = start_time
            if end_time:
                pipeline[0]["$match"]["collected_at"]["$lte"] = end_time
        
        collection = self.repository.doc_repo.client.get_collection("raw_documents")
        results = list(collection.aggregate(pipeline))
        
        return {r["_id"]: r["count"] for r in results if r["_id"]}
    
    def get_entity_mentions(
        self,
        entity_text: str,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """获取实体提及历史"""
        start_time = datetime.utcnow() - timedelta(days=days)
        
        pipeline = [
            {"$match": {
                "analyzed_at": {"$gte": start_time},
                "entities.text": entity_text
            }},
            {"$project": {
                "doc_id": 1,
                "sentiment": 1,
                "analyzed_at": 1,
                "entity": {
                    "$filter": {
                        "input": "$entities",
                        "as": "e",
                        "cond": {"$eq": ["$$e.text", entity_text]}
                    }
                }
            }},
            {"$sort": {"analyzed_at": -1}},
            {"$limit": 100}
        ]
        
        collection = self.repository.doc_repo.client.get_collection("analysis_results")
        results = list(collection.aggregate(pipeline))
        
        return [
            {
                "doc_id": r["doc_id"],
                "sentiment": r.get("sentiment"),
                "analyzed_at": r.get("analyzed_at"),
                "entity": r["entity"][0] if r.get("entity") else None
            }
            for r in results
        ]
    
    # ==================== 便捷方法 ====================
    
    def get_today_summary(self) -> Dict[str, Any]:
        """获取今日摘要"""
        today = datetime.utcnow().replace(hour=0, minute=0, second=0)
        
        stats = self.repository.get_sentiment_statistics(today)
        events = self.repository.find_events(start_time=today, limit=10)
        
        return {
            "date": today.strftime("%Y-%m-%d"),
            "total_documents": stats.get("total", 0),
            "sentiment_distribution": {
                "positive": stats.get("positive", {}).get("count", 0),
                "negative": stats.get("negative", {}).get("count", 0),
                "neutral": stats.get("neutral", {}).get("count", 0)
            },
            "events_count": len(events),
            "top_events": events[:5]
        }
    
    def get_weekly_overview(self) -> Dict[str, Any]:
        """获取本周概览"""
        start_time = datetime.utcnow() - timedelta(weeks=1)
        
        stats = self.repository.get_sentiment_statistics(start_time)
        events = self.repository.find_events(start_time=start_time, limit=50)
        
        return {
            "period": "past_week",
            "total_documents": stats.get("total", 0),
            "daily_average": stats.get("total", 0) // 7,
            "sentiment_distribution": {
                "positive": stats.get("positive", {}).get("count", 0),
                "negative": stats.get("negative", {}).get("count", 0),
                "neutral": stats.get("neutral", {}).get("count", 0)
            },
            "events_count": len(events),
            "trending_topics": self.repository.get_trending_topics(days=7, limit=10)
        }