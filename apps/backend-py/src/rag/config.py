"""
Job Raider - RAG Configuration

Dataclasses for RAG pipeline configuration loaded from rag_config.yaml.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict

import yaml


@dataclass
class EmbeddingConfig:
    """Configuration for embedding generation.

    Attributes:
        model: Ollama model name for embeddings.
        endpoint: Ollama API endpoint for embedding generation.
        dimension: Output embedding vector dimension.
        max_context_tokens: Maximum context window in tokens.
        batch_size: Number of texts to embed per batch call.
        cache_enabled: Whether to cache embeddings in memory.
        cache_ttl: Cache time-to-live in seconds.
    """

    model: str = "nomic-embed-text"
    endpoint: str = "/api/embeddings"
    dimension: int = 768
    max_context_tokens: int = 8192
    batch_size: int = 32
    cache_enabled: bool = True
    cache_ttl: int = 86400


@dataclass
class VectorStoreConfig:
    """Configuration for ChromaDB vector store.

    Attributes:
        backend: Vector store backend name.
        persist_directory: Filesystem path for ChromaDB persistence.
        collections: Mapping of collection purpose to collection name.
        distance_metric: Distance metric for similarity search.
    """

    backend: str = "chromadb"
    persist_directory: str = "data/chroma"
    collections: Dict[str, str] = field(
        default_factory=lambda: {
            "jobs": "job_listings",
            "profiles": "user_profiles",
        }
    )
    distance_metric: str = "cosine"


@dataclass
class ChunkingConfig:
    """Configuration for text chunking.

    Attributes:
        max_chunk_size: Maximum chunk size in tokens.
        overlap: Token overlap between adjacent chunks.
        strategy: Chunking strategy name.
    """

    max_chunk_size: int = 512
    overlap: int = 64
    strategy: str = "recursive"


@dataclass
class ReRankingConfig:
    """Configuration for hybrid re-ranking.

    Attributes:
        enabled: Whether RAG re-ranking is active.
        top_k_candidates: Maximum jobs from heuristic to re-rank.
        min_heuristic_score: Minimum heuristic score to qualify for re-ranking.
        final_limit: Top N jobs to return after re-ranking.
        weights: Scoring weights for heuristic and semantic components.
        similarity_threshold: Minimum cosine similarity to keep a result.
    """

    enabled: bool = True
    top_k_candidates: int = 50
    min_heuristic_score: int = 60
    final_limit: int = 20
    weights: Dict[str, float] = field(
        default_factory=lambda: {
            "heuristic": 0.4,
            "semantic": 0.6,
        }
    )
    similarity_threshold: float = 0.3


@dataclass
class BM25Config:
    """Configuration for BM25 sparse retrieval.

    Attributes:
        enabled: Whether BM25 retrieval is active.
        algorithm: BM25 variant to use ("okapi" or "plus").
        n_results: Maximum BM25 results per query.
    """

    enabled: bool = True
    algorithm: str = "okapi"
    n_results: int = 20


@dataclass
class RRFFusionConfig:
    """Configuration for Reciprocal Rank Fusion of dense and sparse results.

    Attributes:
        enabled: Whether RRF fusion is active.
        k: RRF constant for rank dampening (higher k reduces the advantage
            of top-ranked results).
        dense_weight: Weight applied to dense retrieval ranks.
        sparse_weight: Weight applied to BM25 retrieval ranks.
    """

    enabled: bool = True
    k: int = 60
    dense_weight: float = 0.5
    sparse_weight: float = 0.5


@dataclass
class CrossEncoderConfig:
    """Configuration for cross-encoder reranking.

    Attributes:
        enabled: Whether cross-encoder reranking is active.
        model_name: Sentence-transformers cross-encoder model identifier.
        max_length: Maximum token length for cross-encoder input pairs.
        top_k: Maximum candidates to score per query.
    """

    enabled: bool = False
    model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    max_length: int = 512
    top_k: int = 20


@dataclass
class RAGConfig:
    """Complete RAG pipeline configuration.

    Attributes:
        embedding: Embedding generation settings.
        vector_store: ChromaDB storage settings.
        chunking: Chunking settings keyed by content type.
        re_ranking: Hybrid re-ranking settings.
        bm25: BM25 sparse retrieval settings.
        rrf: Reciprocal Rank Fusion settings.
        cross_encoder: Cross-encoder reranking settings.
    """

    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    vector_store: VectorStoreConfig = field(default_factory=VectorStoreConfig)
    chunking: Dict[str, ChunkingConfig] = field(
        default_factory=lambda: {
            "job_description": ChunkingConfig(
                max_chunk_size=512, overlap=64, strategy="recursive"
            ),
            "profile": ChunkingConfig(
                max_chunk_size=512, overlap=64, strategy="section"
            ),
        }
    )
    re_ranking: ReRankingConfig = field(default_factory=ReRankingConfig)
    bm25: BM25Config = field(default_factory=BM25Config)
    rrf: RRFFusionConfig = field(default_factory=RRFFusionConfig)
    cross_encoder: CrossEncoderConfig = field(default_factory=CrossEncoderConfig)

    @classmethod
    def from_yaml(cls, path: str) -> "RAGConfig":
        """Load configuration from a YAML file.

        Args:
            path: Path to the YAML configuration file.

        Returns:
            Populated RAGConfig instance.

        Raises:
            FileNotFoundError: If the config file does not exist.
        """
        config_path = Path(path)
        if not config_path.exists():
            return cls()

        with open(config_path, "r") as f:
            raw = yaml.safe_load(f) or {}

        embedding_raw = raw.get("embedding", {})
        vector_store_raw = raw.get("vector_store", {})
        chunking_raw = raw.get("chunking", {})
        re_ranking_raw = raw.get("re_ranking", {})
        bm25_raw = raw.get("bm25", {})
        rrf_raw = raw.get("rrf", {})
        cross_encoder_raw = raw.get("cross_encoder", {})

        # Parse chunking configs
        chunking_configs: Dict[str, ChunkingConfig] = {}
        for key, chunk_raw in chunking_raw.items():
            if isinstance(chunk_raw, dict):
                chunking_configs[key] = ChunkingConfig(
                    max_chunk_size=chunk_raw.get("max_chunk_size", 512),
                    overlap=chunk_raw.get("overlap", 64),
                    strategy=chunk_raw.get("strategy", "recursive"),
                )

        # Default chunking if none provided
        if not chunking_configs:
            chunking_configs = {
                "job_description": ChunkingConfig(),
                "profile": ChunkingConfig(strategy="section"),
            }

        return cls(
            embedding=EmbeddingConfig(
                model=embedding_raw.get("model", "nomic-embed-text"),
                endpoint=embedding_raw.get("endpoint", "/api/embeddings"),
                dimension=embedding_raw.get("dimension", 768),
                max_context_tokens=embedding_raw.get("max_context_tokens", 8192),
                batch_size=embedding_raw.get("batch_size", 32),
                cache_enabled=embedding_raw.get("cache_enabled", True),
                cache_ttl=embedding_raw.get("cache_ttl", 86400),
            ),
            vector_store=VectorStoreConfig(
                backend=vector_store_raw.get("backend", "chromadb"),
                persist_directory=vector_store_raw.get(
                    "persist_directory", "data/chroma"
                ),
                collections=vector_store_raw.get(
                    "collections",
                    {
                        "jobs": "job_listings",
                        "profiles": "user_profiles",
                    },
                ),
                distance_metric=vector_store_raw.get("distance_metric", "cosine"),
            ),
            chunking=chunking_configs,
            re_ranking=ReRankingConfig(
                enabled=re_ranking_raw.get("enabled", True),
                top_k_candidates=re_ranking_raw.get("top_k_candidates", 50),
                min_heuristic_score=re_ranking_raw.get("min_heuristic_score", 60),
                final_limit=re_ranking_raw.get("final_limit", 20),
                weights=re_ranking_raw.get(
                    "weights", {"heuristic": 0.4, "semantic": 0.6}
                ),
                similarity_threshold=re_ranking_raw.get("similarity_threshold", 0.3),
            ),
            bm25=BM25Config(
                enabled=bm25_raw.get("enabled", True),
                algorithm=bm25_raw.get("algorithm", "okapi"),
                n_results=bm25_raw.get("n_results", 20),
            ),
            rrf=RRFFusionConfig(
                enabled=rrf_raw.get("enabled", True),
                k=rrf_raw.get("k", 60),
                dense_weight=rrf_raw.get("dense_weight", 0.5),
                sparse_weight=rrf_raw.get("sparse_weight", 0.5),
            ),
            cross_encoder=CrossEncoderConfig(
                enabled=cross_encoder_raw.get("enabled", False),
                model_name=cross_encoder_raw.get(
                    "model_name", "cross-encoder/ms-marco-MiniLM-L-6-v2"
                ),
                max_length=cross_encoder_raw.get("max_length", 512),
                top_k=cross_encoder_raw.get("top_k", 20),
            ),
        )
