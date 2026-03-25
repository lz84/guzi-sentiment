"""
渠道适配模块 - 数据类型定义
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class ChannelType(str, Enum):
    """渠道类型"""
    TWITTER = "twitter"
    REDDIT = "reddit"
    WEIBO = "weibo"
    YOUTUBE = "youtube"
    NEWS = "news"
    WECHAT = "wechat"
    CUSTOM = "custom"


class ChannelStatus(str, Enum):
    """渠道状态"""
    ACTIVE = "active"          # 活跃
    INACTIVE = "inactive"      # 未激活
    ERROR = "error"            # 错误
    RATE_LIMITED = "rate_limited"  # 限流
    MAINTENANCE = "maintenance"    # 维护中


@dataclass
class ChannelData:
    """渠道数据"""
    channel_id: str
    channel_type: ChannelType
    external_id: str
    content: str
    author: str
    published_at: Optional[datetime] = None
    url: Optional[str] = None
    title: Optional[str] = None
    language: Optional[str] = None
    metrics: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    collected_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "channel_id": self.channel_id,
            "channel_type": self.channel_type.value,
            "external_id": self.external_id,
            "content": self.content,
            "author": self.author,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "url": self.url,
            "title": self.title,
            "language": self.language,
            "metrics": self.metrics,
            "metadata": self.metadata,
            "collected_at": self.collected_at.isoformat() if self.collected_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChannelData":
        """从字典创建"""
        return cls(
            channel_id=data.get("channel_id", ""),
            channel_type=ChannelType(data.get("channel_type", "custom")),
            external_id=data.get("external_id", ""),
            content=data.get("content", ""),
            author=data.get("author", ""),
            published_at=datetime.fromisoformat(data["published_at"]) if data.get("published_at") else None,
            url=data.get("url"),
            title=data.get("title"),
            language=data.get("language"),
            metrics=data.get("metrics", {}),
            metadata=data.get("metadata", {}),
            collected_at=datetime.fromisoformat(data["collected_at"]) if data.get("collected_at") else datetime.now(),
        )


@dataclass
class ChannelMetrics:
    """渠道指标"""
    total_collected: int = 0
    successful: int = 0
    failed: int = 0
    last_collected_at: Optional[datetime] = None
    avg_response_time_ms: float = 0.0
    error_rate: float = 0.0
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "total_collected": self.total_collected,
            "successful": self.successful,
            "failed": self.failed,
            "last_collected_at": self.last_collected_at.isoformat() if self.last_collected_at else None,
            "avg_response_time_ms": self.avg_response_time_ms,
            "error_rate": self.error_rate,
        }