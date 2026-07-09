"""
Job Raider - RAG Module

Provides semantic search and re-ranking capabilities using
vector embeddings, ChromaDB, BM25 sparse retrieval, and
Reciprocal Rank Fusion for hybrid search.
"""

from .bm25_retriever import BM25Result, BM25Retriever
from .chunker import TextChunk, TextChunker
from .config import (
    BM25Config,
    CrossEncoderConfig,
    EmbeddingConfig,
    RAGConfig,
    ReRankingConfig,
    RRFFusionConfig,
    VectorStoreConfig,
)
from .cross_encoder import CrossEncoderReranker
from .ranker import RAGMatchScore, RAGRanker
from .rrf_fusion import RRFResult, reciprocal_rank_fusion
from .vector_store import ChromaStore

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
