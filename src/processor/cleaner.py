"""
Data cleaner for cleaning raw text data.
"""

import re
import html
import logging
from typing import List, Optional, Dict, Any, Set
from datetime import datetime

from .models import RawDocument, ContentType

logger = logging.getLogger(__name__)


class DataCleaner:
    """
    Clean raw text data from various sources.
    
    Features:
    - HTML tag removal
    - URL removal/replacement
    - Emoji handling
    - Special character cleaning
    - Whitespace normalization
    - Encoding fixes
    """
    
    # Default patterns to clean
    DEFAULT_PATTERNS = {
        # HTML tags
        "html_tags": r"<[^>]+>",
        # URLs
        "urls": r"https?://[^\s<>\"']+|www\.[^\s<>\"']+",
        # Email addresses
        "emails": r"[\w\.-]+@[\w\.-]+\.\w+",
        # Mentions (Twitter style)
        "mentions": r"@\w+",
        # Hashtags
        "hashtags": r"#\w+",
        # Multiple whitespace
        "multiple_whitespace": r"\s+",
        # Control characters
        "control_chars": r"[\x00-\x1f\x7f-\x9f]",
    }
    
    # Emoji patterns
    EMOJI_PATTERN = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F700-\U0001F77F"  # alchemical symbols
        "\U0001F780-\U0001F7FF"  # Geometric Shapes Extended
        "\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
        "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
        "\U0001FA00-\U0001FA6F"  # Chess Symbols
        "\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
        "\U00002702-\U000027B0"  # Dingbats
        "\U000024C2-\U0001F251" 
        "]+",
        flags=re.UNICODE
    )
    
    def __init__(
        self,
        remove_html: bool = True,
        remove_urls: bool = False,
        replace_urls: str = "[URL]",
        remove_emails: bool = False,
        replace_emails: str = "[EMAIL]",
        remove_mentions: bool = False,
        replace_mentions: str = "@USER",
        remove_hashtags: bool = False,
        replace_hashtags: str = "#TAG",
        remove_emojis: bool = False,
        normalize_whitespace: bool = True,
        custom_patterns: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize the data cleaner.
        
        Args:
            remove_html: Remove HTML tags
            remove_urls: Remove URLs entirely
            replace_urls: Replacement text for URLs
            remove_emails: Remove email addresses entirely
            replace_emails: Replacement text for emails
            remove_mentions: Remove mentions entirely
            replace_mentions: Replacement text for mentions
            remove_hashtags: Remove hashtags entirely
            replace_hashtags: Replacement text for hashtags
            remove_emojis: Remove emojis
            normalize_whitespace: Normalize whitespace
            custom_patterns: Additional custom patterns
        """
        self.remove_html = remove_html
        self.remove_urls = remove_urls
        self.replace_urls = replace_urls
        self.remove_emails = remove_emails
        self.replace_emails = replace_emails
        self.remove_mentions = remove_mentions
        self.replace_mentions = replace_mentions
        self.remove_hashtags = remove_hashtags
        self.replace_hashtags = replace_hashtags
        self.remove_emojis = remove_emojis
        self.normalize_whitespace = normalize_whitespace
        self.custom_patterns = custom_patterns or {}
    
    def clean(self, text: str) -> str:
        """
        Clean text content.
        
        Args:
            text: Text to clean
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        result = text
        
        # Fix HTML entities
        result = html.unescape(result)
        
        # Remove HTML tags
        if self.remove_html:
            result = re.sub(self.DEFAULT_PATTERNS["html_tags"], "", result)
        
        # Handle URLs
        if self.remove_urls:
            result = re.sub(self.DEFAULT_PATTERNS["urls"], "", result)
        elif self.replace_urls:
            result = re.sub(self.DEFAULT_PATTERNS["urls"], self.replace_urls, result)
        
        # Handle emails
        if self.remove_emails:
            result = re.sub(self.DEFAULT_PATTERNS["emails"], "", result)
        elif self.replace_emails:
            result = re.sub(self.DEFAULT_PATTERNS["emails"], self.replace_emails, result)
        
        # Handle mentions
        if self.remove_mentions:
            result = re.sub(self.DEFAULT_PATTERNS["mentions"], "", result)
        elif self.replace_mentions:
            result = re.sub(self.DEFAULT_PATTERNS["mentions"], self.replace_mentions, result)
        
        # Handle hashtags
        if self.remove_hashtags:
            result = re.sub(self.DEFAULT_PATTERNS["hashtags"], "", result)
        elif self.replace_hashtags:
            result = re.sub(self.DEFAULT_PATTERNS["hashtags"], self.replace_hashtags, result)
        
        # Remove emojis
        if self.remove_emojis:
            result = self.EMOJI_PATTERN.sub("", result)
        
        # Remove control characters
        result = re.sub(self.DEFAULT_PATTERNS["control_chars"], "", result)
        
        # Apply custom patterns
        for pattern_name, pattern in self.custom_patterns.items():
            result = re.sub(pattern, "", result)
        
        # Normalize whitespace
        if self.normalize_whitespace:
            result = re.sub(self.DEFAULT_PATTERNS["multiple_whitespace"], " ", result)
            result = result.strip()
        
        return result
    
    def clean_document(self, document: RawDocument) -> str:
        """
        Clean a document's content.
        
        Args:
            document: Document to clean
            
        Returns:
            Cleaned content
        """
        return self.clean(document.content)
    
    def clean_batch(self, documents: List[RawDocument]) -> List[str]:
        """
        Clean multiple documents.
        
        Args:
            documents: Documents to clean
            
        Returns:
            List of cleaned contents
        """
        return [self.clean_document(doc) for doc in documents]
    
    def extract_urls(self, text: str) -> List[str]:
        """
        Extract URLs from text.
        
        Args:
            text: Text to extract from
            
        Returns:
            List of URLs
        """
        return re.findall(self.DEFAULT_PATTERNS["urls"], text)
    
    def extract_mentions(self, text: str) -> List[str]:
        """
        Extract mentions from text.
        
        Args:
            text: Text to extract from
            
        Returns:
            List of mentions
        """
        return re.findall(self.DEFAULT_PATTERNS["mentions"], text)
    
    def extract_hashtags(self, text: str) -> List[str]:
        """
        Extract hashtags from text.
        
        Args:
            text: Text to extract from
            
        Returns:
            List of hashtags
        """
        return re.findall(self.DEFAULT_PATTERNS["hashtags"], text)
    
    def count_words(self, text: str) -> int:
        """
        Count words in text.
        
        Args:
            text: Text to count
            
        Returns:
            Word count
        """
        if not text:
            return 0
        
        # For Chinese text, count characters
        chinese_chars = len(re.findall(r"[\u4e00-\u9fa5]", text))
        
        # For English text, count words
        english_words = len(re.findall(r"\b[a-zA-Z]+\b", text))
        
        return chinese_chars + english_words
    
    def detect_language(self, text: str) -> str:
        """
        Detect the language of text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Language code (zh, en, etc.)
        """
        if not text:
            return "unknown"
        
        # Count Chinese and English characters
        chinese_ratio = len(re.findall(r"[\u4e00-\u9fa5]", text)) / len(text)
        
        if chinese_ratio > 0.3:
            return "zh"
        else:
            return "en"
    
    def get_stats(self, text: str) -> Dict[str, Any]:
        """
        Get statistics about text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Statistics dictionary
        """
        return {
            "length": len(text),
            "word_count": self.count_words(text),
            "language": self.detect_language(text),
            "url_count": len(self.extract_urls(text)),
            "mention_count": len(self.extract_mentions(text)),
            "hashtag_count": len(self.extract_hashtags(text)),
            "emoji_count": len(self.EMOJI_PATTERN.findall(text)),
        }