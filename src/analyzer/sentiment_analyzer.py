"""
Sentiment analyzer for sentiment analysis using LLM or rule-based methods.
"""

import re
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from abc import ABC, abstractmethod

from .models import SentimentResult, SentimentLabel

logger = logging.getLogger(__name__)


class SentimentAnalyzerBase(ABC):
    """Base class for sentiment analyzers."""
    
    @abstractmethod
    def analyze(self, text: str) -> SentimentResult:
        """Analyze sentiment of text."""
        pass
    
    @abstractmethod
    def analyze_batch(self, texts: List[str]) -> List[SentimentResult]:
        """Analyze sentiment of multiple texts."""
        pass


class RuleBasedSentimentAnalyzer(SentimentAnalyzerBase):
    """
    Rule-based sentiment analyzer using lexicons and patterns.
    
    Used as fallback when LLM is not available.
    """
    
    # Positive and negative word lists
    POSITIVE_WORDS = {
        "zh": [
            "好", "优秀", "棒", "赞", "喜欢", "支持", "成功", "增长", "上涨",
            "利好", "积极", "乐观", "繁荣", "进步", "创新", "突破", "胜利",
            "高兴", "满意", "期待", "希望", "祝福", "恭喜", "厉害", "牛",
        ],
        "en": [
            "good", "great", "excellent", "amazing", "wonderful", "fantastic",
            "love", "like", "support", "success", "growth", "positive", "bullish",
            "optimistic", "happy", "pleased", "hope", "win", "best", "nice",
        ],
    }
    
    NEGATIVE_WORDS = {
        "zh": [
            "坏", "差", "烂", "糟", "讨厌", "反对", "失败", "下降", "下跌",
            "利空", "消极", "悲观", "危机", "风险", "损失", "丑闻", "腐败",
            "愤怒", "失望", "担忧", "恐惧", "警告", "危险", "问题", "错误",
        ],
        "en": [
            "bad", "terrible", "awful", "horrible", "poor", "worst", "hate",
            "dislike", "oppose", "fail", "decline", "loss", "negative", "bearish",
            "pessimistic", "crisis", "risk", "danger", "problem", "error", "wrong",
        ],
    }
    
    # Intensifiers
    INTENSIFIERS = {
        "zh": ["非常", "极其", "特别", "相当", "十分", "很", "太"],
        "en": ["very", "extremely", "really", "absolutely", "highly", "so"],
    }
    
    # Negation words
    NEGATIONS = {
        "zh": ["不", "没", "无", "非", "未"],
        "en": ["not", "no", "never", "neither", "nobody", "nothing"],
    }
    
    def __init__(self, language: str = "auto"):
        """
        Initialize the rule-based analyzer.
        
        Args:
            language: Default language (auto, zh, en)
        """
        self.language = language
    
    def analyze(self, text: str) -> SentimentResult:
        """Analyze sentiment using rules."""
        lang = self._detect_language(text) if self.language == "auto" else self.language
        
        positive_count = self._count_words(text, self.POSITIVE_WORDS.get(lang, []))
        negative_count = self._count_words(text, self.NEGATIVE_WORDS.get(lang, []))
        
        # Calculate sentiment score
        total = positive_count + negative_count
        if total == 0:
            score = 0.0
            label = SentimentLabel.NEUTRAL
            confidence = 0.5
        else:
            score = (positive_count - negative_count) / total
            confidence = min(total / 5, 1.0)  # More words = higher confidence
            
            if score > 0.1:
                label = SentimentLabel.POSITIVE
            elif score < -0.1:
                label = SentimentLabel.NEGATIVE
            else:
                label = SentimentLabel.NEUTRAL
        
        return SentimentResult(
            label=label,
            score=score,
            confidence=confidence,
            model="rule-based",
        )
    
    def analyze_batch(self, texts: List[str]) -> List[SentimentResult]:
        """Analyze multiple texts."""
        return [self.analyze(text) for text in texts]
    
    def _detect_language(self, text: str) -> str:
        """Detect language of text."""
        chinese_ratio = len(re.findall(r"[\u4e00-\u9fa5]", text)) / max(len(text), 1)
        return "zh" if chinese_ratio > 0.3 else "en"
    
    def _count_words(self, text: str, words: List[str]) -> int:
        """Count occurrences of words in text."""
        text_lower = text.lower()
        return sum(1 for word in words if word in text_lower)


class LLMSentimentAnalyzer(SentimentAnalyzerBase):
    """
    LLM-based sentiment analyzer.
    
    Uses LLM API for more accurate sentiment analysis.
    """
    
    SYSTEM_PROMPT = """你是一个情感分析专家。分析文本的情感倾向。

返回JSON格式：
{
    "label": "positive|negative|neutral",
    "score": -1到1之间的数字,
    "confidence": 0到1之间的数字,
    "reasoning": "简要说明判断依据"
}

只返回JSON，不要其他内容。"""
    
    def __init__(self, llm_client: Any, model: str = "default"):
        """
        Initialize the LLM analyzer.
        
        Args:
            llm_client: LLM client instance
            model: Model name to use
        """
        self.llm_client = llm_client
        self.model = model
    
    def analyze(self, text: str) -> SentimentResult:
        """Analyze sentiment using LLM."""
        try:
            prompt = f"{self.SYSTEM_PROMPT}\n\n文本：{text}"
            
            response = self.llm_client.generate(prompt)
            
            # Parse response
            result = self._parse_response(response)
            
            return SentimentResult(
                label=SentimentLabel(result.get("label", "neutral")),
                score=result.get("score", 0.0),
                confidence=result.get("confidence", 0.8),
                model=self.model,
            )
            
        except Exception as e:
            logger.error(f"LLM sentiment analysis failed: {e}")
            # Fallback to rule-based
            fallback = RuleBasedSentimentAnalyzer()
            return fallback.analyze(text)
    
    def analyze_batch(self, texts: List[str]) -> List[SentimentResult]:
        """Analyze multiple texts."""
        return [self.analyze(text) for text in texts]
    
    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response."""
        try:
            # Try to extract JSON
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
        
        # Default values
        return {"label": "neutral", "score": 0.0, "confidence": 0.5}


class HybridSentimentAnalyzer(SentimentAnalyzerBase):
    """
    Hybrid sentiment analyzer combining multiple methods.
    
    Uses LLM for important documents and rule-based for others.
    """
    
    def __init__(
        self,
        llm_client: Optional[Any] = None,
        use_llm_for_long: bool = True,
        min_length_for_llm: int = 50,
    ):
        """
        Initialize hybrid analyzer.
        
        Args:
            llm_client: Optional LLM client
            use_llm_for_long: Use LLM for longer texts
            min_length_for_llm: Minimum text length to use LLM
        """
        self.rule_analyzer = RuleBasedSentimentAnalyzer()
        self.llm_analyzer = LLMSentimentAnalyzer(llm_client) if llm_client else None
        self.use_llm_for_long = use_llm_for_long
        self.min_length_for_llm = min_length_for_llm
    
    def analyze(self, text: str) -> SentimentResult:
        """Analyze sentiment using hybrid approach."""
        # Use LLM for longer, more important texts
        if self.llm_analyzer and self.use_llm_for_long and len(text) >= self.min_length_for_llm:
            return self.llm_analyzer.analyze(text)
        
        # Use rule-based for shorter texts or when LLM unavailable
        return self.rule_analyzer.analyze(text)
    
    def analyze_batch(self, texts: List[str]) -> List[SentimentResult]:
        """Analyze multiple texts."""
        return [self.analyze(text) for text in texts]


# Factory function
def create_sentiment_analyzer(
    method: str = "rule",
    llm_client: Optional[Any] = None,
    **kwargs
) -> SentimentAnalyzerBase:
    """
    Create a sentiment analyzer.
    
    Args:
        method: Analyzer method (rule, llm, hybrid)
        llm_client: Optional LLM client
        **kwargs: Additional arguments
        
    Returns:
        SentimentAnalyzer instance
    """
    if method == "llm" and llm_client:
        return LLMSentimentAnalyzer(llm_client, **kwargs)
    elif method == "hybrid":
        return HybridSentimentAnalyzer(llm_client=llm_client, **kwargs)
    else:
        return RuleBasedSentimentAnalyzer(**kwargs)