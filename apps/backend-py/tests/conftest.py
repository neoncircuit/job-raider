# Job Raider - Pytest Fixtures
#
# Shared fixtures for all tests.
#
# Author: Job Raider
# Date: 2026-04-21

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, Mock, patch

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture
def sample_job_listing():
    """Sample job listing for testing."""
    from src.models.job_listing import (
        JobListing,
        JobRequirement,
        JobResponsibility,
        JobSource,
        SalaryRange,
        Skill,
    )

    return JobListing(
        title="Senior Python Engineer",
        company="Tech Corp",
        location="San Francisco, CA",
        description="We are looking for a senior Python engineer...",
        requirements=[
            JobRequirement(text="5+ years of Python experience"),
            JobRequirement(text="Experience with Django and FastAPI"),
            JobRequirement(text="Knowledge of AWS services"),
        ],
        responsibilities=[
            JobResponsibility(text="Design and implement scalable APIs"),
            JobResponsibility(text="Mentor junior developers"),
            JobResponsibility(text="Participate in code reviews"),
        ],
        skills=[
            Skill(name="python"),
            Skill(name="django"),
            Skill(name="fastapi"),
            Skill(name="aws"),
            Skill(name="postgresql"),
        ],
        salary_range=SalaryRange(
            min_amount=150000,
            max_amount=200000,
            currency="USD",
            period="annual",
        ),
        source=JobSource.LINKEDIN,
        source_url="https://linkedin.com/jobs/view/123456789",
        job_id="linkedin_123456789",
        posted_date=datetime.now(),
    )


@pytest.fixture
def sample_user_profile():
    """Sample user profile for testing."""
    from src.models.job_listing import ExperienceLevel
    from src.models.user_profile import (
        ContactInfo,
        Education,
        ProficiencyLevel,
        Project,
        Skill,
        SkillCategory,
        TargetJob,
        UserProfile,
        WorkExperience,
    )

    return UserProfile(
        name="John Doe",
        contact=ContactInfo(
            email="john.doe@example.com",
            phone="555-1234",
            location="San Francisco, CA",
            linkedin="https://linkedin.com/in/johndoe",
            github="https://github.com/johndoe",
        ),
        skills=[
            Skill(
                name="Python",
                category=SkillCategory.PROGRAMMING_LANGUAGE,
                proficiency=ProficiencyLevel.EXPERT,
                years_experience=7,
            ),
            Skill(
                name="JavaScript",
                category=SkillCategory.PROGRAMMING_LANGUAGE,
                proficiency=ProficiencyLevel.INTERMEDIATE,
                years_experience=3,
            ),
            Skill(
                name="Django",
                category=SkillCategory.FRAMEWORK,
                proficiency=ProficiencyLevel.EXPERT,
                years_experience=6,
            ),
            Skill(
                name="FastAPI",
                category=SkillCategory.FRAMEWORK,
                proficiency=ProficiencyLevel.ADVANCED,
                years_experience=3,
            ),
            Skill(
                name="AWS",
                category=SkillCategory.CLOUD,
                proficiency=ProficiencyLevel.INTERMEDIATE,
                years_experience=2,
            ),
        ],
        experience=[
            WorkExperience(
                title="Senior Software Engineer",
                company="Previous Company",
                start_date=datetime(2020, 1, 1),
                end_date=datetime(2023, 12, 31),
                description="Led development of microservices architecture",
                technologies=["Python", "Django", "AWS"],
            )
        ],
        projects=[
            Project(
                name="E-commerce Platform",
                description="Built full-stack e-commerce platform",
                technologies=["Python", "Django", "React", "PostgreSQL"],
                start_date=datetime(2021, 6, 1),
                end_date=datetime(2022, 12, 31),
                highlights=[
                    "Handled 10,000+ daily active users",
                    "Reduced page load time by 40%",
                ],
            )
        ],
        education=[
            Education(
                degree="B.S. Computer Science",
                school="University of California",
            )
        ],
        targets=TargetJob(
            keywords=["python", "engineer", "developer", "backend"],
            locations=["remote", "san francisco", "new york"],
            experience_levels=[ExperienceLevel.MID, ExperienceLevel.SENIOR],
        ),
    )


@pytest.fixture
def sample_submission_info():
    """Sample submission info for testing."""
    from src.models.job_listing import JobSource
    from src.submission.detector import ApplyMethod, SubmissionInfo

    job = Mock()
    job.title = "Software Engineer"
    job.company = "Test Company"
    job.job_id = "test_123"

    return SubmissionInfo(
        job=job,
        can_auto_submit=True,
        apply_method=ApplyMethod.EASY_APPLY,
        apply_url="https://linkedin.com/jobs/apply/123",
        requirements=["Click Easy Apply button"],
        estimated_time_minutes=2,
    )


@pytest.fixture
def mock_llm_response():
    """Mock LLM response for testing."""
    return Mock(
        content="This is a mock response",
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        model="qwen2.5:3b",
        finish_reason="stop",
    )


@pytest.fixture
def temp_data_dir(tmp_path):
    """Temporary data directory for testing."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "listings").mkdir()
    (data_dir / "cache").mkdir()
    (data_dir / "results").mkdir()
    (data_dir / "applications").mkdir()
    (data_dir / "metrics").mkdir()
    return data_dir


@pytest.fixture
def client():
    """Shared FastAPI TestClient for API route tests.

    Modules that need mocked dependencies (e.g. ``test_assessment_api.py`` and
    ``test_application_api.py``) define their own local ``client`` fixture,
    which takes precedence over this shared one.
    """
    from fastapi.testclient import TestClient

    from src.api.main import app

    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Mock environment variables for testing."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-12345")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")


@pytest.fixture
def mock_ollama_client():
    """Mock Ollama client for testing."""
    client = MagicMock()
    client.generate.return_value = {
        "response": "Mock response",
        "prompt_eval_count": 100,
        "eval_count": 50,
        "model": "qwen2.5:3b",
    }
    return client


@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic client for testing."""
    client = MagicMock()
    client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="Mock response")],
        usage=MagicMock(
            input_tokens=100,
            output_tokens=50,
        ),
        model="claude-sonnet-4-6",
        stop_reason="end_turn",
    )
    return client


@pytest.fixture
def sample_token_usage():
    """Sample token usage for testing."""
    from src.metrics.cost_tracker import TokenUsage

    return TokenUsage(
        prompt_tokens=1000,
        completion_tokens=500,
        total_tokens=1500,
    )


@pytest.fixture
def sample_job_listings():
    """Sample list of job listings for testing."""
    from src.models.job_listing import JobListing, JobRequirement, JobSource, Skill

    listings = []
    companies = ["Tech Corp", "Data Inc", "Cloud Co", "AI Labs", "Startup XYZ"]

    for i, company in enumerate(companies):
        listing = JobListing(
            title=f"Software Engineer {i+1}",
            company=company,
            location="Remote",
            description=f"Job description {i+1}",
            requirements=[JobRequirement(text=f"Requirement {j}") for j in range(3)],
            skills=[Skill(name="python"), Skill(name="django")],
            source=JobSource.LINKEDIN,
            job_id=f"job_{i}",
        )
        listings.append(listing)

    return listings


# Skip decorators for expensive tests


def pytest_addoption(parser):
    """Register custom pytest options."""
    parser.addoption(
        "--run-llm-tests",
        action="store_true",
        default=False,
        help="Run LLM integration tests (requires API keys or Ollama)",
    )


@pytest.fixture
def skip_if_no_api_key():
    """Skip test if API key is not available."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")


@pytest.fixture
def skip_if_no_gpu():
    """Skip test if GPU is not available."""
    try:
        import subprocess

        result = subprocess.run(
            ["nvidia-smi"],
            capture_output=True,
            timeout=5,
        )
        if result.returncode != 0:
            pytest.skip("No GPU available")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pytest.skip("nvidia-smi not available")


@pytest.fixture
def skip_if_no_ollama():
    """Skip test if Ollama is not available."""
    try:
        import subprocess

        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            timeout=5,
        )
        if result.returncode != 0:
            pytest.skip("Ollama not available")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pytest.skip("Ollama not installed")


# -- RAG / Embedding Fixtures --


@pytest.fixture
def rag_config():
    """Sample RAG configuration for testing."""
    from src.rag.config import (
        ChunkingConfig,
        EmbeddingConfig,
        RAGConfig,
        ReRankingConfig,
        VectorStoreConfig,
    )

    return RAGConfig(
        embedding=EmbeddingConfig(model="nomic-embed-text", dimension=768),
        vector_store=VectorStoreConfig(persist_directory="data/chroma"),
        chunking={
            "job_description": ChunkingConfig(max_chunk_size=512, overlap=64),
            "profile": ChunkingConfig(
                max_chunk_size=512, overlap=64, strategy="section"
            ),
        },
        re_ranking=ReRankingConfig(
            enabled=True,
            top_k_candidates=50,
            min_heuristic_score=60,
            final_limit=20,
            weights={"heuristic": 0.4, "semantic": 0.6},
            similarity_threshold=0.3,
        ),
    )


@pytest.fixture
def mock_embedding_client():
    """Mock embedding client returning deterministic vectors."""
    import hashlib

    import numpy as np

    client = MagicMock()
    client.model = "nomic-embed-text"
    client.dimension = 768

    def _fake_embed(text):
        """Generate deterministic embedding from text hash."""
        h = hashlib.sha256(text.encode()).hexdigest()
        seed = int(h[:8], 16)
        rng = np.random.RandomState(seed)
        vec = rng.randn(768).astype(float)
        vec /= np.linalg.norm(vec)  # normalize
        return vec.tolist()

    client.embed.side_effect = _fake_embed
    client.embed_batch.side_effect = lambda texts: [_fake_embed(t) for t in texts]
    client.is_model_available.return_value = True
    client.stats = {"total_embedded": 0, "cache_hits": 0, "cache_misses": 0}
    return client


@pytest.fixture
def temp_chroma_dir(tmp_path):
    """Temporary ChromaDB directory for testing."""
    chroma_dir = tmp_path / "chroma"
    chroma_dir.mkdir()
    return str(chroma_dir)


@pytest.fixture
def skip_if_no_embedding_model():
    """Skip test if nomic-embed-text is not available in Ollama."""
    import requests

    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=3)
        models = [m["name"] for m in resp.json().get("models", [])]
        if "nomic-embed-text" not in models and "nomic-embed-text:latest" not in models:
            pytest.skip("nomic-embed-text model not available")
    except Exception:
        pytest.skip("Ollama not reachable")
