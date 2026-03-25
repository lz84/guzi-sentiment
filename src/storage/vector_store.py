"""
向量存储和嵌入服务

提供文档向量化和语义检索功能。
"""

import hashlib
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False


class EmbeddingService:
    """
    嵌入服务
    
    支持多种嵌入模型:
    - OpenAI text-embedding-ada-002
    - Sentence Transformers (本地模型)
    """
    
    def __init__(
        self,
        provider: str = "sentence_transformers",
        model_name: str = "all-MiniLM-L6-v2",
        openai_api_key: Optional[str] = None,
        openai_base_url: Optional[str] = None,
    ):
        """
        初始化嵌入服务
        
        Args:
            provider: 提供者 ("openai" 或 "sentence_transformers")
            model_name: 模型名称
            openai_api_key: OpenAI API Key
            openai_base_url: OpenAI API Base URL (用于自定义端点)
        """
        self.provider = provider
        self.model_name = model_name
        self.openai_api_key = openai_api_key
        self.openai_base_url = openai_base_url
        self._model = None
        self._client = None
        self.dimension = 384  # 默认维度
    
    def _init_model(self):
        """初始化模型"""
        if self._model is not None:
            return
        
        if self.provider == "openai":
            if not OPENAI_AVAILABLE:
                raise ImportError("openai package not installed")
            
            self._client = OpenAI(
                api_key=self.openai_api_key,
                base_url=self.openai_base_url
            )
            self.dimension = 1536  # text-embedding-ada-002
        
        elif self.provider == "sentence_transformers":
            if not SENTENCE_TRANSFORMERS_AVAILABLE:
                raise ImportError("sentence-transformers package not installed")
            
            self._model = SentenceTransformer(self.model_name)
            self.dimension = self._model.get_sentence_embedding_dimension()
        
        else:
            raise ValueError(f"Unknown provider: {self.provider}")
    
    def embed(self, texts: List[str]) -> List[List[float]]:
        """
        生成嵌入向量
        
        Args:
            texts: 文本列表
        
        Returns:
            嵌入向量列表
        """
        self._init_model()
        
        if self.provider == "openai":
            response = self._client.embeddings.create(
                model=self.model_name,
                input=texts
            )
            return [item.embedding for item in response.data]
        
        elif self.provider == "sentence_transformers":
            embeddings = self._model.encode(texts, convert_to_numpy=True)
            return embeddings.tolist()
    
    def embed_single(self, text: str) -> List[float]:
        """生成单个文本的嵌入向量"""
        return self.embed([text])[0]
    
    def similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        a = np.array(vec1)
        b = np.array(vec2)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
    
    def similarities(self, query_vec: List[float], doc_vecs: List[List[float]]) -> List[float]:
        """计算查询向量与多个文档向量的相似度"""
        query = np.array(query_vec)
        docs = np.array(doc_vecs)
        
        # 归一化
        query_norm = query / np.linalg.norm(query)
        docs_norm = docs / np.linalg.norm(docs, axis=1, keepdims=True)
        
        # 点积
        return np.dot(docs_norm, query_norm).tolist()


class VectorStore:
    """
    向量存储
    
    提供文档的向量化和语义检索功能。
    支持本地 ChromaDB 或内存存储。
    """
    
    def __init__(
        self,
        persist_directory: Optional[str] = None,
        collection_name: str = "guzi_sentiment",
        embedding_service: Optional[EmbeddingService] = None,
    ):
        """
        初始化向量存储
        
        Args:
            persist_directory: 持久化目录
            collection_name: 集合名称
            embedding_service: 嵌入服务实例
        """
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self.embedding = embedding_service or EmbeddingService()
        self._collection = None
        self._client = None
        
        # 内存存储 (当 ChromaDB 不可用时)
        self._memory_store: Dict[str, Dict[str, Any]] = {}
        self._use_memory = False
    
    def _init_client(self):
        """初始化客户端"""
        if self._client is not None:
            return
        
        if CHROMADB_AVAILABLE and self.persist_directory:
            self._client = chromadb.Client(Settings(
                chroma_db_impl="duckdb+parquet",
                persist_directory=self.persist_directory
            ))
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
        else:
            # 使用内存存储
            self._use_memory = True
            self._memory_store = {}
    
    def add_documents(
        self,
        documents: List[Dict[str, Any]],
        ids: Optional[List[str]] = None,
        metadatas: Optional[List[Dict[str, Any]]] = None
    ) -> List[str]:
        """
        添加文档
        
        Args:
            documents: 文档列表，每个文档包含 "content" 字段
            ids: 文档ID列表 (可选)
            metadatas: 元数据列表 (可选)
        
        Returns:
            文档ID列表
        """
        self._init_client()
        
        # 提取文本内容
        texts = [doc.get("content", doc.get("text", "")) for doc in documents]
        
        # 生成ID
        if ids is None:
            ids = [self._generate_id(text) for text in texts]
        
        # 生成嵌入向量
        embeddings = self.embedding.embed(texts)
        
        # 准备元数据
        if metadatas is None:
            metadatas = [
                {
                    "doc_id": doc.get("doc_id", ids[i]),
                    "platform": doc.get("platform", ""),
                    "collected_at": doc.get("collected_at", datetime.utcnow().isoformat()),
                }
                for i, doc in enumerate(documents)
            ]
        
        if self._use_memory:
            # 内存存储
            for i, (doc_id, text, embedding, metadata) in enumerate(zip(ids, texts, embeddings, metadatas)):
                self._memory_store[doc_id] = {
                    "id": doc_id,
                    "text": text,
                    "embedding": embedding,
                    "metadata": metadata,
                    "document": documents[i]
                }
        else:
            # ChromaDB 存储
            self._collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas
            )
        
        return ids
    
    def add_document(
        self,
        document: Dict[str, Any],
        doc_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """添加单个文档"""
        ids = self.add_documents([document], [doc_id] if doc_id else None, [metadata] if metadata else None)
        return ids[0]
    
    def search(
        self,
        query: str,
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        语义搜索
        
        Args:
            query: 查询文本
            n_results: 返回结果数量
            where: 元数据过滤条件
            where_document: 文档内容过滤条件
        
        Returns:
            搜索结果列表
        """
        self._init_client()
        
        # 生成查询向量
        query_embedding = self.embedding.embed_single(query)
        
        if self._use_memory:
            # 内存搜索
            results = []
            for doc_id, doc in self._memory_store.items():
                # 应用过滤条件
                if where:
                    match = all(doc["metadata"].get(k) == v for k, v in where.items())
                    if not match:
                        continue
                
                if where_document:
                    # 简单的文本包含检查
                    text = doc["text"].lower()
                    match = all(cond.get("$contains", "").lower() in text for cond in where_document.values())
                    if not match:
                        continue
                
                # 计算相似度
                similarity = self.embedding.similarity(query_embedding, doc["embedding"])
                results.append({
                    "id": doc_id,
                    "text": doc["text"],
                    "metadata": doc["metadata"],
                    "distance": 1 - similarity,
                    "similarity": similarity
                })
            
            # 按相似度排序
            results.sort(key=lambda x: x["similarity"], reverse=True)
            return results[:n_results]
        else:
            # ChromaDB 搜索
            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where,
                where_document=where_document
            )
            
            # 格式化结果
            formatted = []
            for i in range(len(results["ids"][0])):
                formatted.append({
                    "id": results["ids"][0][i],
                    "text": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "distance": results["distances"][0][i] if results.get("distances") else None,
                })
            
            return formatted
    
    def get(self, ids: List[str]) -> List[Dict[str, Any]]:
        """获取指定ID的文档"""
        self._init_client()
        
        if self._use_memory:
            return [self._memory_store.get(id) for id in ids if id in self._memory_store]
        else:
            results = self._collection.get(ids=ids)
            formatted = []
            for i in range(len(results["ids"])):
                formatted.append({
                    "id": results["ids"][i],
                    "text": results["documents"][i],
                    "metadata": results["metadatas"][i] if results.get("metadatas") else {},
                    "embedding": results["embeddings"][i] if results.get("embeddings") else None,
                })
            return formatted
    
    def delete(self, ids: List[str]) -> bool:
        """删除文档"""
        self._init_client()
        
        if self._use_memory:
            for id in ids:
                self._memory_store.pop(id, None)
            return True
        else:
            self._collection.delete(ids=ids)
            return True
    
    def update(
        self,
        id: str,
        document: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """更新文档"""
        self._init_client()
        
        if self._use_memory:
            if id not in self._memory_store:
                return False
            
            if document:
                text = document.get("content", document.get("text", ""))
                self._memory_store[id]["text"] = text
                self._memory_store[id]["embedding"] = self.embedding.embed_single(text)
                self._memory_store[id]["document"] = document
            
            if metadata:
                self._memory_store[id]["metadata"].update(metadata)
            
            return True
        else:
            if document:
                text = document.get("content", document.get("text", ""))
                embedding = self.embedding.embed_single(text)
                self._collection.update(
                    ids=[id],
                    embeddings=[embedding],
                    documents=[text],
                    metadatas=[metadata] if metadata else None
                )
            elif metadata:
                # ChromaDB 需要提供文档来更新
                existing = self.get([id])
                if existing:
                    self._collection.update(
                        ids=[id],
                        metadatas=[metadata]
                    )
            
            return True
    
    def count(self) -> int:
        """获取文档数量"""
        self._init_client()
        
        if self._use_memory:
            return len(self._memory_store)
        else:
            return self._collection.count()
    
    def clear(self) -> bool:
        """清空集合"""
        self._init_client()
        
        if self._use_memory:
            self._memory_store.clear()
            return True
        else:
            # 删除并重建集合
            self._client.delete_collection(self.collection_name)
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            return True
    
    def _generate_id(self, text: str) -> str:
        """生成文档ID"""
        return hashlib.md5(text.encode()).hexdigest()
    
    # ==================== 便捷方法 ====================
    
    def search_similar_documents(
        self,
        doc_id: str,
        n_results: int = 10
    ) -> List[Dict[str, Any]]:
        """查找相似文档"""
        docs = self.get([doc_id])
        if not docs:
            return []
        
        return self.search(docs[0]["text"], n_results=n_results)
    
    def find_duplicates(
        self,
        text: str,
        threshold: float = 0.95
    ) -> List[Dict[str, Any]]:
        """
        查找重复文档
        
        Args:
            text: 待检查文本
            threshold: 相似度阈值
        
        Returns:
            相似度超过阈值的文档列表
        """
        results = self.search(text, n_results=20)
        return [r for r in results if r.get("similarity", 0) >= threshold]
    
    def get_sentiment_neighbors(
        self,
        query: str,
        sentiment: str,
        n_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        按情感过滤的语义搜索
        
        Args:
            query: 查询文本
            sentiment: 情感标签 ("positive", "negative", "neutral")
            n_results: 返回结果数量
        """
        return self.search(
            query,
            n_results=n_results,
            where={"sentiment": sentiment}
        )


class DocumentIndexer:
    """
    文档索引器
    
    提供批量索引和增量更新功能。
    """
    
    def __init__(
        self,
        vector_store: VectorStore,
        batch_size: int = 100
    ):
        self.vector_store = vector_store
        self.batch_size = batch_size
    
    def index_documents(
        self,
        documents: List[Dict[str, Any]],
        update_existing: bool = False
    ) -> Dict[str, int]:
        """
        批量索引文档
        
        Args:
            documents: 文档列表
            update_existing: 是否更新已存在的文档
        
        Returns:
            索引统计
        """
        stats = {
            "total": len(documents),
            "indexed": 0,
            "skipped": 0,
            "errors": 0
        }
        
        # 分批处理
        for i in range(0, len(documents), self.batch_size):
            batch = documents[i:i + self.batch_size]
            
            try:
                ids = [doc.get("doc_id") for doc in batch]
                
                if not update_existing:
                    # 检查已存在的文档
                    existing = self.vector_store.get(ids)
                    existing_ids = {doc["id"] for doc in existing if doc}
                    
                    # 过滤已存在的
                    new_batch = []
                    new_ids = []
                    for doc, doc_id in zip(batch, ids):
                        if doc_id not in existing_ids:
                            new_batch.append(doc)
                            new_ids.append(doc_id)
                    
                    batch = new_batch
                    ids = new_ids
                    stats["skipped"] += len(existing_ids)
                
                if batch:
                    self.vector_store.add_documents(batch, ids)
                    stats["indexed"] += len(batch)
            
            except Exception as e:
                stats["errors"] += len(batch)
        
        return stats
    
    def remove_old_documents(self, days: int = 30) -> int:
        """
        删除旧文档
        
        Args:
            days: 保留天数
        
        Returns:
            删除数量
        """
        # 这个功能需要根据实际存储实现
        # ChromaDB 支持按元数据过滤删除
        cutoff = datetime.utcnow() - timedelta(days=days)
        # 实现取决于具体需求
        return 0