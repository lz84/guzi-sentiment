"""
Text deduplicator for removing duplicate content.
"""

import hashlib
import logging
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass
import re

from .models import RawDocument, ProcessedDocument, DeduplicationResult

logger = logging.getLogger(__name__)


@dataclass
class DocumentHash:
    """Hash information for a document."""
    doc_id: str
    content_hash: str
    simhash: Optional[int] = None
    minhash: Optional[List[int]] = None


class TextDeduplicator:
    """
    Remove duplicate text content.
    
    Features:
    - Exact deduplication using hash
    - Near-duplicate detection using SimHash/MinHash
    - Configurable similarity threshold
    - Document grouping
    """
    
    def __init__(
        self,
        exact_match: bool = True,
        near_duplicate: bool = True,
        similarity_threshold: float = 0.95,
        hash_algorithm: str = "sha256",
    ):
        """
        Initialize the text deduplicator.
        
        Args:
            exact_match: Enable exact match deduplication
            near_duplicate: Enable near-duplicate detection
            similarity_threshold: Threshold for near-duplicate (0-1)
            hash_algorithm: Hash algorithm for exact match
        """
        self.exact_match = exact_match
        self.near_duplicate = near_duplicate
        self.similarity_threshold = similarity_threshold
        self.hash_algorithm = hash_algorithm
        
        # Storage for hashes
        self._hash_index: Dict[str, str] = {}  # hash -> doc_id
        self._doc_hashes: Dict[str, DocumentHash] = {}  # doc_id -> hash info
    
    def compute_hash(self, text: str) -> str:
        """
        Compute hash for text.
        
        Args:
            text: Text to hash
            
        Returns:
            Hash string
        """
        normalized = self._normalize_text(text)
        
        if self.hash_algorithm == "sha256":
            return hashlib.sha256(normalized.encode()).hexdigest()
        elif self.hash_algorithm == "md5":
            return hashlib.md5(normalized.encode()).hexdigest()
        else:
            return hashlib.sha256(normalized.encode()).hexdigest()
    
    def _normalize_text(self, text: str) -> str:
        """
        Normalize text for hashing.
        
        Args:
            text: Text to normalize
            
        Returns:
            Normalized text
        """
        # Lowercase
        result = text.lower()
        # Remove extra whitespace
        result = re.sub(r"\s+", " ", result)
        # Remove punctuation (optional)
        result = re.sub(r"[^\w\s]", "", result)
        return result.strip()
    
    def compute_simhash(self, text: str) -> int:
        """
        Compute SimHash for near-duplicate detection.
        
        Args:
            text: Text to hash
            
        Returns:
            SimHash integer
        """
        # Tokenize
        tokens = self._tokenize(text)
        
        # Compute hash for each token and aggregate
        v = [0] * 64
        
        for token in tokens:
            token_hash = int(hashlib.md5(token.encode()).hexdigest(), 16)
            for i in range(64):
                bit = (token_hash >> i) & 1
                if bit:
                    v[i] += 1
                else:
                    v[i] -= 1
        
        # Generate final hash
        simhash = 0
        for i in range(64):
            if v[i] > 0:
                simhash |= (1 << i)
        
        return simhash
    
    def _tokenize(self, text: str, n: int = 3) -> List[str]:
        """
        Tokenize text into n-grams.
        
        Args:
            text: Text to tokenize
            n: N-gram size
            
        Returns:
            List of n-grams
        """
        text = self._normalize_text(text)
        tokens = []
        
        # Character n-grams for Chinese
        for i in range(len(text) - n + 1):
            tokens.append(text[i:i+n])
        
        # Word n-grams for English
        words = text.split()
        for i in range(len(words) - n + 1):
            tokens.append(" ".join(words[i:i+n]))
        
        return tokens
    
    def hamming_distance(self, hash1: int, hash2: int) -> int:
        """
        Compute Hamming distance between two hashes.
        
        Args:
            hash1: First hash
            hash2: Second hash
            
        Returns:
            Hamming distance
        """
        return bin(hash1 ^ hash2).count("1")
    
    def similarity(self, hash1: int, hash2: int) -> float:
        """
        Compute similarity between two SimHash values.
        
        Args:
            hash1: First hash
            hash2: Second hash
            
        Returns:
            Similarity score (0-1)
        """
        distance = self.hamming_distance(hash1, hash2)
        return 1 - (distance / 64)
    
    def is_duplicate(self, text: str) -> Tuple[bool, Optional[str]]:
        """
        Check if text is a duplicate.
        
        Args:
            text: Text to check
            
        Returns:
            Tuple of (is_duplicate, existing_doc_id)
        """
        content_hash = self.compute_hash(text)
        
        # Check exact match
        if self.exact_match and content_hash in self._hash_index:
            return True, self._hash_index[content_hash]
        
        # Check near-duplicate
        if self.near_duplicate:
            simhash = self.compute_simhash(text)
            
            for doc_id, doc_hash in self._doc_hashes.items():
                if doc_hash.simhash is not None:
                    sim = self.similarity(simhash, doc_hash.simhash)
                    if sim >= self.similarity_threshold:
                        return True, doc_id
        
        return False, None
    
    def add_document(self, doc_id: str, text: str) -> DocumentHash:
        """
        Add a document to the deduplication index.
        
        Args:
            doc_id: Document ID
            text: Document text
            
        Returns:
            DocumentHash for the document
        """
        content_hash = self.compute_hash(text)
        simhash = self.compute_simhash(text) if self.near_duplicate else None
        
        doc_hash = DocumentHash(
            doc_id=doc_id,
            content_hash=content_hash,
            simhash=simhash,
        )
        
        self._hash_index[content_hash] = doc_id
        self._doc_hashes[doc_id] = doc_hash
        
        return doc_hash
    
    def deduplicate_batch(
        self, documents: List[Tuple[str, str]]
    ) -> DeduplicationResult:
        """
        Deduplicate a batch of documents.
        
        Args:
            documents: List of (doc_id, text) tuples
            
        Returns:
            DeduplicationResult
        """
        result = DeduplicationResult(total_documents=len(documents))
        
        # Group duplicates
        duplicate_map: Dict[str, List[str]] = {}  # original_id -> [duplicate_ids]
        
        for doc_id, text in documents:
            is_dup, existing_id = self.is_duplicate(text)
            
            if is_dup and existing_id:
                # Document is duplicate
                result.duplicate_documents += 1
                
                if existing_id not in duplicate_map:
                    duplicate_map[existing_id] = [existing_id]
                duplicate_map[existing_id].append(doc_id)
            else:
                # Document is unique
                result.unique_documents += 1
                self.add_document(doc_id, text)
        
        result.duplicate_groups = list(duplicate_map.values())
        
        return result
    
    def get_unique_documents(
        self, documents: List[Tuple[str, str]]
    ) -> List[Tuple[str, str]]:
        """
        Get unique documents from a batch.
        
        Args:
            documents: List of (doc_id, text) tuples
            
        Returns:
            List of unique (doc_id, text) tuples
        """
        unique = []
        
        for doc_id, text in documents:
            is_dup, _ = self.is_duplicate(text)
            if not is_dup:
                unique.append((doc_id, text))
                self.add_document(doc_id, text)
        
        return unique
    
    def clear_index(self):
        """Clear the deduplication index."""
        self._hash_index.clear()
        self._doc_hashes.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get deduplicator statistics."""
        return {
            "indexed_documents": len(self._doc_hashes),
            "unique_hashes": len(self._hash_index),
            "exact_match_enabled": self.exact_match,
            "near_duplicate_enabled": self.near_duplicate,
            "similarity_threshold": self.similarity_threshold,
        }