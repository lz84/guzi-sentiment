"""
Data normalizer for normalizing and standardizing text data.
"""

import re
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import unicodedata

from .models import RawDocument, ProcessedDocument, ContentType

logger = logging.getLogger(__name__)


class DataNormalizer:
    """
    Normalize and standardize text data.
    
    Features:
    - Text normalization (Unicode, case, etc.)
    - Language-specific normalization
    - Format standardization
    - Field mapping
    - Metadata extraction
    """
    
    # Common abbreviations
    ABBREVIATIONS = {
        "en": {
            "u": "you",
            "ur": "your",
            "r": "are",
            "n": "and",
            "w/": "with",
            "w/o": "without",
            "thx": "thanks",
            "pls": "please",
            "btw": "by the way",
            "imo": "in my opinion",
            "imho": "in my humble opinion",
            "lol": "laugh out loud",
            "omg": "oh my god",
            "fyi": "for your information",
            "asap": "as soon as possible",
        },
        "zh": {
            "emmm": "嗯",
            "hhh": "哈哈",
            "233": "哈哈",
            "666": "厉害",
            "xswl": "笑死我了",
            "yyds": "永远的神",
            "zqsg": "真情实感",
            "xjj": "小姐姐",
        }
    }
    
    # Common patterns to normalize
    PATTERNS = {
        # Numbers
        "numbers": r"\d+",
        # Dates
        "dates": r"\d{4}[-/]\d{1,2}[-/]\d{1,2}",
        # Times
        "times": r"\d{1,2}:\d{2}(:\d{2})?",
        # Money
        "money": r"[$￥€£]\d+(\.\d+)?",
        # Percentages
        "percentages": r"\d+(\.\d+)?%",
    }
    
    def __init__(
        self,
        lowercase: bool = False,
        normalize_unicode: bool = True,
        expand_abbreviations: bool = True,
        standardize_numbers: bool = False,
        standardize_dates: bool = False,
        remove_accents: bool = False,
        language: str = "auto",
    ):
        """
        Initialize the data normalizer.
        
        Args:
            lowercase: Convert to lowercase
            normalize_unicode: Normalize Unicode characters
            expand_abbreviations: Expand common abbreviations
            standardize_numbers: Standardize number formats
            standardize_dates: Standardize date formats
            remove_accents: Remove accents from characters
            language: Default language (auto, en, zh)
        """
        self.lowercase = lowercase
        self.normalize_unicode = normalize_unicode
        self.expand_abbreviations = expand_abbreviations
        self.standardize_numbers = standardize_numbers
        self.standardize_dates = standardize_dates
        self.remove_accents = remove_accents
        self.language = language
    
    def normalize(self, text: str) -> str:
        """
        Normalize text content.
        
        Args:
            text: Text to normalize
            
        Returns:
            Normalized text
        """
        if not text:
            return ""
        
        result = text
        
        # Unicode normalization
        if self.normalize_unicode:
            result = unicodedata.normalize("NFKC", result)
        
        # Remove accents
        if self.remove_accents:
            result = self._remove_accents(result)
        
        # Lowercase
        if self.lowercase:
            result = result.lower()
        
        # Expand abbreviations
        if self.expand_abbreviations:
            result = self._expand_abbreviations(result)
        
        # Standardize numbers
        if self.standardize_numbers:
            result = self._standardize_numbers(result)
        
        # Standardize dates
        if self.standardize_dates:
            result = self._standardize_dates(result)
        
        # Final cleanup
        result = re.sub(r"\s+", " ", result).strip()
        
        return result
    
    def _remove_accents(self, text: str) -> str:
        """Remove accents from text."""
        # Normalize to decomposed form
        nfd = unicodedata.normalize("NFD", text)
        # Remove combining characters
        return "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    
    def _expand_abbreviations(self, text: str) -> str:
        """Expand abbreviations in text."""
        result = text
        
        # Detect language
        lang = self._detect_language(text) if self.language == "auto" else self.language
        
        # Expand for detected language
        if lang in self.ABBREVIATIONS:
            for abbr, expansion in self.ABBREVIATIONS[lang].items():
                pattern = r"\b" + re.escape(abbr) + r"\b"
                result = re.sub(pattern, expansion, result, flags=re.IGNORECASE)
        
        # Expand for both languages if auto
        if self.language == "auto":
            for lang_abbrs in self.ABBREVIATIONS.values():
                for abbr, expansion in lang_abbrs.items():
                    pattern = r"\b" + re.escape(abbr) + r"\b"
                    result = re.sub(pattern, expansion, result, flags=re.IGNORECASE)
        
        return result
    
    def _standardize_numbers(self, text: str) -> str:
        """Standardize number formats."""
        # Add [NUM] placeholder for numbers
        return re.sub(self.PATTERNS["numbers"], "[NUM]", text)
    
    def _standardize_dates(self, text: str) -> str:
        """Standardize date formats."""
        # Add [DATE] placeholder for dates
        return re.sub(self.PATTERNS["dates"], "[DATE]", text)
    
    def _detect_language(self, text: str) -> str:
        """Detect language of text."""
        if not text:
            return "en"
        
        chinese_ratio = len(re.findall(r"[\u4e00-\u9fa5]", text)) / len(text)
        
        if chinese_ratio > 0.3:
            return "zh"
        return "en"
    
    def normalize_document(
        self, document: RawDocument, cleaned_content: str
    ) -> ProcessedDocument:
        """
        Normalize a document.
        
        Args:
            document: Raw document
            cleaned_content: Pre-cleaned content
            
        Returns:
            ProcessedDocument with normalized content
        """
        normalized_content = self.normalize(cleaned_content)
        
        return ProcessedDocument(
            doc_id=f"proc_{document.doc_id}",
            raw_doc_id=document.doc_id,
            source=document.source,
            platform=document.platform,
            original_content=document.content,
            cleaned_content=cleaned_content,
            normalized_content=normalized_content,
            language=self._detect_language(normalized_content),
            metadata=document.metadata,
        )
    
    def extract_metadata(self, text: str) -> Dict[str, Any]:
        """
        Extract metadata from text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Extracted metadata
        """
        return {
            "length": len(text),
            "word_count": len(re.findall(r"\b\w+\b", text)),
            "chinese_char_count": len(re.findall(r"[\u4e00-\u9fa5]", text)),
            "language": self._detect_language(text),
            "has_urls": bool(re.search(self.PATTERNS.get("urls", r"https?://"), text)),
            "has_numbers": bool(re.search(self.PATTERNS["numbers"], text)),
            "has_dates": bool(re.search(self.PATTERNS["dates"], text)),
            "has_money": bool(re.search(self.PATTERNS["money"], text)),
        }
    
    def standardize_field(
        self, value: Any, field_type: str = "string"
    ) -> Any:
        """
        Standardize a field value.
        
        Args:
            value: Value to standardize
            field_type: Type of field (string, number, date, etc.)
            
        Returns:
            Standardized value
        """
        if value is None:
            return None
        
        if field_type == "string":
            return self.normalize(str(value))
        
        elif field_type == "number":
            try:
                if isinstance(value, (int, float)):
                    return value
                return float(re.sub(r"[^\d.-]", "", str(value)))
            except ValueError:
                return None
        
        elif field_type == "date":
            if isinstance(value, datetime):
                return value.isoformat()
            # Try to parse date string
            try:
                # Add common date parsing logic here
                return str(value)
            except:
                return str(value)
        
        return value
    
    def map_fields(
        self, data: Dict[str, Any], mapping: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Map fields from source to target names.
        
        Args:
            data: Source data
            mapping: Field mapping {source: target}
            
        Returns:
            Mapped data
        """
        result = {}
        
        for source_field, target_field in mapping.items():
            if source_field in data:
                result[target_field] = data[source_field]
        
        return result