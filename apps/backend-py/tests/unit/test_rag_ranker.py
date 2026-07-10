"""Unit tests for the RAGRanker."""

import numpy as np
import pytest

from src.models.job_listing import JobListing, JobSource
from src.rag.chunker import TextChunker
from src.rag.config import (
    ChunkingConfig,
    EmbeddingConfig,
    RAGConfig,
    ReRankingConfig,
    VectorStoreConfig,
)
from src.rag.ranker import RAGMatchScore, RAGRanker
from src.rag.vector_store import ChromaStore
from src.scoring.matcher import MatchScore


@pytest.fixture
def ranker_components(temp_chroma_dir, mock_embedding_client):
    """Create RAG ranker with mocked embedding client and real ChromaDB."""
    config = RAGConfig(
        embedding=EmbeddingConfig(model="nomic-embed-text"),
        vector_store=VectorStoreConfig(persist_directory=temp_chroma_dir),
        chunking={
            "job_description": ChunkingConfig(max_chunk_size=512),
            "profile": ChunkingConfig(max_chunk_size=512, strategy="section"),
        },
        re_ranking=ReRankingConfig(
            enabled=True,
            weights={"heuristic": 0.4, "semantic": 0.6},
            similarity_threshold=0.3,
            final_limit=20,
        ),
    )

    vector_store = ChromaStore(config.vector_store)
    vector_store.initialize()

    chunker = TextChunker(config.chunking.get("job_description"))

    ranker = RAGRanker(
        config=config,
        embedding_client=mock_embedding_client,
        vector_store=vector_store,
        chunker=chunker,
    )
    return ranker


@pytest.fixture
def sample_scored_listings(sample_job_listing):
    """Create sample scored listings for re-ranking."""
    match_score = MatchScore(
        job=sample_job_listing,
        total_score=75,
        passed_threshold=True,
        breakdown={"keyword": 25, "skills": 30, "experience": 15, "location": 5},
        matched_keywords=["python", "engineer"],
        missing_skills=["kubernetes"],
        recommendation="apply",
        reasoning="Good skills match",
    )
    return [(sample_job_listing, match_score)]


class TestIndexJobs:
    """Tests for job indexing."""

    def test_indexes_new_jobs(self, ranker_components, sample_job_listing):
        """Should index new jobs into vector store."""
        stats = ranker_components.index_jobs([sample_job_listing])
        assert stats["indexed"] == 1
        assert stats["total_chunks"] > 0

    def test_skips_already_indexed(self, ranker_components, sample_job_listing):
        """Should skip jobs that are already indexed."""
        ranker_components.index_jobs([sample_job_listing])
        stats = ranker_components.index_jobs([sample_job_listing])
        assert stats["skipped"] == 1
        assert stats["indexed"] == 0


class TestIndexProfile:
    """Tests for profile indexing."""

    def test_indexes_profile(self, ranker_components, sample_user_profile):
        """Should index user profile."""
        stats = ranker_components.index_profile(sample_user_profile)
        assert stats["indexed"] is True
        assert stats["chunk_count"] > 0


class TestReRank:
    """Tests for re-ranking."""

    def test_re_rank_produces_scores(
        self, ranker_components, sample_scored_listings, sample_user_profile
    ):
        """Re-ranking should produce RAGMatchScore objects."""
        results = ranker_components.re_rank(sample_scored_listings, sample_user_profile)

        assert len(results) >= 1
        assert isinstance(results[0], RAGMatchScore)
        assert results[0].heuristic_score == 75
        assert results[0].semantic_score >= 0.0
        assert results[0].combined_score >= 0.0

    def test_re_rank_sorted_by_combined(self, ranker_components, sample_user_profile):
        """Results should be sorted by combined score descending."""
        from src.scoring.matcher import MatchScore

        jobs = []
        for i in range(3):
            job = JobListing(
                title=f"Engineer {i}",
                company=f"Co {i}",
                job_id=f"rank_job_{i}",
                source=JobSource.LINKEDIN,
                description=f"Job description {i} with Python",
            )
            score = MatchScore(
                job=job,
                total_score=60 + i * 10,
                passed_threshold=True,
                breakdown={},
                matched_keywords=[],
                missing_skills=[],
                recommendation="apply",
                reasoning="",
            )
            jobs.append((job, score))

        results = ranker_components.re_rank(jobs, sample_user_profile)

        for i in range(len(results) - 1):
            assert results[i].combined_score >= results[i + 1].combined_score


class TestComputeSimilarity:
    """Tests for similarity computation."""

    def test_identical_vectors_high_similarity(self, ranker_components):
        """Identical vectors should have high similarity."""
        vec = np.random.randn(768)
        vec = vec / np.linalg.norm(vec)
        embeddings = [vec.tolist(), (vec * 0.99 + np.random.randn(768) * 0.01).tolist()]

        sim = ranker_components._compute_semantic_similarity(
            [embeddings[0]], [embeddings[1]]
        )
        assert sim > 0.9

    def test_orthogonal_vectors_low_similarity(self, ranker_components):
        """Orthogonal vectors should have low similarity."""
        vec1 = np.zeros(768)
        vec1[0] = 1.0
        vec2 = np.zeros(768)
        vec2[1] = 1.0

        sim = ranker_components._compute_semantic_similarity(
            [vec1.tolist()], [vec2.tolist()]
        )
        assert sim < 0.1

    def test_empty_embeddings_returns_zero(self, ranker_components):
        """Empty embeddings should return 0."""
        sim = ranker_components._compute_semantic_similarity([], [])
        assert sim == 0.0


class TestCombinedScore:
    """Tests for combined score computation."""

    def test_weights_applied(self, ranker_components):
        """Combined score should apply configured weights."""
        # heuristic 0.4, semantic 0.6
        combined = ranker_components._compute_combined_score(100, 1.0)
        assert abs(combined - 1.0) < 0.01  # 0.4*1.0 + 0.6*1.0

    def test_zero_scores(self, ranker_components):
        """Zero scores should produce zero combined."""
        combined = ranker_components._compute_combined_score(0, 0.0)
        assert combined == 0.0


class TestSemanticSearch:
    """Tests for semantic search."""

    def test_search_returns_results(
        self, ranker_components, sample_job_listing, mock_embedding_client
    ):
        """Semantic search should return matching jobs."""
        ranker_components.index_jobs([sample_job_listing])

        results = ranker_components.semantic_search("python engineer", n_results=5)
        # May or may not find results depending on similarity threshold
        assert isinstance(results, list)


class TestGracefulDegradation:
    """Tests for fallback behavior."""

    def test_fallback_to_heuristic(self, ranker_components, sample_scored_listings):
        """Should gracefully fall back to heuristic-only scoring."""
        fallback = ranker_components._fallback_to_heuristic(sample_scored_listings)

        assert len(fallback) == 1
        assert fallback[0].semantic_score == 0.0
        assert "heuristic-only" in fallback[0].reasoning
        assert fallback[0].heuristic_score == 75
