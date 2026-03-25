"""
MongoDB 客户端和文档仓库

提供文档的 CRUD 操作和查询功能。
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

from pymongo import MongoClient, ASCENDING, DESCENDING, TEXT
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import ConnectionFailure, DuplicateKeyError


class MongoDBClient:
    """MongoDB 客户端管理器"""
    
    _instance: Optional["MongoDBClient"] = None
    _client: Optional[MongoClient] = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 27017,
        database: str = "guzi_sentiment",
        username: Optional[str] = None,
        password: Optional[str] = None,
        auth_source: str = "admin",
        **kwargs
    ):
        self.host = host
        self.port = port
        self.database_name = database
        self.username = username
        self.password = password
        self.auth_source = auth_source
        self.kwargs = kwargs
        
        if self._client is None:
            self._connect()
    
    def _connect(self) -> None:
        """建立 MongoDB 连接"""
        if self.username and self.password:
            escaped_password = quote_plus(self.password)
            uri = f"mongodb://{self.username}:{escaped_password}@{self.host}:{self.port}/{self.database_name}?authSource={self.auth_source}"
            self._client = MongoClient(uri, **self.kwargs)
        else:
            uri = f"mongodb://{self.host}:{self.port}"
            self._client = MongoClient(uri, **self.kwargs)
        
        # 测试连接
        try:
            self._client.admin.command('ping')
        except ConnectionFailure as e:
            raise ConnectionError(f"Failed to connect to MongoDB: {e}")
    
    @property
    def db(self) -> Database:
        """获取数据库实例"""
        return self._client[self.database_name]
    
    def get_collection(self, name: str) -> Collection:
        """获取集合"""
        return self.db[name]
    
    def close(self) -> None:
        """关闭连接"""
        if self._client:
            self._client.close()
            self._client = None
    
    @classmethod
    def get_instance(cls) -> "MongoDBClient":
        """获取单例实例"""
        if cls._instance is None:
            raise RuntimeError("MongoDBClient not initialized. Call constructor first.")
        return cls._instance


class DocumentRepository:
    """
    文档仓库 - 提供统一的文档 CRUD 操作
    
    支持的集合:
    - raw_documents: 原始采集文档
    - processed_documents: 处理后文档
    - analysis_results: 分析结果
    - events: 事件记录
    - topics: 主题/话题
    - alerts: 预警记录
    """
    
    COLLECTIONS = {
        "raw_documents": "raw_documents",
        "processed_documents": "processed_documents",
        "analysis_results": "analysis_results",
        "events": "events",
        "topics": "topics",
        "alerts": "alerts",
        "daily_reports": "daily_reports",
        "alert_subscriptions": "alert_subscriptions",
    }
    
    def __init__(self, mongodb_client: Optional[MongoDBClient] = None):
        self.client = mongodb_client or MongoDBClient.get_instance()
        self._ensure_indexes()
    
    def _ensure_indexes(self) -> None:
        """确保必要的索引存在"""
        db = self.client.db
        
        # raw_documents 索引
        db.raw_documents.create_index([("doc_id", ASCENDING)], unique=True)
        db.raw_documents.create_index([("platform", ASCENDING)])
        db.raw_documents.create_index([("collected_at", DESCENDING)])
        db.raw_documents.create_index([("content", TEXT)])
        
        # processed_documents 索引
        db.processed_documents.create_index([("doc_id", ASCENDING)], unique=True)
        db.processed_documents.create_index([("raw_doc_id", ASCENDING)])
        db.processed_documents.create_index([("content_hash", ASCENDING)])
        db.processed_documents.create_index([("processed_at", DESCENDING)])
        
        # analysis_results 索引
        db.analysis_results.create_index([("doc_id", ASCENDING)], unique=True)
        db.analysis_results.create_index([("sentiment.label", ASCENDING)])
        db.analysis_results.create_index([("analyzed_at", DESCENDING)])
        
        # events 索引
        db.events.create_index([("event_id", ASCENDING)], unique=True)
        db.events.create_index([("type", ASCENDING)])
        db.events.create_index([("extracted_at", DESCENDING)])
        
        # topics 索引
        db.topics.create_index([("topic_id", ASCENDING)], unique=True)
        db.topics.create_index([("keywords", ASCENDING)])
        
        # alerts 索引
        db.alerts.create_index([("alert_id", ASCENDING)], unique=True)
        db.alerts.create_index([("status", ASCENDING)])
        db.alerts.create_index([("triggered_at", DESCENDING)])
        
        # daily_reports 索引
        db.daily_reports.create_index([("report_id", ASCENDING)], unique=True)
        db.daily_reports.create_index([("report_date", DESCENDING)])
        
        # alert_subscriptions 索引
        db.alert_subscriptions.create_index([("subscription_id", ASCENDING)], unique=True)
        db.alert_subscriptions.create_index([("agent_id", ASCENDING)])
    
    # ==================== 原始文档操作 ====================
    
    def insert_raw_document(self, doc: Dict[str, Any]) -> str:
        """插入原始文档"""
        collection = self.client.get_collection("raw_documents")
        if "collected_at" not in doc:
            doc["collected_at"] = datetime.utcnow()
        
        try:
            result = collection.insert_one(doc)
            return str(result.inserted_id)
        except DuplicateKeyError:
            # 文档已存在，更新它
            collection.update_one(
                {"doc_id": doc["doc_id"]},
                {"$set": doc}
            )
            return doc["doc_id"]
    
    def insert_raw_documents(self, docs: List[Dict[str, Any]]) -> List[str]:
        """批量插入原始文档"""
        collection = self.client.get_collection("raw_documents")
        for doc in docs:
            if "collected_at" not in doc:
                doc["collected_at"] = datetime.utcnow()
        
        result = collection.insert_many(docs, ordered=False)
        return [str(id) for id in result.inserted_ids]
    
    def get_raw_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """获取原始文档"""
        collection = self.client.get_collection("raw_documents")
        return collection.find_one({"doc_id": doc_id})
    
    def find_raw_documents(
        self,
        platform: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
        skip: int = 0
    ) -> List[Dict[str, Any]]:
        """查询原始文档"""
        collection = self.client.get_collection("raw_documents")
        query = {}
        
        if platform:
            query["platform"] = platform
        if start_time or end_time:
            query["collected_at"] = {}
            if start_time:
                query["collected_at"]["$gte"] = start_time
            if end_time:
                query["collected_at"]["$lte"] = end_time
        
        cursor = collection.find(query).sort("collected_at", DESCENDING).skip(skip).limit(limit)
        return list(cursor)
    
    def count_raw_documents(self, platform: Optional[str] = None) -> int:
        """统计原始文档数量"""
        collection = self.client.get_collection("raw_documents")
        query = {}
        if platform:
            query["platform"] = platform
        return collection.count_documents(query)
    
    # ==================== 处理后文档操作 ====================
    
    def insert_processed_document(self, doc: Dict[str, Any]) -> str:
        """插入处理后文档"""
        collection = self.client.get_collection("processed_documents")
        if "processed_at" not in doc:
            doc["processed_at"] = datetime.utcnow()
        
        try:
            result = collection.insert_one(doc)
            return str(result.inserted_id)
        except DuplicateKeyError:
            collection.update_one(
                {"doc_id": doc["doc_id"]},
                {"$set": doc}
            )
            return doc["doc_id"]
    
    def get_processed_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """获取处理后文档"""
        collection = self.client.get_collection("processed_documents")
        return collection.find_one({"doc_id": doc_id})
    
    def find_by_content_hash(self, content_hash: str) -> Optional[Dict[str, Any]]:
        """通过内容哈希查找文档（用于去重）"""
        collection = self.client.get_collection("processed_documents")
        return collection.find_one({"content_hash": content_hash})
    
    # ==================== 分析结果操作 ====================
    
    def insert_analysis_result(self, result: Dict[str, Any]) -> str:
        """插入分析结果"""
        collection = self.client.get_collection("analysis_results")
        if "analyzed_at" not in result:
            result["analyzed_at"] = datetime.utcnow()
        
        try:
            insert_result = collection.insert_one(result)
            return str(insert_result.inserted_id)
        except DuplicateKeyError:
            collection.update_one(
                {"doc_id": result["doc_id"]},
                {"$set": result}
            )
            return result["doc_id"]
    
    def get_analysis_result(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """获取分析结果"""
        collection = self.client.get_collection("analysis_results")
        return collection.find_one({"doc_id": doc_id})
    
    def find_by_sentiment(
        self,
        label: str,
        min_score: Optional[float] = None,
        max_score: Optional[float] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """按情感查找分析结果"""
        collection = self.client.get_collection("analysis_results")
        query = {"sentiment.label": label}
        
        if min_score is not None or max_score is not None:
            query["sentiment.score"] = {}
            if min_score is not None:
                query["sentiment.score"]["$gte"] = min_score
            if max_score is not None:
                query["sentiment.score"]["$lte"] = max_score
        
        cursor = collection.find(query).sort("analyzed_at", DESCENDING).limit(limit)
        return list(cursor)
    
    # ==================== 事件操作 ====================
    
    def insert_event(self, event: Dict[str, Any]) -> str:
        """插入事件"""
        collection = self.client.get_collection("events")
        if "extracted_at" not in event:
            event["extracted_at"] = datetime.utcnow()
        
        try:
            result = collection.insert_one(event)
            return str(result.inserted_id)
        except DuplicateKeyError:
            collection.update_one(
                {"event_id": event["event_id"]},
                {"$set": event}
            )
            return event["event_id"]
    
    def find_events(
        self,
        event_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """查询事件"""
        collection = self.client.get_collection("events")
        query = {}
        
        if event_type:
            query["type"] = event_type
        if start_time or end_time:
            query["extracted_at"] = {}
            if start_time:
                query["extracted_at"]["$gte"] = start_time
            if end_time:
                query["extracted_at"]["$lte"] = end_time
        
        cursor = collection.find(query).sort("extracted_at", DESCENDING).limit(limit)
        return list(cursor)
    
    # ==================== 主题操作 ====================
    
    def upsert_topic(self, topic: Dict[str, Any]) -> str:
        """插入或更新主题"""
        collection = self.client.get_collection("topics")
        if "created_at" not in topic:
            topic["created_at"] = datetime.utcnow()
        
        collection.update_one(
            {"topic_id": topic["topic_id"]},
            {"$set": topic},
            upsert=True
        )
        return topic["topic_id"]
    
    def find_topics(self, keywords: Optional[List[str]] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """查询主题"""
        collection = self.client.get_collection("topics")
        query = {}
        
        if keywords:
            query["keywords"] = {"$in": keywords}
        
        cursor = collection.find(query).sort("document_count", DESCENDING).limit(limit)
        return list(cursor)
    
    # ==================== 预警操作 ====================
    
    def insert_alert(self, alert: Dict[str, Any]) -> str:
        """插入预警记录"""
        collection = self.client.get_collection("alerts")
        if "triggered_at" not in alert:
            alert["triggered_at"] = datetime.utcnow()
        
        result = collection.insert_one(alert)
        return str(result.inserted_id)
    
    def find_alerts(
        self,
        status: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """查询预警"""
        collection = self.client.get_collection("alerts")
        query = {}
        
        if status:
            query["status"] = status
        if start_time or end_time:
            query["triggered_at"] = {}
            if start_time:
                query["triggered_at"]["$gte"] = start_time
            if end_time:
                query["triggered_at"]["$lte"] = end_time
        
        cursor = collection.find(query).sort("triggered_at", DESCENDING).limit(limit)
        return list(cursor)
    
    def update_alert_status(self, alert_id: str, status: str) -> bool:
        """更新预警状态"""
        collection = self.client.get_collection("alerts")
        result = collection.update_one(
            {"alert_id": alert_id},
            {"$set": {"status": status, "updated_at": datetime.utcnow()}}
        )
        return result.modified_count > 0
    
    # ==================== 日报操作 ====================
    
    def insert_daily_report(self, report: Dict[str, Any]) -> str:
        """插入日报"""
        collection = self.client.get_collection("daily_reports")
        if "created_at" not in report:
            report["created_at"] = datetime.utcnow()
        
        try:
            result = collection.insert_one(report)
            return str(result.inserted_id)
        except DuplicateKeyError:
            collection.update_one(
                {"report_id": report["report_id"]},
                {"$set": report}
            )
            return report["report_id"]
    
    def get_daily_report(self, report_date: str) -> Optional[Dict[str, Any]]:
        """获取指定日期的日报"""
        collection = self.client.get_collection("daily_reports")
        return collection.find_one({"report_date": report_date})
    
    def find_daily_reports(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 30
    ) -> List[Dict[str, Any]]:
        """查询日报"""
        collection = self.client.get_collection("daily_reports")
        query = {}
        
        if start_date or end_date:
            query["report_date"] = {}
            if start_date:
                query["report_date"]["$gte"] = start_date
            if end_date:
                query["report_date"]["$lte"] = end_date
        
        cursor = collection.find(query).sort("report_date", DESCENDING).limit(limit)
        return list(cursor)
    
    # ==================== 预警订阅操作 ====================
    
    def insert_alert_subscription(self, subscription: Dict[str, Any]) -> str:
        """插入预警订阅"""
        collection = self.client.get_collection("alert_subscriptions")
        if "created_at" not in subscription:
            subscription["created_at"] = datetime.utcnow()
        subscription["status"] = "active"
        
        try:
            result = collection.insert_one(subscription)
            return str(result.inserted_id)
        except DuplicateKeyError:
            collection.update_one(
                {"subscription_id": subscription["subscription_id"]},
                {"$set": subscription}
            )
            return subscription["subscription_id"]
    
    def find_alert_subscriptions(
        self,
        agent_id: Optional[str] = None,
        status: str = "active"
    ) -> List[Dict[str, Any]]:
        """查询预警订阅"""
        collection = self.client.get_collection("alert_subscriptions")
        query = {"status": status}
        
        if agent_id:
            query["agent_id"] = agent_id
        
        return list(collection.find(query))
    
    def delete_alert_subscription(self, subscription_id: str) -> bool:
        """删除预警订阅"""
        collection = self.client.get_collection("alert_subscriptions")
        result = collection.update_one(
            {"subscription_id": subscription_id},
            {"$set": {"status": "deleted", "deleted_at": datetime.utcnow()}}
        )
        return result.modified_count > 0
    
    # ==================== 统计操作 ====================
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计数据"""
        db = self.client.db
        
        return {
            "raw_documents": db.raw_documents.count_documents({}),
            "processed_documents": db.processed_documents.count_documents({}),
            "analysis_results": db.analysis_results.count_documents({}),
            "events": db.events.count_documents({}),
            "topics": db.topics.count_documents({}),
            "alerts": db.alerts.count_documents({}),
            "daily_reports": db.daily_reports.count_documents({}),
        }
    
    def get_sentiment_statistics(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """获取情感统计"""
        collection = self.client.get_collection("analysis_results")
        match = {}
        
        if start_time or end_time:
            match["analyzed_at"] = {}
            if start_time:
                match["analyzed_at"]["$gte"] = start_time
            if end_time:
                match["analyzed_at"]["$lte"] = end_time
        
        pipeline = [
            {"$match": match},
            {"$group": {
                "_id": "$sentiment.label",
                "count": {"$sum": 1},
                "avg_score": {"$avg": "$sentiment.score"}
            }}
        ]
        
        results = list(collection.aggregate(pipeline))
        
        stats = {
            "positive": {"count": 0, "avg_score": 0.0},
            "negative": {"count": 0, "avg_score": 0.0},
            "neutral": {"count": 0, "avg_score": 0.0},
            "total": 0
        }
        
        for r in results:
            label = r["_id"]
            if label in stats:
                stats[label]["count"] = r["count"]
                stats[label]["avg_score"] = r["avg_score"]
                stats["total"] += r["count"]
        
        return stats