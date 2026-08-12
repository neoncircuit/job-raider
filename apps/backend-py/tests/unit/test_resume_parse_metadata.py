"""
Tests for resume parse metadata (duration, datetime, model).
"""

from src.extractors.resume_parser import ResumeParser
from src.models.user_profile import ContactInfo, UserProfile


def test_set_resume_parse_meta_records_method_and_model():
    """Parse meta helper stores method/model/provider on profile metadata."""
    parser = ResumeParser()
    profile = UserProfile(
        name="James",
        contact=ContactInfo(email="j@example.com", location="Singapore"),
    )
    parser._set_resume_parse_meta(
        profile,
        method="llm",
        model="qwen3.5:9b",
        provider="ollama",
    )
    meta = profile.metadata["resume_parse"]
    assert meta["method"] == "llm"
    assert meta["model"] == "qwen3.5:9b"
    assert meta["provider"] == "ollama"


def test_parse_text_rule_based_includes_duration_and_timestamp():
    """Rule-based parse_text attaches parsed_at and duration_ms."""
    parser = ResumeParser(llm_router=None)
    profile = parser.parse_text(
        "James Tan\njames@example.com\nSingapore\n\nTechnical Skills\nPython, FastAPI\n"
    )
    meta = profile.metadata.get("resume_parse")
    assert isinstance(meta, dict)
    assert meta["method"] == "rule_based"
    assert meta["model"] == "rule-based"
    assert isinstance(meta["duration_ms"], int)
    assert meta["duration_ms"] >= 0
    assert isinstance(meta["parsed_at"], str)
    assert "T" in meta["parsed_at"]
