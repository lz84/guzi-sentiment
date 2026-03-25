"""
采集服务

整合渠道适配器，提供统一的数据采集接口。
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import uuid
import asyncio

from ..channels.base import ChannelAdapter
from ..channels.registry import ChannelRegistry
from ..processor.pipeline import ProcessingPipeline
from ..storage.repository import SentimentRepository


class CollectService:
    """
    采集服务
    
    负责:
    - 管理渠道适配器
    - 执行数据采集任务
    - 协调数据处理流水线
    """
    
    def __init__(
        self,
        repository: SentimentRepository,
        channel_registry: Optional[ChannelRegistry] = None,
        processing_pipeline: Optional[ProcessingPipeline] = None,
    ):
        self.repository = repository
        self.channel_registry = channel_registry or ChannelRegistry()
        self.pipeline = processing_pipeline
        self._active_tasks: Dict[str, Dict[str, Any]] = {}
    
    # ==================== 渠道管理 ====================
    
    def register_channel(self, channel_adapter: ChannelAdapter) -> bool:
        """注册渠道"""
        return self.channel_registry.register(channel_adapter)
    
    def unregister_channel(self, channel_id: str) -> bool:
        """注销渠道"""
        return self.channel_registry.unregister(channel_id)
    
    def get_channel(self, channel_id: str) -> Optional[ChannelAdapter]:
        """获取渠道"""
        return self.channel_registry.get_channel(channel_id)
    
    def list_channels(self) -> List[Dict[str, Any]]:
        """列出所有渠道"""
        return self.channel_registry.list_channels()
    
    # ==================== 采集操作 ====================
    
    async def collect(
        self,
        channels: List[str],
        keywords: List[str],
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        执行采集任务
        
        Args:
            channels: 渠道ID列表
            keywords: 关键词列表
            options: 采集选项
                - limit: 每个渠道的采集数量限制
                - time_range: 时间范围
                - process: 是否立即处理
        
        Returns:
            采集结果
        """
        options = options or {}
        limit = options.get("limit", 100)
        process = options.get("process", True)
        
        task_id = str(uuid.uuid4())
        self._active_tasks[task_id] = {
            "status": "running",
            "channels": channels,
            "keywords": keywords,
            "started_at": datetime.utcnow().isoformat(),
            "results": {}
        }
        
        all_data = []
        errors = []
        
        for channel_id in channels:
            channel = self.get_channel(channel_id)
            if not channel:
                errors.append(f"Channel not found: {channel_id}")
                continue
            
            try:
                # 执行采集
                data = await channel.collect(keywords, options)
                
                # 保存原始数据
                for item in data:
                    doc = self._convert_to_document(item, channel_id)
                    self.repository.save_raw_document(doc)
                    all_data.append(doc)
                
                self._active_tasks[task_id]["results"][channel_id] = {
                    "count": len(data),
                    "status": "success"
                }
            
            except Exception as e:
                errors.append(f"Channel {channel_id} error: {str(e)}")
                self._active_tasks[task_id]["results"][channel_id] = {
                    "count": 0,
                    "status": "error",
                    "error": str(e)
                }
        
        # 处理数据
        processed_count = 0
        if process and all_data and self.pipeline:
            try:
                processed = self.pipeline.process_batch(all_data)
                processed_count = len(processed)
            except Exception as e:
                errors.append(f"Processing error: {str(e)}")
        
        self._active_tasks[task_id]["status"] = "completed"
        self._active_tasks[task_id]["completed_at"] = datetime.utcnow().isoformat()
        
        return {
            "task_id": task_id,
            "total_collected": len(all_data),
            "total_processed": processed_count,
            "results": self._active_tasks[task_id]["results"],
            "errors": errors
        }
    
    def collect_sync(
        self,
        channels: List[str],
        keywords: List[str],
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """同步采集"""
        return asyncio.run(self.collect(channels, keywords, options))
    
    async def collect_by_topic(
        self,
        topic: str,
        channels: Optional[List[str]] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        按主题采集
        
        Args:
            topic: 主题关键词
            channels: 渠道列表 (默认所有活跃渠道)
            options: 采集选项
        """
        if not channels:
            channels = [ch["channel_id"] for ch in self.list_channels() 
                       if ch.get("status") == "active"]
        
        # 将主题转换为关键词
        keywords = [topic]
        
        return await self.collect(channels, keywords, options)
    
    # ==================== 定时采集 ====================
    
    async def schedule_collect(
        self,
        channels: List[str],
        keywords: List[str],
        interval_minutes: int = 60,
        options: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        调度定时采集任务
        
        Args:
            channels: 渠道列表
            keywords: 关键词列表
            interval_minutes: 间隔分钟数
            options: 采集选项
        
        Returns:
            任务ID
        """
        task_id = str(uuid.uuid4())
        
        # 入队采集任务
        self.repository.enqueue_collect_task({
            "task_id": task_id,
            "channels": channels,
            "keywords": keywords,
            "interval_minutes": interval_minutes,
            "options": options,
            "scheduled_at": datetime.utcnow().isoformat()
        })
        
        return task_id
    
    # ==================== 任务管理 ====================
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        return self._active_tasks.get(task_id)
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        if task_id in self._active_tasks:
            self._active_tasks[task_id]["status"] = "cancelled"
            return True
        return False
    
    # ==================== 统计 ====================
    
    def get_collection_stats(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """获取采集统计"""
        # 从仓库获取统计
        total_docs = self.repository.doc_repo.count_raw_documents()
        
        channel_stats = {}
        for channel in self.list_channels():
            channel_id = channel["channel_id"]
            # 简化统计
            channel_stats[channel_id] = {
                "total": 0,  # 需要从实际数据计算
                "status": channel.get("status", "unknown")
            }
        
        return {
            "total_documents": total_docs,
            "channels": channel_stats,
            "active_tasks": len([t for t in self._active_tasks.values() 
                               if t["status"] == "running"])
        }
    
    # ==================== 辅助方法 ====================
    
    def _convert_to_document(
        self,
        data: Any,
        channel_id: str
    ) -> Dict[str, Any]:
        """将渠道数据转换为文档格式"""
        if hasattr(data, "to_dict"):
            data = data.to_dict()
        
        return {
            "doc_id": str(uuid.uuid4()),
            "source": channel_id,
            "platform": data.get("channel_type", data.get("platform", "unknown")),
            "content": data.get("content", data.get("text", "")),
            "author": data.get("author", data.get("user", "")),
            "published_at": data.get("published_at"),
            "url": data.get("url", ""),
            "metadata": data.get("metadata", {}),
            "collected_at": datetime.utcnow().isoformat()
        }