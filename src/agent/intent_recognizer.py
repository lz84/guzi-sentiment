"""
Intent recognizer for recognizing Agent intents using LLM.
"""

import json
import re
from typing import Dict, Any, Optional, List
from datetime import datetime
from abc import ABC, abstractmethod

from .models import Intent, IntentType


class IntentRecognizer:
    """
    Recognize Agent intents from natural language.
    
    Supports both rule-based and LLM-based intent recognition.
    """
    
    # Intent patterns for rule-based recognition
    INTENT_PATTERNS = {
        IntentType.COLLECT: [
            r"采集(.+?)的?数据",
            r"抓取(.+?)的?内容",
            r"获取(.+?)的?信息",
            r"收集(.+?)相关",
        ],
        IntentType.ANALYZE: [
            r"分析(.+?)的?情感",
            r"评估(.+?)的?倾向",
            r"检测(.+?)的?趋势",
        ],
        IntentType.QUERY: [
            r"查询(.+?)的?数据",
            r"搜索(.+?)相关",
            r"显示(.+?)的?信息",
            r"列出(.+?)的?内容",
        ],
        IntentType.REPORT: [
            r"生成(.+?)报告",
            r"输出(.+?)日报",
            r"总结(.+?)情况",
        ],
        IntentType.SUBSCRIBE: [
            r"订阅(.+?)预警",
            r"关注(.+?)动态",
            r"设置(.+?)提醒",
        ],
        IntentType.CONFIG: [
            r"配置(.+?)参数",
            r"设置(.+?)选项",
            r"添加(.+?)关键词",
            r"更新(.+?)配置",
        ],
    }
    
    def __init__(self, llm_client: Optional[Any] = None, use_llm: bool = True):
        """
        Initialize the intent recognizer.
        
        Args:
            llm_client: Optional LLM client for LLM-based recognition
            use_llm: Whether to use LLM for recognition (default: True)
        """
        self.llm_client = llm_client
        self.use_llm = use_llm and llm_client is not None
    
    def recognize(self, text: str, context: Optional[Dict[str, Any]] = None) -> Intent:
        """
        Recognize intent from natural language text.
        
        Args:
            text: Natural language text
            context: Optional context information
            
        Returns:
            Recognized Intent
        """
        # 优先使用 LLM 识别
        if self.use_llm:
            try:
                return self._recognize_with_llm(text, context)
            except Exception:
                pass  # Fall back to rule-based
        
        # 规则识别
        return self._recognize_with_rules(text, context)
    
    def _recognize_with_llm(self, text: str, context: Optional[Dict[str, Any]] = None) -> Intent:
        """Recognize intent using LLM."""
        prompt = self._build_prompt(text, context)
        
        response = self.llm_client.generate(prompt)
        
        # Parse LLM response
        intent_data = self._parse_llm_response(response)
        
        return Intent(
            intent_type=IntentType(intent_data.get("type", "unknown")),
            params=intent_data.get("params", {}),
            confidence=intent_data.get("confidence", 0.8),
            raw_text=text,
        )
    
    def _build_prompt(self, text: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Build prompt for LLM."""
        return f"""分析以下 Agent 指令，识别意图和参数。

指令: {text}
上下文: {json.dumps(context or {}, ensure_ascii=False)}

请以 JSON 格式返回：
{{
    "type": "collect|analyze|query|report|subscribe|config|unknown",
    "params": {{
        "platform": "twitter|reddit|news|youtube|weibo|wechat",
        "keywords": ["关键词列表"],
        "time_range": "1h|24h|7d|30d",
        "sentiment": "positive|negative|neutral",
        "event_type": "election|policy|economic|social",
        "limit": 数字,
        "channel": "feishu|wechat|email"
    }},
    "confidence": 0.0-1.0
}}

只返回 JSON，不要其他内容。"""

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response to extract intent data."""
        # 尝试提取 JSON
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        # 返回默认值
        return {"type": "unknown", "params": {}, "confidence": 0.0}
    
    def _recognize_with_rules(self, text: str, context: Optional[Dict[str, Any]] = None) -> Intent:
        """Recognize intent using rule-based patterns."""
        text_lower = text.lower()
        
        best_match = None
        best_score = 0
        best_params = {}
        
        for intent_type, patterns in self.INTENT_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    score = len(match.group(1)) / len(text) if match.group(1) else 0.5
                    if score > best_score:
                        best_score = score
                        best_match = intent_type
                        # 提取匹配的主题
                        if match.group(1):
                            best_params["keywords"] = [match.group(1)]
        
        if best_match:
            # 提取额外参数
            best_params.update(self._extract_extra_params(text))
            
            return Intent(
                intent_type=best_match,
                params=best_params,
                confidence=min(0.5 + best_score, 0.9),
                raw_text=text,
            )
        
        return Intent(
            intent_type=IntentType.UNKNOWN,
            params={},
            confidence=0.0,
            raw_text=text,
        )
    
    def _extract_extra_params(self, text: str) -> Dict[str, Any]:
        """Extract additional parameters from text."""
        params = {}
        
        # 提取平台
        platforms = {
            "twitter": ["twitter", "推特"],
            "reddit": ["reddit"],
            "news": ["新闻", "资讯"],
            "youtube": ["youtube", "油管"],
            "weibo": ["微博"],
        }
        for platform, keywords in platforms.items():
            if any(kw in text.lower() for kw in keywords):
                params["platform"] = platform
                break
        
        # 提取时间范围
        time_ranges = {
            "1h": ["最近一小时", "1小时"],
            "24h": ["今天", "最近一天", "24小时"],
            "7d": ["最近一周", "7天", "本周"],
            "30d": ["最近一月", "30天", "本月"],
        }
        for time_range, keywords in time_ranges.items():
            if any(kw in text for kw in keywords):
                params["time_range"] = time_range
                break
        
        # 提取情感
        sentiments = {
            "positive": ["正面", "积极", "利好"],
            "negative": ["负面", "消极", "利空"],
        }
        for sentiment, keywords in sentiments.items():
            if any(kw in text for kw in keywords):
                params["sentiment"] = sentiment
                break
        
        return params
    
    def get_supported_intents(self) -> List[str]:
        """Get list of supported intent types."""
        return [intent.value for intent in IntentType]
    
    def get_intent_examples(self, intent_type: IntentType) -> List[str]:
        """Get example commands for an intent type."""
        examples = {
            IntentType.COLLECT: [
                "采集Twitter关于选举的最新数据",
                "抓取Reddit上关于经济的讨论",
                "获取最近24小时的新闻",
            ],
            IntentType.ANALYZE: [
                "分析今天选举话题的情感倾向",
                "评估过去一周的舆情趋势",
            ],
            IntentType.QUERY: [
                "查询过去一周的负面事件",
                "显示今天的热点话题",
                "列出选举相关的关键事件",
            ],
            IntentType.REPORT: [
                "生成今天舆情日报",
                "输出本周舆情摘要",
            ],
            IntentType.SUBSCRIBE: [
                "订阅选举相关的重大事件预警",
                "关注经济话题的变化并通知我",
            ],
            IntentType.CONFIG: [
                "添加新关键词：降息",
                "设置预警阈值为30%",
            ],
        }
        return examples.get(intent_type, [])