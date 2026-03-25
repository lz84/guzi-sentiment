"""
渠道管理 API 路由
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from ...channels.registry import ChannelRegistry
from ...channels.base import ChannelAdapter, ChannelConfig
from ...channels.models import ChannelType, ChannelStatus

router = APIRouter()


# 请求/响应模型
class ChannelRegisterRequest(BaseModel):
    channel_id: str = Field(..., description="渠道ID")
    channel_name: str = Field(..., description="渠道名称")
    channel_type: str = Field(..., description="渠道类型")
    config: Optional[Dict[str, Any]] = Field(default=None, description="渠道配置")
    enabled: bool = Field(default=True, description="是否启用")


# 获取注册器
def get_registry():
    return ChannelRegistry()


@router.get("/")
async def list_channels(
    registry: ChannelRegistry = Depends(get_registry)
):
    """
    列出所有渠道
    """
    channels = registry.list_channels()
    return {
        "channels": channels,
        "total": len(channels)
    }


@router.post("/register")
async def register_channel(
    request: ChannelRegisterRequest,
    registry: ChannelRegistry = Depends(get_registry)
):
    """
    注册新渠道
    
    - **channel_id**: 渠道唯一标识
    - **channel_name**: 渠道显示名称
    - **channel_type**: 渠道类型 (twitter, reddit, news, weibo, youtube, custom)
    - **config**: 渠道特定配置
    """
    try:
        # 创建渠道配置
        config = ChannelConfig(
            channel_id=request.channel_id,
            channel_name=request.channel_name,
            channel_type=request.channel_type,
            config=request.config or {},
            enabled=request.enabled
        )
        
        # 注册渠道 (实际实现需要根据类型创建适配器)
        success = registry.register_by_config(config)
        
        if not success:
            raise HTTPException(status_code=400, detail="Failed to register channel")
        
        return {
            "channel_id": request.channel_id,
            "status": "registered"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{channel_id}")
async def get_channel(
    channel_id: str,
    registry: ChannelRegistry = Depends(get_registry)
):
    """
    获取渠道详情
    """
    channel = registry.get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    return {
        "channel_id": channel_id,
        "config": channel.config.to_dict() if hasattr(channel, 'config') else {},
        "status": channel.status.value if hasattr(channel, 'status') else "unknown"
    }


@router.delete("/{channel_id}")
async def unregister_channel(
    channel_id: str,
    registry: ChannelRegistry = Depends(get_registry)
):
    """
    注销渠道
    """
    success = registry.unregister(channel_id)
    if not success:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    return {"channel_id": channel_id, "status": "unregistered"}


@router.post("/{channel_id}/enable")
async def enable_channel(
    channel_id: str,
    registry: ChannelRegistry = Depends(get_registry)
):
    """
    启用渠道
    """
    channel = registry.get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    await channel.enable()
    return {"channel_id": channel_id, "status": "enabled"}


@router.post("/{channel_id}/disable")
async def disable_channel(
    channel_id: str,
    registry: ChannelRegistry = Depends(get_registry)
):
    """
    禁用渠道
    """
    channel = registry.get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    await channel.disable()
    return {"channel_id": channel_id, "status": "disabled"}


@router.post("/{channel_id}/test")
async def test_channel(
    channel_id: str,
    registry: ChannelRegistry = Depends(get_registry)
):
    """
    测试渠道连接
    """
    channel = registry.get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    try:
        success = await channel.test_connection()
        return {
            "channel_id": channel_id,
            "connection": "ok" if success else "failed"
        }
    except Exception as e:
        return {
            "channel_id": channel_id,
            "connection": "error",
            "error": str(e)
        }


@router.get("/{channel_id}/metrics")
async def get_channel_metrics(
    channel_id: str,
    registry: ChannelRegistry = Depends(get_registry)
):
    """
    获取渠道指标
    """
    channel = registry.get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # 返回渠道指标
    return {
        "channel_id": channel_id,
        "metrics": {
            "total_collected": 0,
            "successful": 0,
            "failed": 0,
            "last_collected_at": None
        }
    }


@router.get("/types")
async def list_channel_types():
    """
    列出支持的渠道类型
    """
    return {
        "types": [
            {"type": "twitter", "name": "Twitter/X", "description": "Twitter 社交平台"},
            {"type": "reddit", "name": "Reddit", "description": "Reddit 论坛"},
            {"type": "news", "name": "新闻网站", "description": "新闻媒体网站"},
            {"type": "weibo", "name": "微博", "description": "微博社交平台"},
            {"type": "youtube", "name": "YouTube", "description": "YouTube 视频平台"},
            {"type": "wechat", "name": "微信公众号", "description": "微信公众号文章"},
            {"type": "custom", "name": "自定义", "description": "自定义渠道"}
        ]
    }