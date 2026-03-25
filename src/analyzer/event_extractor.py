"""
Event extractor for extracting events from text.
"""

import re
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid

from .models import Event, EventType, SentimentResult

logger = logging.getLogger(__name__)


class EventExtractor:
    """
    Extract events from text using patterns and LLM.
    
    Features:
    - Event type classification
    - Entity extraction within events
    - Impact assessment
    """
    
    # Event type patterns
    EVENT_PATTERNS = {
        EventType.ELECTION: [
            r"选举|投票|候选人|竞选|民意调查|总统|总理|议会|国会",
            r"election|vote|candidate|campaign|poll|president|parliament",
        ],
        EventType.POLICY: [
            r"政策|法规|条例|决定|措施|改革|立法|通过|签署",
            r"policy|regulation|law|decree|reform|legislation|signed|passed",
        ],
        EventType.ECONOMIC: [
            r"经济|GDP|通胀|利率|汇率|股市|期货|债券|央行|加息|降息",
            r"economic|GDP|inflation|interest rate|stock|bond|central bank|Fed",
        ],
        EventType.SOCIAL: [
            r"社会|抗议|示威|游行|罢工|事故|灾难|疫情|公共卫生",
            r"protest|demonstration|strike|disaster|pandemic|epidemic|outbreak",
        ],
        EventType.SCANDAL: [
            r"丑闻|腐败|贪污|贿赂|欺诈|丑事|曝光|调查|起诉|判刑",
            r"scandal|corruption|bribery|fraud|investigation|charged|sentenced",
        ],
        EventType.DISASTER: [
            r"灾难|地震|洪水|台风|海啸|火灾|旱灾|雪灾|泥石流",
            r"disaster|earthquake|flood|typhoon|tsunami|fire|drought",
        ],
        EventType.BREAKTHROUGH: [
            r"突破|发现|发明|创新|首次|纪录|专利|技术|科学",
            r"breakthrough|discovery|invention|innovation|first|record|patent",
        ],
    }
    
    # Impact indicators
    IMPACT_INDICATORS = {
        "high": [
            r"重大|重要|关键|严重|巨额|大规模|历史性",
            r"major|significant|critical|serious|huge|historic|landmark",
        ],
        "medium": [
            r"较大|显著|明显|一定",
            r"considerable|notable|significant",
        ],
        "low": [
            r"较小|轻微|有限|局部",
            r"minor|limited|small|local",
        ],
    }
    
    # LLM prompt template
    LLM_PROMPT = """分析文本中的事件。

返回JSON格式：
{
    "events": [
        {
            "type": "election|policy|economic|social|scandal|disaster|breakthrough|unknown",
            "title": "事件标题",
            "description": "事件描述",
            "entities": ["相关实体"],
            "impact": {
                "level": "high|medium|low",
                "direction": "positive|negative|neutral",
                "affected_areas": ["影响的领域"]
            },
            "confidence": 0.8
        }
    ]
}

文本：{text}

只返回JSON。"""

    def __init__(
        self,
        llm_client: Optional[Any] = None,
        use_llm: bool = True,
        min_confidence: float = 0.5,
    ):
        """
        Initialize event extractor.
        
        Args:
            llm_client: Optional LLM client
            use_llm: Use LLM for extraction
            min_confidence: Minimum confidence threshold
        """
        self.llm_client = llm_client
        self.use_llm = use_llm and llm_client is not None
        self.min_confidence = min_confidence
    
    def extract(self, text: str, entities: Optional[List[str]] = None) -> List[Event]:
        """
        Extract events from text.
        
        Args:
            text: Text to analyze
            entities: Pre-extracted entities for context
            
        Returns:
            List of extracted events
        """
        events = []
        
        # Use LLM if available
        if self.use_llm:
            llm_events = self._extract_with_llm(text, entities)
            events.extend(llm_events)
        
        # Also use rule-based patterns
        pattern_events = self._extract_with_patterns(text)
        events.extend(pattern_events)
        
        # Deduplicate
        events = self._deduplicate_events(events)
        
        # Filter by confidence
        events = [e for e in events if e.confidence >= self.min_confidence]
        
        return events
    
    def _extract_with_llm(
        self, text: str, entities: Optional[List[str]] = None
    ) -> List[Event]:
        """Extract events using LLM."""
        if not self.llm_client:
            return []
        
        try:
            prompt = self.LLM_PROMPT.format(text=text)
            if entities:
                prompt += f"\n\n已知实体：{', '.join(entities)}"
            
            response = self.llm_client.generate(prompt)
            
            # Parse response
            json_match = re.search(r'\{[\s\S]*\}', response)
            if not json_match:
                return []
            
            result = json.loads(json_match.group())
            
            events = []
            for event_data in result.get("events", []):
                type_map = {
                    "election": EventType.ELECTION,
                    "policy": EventType.POLICY,
                    "economic": EventType.ECONOMIC,
                    "social": EventType.SOCIAL,
                    "scandal": EventType.SCANDAL,
                    "disaster": EventType.DISASTER,
                    "breakthrough": EventType.BREAKTHROUGH,
                }
                
                event = Event(
                    event_id=f"evt_{uuid.uuid4().hex[:8]}",
                    type=type_map.get(event_data.get("type", ""), EventType.UNKNOWN),
                    title=event_data.get("title", ""),
                    description=event_data.get("description", ""),
                    entities=event_data.get("entities", []),
                    impact=event_data.get("impact", {}),
                    confidence=event_data.get("confidence", 0.7),
                )
                events.append(event)
            
            return events
            
        except Exception as e:
            logger.error(f"LLM event extraction failed: {e}")
            return []
    
    def _extract_with_patterns(self, text: str) -> List[Event]:
        """Extract events using patterns."""
        events = []
        
        for event_type, patterns in self.EVENT_PATTERNS.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    # Extract context around the match
                    start = max(0, match.start() - 50)
                    end = min(len(text), match.end() + 100)
                    context = text[start:end]
                    
                    # Assess impact
                    impact = self._assess_impact(context)
                    
                    event = Event(
                        event_id=f"evt_{uuid.uuid4().hex[:8]}",
                        type=event_type,
                        title=context[:100] + "..." if len(context) > 100 else context,
                        description=f"检测到{event_type.value}相关事件",
                        confidence=0.6,
                        impact=impact,
                    )
                    events.append(event)
        
        return events
    
    def _assess_impact(self, text: str) -> Dict[str, Any]:
        """Assess event impact."""
        impact = {"level": "medium", "direction": "neutral"}
        
        for level, patterns in self.IMPACT_INDICATORS.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    impact["level"] = level
                    break
        
        # Assess direction based on sentiment
        positive_words = ["利好", "增长", "上涨", "成功", "突破", "胜利"]
        negative_words = ["利空", "下降", "下跌", "失败", "损失", "危机"]
        
        pos_count = sum(1 for w in positive_words if w in text)
        neg_count = sum(1 for w in negative_words if w in text)
        
        if pos_count > neg_count:
            impact["direction"] = "positive"
        elif neg_count > pos_count:
            impact["direction"] = "negative"
        
        return impact
    
    def _deduplicate_events(self, events: List[Event]) -> List[Event]:
        """Remove duplicate events."""
        seen = set()
        unique = []
        
        for event in events:
            # Create a key based on type and title similarity
            key = (event.type, event.title[:50])
            if key not in seen:
                seen.add(key)
                unique.append(event)
        
        return unique
    
    def get_event_stats(self, events: List[Event]) -> Dict[str, Any]:
        """Get statistics about extracted events."""
        type_counts = {}
        for event in events:
            type_name = event.type.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1
        
        impact_counts = {"high": 0, "medium": 0, "low": 0}
        for event in events:
            level = event.impact.get("level", "medium")
            impact_counts[level] = impact_counts.get(level, 0) + 1
        
        return {
            "total_events": len(events),
            "type_counts": type_counts,
            "impact_counts": impact_counts,
        }