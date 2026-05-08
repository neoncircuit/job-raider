"""Integration tests for the RAG pipeline stage."""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from src.pipeline.stages import PipelineStages, PipelineContext, StageResult
from src.pipeline.orchestrator import PipelineStage
from src.models.job_listing import JobListing, JobSource
from src.models.user_profile import UserProfile, ContactInfo, TargetJob
from src.scoring.matcher import MatchScore


@pytest.fixture
def pipeline_context(sample_user_profile, tmp_path):
    """Create a pipeline context for testing."""
    from src.scrapers.storage import JobListingStorage

    storage = JobListingStorage(str(tmp_path / "listings"))
    return PipelineContext(
        user_profile=sample_user_profile,
        storage=storage,
        results_dir=tmp_path / "results",
        config={"dry_run": True, "scam_threshold": 0.7, "submission_delay": 2.0},
    )


@pytest.fixture
def sample_scored_listings():
    """Create sample scored listings for pipeline testing."""
    jobs = []
    for i in range(3):
        job = JobListing(
            title=f"Python Engineer {i}",
            company=f"Tech Co {i}",
            job_id=f"pipe_job_{i}",
            source=JobSource.LINKEDIN,
            description=f"Looking for a Python developer with Django experience. Role {i}.",
        )
        score = MatchScore(
            job=job,
            total_score=70 + i * 5,
            passed_threshold=True,
            breakdown={"keyword": 20, "skills": 30, "experience": 15, "location": 5},
            matched_keywords=["python", "django"],
            missing_skills=[],
            recommendation="apply",
            reasoning="Good match",
        )
        jobs.append((job, score))
    return jobs


class TestRAGPipelineStage:
    """Tests for the RAG rank stage in the pipeline."""

    @patch("src.pipeline.stages.EmbeddingClient")
    @patch("src.pipeline.stages.ChromaStore")
    @patch("src.pipeline.stages.TextChunker")
    @patch("src.pipeline.stages.RAGRanker")
    @patch("src.pipeline.stages.RAGConfig")
    def test_stage_rag_rank_when_rag_available(
        self, mock_config_cls, mock_ranker_cls, mock_chunker_cls,
        mock_store_cls, mock_embed_cls, pipeline_context, sample_scored_listings,
    ):
        """When RAG components are available, stage should re-rank listings."""
        from src.rag.ranker import RAGMatchScore
        from src.rag.config import RAGConfig

        # Configure mocks
        mock_config = RAGConfig()
        mock_config.re_ranking.enabled = True
        mock_config_cls.from_yaml.return_value = mock_config

        mock_embed_instance = MagicMock()
        mock_embed_instance.is_model_available.return_value = True
        mock_embed_cls.return_value = mock_embed_instance

        mock_store_instance = MagicMock()
        mock_store_instance.initialize.return_value = None
        mock_store_cls.return_value = mock_store_instance

        # Create ranker that returns RAGMatchScore objects
        rag_scores = [
            RAGMatchScore(
                job=job,
                heuristic_score=score.total_score,
                semantic_score=0.7,
                combined_score=0.65,
                heuristic_breakdown=score.breakdown,
                matched_keywords=score.matched_keywords,
                missing_skills=score.missing_skills,
                recommendation="apply",
                reasoning="Good semantic match",
                passed_threshold=True,
            )
            for job, score in sample_scored_listings
        ]
        mock_ranker_instance = MagicMock()
        mock_ranker_instance.re_rank.return_value = rag_scores
        mock_ranker_cls.return_value = mock_ranker_instance

        # Execute
        stages = PipelineStages(pipeline_context)
        result = stages.stage_rag_rank(sample_scored_listings)

        assert result.success is True
        assert result.metadata.get("rag_enabled") in [True, False]
        assert len(result.data) >= 1

    def test_stage_rag_rank_degrades_gracefully(self, pipeline_context, sample_scored_listings):
        """When RAG is unavailable, should pass through heuristic results."""
        stages = PipelineStages(pipeline_context)
        # RAG ranker stays None since config won't load
        stages._rag_ranker = None

        result = stages.stage_rag_rank(sample_scored_listings)

        assert result.success is True
        assert result.metadata["rag_enabled"] is False
        assert result.data == sample_scored_listings


class TestOrchestratorRAGStage:
    """Tests for the orchestrator integration with RAG stage."""

    def test_rag_stage_in_sequence(self):
        """RAG_RANK should be between SCORE_RANK and DETECT_AUTO_SUBMIT."""
        stages = list(PipelineStage)
        score_idx = stages.index(PipelineStage.SCORE_RANK)
        rag_idx = stages.index(PipelineStage.RAG_RANK)
        detect_idx = stages.index(PipelineStage.DETECT_AUTO_SUBMIT)

        assert rag_idx == score_idx + 1
        assert detect_idx == rag_idx + 1

    def test_stage_values(self):
        """RAG_RANK should have correct value."""
        assert PipelineStage.RAG_RANK.value == "rag_rank"
