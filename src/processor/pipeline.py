"""
Processing pipeline for orchestrating data processing steps.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Callable, Awaitable
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import time

from .models import (
    RawDocument,
    ProcessedDocument,
    ProcessingResult,
    ContentType,
)
from .cleaner import DataCleaner
from .deduplicator import TextDeduplicator
from .normalizer import DataNormalizer

logger = logging.getLogger(__name__)


class PipelineStage(Enum):
    """Processing pipeline stages."""
    CLEAN = "clean"
    DEDUPLICATE = "deduplicate"
    NORMALIZE = "normalize"


@dataclass
class PipelineConfig:
    """Configuration for processing pipeline."""
    enable_clean: bool = True
    enable_deduplicate: bool = True
    enable_normalize: bool = True
    
    # Cleaner config
    remove_html: bool = True
    remove_urls: bool = False
    replace_urls: str = "[URL]"
    remove_emojis: bool = False
    
    # Deduplicator config
    exact_match: bool = True
    near_duplicate: bool = True
    similarity_threshold: float = 0.95
    
    # Normalizer config
    lowercase: bool = False
    expand_abbreviations: bool = True
    normalize_unicode: bool = True


class ProcessingPipeline:
    """
    Orchestrate data processing through multiple stages.
    
    Pipeline stages:
    1. Clean - Remove noise, HTML, normalize encoding
    2. Deduplicate - Remove exact and near duplicates
    3. Normalize - Standardize text format
    """
    
    def __init__(self, config: Optional[PipelineConfig] = None):
        """
        Initialize the processing pipeline.
        
        Args:
            config: Pipeline configuration
        """
        self.config = config or PipelineConfig()
        
        # Initialize components
        self.cleaner = DataCleaner(
            remove_html=self.config.remove_html,
            remove_urls=self.config.remove_urls,
            replace_urls=self.config.replace_urls,
            remove_emojis=self.config.remove_emojis,
        )
        
        self.deduplicator = TextDeduplicator(
            exact_match=self.config.exact_match,
            near_duplicate=self.config.near_duplicate,
            similarity_threshold=self.config.similarity_threshold,
        )
        
        self.normalizer = DataNormalizer(
            lowercase=self.config.lowercase,
            expand_abbreviations=self.config.expand_abbreviations,
            normalize_unicode=self.config.normalize_unicode,
        )
        
        # Processing hooks
        self._pre_hooks: List[Callable] = []
        self._post_hooks: List[Callable] = []
        
        # Statistics
        self._stats = {
            "total_processed": 0,
            "total_duplicates": 0,
            "total_errors": 0,
        }
    
    def add_pre_hook(self, hook: Callable):
        """Add a pre-processing hook."""
        self._pre_hooks.append(hook)
    
    def add_post_hook(self, hook: Callable):
        """Add a post-processing hook."""
        self._post_hooks.append(hook)
    
    async def process_document(
        self, document: RawDocument
    ) -> Optional[ProcessedDocument]:
        """
        Process a single document through the pipeline.
        
        Args:
            document: Document to process
            
        Returns:
            Processed document, or None if duplicate
        """
        try:
            # Run pre-hooks
            for hook in self._pre_hooks:
                document = await self._run_hook(hook, document)
            
            # Stage 1: Clean
            cleaned_content = document.content
            if self.config.enable_clean:
                cleaned_content = self.cleaner.clean(document.content)
            
            # Stage 2: Deduplicate
            if self.config.enable_deduplicate:
                is_dup, _ = self.deduplicator.is_duplicate(cleaned_content)
                if is_dup:
                    self._stats["total_duplicates"] += 1
                    return None
                self.deduplicator.add_document(document.doc_id, cleaned_content)
            
            # Stage 3: Normalize
            normalized_content = cleaned_content
            if self.config.enable_normalize:
                normalized_content = self.normalizer.normalize(cleaned_content)
            
            # Create processed document
            processed = ProcessedDocument(
                doc_id=f"proc_{document.doc_id}",
                raw_doc_id=document.doc_id,
                source=document.source,
                platform=document.platform,
                original_content=document.content,
                cleaned_content=cleaned_content,
                normalized_content=normalized_content,
                language=self.normalizer._detect_language(normalized_content),
                word_count=self.cleaner.count_words(normalized_content),
                processing_steps=self._get_enabled_steps(),
                metadata=document.metadata,
            )
            
            # Run post-hooks
            for hook in self._post_hooks:
                processed = await self._run_hook(hook, processed)
            
            self._stats["total_processed"] += 1
            
            return processed
            
        except Exception as e:
            logger.error(f"Error processing document {document.doc_id}: {e}")
            self._stats["total_errors"] += 1
            return None
    
    async def process_batch(
        self, documents: List[RawDocument]
    ) -> ProcessingResult:
        """
        Process a batch of documents.
        
        Args:
            documents: Documents to process
            
        Returns:
            ProcessingResult with statistics
        """
        start_time = time.time()
        
        result = ProcessingResult(success=True)
        
        processed_docs = []
        
        for doc in documents:
            processed = await self.process_document(doc)
            
            if processed:
                processed_docs.append(processed)
                result.documents_processed += 1
            else:
                result.documents_failed += 1
        
        result.processing_time_ms = (time.time() - start_time) * 1000
        result.metadata["processed_documents"] = len(processed_docs)
        
        return result
    
    async def process_stream(
        self, documents: List[RawDocument], batch_size: int = 100
    ) -> List[ProcessedDocument]:
        """
        Process documents in streaming batches.
        
        Args:
            documents: Documents to process
            batch_size: Batch size for processing
            
        Returns:
            List of processed documents
        """
        all_processed = []
        
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            
            result = await self.process_batch(batch)
            
            # Collect processed documents
            # (In real implementation, these would be returned from process_batch)
            for doc in batch:
                processed = await self.process_document(doc)
                if processed:
                    all_processed.append(processed)
        
        return all_processed
    
    async def _run_hook(self, hook: Callable, data: Any) -> Any:
        """Run a processing hook."""
        if asyncio.iscoroutinefunction(hook):
            return await hook(data)
        return hook(data)
    
    def _get_enabled_steps(self) -> List[str]:
        """Get list of enabled processing steps."""
        steps = []
        if self.config.enable_clean:
            steps.append("cleaned")
        if self.config.enable_deduplicate:
            steps.append("deduplicated")
        if self.config.enable_normalize:
            steps.append("normalized")
        return steps
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pipeline statistics."""
        return {
            **self._stats,
            "deduplicator_stats": self.deduplicator.get_stats(),
            "config": {
                "enable_clean": self.config.enable_clean,
                "enable_deduplicate": self.config.enable_deduplicate,
                "enable_normalize": self.config.enable_normalize,
            },
        }
    
    def reset_stats(self):
        """Reset pipeline statistics."""
        self._stats = {
            "total_processed": 0,
            "total_duplicates": 0,
            "total_errors": 0,
        }
        self.deduplicator.clear_index()
    
    def clear_deduplication_index(self):
        """Clear the deduplication index."""
        self.deduplicator.clear_index()


class PipelineBuilder:
    """Builder for creating processing pipelines."""
    
    def __init__(self):
        self._config = PipelineConfig()
    
    def with_cleaning(
        self,
        remove_html: bool = True,
        remove_urls: bool = False,
        replace_urls: str = "[URL]",
        remove_emojis: bool = False,
    ) -> "PipelineBuilder":
        """Configure cleaning stage."""
        self._config.enable_clean = True
        self._config.remove_html = remove_html
        self._config.remove_urls = remove_urls
        self._config.replace_urls = replace_urls
        self._config.remove_emojis = remove_emojis
        return self
    
    def with_deduplication(
        self,
        exact_match: bool = True,
        near_duplicate: bool = True,
        similarity_threshold: float = 0.95,
    ) -> "PipelineBuilder":
        """Configure deduplication stage."""
        self._config.enable_deduplicate = True
        self._config.exact_match = exact_match
        self._config.near_duplicate = near_duplicate
        self._config.similarity_threshold = similarity_threshold
        return self
    
    def with_normalization(
        self,
        lowercase: bool = False,
        expand_abbreviations: bool = True,
        normalize_unicode: bool = True,
    ) -> "PipelineBuilder":
        """Configure normalization stage."""
        self._config.enable_normalize = True
        self._config.lowercase = lowercase
        self._config.expand_abbreviations = expand_abbreviations
        self._config.normalize_unicode = normalize_unicode
        return self
    
    def without_cleaning(self) -> "PipelineBuilder":
        """Disable cleaning stage."""
        self._config.enable_clean = False
        return self
    
    def without_deduplication(self) -> "PipelineBuilder":
        """Disable deduplication stage."""
        self._config.enable_deduplicate = False
        return self
    
    def without_normalization(self) -> "PipelineBuilder":
        """Disable normalization stage."""
        self._config.enable_normalize = False
        return self
    
    def build(self) -> ProcessingPipeline:
        """Build the pipeline."""
        return ProcessingPipeline(self._config)