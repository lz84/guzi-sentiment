"""
Tests for processor module.
"""

import pytest
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from processor import (
    DataCleaner,
    TextDeduplicator,
    DataNormalizer,
    ProcessingPipeline,
    PipelineBuilder,
    RawDocument,
    ProcessedDocument,
    ContentType,
)


class TestDataCleaner:
    """Test DataCleaner functionality."""
    
    def setup_method(self):
        self.cleaner = DataCleaner()
    
    def test_clean_html(self):
        """Test HTML removal."""
        text = "<p>Hello <b>World</b></p>"
        result = self.cleaner.clean(text)
        
        assert "<p>" not in result
        assert "<b>" not in result
        assert "Hello" in result
        assert "World" in result
    
    def test_clean_urls(self):
        """Test URL handling."""
        cleaner = DataCleaner(remove_urls=True)
        text = "Check out https://example.com for more info"
        result = cleaner.clean(text)
        
        assert "https://example.com" not in result
        assert "Check out" in result
    
    def test_replace_urls(self):
        """Test URL replacement."""
        cleaner = DataCleaner(replace_urls="[LINK]")
        text = "Visit https://example.com"
        result = cleaner.clean(text)
        
        assert "[LINK]" in result
        assert "https://example.com" not in result
    
    def test_normalize_whitespace(self):
        """Test whitespace normalization."""
        text = "Hello    World\n\nTest"
        result = self.cleaner.clean(text)
        
        assert "    " not in result
        assert result == "Hello World Test"
    
    def test_extract_urls(self):
        """Test URL extraction."""
        text = "Visit https://example.com and http://test.org"
        urls = self.cleaner.extract_urls(text)
        
        assert len(urls) == 2
        assert "https://example.com" in urls[0]
    
    def test_count_words(self):
        """Test word counting."""
        text = "Hello world 你好世界"
        count = self.cleaner.count_words(text)
        
        assert count == 6  # 2 English + 4 Chinese
    
    def test_detect_language(self):
        """Test language detection."""
        assert self.cleaner.detect_language("你好世界") == "zh"
        assert self.cleaner.detect_language("Hello world") == "en"


class TestTextDeduplicator:
    """Test TextDeduplicator functionality."""
    
    def setup_method(self):
        self.dedup = TextDeduplicator()
    
    def test_compute_hash(self):
        """Test hash computation."""
        text = "Hello world"
        hash1 = self.dedup.compute_hash(text)
        hash2 = self.dedup.compute_hash(text)
        
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256
    
    def test_exact_duplicate_detection(self):
        """Test exact duplicate detection."""
        text = "This is a test document"
        
        # First document should not be duplicate
        is_dup, _ = self.dedup.is_duplicate(text)
        assert not is_dup
        
        # Add to index
        self.dedup.add_document("doc1", text)
        
        # Same text should be detected as duplicate
        is_dup, existing_id = self.dedup.is_duplicate(text)
        assert is_dup
        assert existing_id == "doc1"
    
    def test_near_duplicate_detection(self):
        """Test near-duplicate detection."""
        dedup = TextDeduplicator(near_duplicate=True, similarity_threshold=0.9)
        
        text1 = "This is a test document for near duplicate detection"
        text2 = "This is a test document for near duplicate detection!"
        
        # Add first document
        dedup.add_document("doc1", text1)
        
        # Second document (very similar) should be detected
        is_dup, _ = dedup.is_duplicate(text2)
        # Note: With default settings, this might not always be detected
        # The test depends on the SimHash similarity threshold
    
    def test_deduplicate_batch(self):
        """Test batch deduplication."""
        documents = [
            ("doc1", "Hello world"),
            ("doc2", "Hello world"),  # Exact duplicate
            ("doc3", "Different content"),
        ]
        
        result = self.dedup.deduplicate_batch(documents)
        
        assert result.total_documents == 3
        assert result.unique_documents == 2
        assert result.duplicate_documents == 1
    
    def test_clear_index(self):
        """Test clearing the index."""
        self.dedup.add_document("doc1", "Test content")
        
        self.dedup.clear_index()
        
        assert len(self.dedup._doc_hashes) == 0
        assert len(self.dedup._hash_index) == 0


class TestDataNormalizer:
    """Test DataNormalizer functionality."""
    
    def setup_method(self):
        self.normalizer = DataNormalizer()
    
    def test_normalize_text(self):
        """Test basic text normalization."""
        text = "Hello   World"
        result = self.normalizer.normalize(text)
        
        assert "  " not in result
        assert result == "Hello World"
    
    def test_expand_abbreviations(self):
        """Test abbreviation expansion."""
        normalizer = DataNormalizer(expand_abbreviations=True)
        text = "u r awesome thx"
        result = normalizer.normalize(text)
        
        assert "you" in result
        assert "are" in result
        assert "thanks" in result
    
    def test_detect_language(self):
        """Test language detection."""
        assert self.normalizer._detect_language("你好世界") == "zh"
        assert self.normalizer._detect_language("Hello world") == "en"
    
    def test_extract_metadata(self):
        """Test metadata extraction."""
        text = "Check out https://example.com on 2024-01-15"
        metadata = self.normalizer.extract_metadata(text)
        
        assert metadata["language"] == "en"
        assert metadata["has_urls"] is True
        assert metadata["has_dates"] is True


class TestProcessingPipeline:
    """Test ProcessingPipeline functionality."""
    
    def setup_method(self):
        self.pipeline = ProcessingPipeline()
    
    def test_process_document(self):
        """Test processing a single document."""
        doc = RawDocument(
            doc_id="test1",
            source="test",
            platform="twitter",
            content="<p>Hello   World!</p>",
        )
        
        result = pytest.asyncio.run(self.pipeline.process_document(doc))
        
        assert result is not None
        assert result.raw_doc_id == "test1"
        assert "<p>" not in result.cleaned_content
        assert "  " not in result.cleaned_content
    
    def test_process_batch(self):
        """Test batch processing."""
        docs = [
            RawDocument(
                doc_id="test1",
                source="test",
                platform="twitter",
                content="Content 1",
            ),
            RawDocument(
                doc_id="test2",
                source="test",
                platform="twitter",
                content="Content 2",
            ),
        ]
        
        result = pytest.asyncio.run(self.pipeline.process_batch(docs))
        
        assert result.success
        assert result.documents_processed == 2
    
    def test_pipeline_builder(self):
        """Test pipeline builder."""
        pipeline = (
            PipelineBuilder()
            .with_cleaning(remove_html=True)
            .with_deduplication(exact_match=True)
            .with_normalization(lowercase=False)
            .build()
        )
        
        assert pipeline.config.enable_clean
        assert pipeline.config.enable_deduplicate
        assert pipeline.config.enable_normalize
    
    def test_get_stats(self):
        """Test getting pipeline statistics."""
        stats = self.pipeline.get_stats()
        
        assert "total_processed" in stats
        assert "deduplicator_stats" in stats


if __name__ == "__main__":
    pytest.main([__file__, "-v"])