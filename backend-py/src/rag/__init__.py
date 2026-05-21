"""
Job Raider - RAG Module

Provides semantic search and re-ranking capabilities using
vector embeddings, ChromaDB, BM25 sparse retrieval, and
Reciprocal Rank Fusion for hybrid search.
"""

from .config import (
    RAGConfig,
    EmbeddingConfig,
    VectorStoreConfig,
    ReRankingConfig,
    BM25Config,
    RRFFusionConfig,
    CrossEncoderConfig,
)
from .chunker import TextChunker, TextChunk
from .vector_store import ChromaStore
from .ranker import RAGRanker, RAGMatchScore
from .bm25_retriever import BM25Retriever, BM25Result
from .rrf_fusion import reciprocal_rank_fusion, RRFResult
from .cross_encoder import CrossEncoderReranker

__all__ = [
    "RAGConfig",
    "EmbeddingConfig",
    "VectorStoreConfig",
    "ReRankingConfig",
    "BM25Config",
    "RRFFusionConfig",
    "CrossEncoderConfig",
    "TextChunker",
    "TextChunk",
    "ChromaStore",
    "RAGRanker",
    "RAGMatchScore",
    "BM25Retriever",
    "BM25Result",
    "reciprocal_rank_fusion",
    "RRFResult",
    "CrossEncoderReranker",
]
