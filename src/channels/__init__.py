"""
渠道适配模块

实现多渠道数据采集的适配器，支持社交媒体、新闻等平台。

模块结构:
- base: 渠道适配器基类
- registry: 渠道注册器
- adapters: 各平台适配器实现
"""

from .base import (
    ChannelAdapter,
    ChannelConfig,
    ChannelResult,
    ChannelStatus,
)
from .registry import ChannelRegistry
from .models import ChannelData, ChannelType

__all__ = [
    # 基类
    "ChannelAdapter",
    "ChannelConfig",
    "ChannelResult",
    "ChannelStatus",
    # 注册器
    "ChannelRegistry",
    # 数据模型
    "ChannelData",
    "ChannelType",
]