"""Tests for the structured LLM output models and the strict parser (Step 3.7, MH-1)."""

import json
from typing import Any, Dict

import pytest

from src.llm.structured import (
    OUTPUT_MODELS,
    CoverLetterReviewAnswer,
    ResumeAnalysisAnswer,
    ResumeValidationAnswer,
    StructuredOutputError,
    extract_braced_object,
    parse_structured,
    strip_code_fence,
)

SAMPLE_ANSWERS: Dict[str, Dict[str, Any]] = {
    "selection": {
        "selected_projects": [{"name": "Ledger", "reason": "Payments work"}],
        "keywords_to_emphasize": ["Python"],
        "key_achievements": ["Cut batch time by half"],
        "summary_suggestion": "Backend engineer with payments work.",
    },
    "resume_writing": {
        "summary": "Backend engineer.",
        "skills": ["Python", "SQL"],
        "experience": [
            {
                "title": "Engineer",
                "company": "Acme",
                "dates": "2024 - 2025",
                "highlights": ["Built an API"],
            }
        ],
        "projects": [
            {
                "name": "Ledger",
                "description": "A ledger service.",
                "technologies": ["Python"],
                "highlights": ["Handles refunds"],
            }
        ],
        "education": [{"degree": "BSc", "school": "NUS", "year": "2025"}],
    },
    "resume_validation": {
        "is_valid": True,
        "missing_projects": [],
        "missing_keywords": ["Go"],
        "fabricated_content": [],
        "date_inconsistencies": [],
        "overall_score": 85,
        "recommendation": "approve",
    },
    "resume_analysis": {
        "overall_score": 70,
        "summary": "Solid junior profile.",
        "key_strengths": ["Python"],
        "key_improvements": ["Add metrics"],
        "resume_improvements": ["Quantify results"],
        "skill_gaps": ["Kubernetes"],
        "next_steps": ["Build a cloud project"],
    },
    "cover_letter_review": {"critique": "Name the role.", "rewrite_needed": True},
    "cover_letter_validation": {
        "structure_score": 80,
        "content_score": 75,
        "tone_score": 90,
        "overall_score": 80,
        "is_valid": True,
        "recommendation": "needs_revision",
        "issues": ["Generic opening"],
    },
    "resume_parsing": {
        "basics": {
            "name": "Mara Chen",
            "email": None,
            "phone": None,
            "location": "Singapore, Singapore",
            "linkedin": None,
            "github": None,
        },
        "summary": None,
        "skills": {
            "programming_languages": ["Python"],
            "frameworks": ["FastAPI"],
            "tools": [],
            "databases": ["PostgreSQL"],
            "cloud": [],
            "domains": [],
        },
        "experience": [
            {
                "title": "Engineer",
                "company": "Acme",
                "location": None,
                "start_date": "2024-01",
                "end_date": "present",
                "highlights": ["Built an API"],
            }
        ],
        "projects": [
            {
                "name": "Ledger",
                "description": None,
                "technologies": ["Python"],
                "url": None,
                "highlights": [],
            }
        ],
        "education": [
            {
                "degree": "BSc",
                "school": "NUS",
                "location": None,
                "graduation_year": "2025",
                "gpa": None,
            }
        ],
        "certifications": [],
        "target_job": {
            "keywords": ["Software Engineer"],
            "locations": ["Singapore"],
            "experience_levels": ["Entry Level"],
            "remote_preference": None,
            "industries": ["Technology"],
        },
        "apprenticeship": None,
    },
    "jd_extraction": {
        "title": "Backend Engineer",
        "company": "Acme",
        "location": "Singapore",
        "requirements": ["3 years of Python"],
        "responsibilities": ["Build APIs"],
        "skills": ["Python"],
        "experience_level": "Mid",
        "salary_range": None,
    },
    "job_classification": {
        "industry": "Technology",
        "role_category": "Engineering",
        "company_size": "Unknown",
        "company_stage": None,
        "work_pace": "Unknown",
        "team_structure": "Unknown",
        "technical_skills": [
            {
                "name": "Python",
                "proficiency": "Advanced",
                "is_required": True,
                "category": "programming_language",
            }
        ],
        "soft_skills": [],
        "domain_skills": [],
        "experience_level_confidence": 0.8,
        "actual_experience_years": [3.0, 5.0],
        "management_level": None,
        "impact_scope": None,
        "classification_confidence": 0.7,
        "tags": ["backend"],
        "red_flags": [],
    },
}

REVIEW = '{"critique": "Name the role.", "rewrite_needed": true}'


def test_output_models_cover_the_nine_call_sites() -> None:
    """There is one output model for each of the 9 JSON call sites."""
    assert set(OUTPUT_MODELS) == set(SAMPLE_ANSWERS)


@pytest.mark.parametrize("site", sorted(SAMPLE_ANSWERS))
def test_each_model_accepts_the_shape_of_its_prompt(site: str) -> None:
    """A sample answer in the shape that each prompt asks for validates."""
    parsed = parse_structured(json.dumps(SAMPLE_ANSWERS[site]), OUTPUT_MODELS[site])

    assert isinstance(parsed, OUTPUT_MODELS[site])


@pytest.mark.parametrize("site", sorted(SAMPLE_ANSWERS))
def test_each_model_has_a_json_schema_with_required_fields(site: str) -> None:
    """Each schema is a JSON object schema with required fields, for Ollama."""
    schema = OUTPUT_MODELS[site].model_json_schema()

    assert schema["type"] == "object"
    assert schema["required"]
    json.dumps(schema)


def test_parse_returns_the_model() -> None:
    """A whole JSON answer becomes a model instance."""
    parsed = parse_structured(REVIEW, CoverLetterReviewAnswer)

    assert parsed.critique == "Name the role."
    assert parsed.rewrite_needed is True


@pytest.mark.parametrize(
    "content",
    [
        "```json\n" + REVIEW + "\n```",
        "```\n" + REVIEW + "\n```",
        "  " + REVIEW + "\n",
    ],
)
def test_parse_accepts_a_code_fence_and_spaces(content: str) -> None:
    """A code fence or spaces around the JSON are allowed."""
    parsed = parse_structured(content, CoverLetterReviewAnswer)

    assert parsed.rewrite_needed is True


def test_strip_code_fence_keeps_an_answer_without_a_fence() -> None:
    """An answer without a fence comes back stripped and otherwise unchanged."""
    assert strip_code_fence("  " + REVIEW + "  ") == REVIEW


def test_parse_rejects_text_around_the_json() -> None:
    """Prose around the JSON is a ``not_json`` failure; the parser does not search."""
    with pytest.raises(StructuredOutputError) as caught:
        parse_structured("Here is the review: " + REVIEW, CoverLetterReviewAnswer)

    assert caught.value.reason == "not_json"


def test_parse_rejects_a_json_array() -> None:
    """A JSON array is a ``not_object`` failure."""
    with pytest.raises(StructuredOutputError) as caught:
        parse_structured("[" + REVIEW + "]", CoverLetterReviewAnswer)

    assert caught.value.reason == "not_object"


def test_parse_rejects_a_missing_field() -> None:
    """A missing required field is a ``schema`` failure."""
    with pytest.raises(StructuredOutputError) as caught:
        parse_structured('{"critique": "Fine."}', CoverLetterReviewAnswer)

    assert caught.value.reason == "schema"


def test_parse_rejects_an_unknown_recommendation() -> None:
    """A recommendation outside the three allowed values is a ``schema`` failure."""
    answer = dict(SAMPLE_ANSWERS["resume_validation"], recommendation="Approve")

    with pytest.raises(StructuredOutputError) as caught:
        parse_structured(json.dumps(answer), ResumeValidationAnswer)

    assert caught.value.reason == "schema"


def test_parse_rejects_a_score_above_100() -> None:
    """A score above 100 is a ``schema`` failure."""
    answer = dict(SAMPLE_ANSWERS["resume_validation"], overall_score=150)

    with pytest.raises(StructuredOutputError) as caught:
        parse_structured(json.dumps(answer), ResumeValidationAnswer)

    assert caught.value.reason == "schema"


def test_analysis_fields_of_the_job_specific_prompt_are_optional() -> None:
    """The general analysis has no alignment score or competitive fields."""
    parsed = parse_structured(
        json.dumps(SAMPLE_ANSWERS["resume_analysis"]), ResumeAnalysisAnswer
    )

    assert parsed.target_alignment_score is None
    assert parsed.competitive_advantages == []
    assert parsed.competitive_gaps == []
    assert parsed.metadata == {}


def test_error_is_a_value_error() -> None:
    """Call sites that catch ``ValueError`` also catch a parse failure."""
    assert issubclass(StructuredOutputError, ValueError)


def test_extract_braced_object_takes_the_first_and_last_brace() -> None:
    """The old regex took the text from the first ``{`` to the last ``}``."""
    content = 'Sure: {"a": {"b": 1}} Thanks.'

    assert extract_braced_object(content) == '{"a": {"b": 1}}'


@pytest.mark.parametrize("content", ["no braces here", "} then {", ""])
def test_extract_braced_object_without_an_object(content: str) -> None:
    """Without a ``{`` before a ``}`` there is nothing to rescue."""
    assert extract_braced_object(content) is None
