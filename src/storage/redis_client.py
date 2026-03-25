"""
Redis 客户端、缓存管理器和任务队列

提供缓存、会话管理和异步任务队列功能。
"""

import json
import hashlib
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
import redis.asyncio as aioredis
import redis


class RedisClient:
    """
    Redis 客户端管理器
    
    支持同步和异步操作。
    """
    
    _instance: Optional["RedisClient"] = None
    _sync_client: Optional[redis.Redis] = None
    _async_client: Optional[aioredis.Redis] = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        encoding: str = "utf-8",
        decode_responses: bool = True,
        **kwargs
    ):
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.encoding = encoding
        self.decode_responses = decode_responses
        self.kwargs = kwargs
        
        if self._sync_client is None:
            self._connect_sync()
    
    def _connect_sync(self) -> None:
        """建立同步 Redis 连接"""
        self._sync_client = redis.Redis(
            host=self.host,
            port=self.port,
            db=self.db,
            password=self.password,
            encoding=self.encoding,
            decode_responses=self.decode_responses,
            **self.kwargs
        )
    
    async def _connect_async(self) -> None:
        """建立异步 Redis 连接"""
        self._async_client = aioredis.Redis(
            host=self.host,
            port=self.port,
            db=self.db,
            password=self.password,
            encoding=self.encoding,
            decode_responses=self.decode_responses,
            **self.kwargs
        )
    
    @property
    def sync(self) -> redis.Redis:
        """获取同步客户端"""
        if self._sync_client is None:
            self._connect_sync()
        return self._sync_client
    
    @property
    async def async_client(self) -> aioredis.Redis:
        """获取异步客户端"""
        if self._async_client is None:
            await self._connect_async()
        return self._async_client
    
    def close(self) -> None:
        """关闭连接"""
        if self._sync_client:
            self._sync_client.close()
            self._sync_client = None
    
    async def close_async(self) -> None:
        """异步关闭连接"""
        if self._async_client:
            await self._async_client.close()
            self._async_client = None
    
    @classmethod
    def get_instance(cls) -> "RedisClient":
        """获取单例实例"""
        if cls._instance is None:
            raise RuntimeError("RedisClient not initialized. Call constructor first.")
        return cls._instance
    
    def ping(self) -> bool:
        """测试连接"""
        try:
            return self.sync.ping()
        except redis.ConnectionError:
            return False


class CacheManager:
    """
    缓存管理器
    
    提供键值缓存、JSON 缓存和过期管理。
    """
    
    # 缓存键前缀
    PREFIX_SENTIMENT = "sentiment:"
    PREFIX_SESSION = "session:"
    PREFIX_ANALYSIS = "analysis:"
    PREFIX_CONFIG = "config:"
    PREFIX_RATE_LIMIT = "rate_limit:"
    
    # 默认过期时间（秒）
    DEFAULT_TTL = 3600  # 1小时
    SESSION_TTL = 86400  # 24小时
    ANALYSIS_TTL = 7200  # 2小时
    CONFIG_TTL = 300  # 5分钟
    
    def __init__(self, redis_client: Optional[RedisClient] = None):
        self.redis = redis_client or RedisClient.get_instance()
    
    # ==================== 基础操作 ====================
    
    def get(self, key: str) -> Optional[str]:
        """获取缓存值"""
        return self.redis.sync.get(key)
    
    def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        """设置缓存值"""
        if ttl:
            return self.redis.sync.setex(key, ttl, value)
        return self.redis.sync.set(key, value)
    
    def delete(self, key: str) -> bool:
        """删除缓存"""
        return self.redis.sync.delete(key) > 0
    
    def exists(self, key: str) -> bool:
        """检查键是否存在"""
        return self.redis.sync.exists(key) > 0
    
    def expire(self, key: str, ttl: int) -> bool:
        """设置过期时间"""
        return self.redis.sync.expire(key, ttl)
    
    def ttl(self, key: str) -> int:
        """获取剩余过期时间"""
        return self.redis.sync.ttl(key)
    
    # ==================== JSON 操作 ====================
    
    def get_json(self, key: str) -> Optional[Dict[str, Any]]:
        """获取 JSON 缓存"""
        value = self.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return None
        return None
    
    def set_json(self, key: str, value: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """设置 JSON 缓存"""
        try:
            json_str = json.dumps(value, ensure_ascii=False, default=str)
            return self.set(key, json_str, ttl)
        except (TypeError, ValueError):
            return False
    
    # ==================== 会话管理 ====================
    
    def create_session(self, session_id: str, data: Dict[str, Any], ttl: int = None) -> bool:
        """创建会话"""
        key = f"{self.PREFIX_SESSION}{session_id}"
        return self.set_json(key, data, ttl or self.SESSION_TTL)
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话"""
        key = f"{self.PREFIX_SESSION}{session_id}"
        return self.get_json(key)
    
    def update_session(self, session_id: str, data: Dict[str, Any]) -> bool:
        """更新会话"""
        key = f"{self.PREFIX_SESSION}{session_id}"
        existing = self.get_session(session_id)
        if existing:
            existing.update(data)
            # 保持原有 TTL
            ttl = self.ttl(key)
            if ttl > 0:
                return self.set_json(key, existing, ttl)
            return self.set_json(key, existing, self.SESSION_TTL)
        return False
    
    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        key = f"{self.PREFIX_SESSION}{session_id}"
        return self.delete(key)
    
    # ==================== 情感分析缓存 ====================
    
    def cache_sentiment(self, text: str, result: Dict[str, Any], ttl: int = None) -> str:
        """缓存情感分析结果"""
        # 使用文本哈希作为键
        text_hash = hashlib.md5(text.encode()).hexdigest()
        key = f"{self.PREFIX_SENTIMENT}{text_hash}"
        self.set_json(key, result, ttl or self.DEFAULT_TTL)
        return text_hash
    
    def get_cached_sentiment(self, text: str) -> Optional[Dict[str, Any]]:
        """获取缓存的情感分析结果"""
        text_hash = hashlib.md5(text.encode()).hexdigest()
        key = f"{self.PREFIX_SENTIMENT}{text_hash}"
        return self.get_json(key)
    
    # ==================== 配置缓存 ====================
    
    def cache_config(self, config_key: str, config: Dict[str, Any]) -> bool:
        """缓存配置"""
        key = f"{self.PREFIX_CONFIG}{config_key}"
        return self.set_json(key, config, self.CONFIG_TTL)
    
    def get_cached_config(self, config_key: str) -> Optional[Dict[str, Any]]:
        """获取缓存的配置"""
        key = f"{self.PREFIX_CONFIG}{config_key}"
        return self.get_json(key)
    
    def invalidate_config(self, config_key: str) -> bool:
        """使配置缓存失效"""
        key = f"{self.PREFIX_CONFIG}{config_key}"
        return self.delete(key)
    
    # ==================== 限流 ====================
    
    def check_rate_limit(
        self,
        key: str,
        max_requests: int,
        window_seconds: int
    ) -> Dict[str, Any]:
        """
        检查限流
        
        返回:
            allowed: 是否允许
            remaining: 剩余次数
            reset_at: 重置时间戳
        """
        full_key = f"{self.PREFIX_RATE_LIMIT}{key}"
        current = self.redis.sync.get(full_key)
        
        if current is None:
            # 第一次请求
            self.redis.sync.setex(full_key, window_seconds, 1)
            return {
                "allowed": True,
                "remaining": max_requests - 1,
                "reset_at": int(datetime.now().timestamp()) + window_seconds
            }
        
        current = int(current)
        if current >= max_requests:
            ttl = self.redis.sync.ttl(full_key)
            return {
                "allowed": False,
                "remaining": 0,
                "reset_at": int(datetime.now().timestamp()) + ttl
            }
        
        # 增加计数
        self.redis.sync.incr(full_key)
        ttl = self.redis.sync.ttl(full_key)
        return {
            "allowed": True,
            "remaining": max_requests - current - 1,
            "reset_at": int(datetime.now().timestamp()) + ttl
        }
    
    # ==================== 异步操作 ====================
    
    async def get_async(self, key: str) -> Optional[str]:
        """异步获取缓存值"""
        client = await self.redis.async_client
        return await client.get(key)
    
    async def set_async(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        """异步设置缓存值"""
        client = await self.redis.async_client
        if ttl:
            await client.setex(key, ttl, value)
        else:
            await client.set(key, value)
        return True
    
    async def get_json_async(self, key: str) -> Optional[Dict[str, Any]]:
        """异步获取 JSON 缓存"""
        value = await self.get_async(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return None
        return None
    
    async def set_json_async(self, key: str, value: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """异步设置 JSON 缓存"""
        try:
            json_str = json.dumps(value, ensure_ascii=False, default=str)
            return await self.set_async(key, json_str, ttl)
        except (TypeError, ValueError):
            return False


class TaskQueue:
    """
    任务队列
    
    提供异步任务队列和消息发布/订阅功能。
    """
    
    # 队列名称
    QUEUE_COLLECT = "queue:collect"
    QUEUE_ANALYZE = "queue:analyze"
    QUEUE_ALERT = "queue:alert"
    QUEUE_REPORT = "queue:report"
    
    # 通道名称
    CHANNEL_ALERTS = "channel:alerts"
    CHANNEL_REPORTS = "channel:reports"
    CHANNEL_EVENTS = "channel:events"
    
    def __init__(self, redis_client: Optional[RedisClient] = None):
        self.redis = redis_client or RedisClient.get_instance()
    
    # ==================== 队列操作 ====================
    
    def enqueue(self, queue_name: str, task_data: Dict[str, Any], priority: int = 0) -> bool:
        """
        入队任务
        
        Args:
            queue_name: 队列名称
            task_data: 任务数据
            priority: 优先级 (越高越优先)
        """
        task = {
            "data": task_data,
            "priority": priority,
            "enqueued_at": datetime.utcnow().isoformat()
        }
        json_str = json.dumps(task, ensure_ascii=False, default=str)
        
        # 使用有序集合按优先级排序
        # score = -priority (负号使得高优先级在前)
        score = -priority + datetime.utcnow().timestamp() / 1e10
        return self.redis.sync.zadd(queue_name, {json_str: score}) > 0
    
    def dequeue(self, queue_name: str, timeout: int = 0) -> Optional[Dict[str, Any]]:
        """
        出队任务
        
        Args:
            queue_name: 队列名称
            timeout: 阻塞超时时间 (0 表示非阻塞)
        """
        if timeout > 0:
            # 阻塞获取
            result = self.redis.sync.bzpopmin(queue_name, timeout)
            if result:
                _, json_str, _ = result
                task = json.loads(json_str)
                return task
        else:
            # 非阻塞获取
            result = self.redis.sync.zpopmin(queue_name)
            if result:
                json_str, _ = result[0]
                task = json.loads(json_str)
                return task
        return None
    
    def peek(self, queue_name: str, count: int = 10) -> List[Dict[str, Any]]:
        """查看队列头部任务（不出队）"""
        results = self.redis.sync.zrange(queue_name, 0, count - 1)
        tasks = []
        for json_str in results:
            tasks.append(json.loads(json_str))
        return tasks
    
    def queue_size(self, queue_name: str) -> int:
        """获取队列大小"""
        return self.redis.sync.zcard(queue_name)
    
    def clear_queue(self, queue_name: str) -> bool:
        """清空队列"""
        return self.redis.sync.delete(queue_name) > 0
    
    # ==================== 发布/订阅 ====================
    
    def publish(self, channel: str, message: Dict[str, Any]) -> int:
        """
        发布消息
        
        返回接收到消息的订阅者数量
        """
        json_str = json.dumps(message, ensure_ascii=False, default=str)
        return self.redis.sync.publish(channel, json_str)
    
    def subscribe(self, *channels: str) -> redis.client.PubSub:
        """订阅通道"""
        pubsub = self.redis.sync.pubsub()
        pubsub.subscribe(*channels)
        return pubsub
    
    def unsubscribe(self, pubsub: redis.client.PubSub, *channels: str) -> None:
        """取消订阅"""
        if channels:
            pubsub.unsubscribe(*channels)
        else:
            pubsub.unsubscribe()
    
    # ==================== 便捷方法 ====================
    
    def enqueue_collect_task(self, task_data: Dict[str, Any], priority: int = 0) -> bool:
        """入队采集任务"""
        return self.enqueue(self.QUEUE_COLLECT, task_data, priority)
    
    def enqueue_analyze_task(self, task_data: Dict[str, Any], priority: int = 0) -> bool:
        """入队分析任务"""
        return self.enqueue(self.QUEUE_ANALYZE, task_data, priority)
    
    def enqueue_alert_task(self, task_data: Dict[str, Any], priority: int = 10) -> bool:
        """入队预警任务（默认高优先级）"""
        return self.enqueue(self.QUEUE_ALERT, task_data, priority)
    
    def enqueue_report_task(self, task_data: Dict[str, Any], priority: int = 5) -> bool:
        """入队报告任务"""
        return self.enqueue(self.QUEUE_REPORT, task_data, priority)
    
    def publish_alert(self, alert_data: Dict[str, Any]) -> int:
        """发布预警消息"""
        return self.publish(self.CHANNEL_ALERTS, alert_data)
    
    def publish_report(self, report_data: Dict[str, Any]) -> int:
        """发布报告消息"""
        return self.publish(self.CHANNEL_REPORTS, report_data)
    
    def publish_event(self, event_data: Dict[str, Any]) -> int:
        """发布事件消息"""
        return self.publish(self.CHANNEL_EVENTS, event_data)
    
    # ==================== 异步操作 ====================
    
    async def enqueue_async(self, queue_name: str, task_data: Dict[str, Any], priority: int = 0) -> bool:
        """异步入队"""
        client = await self.redis.async_client
        task = {
            "data": task_data,
            "priority": priority,
            "enqueued_at": datetime.utcnow().isoformat()
        }
        json_str = json.dumps(task, ensure_ascii=False, default=str)
        score = -priority + datetime.utcnow().timestamp() / 1e10
        result = await client.zadd(queue_name, {json_str: score})
        return result > 0
    
    async def dequeue_async(self, queue_name: str, timeout: int = 0) -> Optional[Dict[str, Any]]:
        """异步出队"""
        client = await self.redis.async_client
        if timeout > 0:
            result = await client.bzpopmin(queue_name, timeout)
            if result:
                _, json_str, _ = result
                return json.loads(json_str)
        else:
            result = await client.zpopmin(queue_name)
            if result:
                json_str, _ = result[0]
                return json.loads(json_str)
        return None
    
    async def publish_async(self, channel: str, message: Dict[str, Any]) -> int:
        """异步发布消息"""
        client = await self.redis.async_client
        json_str = json.dumps(message, ensure_ascii=False, default=str)
        return await client.publish(channel, json_str)