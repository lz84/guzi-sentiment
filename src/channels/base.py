"""
渠道适配器基类

定义渠道适配器的标准接口。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
import asyncio
import uuid

from .models import ChannelData, ChannelType, ChannelStatus


@dataclass
class ChannelConfig:
    """渠道配置"""
    channel_id: str
    channel_name: str
    channel_type: ChannelType
    enabled: bool = True
    # 请求配置
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    # 限流配置
    rate_limit: int = 100  # 每分钟请求数
    # 批量配置
    batch_size: int = 50
    # 额外配置
    config: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "channel_id": self.channel_id,
            "channel_name": self.channel_name,
            "channel_type": self.channel_type.value,
            "enabled": self.enabled,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "retry_delay": self.retry_delay,
            "rate_limit": self.rate_limit,
            "batch_size": self.batch_size,
            "config": self.config,
        }


@dataclass
class ChannelResult:
    """渠道采集结果"""
    success: bool
    data: list[ChannelData] = field(default_factory=list)
    total_count: int = 0
    error_message: Optional[str] = None
    processing_time_ms: float = 0.0
    has_more: bool = False
    next_cursor: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "success": self.success,
            "data": [item.to_dict() for item in self.data],
            "total_count": self.total_count,
            "error_message": self.error_message,
            "processing_time_ms": self.processing_time_ms,
            "has_more": self.has_more,
            "next_cursor": self.next_cursor,
            "metadata": self.metadata,
        }


class ChannelAdapter(ABC):
    """
    渠道适配器抽象基类
    
    所有渠道适配器都需要继承此类并实现以下方法：
    - collect(): 执行数据采集
    - test_connection(): 测试连接
    """
    
    def __init__(self, config: ChannelConfig):
        self.config = config
        self._status = ChannelStatus.INACTIVE
        self._last_error: Optional[str] = None
        self._request_count = 0
        self._last_request_time: Optional[datetime] = None
    
    @abstractmethod
    async def collect(
        self,
        keywords: list[str],
        options: Optional[dict[str, Any]] = None
    ) -> ChannelResult:
        """
        采集数据
        
        Args:
            keywords: 关键词列表
            options: 额外选项
                - limit: 最大返回数量
                - cursor: 分页游标
                - time_range: 时间范围
                
        Returns:
            ChannelResult: 采集结果
        """
        pass
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """
        测试连接
        
        Returns:
            bool: 连接是否成功
        """
        pass
    
    @property
    def channel_id(self) -> str:
        """渠道ID"""
        return self.config.channel_id
    
    @property
    def channel_name(self) -> str:
        """渠道名称"""
        return self.config.channel_name
    
    @property
    def channel_type(self) -> ChannelType:
        """渠道类型"""
        return self.config.channel_type
    
    @property
    def status(self) -> ChannelStatus:
        """渠道状态"""
        return self._status
    
    @property
    def is_available(self) -> bool:
        """是否可用"""
        return (
            self._status == ChannelStatus.ACTIVE
            and self.config.enabled
        )
    
    @property
    def last_error(self) -> Optional[str]:
        """最后一次错误"""
        return self._last_error
    
    async def enable(self) -> None:
        """启用渠道"""
        self.config.enabled = True
        if self._status == ChannelStatus.INACTIVE:
            self._status = ChannelStatus.ACTIVE
    
    async def disable(self) -> None:
        """禁用渠道"""
        self.config.enabled = False
        self._status = ChannelStatus.INACTIVE
    
    async def health_check(self) -> dict[str, Any]:
        """
        健康检查
        
        Returns:
            dict: 健康状态
        """
        try:
            is_connected = await self.test_connection()
            
            if is_connected:
                self._status = ChannelStatus.ACTIVE
            else:
                self._status = ChannelStatus.ERROR
            
            return {
                "channel_id": self.channel_id,
                "channel_name": self.channel_name,
                "channel_type": self.channel_type.value,
                "status": self._status.value,
                "available": is_connected,
                "enabled": self.config.enabled,
                "last_error": self._last_error,
                "last_check": datetime.now().isoformat(),
            }
        except Exception as e:
            self._last_error = str(e)
            self._status = ChannelStatus.ERROR
            return {
                "channel_id": self.channel_id,
                "channel_name": self.channel_name,
                "channel_type": self.channel_type.value,
                "status": self._status.value,
                "available": False,
                "enabled": self.config.enabled,
                "last_error": str(e),
                "last_check": datetime.now().isoformat(),
            }
    
    def _generate_id(self) -> str:
        """生成唯一ID"""
        return f"{self.channel_type.value}_{uuid.uuid4().hex[:12]}"
    
    async def _execute_with_retry(
        self,
        func,
        *args,
        **kwargs
    ) -> Any:
        """
        带重试的执行
        
        Args:
            func: 要执行的异步函数
            args: 位置参数
            kwargs: 关键字参数
            
        Returns:
            执行结果
        """
        last_error = None
        
        for attempt in range(self.config.max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_error = e
                self._last_error = str(e)
                
                if attempt < self.config.max_retries - 1:
                    delay = self.config.retry_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
        
        raise last_error
    
    def _check_rate_limit(self) -> bool:
        """检查是否超过速率限制"""
        if self._last_request_time:
            elapsed = (datetime.now() - self._last_request_time).total_seconds()
            if elapsed >= 60:
                self._request_count = 0
                return True
            if self._request_count >= self.config.rate_limit:
                return False
        return True
    
    async def wait_for_rate_limit(self) -> None:
        """等待速率限制"""
        while not self._check_rate_limit():
            await asyncio.sleep(1)
    
    def _update_rate_limit(self) -> None:
        """更新请求计数"""
        now = datetime.now()
        if self._last_request_time:
            elapsed = (now - self._last_request_time).total_seconds()
            if elapsed >= 60:
                self._request_count = 0
        
        self._request_count += 1
        self._last_request_time = now
    
    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        return {
            "channel_id": self.channel_id,
            "channel_name": self.channel_name,
            "channel_type": self.channel_type.value,
            "status": self._status.value,
            "available": self.is_available,
            "enabled": self.config.enabled,
            "request_count": self._request_count,
            "last_request_time": self._last_request_time.isoformat() if self._last_request_time else None,
            "last_error": self._last_error,
        }


class BaseChannelAdapter(ChannelAdapter):
    """
    基础渠道适配器
    
    提供默认实现，用于简单的渠道配置。
    """
    
    async def collect(
        self,
        keywords: list[str],
        options: Optional[dict[str, Any]] = None
    ) -> ChannelResult:
        """
        采集数据 - 基础实现
        
        子类应重写此方法以实现具体的采集逻辑。
        """
        return ChannelResult(
            success=False,
            error_message="BaseChannelAdapter does not implement collect. Please use a specific adapter.",
            total_count=0
        )
    
    async def test_connection(self) -> bool:
        """
        测试连接 - 基础实现
        
        默认返回 True，子类可重写。
        """
        self._status = ChannelStatus.ACTIVE
        return True