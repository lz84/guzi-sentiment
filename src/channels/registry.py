"""
渠道注册器

管理和路由多个渠道适配器。
"""

import asyncio
from datetime import datetime
from typing import Any, Optional, Callable

from .base import ChannelAdapter, ChannelConfig, ChannelResult
from .models import ChannelData, ChannelType, ChannelStatus


class ChannelRegistry:
    """
    渠道注册器
    
    管理所有渠道适配器的注册、发现和调用。
    """
    
    def __init__(self):
        self.channels: dict[str, ChannelAdapter] = {}
        self.factories: dict[ChannelType, Callable] = {}
        self._type_channels: dict[ChannelType, list[str]] = {}
    
    def register_factory(
        self,
        channel_type: ChannelType,
        factory: Callable[[ChannelConfig], ChannelAdapter]
    ) -> None:
        """
        注册渠道工厂
        
        Args:
            channel_type: 渠道类型
            factory: 工厂函数，用于创建渠道适配器
        """
        self.factories[channel_type] = factory
    
    async def register_channel(
        self,
        config: ChannelConfig
    ) -> bool:
        """
        注册新渠道
        
        Args:
            config: 渠道配置
            
        Returns:
            bool: 注册是否成功
        """
        factory = self.factories.get(config.channel_type)
        if not factory:
            raise ValueError(f"Unknown channel type: {config.channel_type}")
        
        adapter = factory(config)
        
        # 测试连接
        try:
            is_connected = await adapter.test_connection()
            if is_connected:
                self.channels[config.channel_id] = adapter
                
                # 更新类型索引
                if config.channel_type not in self._type_channels:
                    self._type_channels[config.channel_type] = []
                self._type_channels[config.channel_type].append(config.channel_id)
                
                return True
            return False
        except Exception as e:
            raise RuntimeError(f"Failed to register channel: {e}")
    
    def unregister_channel(self, channel_id: str) -> None:
        """
        注销渠道
        
        Args:
            channel_id: 渠道ID
        """
        if channel_id in self.channels:
            adapter = self.channels[channel_id]
            channel_type = adapter.channel_type
            
            del self.channels[channel_id]
            
            # 更新类型索引
            if channel_type in self._type_channels:
                if channel_id in self._type_channels[channel_type]:
                    self._type_channels[channel_type].remove(channel_id)
    
    def get_channel(self, channel_id: str) -> Optional[ChannelAdapter]:
        """
        获取渠道
        
        Args:
            channel_id: 渠道ID
            
        Returns:
            ChannelAdapter: 渠道适配器
        """
        return self.channels.get(channel_id)
    
    def get_channels_by_type(
        self,
        channel_type: ChannelType
    ) -> list[ChannelAdapter]:
        """
        按类型获取渠道
        
        Args:
            channel_type: 渠道类型
            
        Returns:
            list: 渠道适配器列表
        """
        channel_ids = self._type_channels.get(channel_type, [])
        return [
            self.channels[cid]
            for cid in channel_ids
            if cid in self.channels
        ]
    
    def list_channels(self) -> list[dict[str, Any]]:
        """
        列出所有渠道
        
        Returns:
            list: 渠道信息列表
        """
        return [
            {
                "channel_id": c.channel_id,
                "channel_name": c.channel_name,
                "channel_type": c.channel_type.value,
                "status": c.status.value,
                "available": c.is_available,
            }
            for c in self.channels.values()
        ]
    
    async def collect_from_channel(
        self,
        channel_id: str,
        keywords: list[str],
        options: Optional[dict[str, Any]] = None
    ) -> ChannelResult:
        """
        从指定渠道采集数据
        
        Args:
            channel_id: 渠道ID
            keywords: 关键词列表
            options: 额外选项
            
        Returns:
            ChannelResult: 采集结果
        """
        channel = self.get_channel(channel_id)
        if not channel:
            return ChannelResult(
                success=False,
                error_message=f"Channel not found: {channel_id}",
            )
        
        if not channel.is_available:
            return ChannelResult(
                success=False,
                error_message=f"Channel not available: {channel_id}",
            )
        
        return await channel.collect(keywords, options)
    
    async def collect_from_type(
        self,
        channel_type: ChannelType,
        keywords: list[str],
        options: Optional[dict[str, Any]] = None
    ) -> dict[str, ChannelResult]:
        """
        从指定类型的所有渠道采集数据
        
        Args:
            channel_type: 渠道类型
            keywords: 关键词列表
            options: 额外选项
            
        Returns:
            dict: 渠道ID -> 采集结果
        """
        channels = self.get_channels_by_type(channel_type)
        results = {}
        
        for channel in channels:
            if channel.is_available:
                result = await channel.collect(keywords, options)
                results[channel.channel_id] = result
        
        return results
    
    async def collect_from_all(
        self,
        keywords: list[str],
        options: Optional[dict[str, Any]] = None
    ) -> dict[str, ChannelResult]:
        """
        从所有可用渠道采集数据
        
        Args:
            keywords: 关键词列表
            options: 额外选项
            
        Returns:
            dict: 渠道ID -> 采集结果
        """
        results = {}
        
        for channel_id, channel in self.channels.items():
            if channel.is_available:
                result = await channel.collect(keywords, options)
                results[channel_id] = result
        
        return results
    
    async def health_check(self) -> dict[str, Any]:
        """
        健康检查所有渠道
        
        Returns:
            dict: 健康状态
        """
        results = await asyncio.gather(
            *[c.health_check() for c in self.channels.values()],
            return_exceptions=True
        )
        
        channels_status = []
        for channel, result in zip(self.channels.values(), results):
            if isinstance(result, Exception):
                channels_status.append({
                    "channel_id": channel.channel_id,
                    "channel_name": channel.channel_name,
                    "available": False,
                    "error": str(result),
                })
            else:
                channels_status.append(result)
        
        available_count = sum(
            1 for s in channels_status if s.get("available")
        )
        
        return {
            "total_channels": len(self.channels),
            "available_channels": available_count,
            "channels": channels_status,
            "overall_available": available_count > 0,
        }
    
    def get_stats(self) -> dict[str, Any]:
        """
        获取统计信息
        
        Returns:
            dict: 统计信息
        """
        type_counts = {}
        for channel_type, channel_ids in self._type_channels.items():
            type_counts[channel_type.value] = len(channel_ids)
        
        return {
            "total_channels": len(self.channels),
            "by_type": type_counts,
            "channels": [c.get_stats() for c in self.channels.values()],
        }
    
    def get_available_types(self) -> list[ChannelType]:
        """
        获取可用的渠道类型
        
        Returns:
            list: 渠道类型列表
        """
        return list(self._type_channels.keys())
    
    def get_available_channels(self) -> list[ChannelAdapter]:
        """
        获取可用的渠道列表
        
        Returns:
            list: 可用渠道适配器列表
        """
        return [
            c for c in self.channels.values()
            if c.is_available
        ]
    
    # ==================== 同步接口 (用于 API) ====================
    
    def register(self, adapter: ChannelAdapter) -> bool:
        """
        注册渠道适配器 (同步接口)
        
        Args:
            adapter: 渠道适配器实例
            
        Returns:
            bool: 注册是否成功
        """
        if adapter.channel_id in self.channels:
            return False
        
        self.channels[adapter.channel_id] = adapter
        
        # 更新类型索引
        channel_type = adapter.channel_type
        if channel_type not in self._type_channels:
            self._type_channels[channel_type] = []
        self._type_channels[channel_type].append(adapter.channel_id)
        
        return True
    
    def unregister(self, channel_id: str) -> bool:
        """
        注销渠道 (同步接口)
        
        Args:
            channel_id: 渠道ID
            
        Returns:
            bool: 注销是否成功
        """
        if channel_id not in self.channels:
            return False
        
        adapter = self.channels[channel_id]
        channel_type = adapter.channel_type
        
        del self.channels[channel_id]
        
        # 更新类型索引
        if channel_type in self._type_channels:
            if channel_id in self._type_channels[channel_type]:
                self._type_channels[channel_type].remove(channel_id)
        
        return True
    
    def register_by_config(self, config: ChannelConfig) -> bool:
        """
        通过配置注册渠道
        
        Args:
            config: 渠道配置
            
        Returns:
            bool: 注册是否成功
        """
        factory = self.factories.get(config.channel_type)
        if factory:
            adapter = factory(config)
            return self.register(adapter)
        
        # 如果没有工厂，创建基础适配器
        from .base import BaseChannelAdapter
        adapter = BaseChannelAdapter(config)
        return self.register(adapter)