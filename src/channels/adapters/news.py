"""
新闻渠道适配器

通过 Tavily 或其他新闻 API 采集新闻数据。
"""

from datetime import datetime
from typing import Any, Optional
import hashlib
import os

from ..base import ChannelAdapter, ChannelConfig, ChannelResult
from ..models import ChannelData, ChannelType


class NewsAdapter(ChannelAdapter):
    """
    新闻渠道适配器
    
    采集新闻网站和新闻聚合平台的数据。
    """
    
    # 主流新闻域名
    MAJOR_NEWS_DOMAINS = [
        "reuters.com",
        "bloomberg.com",
        "cnbc.com",
        "wsj.com",
        "ft.com",
        "nytimes.com",
        "washingtonpost.com",
        "bbc.com",
        "cnn.com",
        "apnews.com",
    ]
    
    def __init__(
        self,
        config: ChannelConfig,
        tavily_api_key: Optional[str] = None,
        skill_executor: Optional[Any] = None
    ):
        """
        初始化新闻适配器
        
        Args:
            config: 渠道配置
            tavily_api_key: Tavily API Key
            skill_executor: Agent Skill 执行器
        """
        super().__init__(config)
        self.tavily_api_key = tavily_api_key or os.environ.get("TAVILY_API_KEY")
        self.skill_executor = skill_executor
        self._client = None
    
    async def collect(
        self,
        keywords: list[str],
        options: Optional[dict[str, Any]] = None
    ) -> ChannelResult:
        """
        采集新闻数据
        
        Args:
            keywords: 关键词列表
            options: 额外选项
                - limit: 最大返回数量
                - days: 最近几天的新闻
                - domains: 限制域名列表
                - search_depth: 搜索深度
                
        Returns:
            ChannelResult: 采集结果
        """
        start_time = datetime.now()
        options = options or {}
        limit = options.get("limit", 50)
        
        try:
            if self.skill_executor:
                result = await self._collect_via_skill(keywords, options)
            elif self.tavily_api_key:
                result = await self._collect_via_tavily(keywords, options)
            else:
                result = await self._collect_mock(keywords, options)
            
            data_list = []
            for item in result.get("results", result.get("data", [])):
                channel_data = self._convert_to_channel_data(item)
                data_list.append(channel_data)
            
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return ChannelResult(
                success=True,
                data=data_list[:limit],
                total_count=len(data_list),
                processing_time_ms=processing_time,
                metadata={
                    "keywords": keywords,
                    "source": "news",
                    "answer": result.get("answer"),
                },
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
            "platform": "news",
            "keywords": keywords,
            "limit": options.get("limit", 50),
        }
        
        if options.get("days"):
            skill_params["days"] = options["days"]
        if options.get("domains"):
            skill_params["domains"] = options["domains"]
        
        result = await self.skill_executor.execute(
            skill_name="tavily-search",
            params=skill_params
        )
        
        return result
    
    async def _collect_via_tavily(
        self,
        keywords: list[str],
        options: dict[str, Any]
    ) -> dict[str, Any]:
        """通过 Tavily API 采集"""
        client = self._get_client()
        
        if client is None:
            return await self._collect_mock(keywords, options)
        
        query = " ".join(keywords)
        
        request_body = {
            "api_key": self.tavily_api_key,
            "query": query,
            "max_results": min(options.get("limit", 50), 10),
            "search_depth": options.get("search_depth", "basic"),
            "include_answer": True,
        }
        
        if options.get("days"):
            request_body["days"] = options["days"]
        if options.get("domains"):
            request_body["include_domains"] = options["domains"]
        
        response = await client.post(
            "https://api.tavily.com/search",
            json=request_body
        )
        
        if response.status_code != 200:
            raise Exception(f"Tavily API error: {response.status_code}")
        
        return response.json()
    
    async def _collect_mock(
        self,
        keywords: list[str],
        options: dict[str, Any]
    ) -> dict[str, Any]:
        """模拟采集数据"""
        limit = options.get("limit", 5)
        keyword = " ".join(keywords) if keywords else "test"
        
        mock_data = []
        for i in range(min(limit, 5)):
            domain = self.MAJOR_NEWS_DOMAINS[i % len(self.MAJOR_NEWS_DOMAINS)]
            mock_item = {
                "title": f"关于 {keyword} 的重要新闻报道 #{i+1}",
                "url": f"https://{domain}/article/{hashlib.md5(f'{keyword}_{i}'.encode()).hexdigest()[:8]}",
                "content": f"这是一篇关于 {keyword} 的新闻报道。主要讨论了相关的重要议题和发展趋势...",
                "author": f"Reporter {i+1}",
                "published_date": datetime.now().isoformat(),
                "score": 0.9 - i * 0.1,
            }
            mock_data.append(mock_item)
        
        return {
            "results": mock_data,
            "answer": f"关于 {keyword} 的最新新闻摘要",
            "query": keyword,
        }
    
    def _get_client(self):
        """获取 HTTP 客户端"""
        if self._client is None:
            try:
                import httpx
                self._client = httpx.AsyncClient(timeout=self.config.timeout)
            except ImportError:
                self._client = None
        return self._client
    
    def _convert_to_channel_data(
        self,
        item: dict[str, Any]
    ) -> ChannelData:
        """转换为 ChannelData 格式"""
        published_at = None
        if item.get("published_date"):
            try:
                published_at = datetime.fromisoformat(
                    item["published_date"].replace("Z", "+00:00")
                )
            except:
                pass
        
        return ChannelData(
            channel_id=self.channel_id,
            channel_type=ChannelType.NEWS,
            external_id=item.get("url", ""),
            content=item.get("content", ""),
            author=item.get("author", ""),
            published_at=published_at,
            url=item.get("url", ""),
            title=item.get("title", ""),
            language="auto",
            metrics={
                "score": item.get("score", 0),
            },
            metadata={
                "source": item.get("source", ""),
                "raw": item,
            },
        )
    
    async def test_connection(self) -> bool:
        """测试连接"""
        try:
            if self.skill_executor:
                result = await self.skill_executor.test_skill("tavily-search")
                return result.get("available", False)
            
            if self.tavily_api_key:
                # 发送测试请求
                client = self._get_client()
                if client:
                    response = await client.post(
                        "https://api.tavily.com/search",
                        json={
                            "api_key": self.tavily_api_key,
                            "query": "test",
                            "max_results": 1,
                        }
                    )
                    return response.status_code == 200
            
            return True
        except Exception as e:
            self._last_error = str(e)
            return False
    
    async def search_financial(
        self,
        keywords: list[str],
        limit: int = 20
    ) -> ChannelResult:
        """
        搜索财经新闻
        
        Args:
            keywords: 关键词列表
            limit: 最大返回数量
            
        Returns:
            ChannelResult: 财经新闻
        """
        return await self.collect(
            keywords=keywords,
            options={
                "limit": limit,
                "domains": self.MAJOR_NEWS_DOMAINS,
                "search_depth": "advanced",
            }
        )
    
    async def search_recent(
        self,
        query: str,
        days: int = 7,
        limit: int = 20
    ) -> ChannelResult:
        """
        搜索最近新闻
        
        Args:
            query: 搜索查询
            days: 最近几天
            limit: 最大返回数量
            
        Returns:
            ChannelResult: 最近新闻
        """
        return await self.collect(
            keywords=[query],
            options={
                "limit": limit,
                "days": days,
            }
        )
    
    async def close(self) -> None:
        """关闭客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None