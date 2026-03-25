"""
舆情数据仓库

提供统一的数据访问接口，整合 MongoDB、Redis 和向量存储。
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import uuid

from .mongodb import MongoDBClient, DocumentRepository
from .redis_client import RedisClient, CacheManager, TaskQueue
from .vector_store import VectorStore, EmbeddingService


class SentimentRepository:
    """
    舆情数据仓库
    
    整合所有存储服务，提供统一的数据访问接口。
    """
    
    def __init__(
        self,
        mongodb_client: Optional[MongoDBClient] = None,
        redis_client: Optional[RedisClient] = None,
        vector_store: Optional[VectorStore] = None,
    ):
        self.mongodb = mongodb_client
        self.redis = redis_client
        self.doc_repo = DocumentRepository(mongodb_client) if mongodb_client else None
        self.cache = CacheManager(redis_client) if redis_client else None
        self.task_queue = TaskQueue(redis_client) if redis_client else None
        self.vector_store = vector_store
    
    @classmethod
    def create(
        cls,
        mongo_host: str = "localhost",
        mongo_port: int = 27017,
        mongo_db: str = "guzi_sentiment",
        redis_host: str = "localhost",
        redis_port: int = 6379,
        vector_persist_dir: Optional[str] = None,
    ) -> "SentimentRepository":
        """工厂方法创建仓库实例"""
        mongodb = MongoDBClient(host=mongo_host, port=mongo_port, database=mongo_db)
        redis = RedisClient(host=redis_host, port=redis_port)
        vector_store = VectorStore(persist_directory=vector_persist_dir)
        
        return cls(
            mongodb_client=mongodb,
            redis_client=redis,
            vector_store=vector_store
        )
    
    # ==================== 文档操作 ====================
    
    def save_raw_document(self, doc: Dict[str, Any]) -> str:
        """保存原始文档"""
        if not doc.get("doc_id"):
            doc["doc_id"] = str(uuid.uuid4())
        
        doc_id = self.doc_repo.insert_raw_document(doc)
        
        # 缓存
        if self.cache:
            self.cache.set_json(f"doc:{doc_id}", doc, ttl=3600)
        
        return doc_id
    
    def save_raw_documents(self, docs: List[Dict[str, Any]]) -> List[str]:
        """批量保存原始文档"""
        for doc in docs:
            if not doc.get("doc_id"):
                doc["doc_id"] = str(uuid.uuid4())
        
        return self.doc_repo.insert_raw_documents(docs)
    
    def get_raw_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """获取原始文档"""
        # 先查缓存
        if self.cache:
            cached = self.cache.get_json(f"doc:{doc_id}")
            if cached:
                return cached
        
        # 查数据库
        doc = self.doc_repo.get_raw_document(doc_id)
        if doc and self.cache:
            self.cache.set_json(f"doc:{doc_id}", doc, ttl=3600)
        
        return doc
    
    def find_documents(
        self,
        platform: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
        skip: int = 0
    ) -> List[Dict[str, Any]]:
        """查询文档"""
        return self.doc_repo.find_raw_documents(
            platform=platform,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            skip=skip
        )
    
    # ==================== 分析结果操作 ====================
    
    def save_analysis_result(self, result: Dict[str, Any]) -> str:
        """保存分析结果"""
        if not result.get("doc_id"):
            result["doc_id"] = str(uuid.uuid4())
        
        doc_id = self.doc_repo.insert_analysis_result(result)
        
        # 更新向量索引
        if self.vector_store and result.get("processed_content") or result.get("content"):
            text = result.get("processed_content") or result.get("content", "")
            sentiment = result.get("sentiment", {}).get("label", "neutral")
            
            self.vector_store.add_document(
                document={"content": text, "doc_id": doc_id},
                doc_id=doc_id,
                metadata={
                    "doc_id": doc_id,
                    "sentiment": sentiment,
                    "platform": result.get("platform", ""),
                }
            )
        
        # 缓存情感结果
        if self.cache and result.get("sentiment"):
            sentiment_data = result["sentiment"]
            text = result.get("processed_content") or result.get("content", "")
            self.cache.cache_sentiment(text, sentiment_data)
        
        return doc_id
    
    def get_analysis_result(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """获取分析结果"""
        if self.cache:
            cached = self.cache.get_json(f"analysis:{doc_id}")
            if cached:
                return cached
        
        result = self.doc_repo.get_analysis_result(doc_id)
        if result and self.cache:
            self.cache.set_json(f"analysis:{doc_id}", result, ttl=3600)
        
        return result
    
    def find_by_sentiment(
        self,
        label: str,
        min_score: Optional[float] = None,
        max_score: Optional[float] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """按情感查找"""
        return self.doc_repo.find_by_sentiment(
            label=label,
            min_score=min_score,
            max_score=max_score,
            limit=limit
        )
    
    # ==================== 事件操作 ====================
    
    def save_event(self, event: Dict[str, Any]) -> str:
        """保存事件"""
        if not event.get("event_id"):
            event["event_id"] = str(uuid.uuid4())
        
        event_id = self.doc_repo.insert_event(event)
        
        # 发布事件通知
        if self.task_queue:
            self.task_queue.publish_event({
                "event_id": event_id,
                "type": event.get("type"),
                "title": event.get("title"),
                "triggered_at": datetime.utcnow().isoformat()
            })
        
        return event_id
    
    def find_events(
        self,
        event_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """查询事件"""
        return self.doc_repo.find_events(
            event_type=event_type,
            start_time=start_time,
            end_time=end_time,
            limit=limit
        )
    
    # ==================== 预警操作 ====================
    
    def create_alert(self, alert: Dict[str, Any]) -> str:
        """创建预警"""
        if not alert.get("alert_id"):
            alert["alert_id"] = str(uuid.uuid4())
        
        alert_id = self.doc_repo.insert_alert(alert)
        
        # 入队预警任务
        if self.task_queue:
            self.task_queue.enqueue_alert_task({
                "alert_id": alert_id,
                "type": alert.get("type"),
                "severity": alert.get("severity"),
                "message": alert.get("message"),
                "data": alert.get("data")
            })
        
        return alert_id
    
    def get_pending_alerts(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取待处理预警"""
        return self.doc_repo.find_alerts(status="pending", limit=limit)
    
    def resolve_alert(self, alert_id: str) -> bool:
        """解决预警"""
        return self.doc_repo.update_alert_status(alert_id, "resolved")
    
    # ==================== 日报操作 ====================
    
    def save_daily_report(self, report: Dict[str, Any]) -> str:
        """保存日报"""
        if not report.get("report_id"):
            report["report_id"] = str(uuid.uuid4())
        
        if not report.get("report_date"):
            report["report_date"] = datetime.utcnow().strftime("%Y-%m-%d")
        
        report_id = self.doc_repo.insert_daily_report(report)
        
        # 发布报告通知
        if self.task_queue:
            self.task_queue.publish_report({
                "report_id": report_id,
                "report_date": report.get("report_date"),
                "summary": report.get("summary")
            })
        
        return report_id
    
    def get_daily_report(self, date: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """获取日报"""
        if not date:
            date = datetime.utcnow().strftime("%Y-%m-%d")
        
        # 先查缓存
        if self.cache:
            cached = self.cache.get_json(f"report:{date}")
            if cached:
                return cached
        
        report = self.doc_repo.get_daily_report(date)
        if report and self.cache:
            self.cache.set_json(f"report:{date}", report, ttl=86400)
        
        return report
    
    # ==================== 订阅操作 ====================
    
    def create_subscription(self, subscription: Dict[str, Any]) -> str:
        """创建预警订阅"""
        if not subscription.get("subscription_id"):
            subscription["subscription_id"] = str(uuid.uuid4())
        
        return self.doc_repo.insert_alert_subscription(subscription)
    
    def get_subscriptions(self, agent_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取订阅列表"""
        return self.doc_repo.find_alert_subscriptions(agent_id=agent_id)
    
    def delete_subscription(self, subscription_id: str) -> bool:
        """删除订阅"""
        return self.doc_repo.delete_alert_subscription(subscription_id)
    
    # ==================== 语义搜索 ====================
    
    def semantic_search(
        self,
        query: str,
        n_results: int = 10,
        sentiment: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """语义搜索"""
        if not self.vector_store:
            raise ValueError("Vector store not initialized")
        
        if sentiment:
            return self.vector_store.get_sentiment_neighbors(query, sentiment, n_results)
        
        return self.vector_store.search(query, n_results=n_results)
    
    def find_similar_documents(self, doc_id: str, n_results: int = 10) -> List[Dict[str, Any]]:
        """查找相似文档"""
        if not self.vector_store:
            raise ValueError("Vector store not initialized")
        
        return self.vector_store.search_similar_documents(doc_id, n_results)
    
    def check_duplicate(self, text: str, threshold: float = 0.95) -> List[Dict[str, Any]]:
        """检查重复"""
        if not self.vector_store:
            return []
        
        return self.vector_store.find_duplicates(text, threshold)
    
    # ==================== 统计操作 ====================
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计数据"""
        return self.doc_repo.get_statistics()
    
    def get_sentiment_statistics(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """获取情感统计"""
        return self.doc_repo.get_sentiment_statistics(start_time, end_time)
    
    def get_trending_topics(
        self,
        days: int = 7,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """获取热门话题"""
        start_time = datetime.utcnow() - timedelta(days=days)
        return self.doc_repo.find_topics(limit=limit)
    
    # ==================== 任务队列操作 ====================
    
    def enqueue_collect_task(self, task: Dict[str, Any], priority: int = 0) -> bool:
        """入队采集任务"""
        if not self.task_queue:
            raise ValueError("Task queue not initialized")
        return self.task_queue.enqueue_collect_task(task, priority)
    
    def enqueue_analyze_task(self, task: Dict[str, Any], priority: int = 0) -> bool:
        """入队分析任务"""
        if not self.task_queue:
            raise ValueError("Task queue not initialized")
        return self.task_queue.enqueue_analyze_task(task, priority)
    
    def dequeue_task(self, queue_name: str, timeout: int = 0) -> Optional[Dict[str, Any]]:
        """出队任务"""
        if not self.task_queue:
            raise ValueError("Task queue not initialized")
        return self.task_queue.dequeue(queue_name, timeout)
    
    # ==================== 会话操作 ====================
    
    def create_session(self, session_id: str, data: Dict[str, Any]) -> bool:
        """创建会话"""
        if not self.cache:
            raise ValueError("Cache not initialized")
        return self.cache.create_session(session_id, data)
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话"""
        if not self.cache:
            raise ValueError("Cache not initialized")
        return self.cache.get_session(session_id)
    
    def update_session(self, session_id: str, data: Dict[str, Any]) -> bool:
        """更新会话"""
        if not self.cache:
            raise ValueError("Cache not initialized")
        return self.cache.update_session(session_id, data)