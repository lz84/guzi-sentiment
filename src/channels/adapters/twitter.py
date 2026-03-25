"""
Twitter/X 渠道适配器

通过 agent-reach 技能采集 Twitter 数据。
"""

from datetime import datetime
from typing import Any, Optional
import hashlib

from ..base import ChannelAdapter, ChannelConfig, ChannelResult
from ..models import ChannelData, ChannelType


class TwitterAdapter(ChannelAdapter):
    """
    Twitter/X 渠道适配器
    
    通过 agent-reach 技能或 API 采集 Twitter 数据。
    """
    
    def __init__(
        self,
        config: ChannelConfig,
        skill_executor: Optional[Any] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None
    ):
        """
        初始化 Twitter 适配器
        
        Args:
            config: 渠道配置
            skill_executor: Agent Skill 执行器
            api_key: Twitter API Key
            api_secret: Twitter API Secret
        """
        super().__init__(config)
        self.skill_executor = skill_executor
        self.api_key = api_key
        self.api_secret = api_secret
    
    async def collect(
        self,
        keywords: list[str],
        options: Optional[dict[str, Any]] = None
    ) -> ChannelResult:
        """
        采集 Twitter 数据
        
        Args:
            keywords: 关键词列表
            options: 额外选项
                - limit: 最大返回数量
                - lang: 语言过滤
                - result_type: 结果类型 (recent, popular, mixed)
                
        Returns:
            ChannelResult: 采集结果
        """
        start_time = datetime.now()
        options = options or {}
        limit = options.get("limit", 100)
        
        try:
            # 通过 skill 执行器采集
            if self.skill_executor:
                result = await self._collect_via_skill(keywords, options)
            else:
                # 返回模拟数据
                result = await self._collect_mock(keywords, options)
            
            # 转换为 ChannelData 格式
            data_list = []
            for item in result.get("data", []):
                channel_data = self._convert_to_channel_data(item)
                data_list.append(channel_data)
            
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return ChannelResult(
                success=True,
                data=data_list[:limit],
                total_count=len(data_list),
                processing_time_ms=processing_time,
                has_more=result.get("has_more", False),
                next_cursor=result.get("next_cursor"),
                metadata={"keywords": keywords, "source": "twitter"},
            )
            
        except Exception as e:
            self._last_error = str(e)
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return ChannelResult(
                success=False,
                error_message=str(e),
                processing_time_ms=processing_time,
            )
    
    async def _collect_via_skill(
        self,
        keywords: list[str],
        options: dict[str, Any]
    ) -> dict[str, Any]:
        """通过 Skill 采集"""
        skill_params = {
            "platform": "twitter",
            "keywords": keywords,
            "limit": options.get("limit", 100),
        }
        
        if options.get("lang"):
            skill_params["lang"] = options["lang"]
        if options.get("result_type"):
            skill_params["result_type"] = options["result_type"]
        
        result = await self.skill_executor.execute(
            skill_name="agent-reach",
            params=skill_params
        )
        
        return result
    
    async def _collect_mock(
        self,
        keywords: list[str],
        options: dict[str, Any]
    ) -> dict[str, Any]:
        """模拟采集数据"""
        limit = options.get("limit", 10)
        keyword = keywords[0] if keywords else "test"
        
        mock_data = []
        for i in range(min(limit, 10)):
            mock_item = {
                "id": f"tw_{hashlib.md5(f'{keyword}_{i}'.encode()).hexdigest()[:12]}",
                "text": f"这是一条关于 {keyword} 的推文内容 #{i+1} #话题",
                "user": {
                    "screen_name": f"user_{i+1}",
                    "name": f"用户{i+1}",
                    "followers_count": 1000 * (i + 1),
                },
                "created_at": datetime.now().isoformat(),
                "favorite_count": 100 - i * 10,
                "retweet_count": 50 - i * 5,
                "reply_count": 20 - i * 2,
                "lang": "zh",
            }
            mock_data.append(mock_item)
        
        return {
            "success": True,
            "data": mock_data,
            "total": len(mock_data),
            "has_more": False,
        }
    
    def _convert_to_channel_data(
        self,
        item: dict[str, Any]
    ) -> ChannelData:
        """转换为 ChannelData 格式"""
        # 解析时间
        published_at = None
        if item.get("created_at"):
            try:
                published_at = datetime.fromisoformat(
                    item["created_at"].replace("Z", "+00:00")
                )
            except:
                pass
        
        # 提取作者信息
        user = item.get("user", {})
        author = user.get("screen_name", user.get("name", "unknown"))
        
        return ChannelData(
            channel_id=self.channel_id,
            channel_type=ChannelType.TWITTER,
            external_id=item.get("id", ""),
            content=item.get("text", item.get("full_text", "")),
            author=author,
            published_at=published_at,
            url=f"https://twitter.com/user/status/{item.get('id', '')}",
            language=item.get("lang"),
            metrics={
                "likes": item.get("favorite_count", 0),
                "retweets": item.get("retweet_count", 0),
                "replies": item.get("reply_count", 0),
                "followers": user.get("followers_count", 0),
            },
            metadata={
                "user": user,
                "hashtags": item.get("entities", {}).get("hashtags", []),
                "raw": item,
            },
        )
    
    async def test_connection(self) -> bool:
        """测试连接"""
        try:
            if self.skill_executor:
                result = await self.skill_executor.test_skill("agent-reach")
                return result.get("available", False)
            return True  # 模拟模式
        except Exception as e:
            self._last_error = str(e)
            return False
    
    async def search(
        self,
        query: str,
        limit: int = 100
    ) -> ChannelResult:
        """
        搜索推文
        
        Args:
            query: 搜索查询
            limit: 最大返回数量
            
        Returns:
            ChannelResult: 搜索结果
        """
        return await self.collect(
            keywords=[query],
            options={"limit": limit, "result_type": "mixed"}
        )
    
    async def get_trending(
        self,
        location: str = "worldwide"
    ) -> ChannelResult:
        """
        获取热门话题
        
        Args:
            location: 地点
            
        Returns:
            ChannelResult: 热门话题
        """
        # 模拟热门话题
        mock_trends = [
            {"name": "#热点话题1", "tweet_volume": 10000},
            {"name": "#热点话题2", "tweet_volume": 8000},
            {"name": "#热点话题3", "tweet_volume": 5000},
        ]
        
        return ChannelResult(
            success=True,
            data=[],
            metadata={"trends": mock_trends, "location": location},
        )