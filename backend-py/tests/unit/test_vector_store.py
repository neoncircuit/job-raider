"""Unit tests for the ChromaStore vector store."""

import pytest
from unittest.mock import MagicMock, patch

from src.rag.vector_store import ChromaStore
from src.rag.config import VectorStoreConfig
from src.rag.chunker import TextChunk


@pytest.fixture
def chroma_store(temp_chroma_dir):
    """Create a ChromaStore with a temporary directory."""
    config = VectorStoreConfig(
        persist_directory=temp_chroma_dir,
        collections={"jobs": "test_jobs", "profiles": "test_profiles"},
    )
    store = ChromaStore(config)
    store.initialize()
    return store


@pytest.fixture
def sample_chunks():
    """Create sample chunks for testing."""
    return [
        TextChunk(
            content="Python developer role",
            chunk_index=0,
            source_id="job_1",
            source_type="job",
            section="header",
            token_count=4,
        ),
        TextChunk(
            content="Requirements: 5 years Python, Django",
            chunk_index=1,
            source_id="job_1",
            source_type="job",
            section="requirements",
            token_count=7,
        ),
    ]


@pytest.fixture
def sample_embeddings():
    """Create sample embeddings for testing."""
    import numpy as np
    rng = np.random.RandomState(42)
    return [rng.randn(768).astype(float).tolist() for _ in range(2)]


class TestInitialize:
    """Tests for store initialization."""

    def test_creates_collections(self, chroma_store):
        """Initialize should create configured collections."""
        stats = chroma_store.get_collection_stats("jobs")
        assert stats["count"] == 0

        stats = chroma_store.get_collection_stats("profiles")
        assert stats["count"] == 0


class TestAddAndRetrieve:
    """Tests for adding and retrieving documents."""

    def test_add_and_query_job(self, chroma_store, sample_chunks, sample_embeddings):
        """Should add a job and allow querying it."""
        chroma_store.add_job("job_1", sample_chunks, sample_embeddings)

        assert chroma_store.job_exists("job_1")

        results = chroma_store.query_similar(
            query_embedding=sample_embeddings[0],
            collection="jobs",
            n_results=5,
        )
        assert len(results) >= 1

    def test_add_profile(self, chroma_store):
        """Should add and retrieve profile embeddings."""
        chunks = [
            TextChunk(
                content="Experienced Python developer",
                chunk_index=0,
                source_id="default",
                source_type="profile",
                section="summary",
                token_count=4,
            ),
        ]
        import numpy as np
        embeddings = [np.random.randn(768).astype(float).tolist()]

        chroma_store.add_profile("default", chunks, embeddings)

        retrieved = chroma_store.get_profile_embeddings("default")
        assert retrieved is not None
        assert len(retrieved) == 1

    def test_add_jobs_batch(self, chroma_store):
        """Should add multiple jobs in batch."""
        import numpy as np

        all_chunks = []
        all_embeddings = []
        job_ids = []

        for i in range(3):
            job_ids.append(f"batch_job_{i}")
            chunks = [
                TextChunk(
                    content=f"Job {i} description",
                    chunk_index=0,
                    source_id=f"batch_job_{i}",
                    source_type="job",
                    section="description",
                    token_count=3,
                ),
            ]
            embeddings = [np.random.randn(768).astype(float).tolist()]
            all_chunks.append(chunks)
            all_embeddings.append(embeddings)

        chroma_store.add_jobs_batch(job_ids, all_chunks, all_embeddings)

        for jid in job_ids:
            assert chroma_store.job_exists(jid)


class TestDelete:
    """Tests for deletion operations."""

    def test_delete_job(self, chroma_store, sample_chunks, sample_embeddings):
        """Should remove a job from the store."""
        chroma_store.add_job("job_del", sample_chunks, sample_embeddings)
        assert chroma_store.job_exists("job_del")

        chroma_store.delete_job("job_del")
        assert not chroma_store.job_exists("job_del")


class TestPersistence:
    """Tests for data persistence."""

    def test_data_survives_reinit(self, temp_chroma_dir, sample_chunks, sample_embeddings):
        """Data should persist across ChromaStore instances."""
        config = VectorStoreConfig(
            persist_directory=temp_chroma_dir,
            collections={"jobs": "test_jobs", "profiles": "test_profiles"},
        )

        # Write
        store1 = ChromaStore(config)
        store1.initialize()
        store1.add_job("persist_1", sample_chunks, sample_embeddings)

        # Read with new instance
        store2 = ChromaStore(config)
        store2.initialize()
        assert store2.job_exists("persist_1")


class TestHealthCheck:
    """Tests for health check."""

    def test_returns_healthy(self, chroma_store):
        """Health check should report healthy status."""
        health = chroma_store.health_check()
        assert health["status"] == "healthy"
        assert "jobs" in health["collections"]
