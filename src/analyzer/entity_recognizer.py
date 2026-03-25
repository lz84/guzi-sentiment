"""
Entity recognizer for named entity recognition using spaCy or LLM.
"""

import re
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from .models import Entity, EntityType

logger = logging.getLogger(__name__)


class EntityRecognizer:
    """
    Named entity recognition using spaCy or LLM.
    
    Features:
    - Multi-language support
    - Custom entity patterns
    - Confidence scoring
    """
    
    # Default patterns for rule-based extraction
    DEFAULT_PATTERNS = {
        # Person names (Chinese)
        "person_zh": [
            r"[\u4e00-\u9fa5]{2,4}(?=表示|称|认为|指出|说|认为)",
            r"[王李张刘陈杨赵黄周吴徐孙胡朱高林何郭马罗梁宋郑谢韩唐冯于董萧程曹袁邓许傅沈曾彭吕苏卢蒋蒋蔡贾丁魏薛叶阎余潘杜戴夏钟汪田任姜范方石姚谭廖邹熊金陆郝孔白崔康毛邱秦江史顾侯邵孟龙万段雷钱汤尹黎易常武乔贺赖龚文)",
        ],
        # Organizations
        "organization": [
            r"[\u4e00-\u9fa5]{2,10}(公司|集团|银行|证券|基金|机构|政府|部门|部委|法院|检察院)",
            r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:Inc|Corp|Company|Ltd|LLC|Group))?",
        ],
        # Locations
        "location": [
            r"[\u4e00-\u9fa5]{2,6}(省|市|县|区|州|国|地区)",
            r"(北京|上海|广州|深圳|杭州|成都|武汉|西安|南京|重庆|天津|苏州|郑州|长沙|东莞|青岛|沈阳|宁波|昆明)",
        ],
        # Money
        "money": [
            r"[¥$€£]\s*[\d,]+(?:\.\d+)?(?:万|亿|百万|千万)?(?:元|美元|欧元|英镑)?",
            r"[\d,]+(?:\.\d+)?(?:万|亿|百万|千万)?(?:元|美元|欧元|英镑)",
        ],
        # Percentages
        "percent": [
            r"[\d,]+(?:\.\d+)?%",
        ],
        # Dates
        "date": [
            r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?",
            r"\d{1,2}月\d{1,2}日",
            r"(今天|昨天|明天|本周|上周|下周|本月|上月|下月)",
        ],
    }
    
    def __init__(
        self,
        spacy_model: Optional[str] = None,
        llm_client: Optional[Any] = None,
        use_spacy: bool = True,
        use_llm: bool = False,
        custom_patterns: Optional[Dict[str, List[str]]] = None,
    ):
        """
        Initialize entity recognizer.
        
        Args:
            spacy_model: spaCy model name (e.g., "zh_core_web_sm", "en_core_web_sm")
            llm_client: Optional LLM client
            use_spacy: Use spaCy for NER
            use_llm: Use LLM for NER
            custom_patterns: Additional custom patterns
        """
        self.spacy_model = spacy_model
        self.llm_client = llm_client
        self.use_spacy = use_spacy
        self.use_llm = use_llm
        
        self._nlp = None
        self._patterns = {**self.DEFAULT_PATTERNS, **(custom_patterns or {})}
        
        # Load spaCy model if available
        if use_spacy and spacy_model:
            try:
                import spacy
                self._nlp = spacy.load(spacy_model)
            except ImportError:
                logger.warning("spaCy not available, using rule-based NER")
            except OSError:
                logger.warning(f"spaCy model {spacy_model} not found, using rule-based NER")
    
    def recognize(self, text: str) -> List[Entity]:
        """
        Recognize entities in text.
        
        Args:
            text: Text to analyze
            
        Returns:
            List of recognized entities
        """
        entities = []
        
        # Use spaCy if available
        if self._nlp:
            entities.extend(self._recognize_with_spacy(text))
        
        # Use rule-based patterns
        entities.extend(self._recognize_with_patterns(text))
        
        # Use LLM if enabled
        if self.use_llm and self.llm_client:
            entities.extend(self._recognize_with_llm(text))
        
        # Deduplicate and merge
        entities = self._deduplicate_entities(entities)
        
        return entities
    
    def _recognize_with_spacy(self, text: str) -> List[Entity]:
        """Recognize entities using spaCy."""
        if not self._nlp:
            return []
        
        entities = []
        doc = self._nlp(text)
        
        # Map spaCy entity types to our types
        type_map = {
            "PERSON": EntityType.PERSON,
            "ORG": EntityType.ORGANIZATION,
            "GPE": EntityType.GPE,
            "LOC": EntityType.LOCATION,
            "DATE": EntityType.DATE,
            "MONEY": EntityType.MONEY,
            "PERCENT": EntityType.PERCENT,
            "EVENT": EntityType.EVENT,
            "PRODUCT": EntityType.PRODUCT,
            "LAW": EntityType.LAW,
        }
        
        for ent in doc.ents:
            entity_type = type_map.get(ent.label_, EntityType.PERSON)
            entities.append(Entity(
                text=ent.text,
                type=entity_type,
                start=ent.start_char,
                end=ent.end_char,
                confidence=0.9,
                metadata={"spacy_label": ent.label_},
            ))
        
        return entities
    
    def _recognize_with_patterns(self, text: str) -> List[Entity]:
        """Recognize entities using regex patterns."""
        entities = []
        
        for entity_type_name, patterns in self._patterns.items():
            # Map pattern names to entity types
            type_map = {
                "person_zh": EntityType.PERSON,
                "organization": EntityType.ORGANIZATION,
                "location": EntityType.LOCATION,
                "money": EntityType.MONEY,
                "percent": EntityType.PERCENT,
                "date": EntityType.DATE,
            }
            
            entity_type = type_map.get(entity_type_name, EntityType.PERSON)
            
            for pattern in patterns:
                for match in re.finditer(pattern, text):
                    entities.append(Entity(
                        text=match.group(),
                        type=entity_type,
                        start=match.start(),
                        end=match.end(),
                        confidence=0.7,
                        metadata={"pattern": pattern},
                    ))
        
        return entities
    
    def _recognize_with_llm(self, text: str) -> List[Entity]:
        """Recognize entities using LLM."""
        if not self.llm_client:
            return []
        
        prompt = f"""识别文本中的命名实体。

返回JSON格式：
{{
    "entities": [
        {{"text": "实体文本", "type": "PERSON|ORGANIZATION|LOCATION|DATE|MONEY|EVENT", "confidence": 0.9}}
    ]
}}

文本：{text}

只返回JSON。"""

        try:
            response = self.llm_client.generate(prompt)
            result = json.loads(re.search(r'\{[\s\S]*\}', response).group())
            
            entities = []
            for ent in result.get("entities", []):
                type_map = {
                    "PERSON": EntityType.PERSON,
                    "ORGANIZATION": EntityType.ORGANIZATION,
                    "LOCATION": EntityType.LOCATION,
                    "GPE": EntityType.GPE,
                    "DATE": EntityType.DATE,
                    "MONEY": EntityType.MONEY,
                    "EVENT": EntityType.EVENT,
                }
                
                entities.append(Entity(
                    text=ent.get("text", ""),
                    type=type_map.get(ent.get("type", ""), EntityType.PERSON),
                    confidence=ent.get("confidence", 0.8),
                ))
            
            return entities
            
        except Exception as e:
            logger.error(f"LLM entity recognition failed: {e}")
            return []
    
    def _deduplicate_entities(self, entities: List[Entity]) -> List[Entity]:
        """Remove duplicate entities, keeping highest confidence."""
        seen = {}
        
        for entity in entities:
            key = (entity.text, entity.type)
            if key not in seen or entity.confidence > seen[key].confidence:
                seen[key] = entity
        
        return list(seen.values())
    
    def get_entity_stats(self, entities: List[Entity]) -> Dict[str, Any]:
        """Get statistics about recognized entities."""
        type_counts = {}
        for entity in entities:
            type_name = entity.type.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1
        
        return {
            "total_entities": len(entities),
            "type_counts": type_counts,
            "unique_texts": len(set(e.text for e in entities)),
        }