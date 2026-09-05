"""
Unit tests for cover-letter analysis export formatter.

Author: Job Raider
Date: 2026-08-25
"""

import json
from pathlib import Path

import pytest

from src.generation.cover_letter_analysis_formatter import (
    CoverLetterAnalysisFormatter,
    jd_snippet,
)


@pytest.fixture
def sample_payload():
    """Minimal analysis payload for export tests."""
    return {
        "schema_version": 1,
        "exported_at": "2026-08-25T12:00:00",
        "job": {
            "title": "Backend Engineer",
            "company": "Harbor Labs",
            "location": "Singapore",
            "jd_snippet": "Build FastAPI services.",
            "job_id": "manual-1",
        },
        "job_fit": {
            "score": 78,
            "passed_threshold": True,
            "recommendation": "maybe",
            "reasoning": "Solid keyword overlap.",
            "breakdown": {
                "keyword": 20,
                "skills": 28,
                "experience": 15,
                "location": 10,
                "projects": 0,
                "education": 5,
            },
            "matched_keywords": ["Python", "FastAPI"],
            "missing_skills": ["Kubernetes"],
            "scam_risk": "low",
            "scam_flags": [],
        },
        "letter_text": "Dear Hiring Manager,\n\nI built FastAPI services.\n\nSincerely,\nAlex",
        "settings": {
            "writer_model": "qwen2.5:7b",
            "style": "modern",
            "deep_validation": False,
            "review_rewrite": True,
        },
        "timing": {
            "selection_ms": 100,
            "generation_ms": 2000,
            "review_ms": 400,
            "rewrite_ms": 1500,
            "validation_ms": 10,
            "total_ms": 4010,
        },
        "token_usage": {
            "total_tokens": 1200,
            "prompt_tokens": 900,
            "completion_tokens": 300,
        },
        "proofread": {
            "score": 88,
            "structure_score": 85,
            "content_score": 90,
            "tone_score": 88,
            "recommendation": "approve",
            "issues": [],
            "is_valid": True,
            "word_count": 12,
        },
        "review": {
            "critique": "Tighten the closing.",
            "rewrite_needed": True,
            "rewrite_count": 1,
            "model_used": "qwen2.5:3b",
        },
    }


@pytest.fixture
def formatter(tmp_path):
    """Formatter writing into a temporary directory."""
    return CoverLetterAnalysisFormatter(output_dir=str(tmp_path / "outputs"))


class TestJdSnippet:
    """Tests for JD truncation."""

    def test_short_text_unchanged(self):
        """Short descriptions should pass through."""
        assert jd_snippet("Hello world") == "Hello world"

    def test_long_text_truncated(self):
        """Long descriptions should end with an ellipsis."""
        text = "a" * 600
        snippet = jd_snippet(text, max_chars=50)
        assert len(snippet) == 50
        assert snippet.endswith("…")


class TestCoverLetterAnalysisFormatter:
    """Tests for JSON and PDF analysis export."""

    def test_export_json(self, formatter, sample_payload):
        """JSON export should be pretty-printed and parseable."""
        result = formatter.export(sample_payload, "analysis_json", "json")
        assert result.success is True
        assert result.path is not None
        assert Path(result.path).exists()
        data = json.loads(Path(result.path).read_text(encoding="utf-8"))
        assert data["job"]["company"] == "Harbor Labs"
        assert data["settings"]["writer_model"] == "qwen2.5:7b"
        assert data["token_usage"]["total_tokens"] == 1200

    def test_export_pdf(self, formatter, sample_payload):
        """PDF export should produce a non-empty file."""
        pytest.importorskip("reportlab")
        result = formatter.export(sample_payload, "analysis_pdf", "pdf")
        assert result.success is True
        assert result.path is not None
        assert Path(result.path).exists()
        assert Path(result.path).stat().st_size > 0
        assert result.media_type == "application/pdf"
