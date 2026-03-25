"""
Agent command parser for parsing natural language commands.
"""

import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from .models import ParsedCommand, IntentType


class CommandParser:
    """
    Parse natural language commands from Agent into structured format.
    
    Supported command types:
    - collect: 数据采集指令
    - analyze: 数据分析指令
    - query: 数据查询指令
    - report: 报告生成指令
    - subscribe: 订阅预警指令
    - config: 配置管理指令
    """
    
    # 指令关键词映射
    INTENT_KEYWORDS = {
        IntentType.COLLECT: [
            "采集", "抓取", "获取", "收集", "下载", "爬取",
            "collect", "fetch", "crawl", "scrape"
        ],
        IntentType.ANALYZE: [
            "分析", "评估", "检测", "判断", "识别",
            "analyze", "assess", "detect"
        ],
        IntentType.QUERY: [
            "查询", "搜索", "查找", "检索", "显示", "列出",
            "query", "search", "find", "show", "list"
        ],
        IntentType.REPORT: [
            "报告", "日报", "周报", "摘要", "总结", "生成",
            "report", "summary", "generate"
        ],
        IntentType.SUBSCRIBE: [
            "订阅", "关注", "通知", "预警", "提醒",
            "subscribe", "follow", "alert", "notify"
        ],
        IntentType.CONFIG: [
            "配置", "设置", "添加", "删除", "修改", "更新",
            "config", "set", "add", "delete", "update"
        ],
    }
    
    # 平台关键词映射
    PLATFORM_KEYWORDS = {
        "twitter": ["twitter", "推特", "tw"],
        "reddit": ["reddit", "红迪"],
        "news": ["新闻", "news", "资讯"],
        "youtube": ["youtube", "油管", "yt"],
        "weibo": ["微博", "weibo"],
        "wechat": ["微信", "公众号", "wechat"],
    }
    
    # 时间范围关键词映射
    TIME_RANGE_KEYWORDS = {
        "1h": ["最近一小时", "过去一小时", "1小时", "last hour", "1h"],
        "24h": ["今天", "最近一天", "过去一天", "24小时", "today", "24h"],
        "7d": ["最近一周", "过去一周", "7天", "本周", "this week", "7d"],
        "30d": ["最近一月", "过去一月", "30天", "本月", "this month", "30d"],
    }
    
    # 情感关键词映射
    SENTIMENT_KEYWORDS = {
        "positive": ["正面", "积极", "利好", "好的", "positive"],
        "negative": ["负面", "消极", "利空", "坏的", "negative"],
        "neutral": ["中性", "中立", "neutral"],
    }
    
    def __init__(self):
        """Initialize the command parser."""
        self._build_patterns()
    
    def _build_patterns(self):
        """Build regex patterns for command parsing."""
        # 平台匹配模式
        platform_pattern = "|".join(
            f"(?P<{name}>{'|'.join(map(re.escape, keywords))})"
            for name, keywords in self.PLATFORM_KEYWORDS.items()
        )
        self.platform_re = re.compile(platform_pattern, re.IGNORECASE)
        
        # 时间范围匹配模式
        time_pattern = "|".join(
            f"(?P<{name}>{'|'.join(map(re.escape, keywords))})"
            for name, keywords in self.TIME_RANGE_KEYWORDS.items()
        )
        self.time_re = re.compile(time_pattern, re.IGNORECASE)
        
        # 情感匹配模式
        sentiment_pattern = "|".join(
            f"(?P<{name}>{'|'.join(map(re.escape, keywords))})"
            for name, keywords in self.SENTIMENT_KEYWORDS.items()
        )
        self.sentiment_re = re.compile(sentiment_pattern, re.IGNORECASE)
    
    def parse(self, text: str, context: Optional[Dict[str, Any]] = None) -> ParsedCommand:
        """
        Parse natural language command text.
        
        Args:
            text: Natural language command text
            context: Optional context for parsing
            
        Returns:
            ParsedCommand with parsed intent and parameters
        """
        text = text.strip()
        
        # 1. 识别意图类型
        intent_type = self._recognize_intent(text)
        
        # 2. 提取参数
        params = self._extract_params(text, intent_type)
        
        # 3. 计算置信度
        confidence = self._calculate_confidence(text, intent_type, params)
        
        return ParsedCommand(
            raw_text=text,
            intent_type=intent_type,
            params=params,
            confidence=confidence,
            metadata={"context": context or {}, "parsed_at": datetime.now().isoformat()},
        )
    
    def _recognize_intent(self, text: str) -> IntentType:
        """Recognize intent type from text."""
        text_lower = text.lower()
        
        # 计算每种意图的匹配分数
        scores = {}
        for intent_type, keywords in self.INTENT_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0:
                scores[intent_type] = score
        
        if not scores:
            return IntentType.UNKNOWN
        
        # 返回得分最高的意图
        return max(scores, key=scores.get)
    
    def _extract_params(self, text: str, intent_type: IntentType) -> Dict[str, Any]:
        """Extract parameters from text based on intent type."""
        params = {}
        
        # 提取平台
        platform_match = self.platform_re.search(text)
        if platform_match:
            for name, keywords in self.PLATFORM_KEYWORDS.items():
                if platform_match.group(name):
                    params["platform"] = name
                    break
        
        # 提取时间范围
        time_match = self.time_re.search(text)
        if time_match:
            for name, keywords in self.TIME_RANGE_KEYWORDS.items():
                if time_match.group(name):
                    params["time_range"] = name
                    break
        
        # 提取情感
        sentiment_match = self.sentiment_re.search(text)
        if sentiment_match:
            for name, keywords in self.SENTIMENT_KEYWORDS.items():
                if sentiment_match.group(name):
                    params["sentiment"] = name
                    break
        
        # 提取关键词（主题）
        keywords = self._extract_keywords(text, intent_type)
        if keywords:
            params["keywords"] = keywords
        
        # 根据意图类型提取特定参数
        if intent_type == IntentType.COLLECT:
            params.update(self._extract_collect_params(text))
        elif intent_type == IntentType.QUERY:
            params.update(self._extract_query_params(text))
        elif intent_type == IntentType.SUBSCRIBE:
            params.update(self._extract_subscribe_params(text))
        
        return params
    
    def _extract_keywords(self, text: str, intent_type: IntentType) -> List[str]:
        """Extract topic keywords from text."""
        # 移除已知的关键词
        clean_text = text
        for keywords in self.INTENT_KEYWORDS.values():
            for kw in keywords:
                clean_text = clean_text.replace(kw, "")
        for keywords in self.PLATFORM_KEYWORDS.values():
            for kw in keywords:
                clean_text = clean_text.replace(kw, "")
        for keywords in self.TIME_RANGE_KEYWORDS.values():
            for kw in keywords:
                clean_text = clean_text.replace(kw, "")
        
        # 提取可能的主题关键词
        # 简单分词，提取中文词组
        keywords = []
        
        # 匹配中文词组（2-4个字）
        chinese_pattern = re.findall(r'[\u4e00-\u9fa5]{2,4}', clean_text)
        keywords.extend(chinese_pattern[:3])  # 最多3个关键词
        
        # 匹配英文单词
        english_pattern = re.findall(r'\b[a-zA-Z]{3,}\b', clean_text)
        keywords.extend([w.lower() for w in english_pattern[:2]])
        
        return list(set(keywords))
    
    def _extract_collect_params(self, text: str) -> Dict[str, Any]:
        """Extract parameters specific to collect intent."""
        params = {}
        
        # 提取数量限制
        limit_match = re.search(r'(\d+)\s*(条|个|篇)', text)
        if limit_match:
            params["limit"] = int(limit_match.group(1))
        
        return params
    
    def _extract_query_params(self, text: str) -> Dict[str, Any]:
        """Extract parameters specific to query intent."""
        params = {}
        
        # 提取事件类型
        event_types = ["选举", "政策", "经济", "社会", "election", "policy", "economic", "social"]
        for event_type in event_types:
            if event_type in text.lower():
                params["event_type"] = event_type
                break
        
        return params
    
    def _extract_subscribe_params(self, text: str) -> Dict[str, Any]:
        """Extract parameters specific to subscribe intent."""
        params = {}
        
        # 提取通知渠道
        channels = ["飞书", "微信", "邮件", "feishu", "wechat", "email"]
        for channel in channels:
            if channel in text.lower():
                params["channel"] = channel
                break
        
        # 提取阈值
        threshold_match = re.search(r'超过|大于|高于\s*(\d+)%?', text)
        if threshold_match:
            params["threshold"] = int(threshold_match.group(1))
        
        return params
    
    def _calculate_confidence(
        self, text: str, intent_type: IntentType, params: Dict[str, Any]
    ) -> float:
        """Calculate confidence score for the parsed command."""
        if intent_type == IntentType.UNKNOWN:
            return 0.0
        
        confidence = 0.5  # 基础置信度
        
        # 根据参数完整性增加置信度
        if params.get("platform"):
            confidence += 0.15
        if params.get("keywords"):
            confidence += 0.15
        if params.get("time_range"):
            confidence += 0.10
        if params.get("sentiment"):
            confidence += 0.10
        
        return min(confidence, 1.0)
    
    def suggest_command(self, text: str) -> List[str]:
        """
        Suggest possible commands based on partial input.
        
        Args:
            text: Partial command text
            
        Returns:
            List of suggested complete commands
        """
        suggestions = []
        
        # 基于输入关键词建议
        if any(kw in text for kw in ["采集", "抓取"]):
            suggestions.extend([
                "采集Twitter关于选举的最新数据",
                "采集Reddit关于经济的讨论",
                "采集最近24小时的新闻",
            ])
        
        if any(kw in text for kw in ["分析", "评估"]):
            suggestions.extend([
                "分析今天选举话题的情感倾向",
                "分析过去一周的舆情趋势",
            ])
        
        if any(kw in text for kw in ["查询", "搜索"]):
            suggestions.extend([
                "查询过去一周的负面事件",
                "显示今天的热点话题",
            ])
        
        if any(kw in text for kw in ["报告", "日报"]):
            suggestions.extend([
                "生成今天舆情日报",
                "生成本周舆情摘要",
            ])
        
        return suggestions[:5]  # 最多返回5个建议