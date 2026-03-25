"""
渠道适配器实现

包含各平台的适配器实现。
"""

from .twitter import TwitterAdapter
from .reddit import RedditAdapter
from .news import NewsAdapter

__all__ = [
    "TwitterAdapter",
    "RedditAdapter",
    "NewsAdapter",
]