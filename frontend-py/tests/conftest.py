"""
Pytest fixtures for the Streamlit dashboard tests.

Provides mock API client, sample response data, and session state
fixtures used across all test modules.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from typing import Any, Dict

import pytest


@pytest.fixture
def mock_api_client() -> MagicMock:
    """Create a mock APIClient with all endpoint methods stubbed.

    Returns:
        MagicMock configured as an APIClient with default return values.
    """
    client = MagicMock()
    client.base_url = "http://localhost:8000"
    client.timeout = 30
    client.search_timeout = 120

    # Health & Version
    client.get_health.return_value = {
        "status": "healthy",
        "timestamp": "2026-04-22T10:00:00",
        "checks": [],
        "summary": {"healthy": 1, "degraded": 0, "unhealthy": 0},
    }
    client.get_version.return_value = {"version": "0.1.0", "name": "Job Raider API"}

    # Pipeline
    client.start_pipeline.return_value = "test-run-123"
    client.get_pipeline_status.return_value = {
        "run_id": "test-run-123",
        "status": "running",
        "current_stage": "scrape",
        "stage_progress": 50,
        "jobs_scraped": 10,
        "jobs_scored": 0,
        "jobs_selected": 0,
        "applications_submitted": 0,
        "started_at": "2026-04-22T10:00:00",
        "estimated_completion": None,
        "error_message": None,
    }
    client.get_pipeline_results.return_value = {
        "run_id": "test-run-123",
        "status": "completed",
        "success": True,
        "duration_seconds": 120.5,
        "stages_completed": ["scrape", "deduplicate", "filter_scams"],
        "jobs_scraped": 25,
        "jobs_applied": 5,
        "stage_results": {},
        "started_at": "2026-04-22T10:00:00",
        "completed_at": "2026-04-22T10:02:00",
    }
    client.cancel_pipeline.return_value = {
        "run_id": "test-run-123",
        "status": "cancelled",
    }
    client.get_pipeline_history.return_value = {
        "runs": [],
        "total": 0,
    }

    # Jobs
    client.search_jobs.return_value = {
        "total": 0,
        "jobs": [],
    }

    # Profile
    client.get_profile.return_value = {
        "profile_id": "prof-123",
        "resume_path": "/data/resume.pdf",
        "contact_info": {
            "name": "Test User",
            "email": "test@example.com",
            "phone": None,
            "location": "New York",
            "linkedin_url": None,
            "github_url": None,
            "portfolio_url": None,
        },
        "target_job": {
            "keywords": ["python", "engineer"],
            "locations": ["remote"],
            "experience_levels": ["mid"],
            "remote_preference": True,
            "salary_min": None,
            "industries": [],
        },
        "skills": [],
        "projects": [],
        "work_experience": [],
        "education": [],
        "years_of_experience": 5.0,
        "created_at": "2026-04-22T10:00:00",
        "updated_at": "2026-04-22T10:00:00",
    }
    client.upload_resume.return_value = {
        "profile_id": "prof-123",
        "resume_path": "/data/resume.pdf",
        "message": "Resume uploaded successfully",
    }
    client.update_profile.return_value = {
        "message": "Profile updated successfully",
    }

    # Metrics
    client.get_metrics_summary.return_value = {
        "cost": {
            "total_usd": 1.25,
            "per_application": 0.05,
            "api_usd": 0.25,
            "local_usage_percent": 80.0,
            "total_calls": 50,
        },
        "outcomes": {
            "total_applications": 25,
            "interviews": 3,
            "offers": 1,
            "interview_rate": 12.0,
            "offer_rate": 33.3,
            "overall_rate": 4.0,
        },
        "health": {
            "status": "healthy",
            "checks": 5,
            "healthy": 5,
            "degraded": 0,
            "unhealthy": 0,
        },
        "recent_calls": [],
    }
    client.get_cost_metrics.return_value = {
        "total_cost_usd": 1.25,
        "cost_per_application": 0.05,
        "api_costs_usd": 0.25,
        "local_model_usage": 80.0,
        "pipeline_runs": 3,
    }
    client.get_outcome_metrics.return_value = {
        "total_applications": 25,
        "interviews_scheduled": 3,
        "offers_received": 1,
        "rejection_count": 10,
        "interview_rate": 12.0,
        "offer_rate": 33.3,
        "overall_rate": 4.0,
    }
    client.get_health_metrics.return_value = {
        "status": "healthy",
        "timestamp": "2026-04-22T10:00:00",
        "checks": [],
        "summary": {"healthy": 5, "degraded": 0, "unhealthy": 0},
    }

    return client


@pytest.fixture
def sample_job() -> Dict[str, Any]:
    """Create a sample job listing for testing.

    Returns:
        Dict representing a single job listing.
    """
    return {
        "job_id": "job-001",
        "title": "Senior Python Engineer",
        "company": "Acme Corp",
        "location": "San Francisco, CA",
        "description": "We are looking for a senior Python engineer...",
        "url": "https://example.com/job/001",
        "source": "linkedin",
        "job_type": "full-time",
        "experience_level": "senior",
        "salary_range": "$150,000 - $200,000",
        "remote": True,
        "posted_date": "2026-04-20",
        "scraped_at": "2026-04-22T10:00:00",
    }
