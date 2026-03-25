"""
Reddit 渠道适配器

通过 agent-reach 技能或 Reddit API 采集数据。
"""

from datetime import datetime
from typing import Any, Optional
import hashlib

from ..base import ChannelAdapter, ChannelConfig, ChannelResult
from ..models import ChannelData, ChannelType


class RedditAdapter(ChannelAdapter):
    """
    Reddit 渠道适配器
    
    采集 Reddit 帖子和评论数据。
    """
    
    def __init__(
        self,
        config: ChannelConfig,
        skill_executor: Optional[Any] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None
    ):
        """
        初始化 Reddit 适配器
        
        Args:
            config: 渠道配置
            skill_executor: Agent Skill 执行器
            client_id: Reddit Client ID
            client_secret: Reddit Client Secret
        """
        super().__init__(config)
        self.skill_executor = skill_executor
        self.client_id = client_id
        self.client_secret = client_secret
    
    async def collect(
        self,
        keywords: list[str],
        options: Optional[dict[str, Any]] = None
    ) -> ChannelResult:
        """
        采集 Reddit 数据
        
        Args:
            keywords: 关键词列表
            options: 额外选项
                - limit: 最大返回数量
                - subreddit: 子版块名称
                - sort: 排序方式 (hot, new, top, relevant)
                - time_range: 时间范围
                
        Returns:
            ChannelResult: 采集结果
        """
        start_time = datetime.now()
        options = options or {}
        limit = options.get("limit", 100)
        
        try:
            if self.skill_executor:
                result = await self._collect_via_skill(keywords, options)
            else:
                result = await self._collect_mock(keywords, options)
            
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
                metadata={"keywords": keywords, "source": "reddit"},
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
            "platform": "reddit",
            "keywords": keywords,
            "limit": options.get("limit", 100),
        }
        
        if options.get("subreddit"):
            skill_params["subreddit"] = options["subreddit"]
        if options.get("sort"):
            skill_params["sort"] = options["sort"]
        if options.get("time_range"):
            skill_params["time_range"] = options["time_range"]
        
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
        subreddit = options.get("subreddit", "all")
        
        mock_data = []
        for i in range(min(limit, 10)):
            mock_item = {
                "id": f"rd_{hashlib.md5(f'{keyword}_{i}'.encode()).hexdigest()[:12]}",
                "title": f"关于 {keyword} 的讨论 #{i+1}",
                "selftext": f"这是一篇关于 {keyword} 的帖子内容，欢迎大家讨论...",
                "author": f"redditor_{i+1}",
                "subreddit": subreddit,
                "created_utc": datetime.now().timestamp(),
                "score": 100 - i * 10,
                "num_comments": 50 - i * 5,
                "upvote_ratio": 0.9 - i * 0.05,
                "url": f"https://reddit.com/r/{subreddit}/comments/{i+1}",
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
        published_at = None
        if item.get("created_utc"):
            try:
                published_at = datetime.fromtimestamp(item["created_utc"])
            except:
                pass
        
        content = item.get("selftext", "")
        if not content:
            content = item.get("title", "")
        
        return ChannelData(
            channel_id=self.channel_id,
            channel_type=ChannelType.REDDIT,
            external_id=item.get("id", ""),
            content=content,
            author=item.get("author", "unknown"),
            published_at=published_at,
            url=item.get("url", ""),
            title=item.get("title", ""),
            language="en",
            metrics={
                "score": item.get("score", 0),
                "comments": item.get("num_comments", 0),
                "upvote_ratio": item.get("upvote_ratio", 0),
            },
            metadata={
                "subreddit": item.get("subreddit", ""),
                "raw": item,
            },
        )
    
    async def test_connection(self) -> bool:
        """测试连接"""
        try:
            if self.skill_executor:
                result = await self.skill_executor.test_skill("agent-reach")
                return result.get("available", False)
            return True
        except Exception as e:
            self._last_error = str(e)
            return False
    
    async def get_subreddit_posts(
        self,
        subreddit: str,
        sort: str = "hot",
        limit: int = 100
    ) -> ChannelResult:
        """
        获取子版块帖子
        
        Args:
            subreddit: 子版块名称
            sort: 排序方式
            limit: 最大返回数量
            
        Returns:
            ChannelResult: 帖子列表
        """
        return await self.collect(
            keywords=[],
            options={
                "subreddit": subreddit,
                "sort": sort,
                "limit": limit,
            }
        )
    
    async def search_posts(
        self,
        query: str,
        subreddit: Optional[str] = None,
        limit: int = 100
    ) -> ChannelResult:
        """
        搜索帖子
        
        Args:
            query: 搜索查询
            subreddit: 限制子版块
            limit: 最大返回数量
            
        Returns:
            ChannelResult: 搜索结果
        """
        options = {"limit": limit, "sort": "relevant"}
        if subreddit:
            options["subreddit"] = subreddit
        
        return await self.collect(keywords=[query], options=options)