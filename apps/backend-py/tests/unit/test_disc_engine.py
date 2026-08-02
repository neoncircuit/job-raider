"""
Unit tests for DISC assessment scoring and answer validation.
"""

from datetime import datetime
from pathlib import Path

import pytest

from src.assessment.disc_engine import DISCEngine, DISCJobMatcher
from src.models.assessment import DISCAnswer, DISCTrait


@pytest.fixture
def disc_engine() -> DISCEngine:
    """Build an engine pointed at the repo question bank."""
    root = Path(__file__).resolve().parents[2]
    questions = root / "config" / "disc_questions.json"
    results = root / "data" / "disc_results_test"
    results.mkdir(parents=True, exist_ok=True)
    return DISCEngine(questions_path=questions, results_path=results)


def _balanced_answers(engine: DISCEngine) -> list[DISCAnswer]:
    """
    Build a full answer set that prefers D as Most and C as Least.

    Args:
        engine: Loaded DISC engine with questions.

    Returns:
        One answer per question.
    """
    answers: list[DISCAnswer] = []
    for question in engine.questions:
        by_label = {opt["label"]: opt["scores"] for opt in question["options"]}
        most = next(
            label for label, scores in by_label.items() if scores.get("D", 0) > 0
        )
        least = next(
            label for label, scores in by_label.items() if scores.get("C", 0) > 0
        )
        answers.append(
            DISCAnswer(
                question_id=question["id"],
                most_like=most,
                least_like=least,
                answered_at=datetime.now(),
            )
        )
    return answers


def test_validate_session_id_rejects_path_traversal(disc_engine: DISCEngine):
    """Session ids must be UUIDs; path segments are rejected."""
    with pytest.raises(ValueError, match="path separators|UUID"):
        disc_engine.validate_session_id("../etc/passwd")
    with pytest.raises(ValueError, match="UUID"):
        disc_engine.validate_session_id("not-a-uuid")
    disc_engine.validate_session_id("123e4567-e89b-12d3-a456-426614174000")


def test_validate_answers_rejects_same_most_and_least(disc_engine: DISCEngine):
    """Most and Least must refer to different options."""
    qid = disc_engine.questions[0]["id"]
    with pytest.raises(ValueError, match="must differ"):
        disc_engine.validate_answers(
            [
                DISCAnswer(
                    question_id=qid,
                    most_like="A",
                    least_like="A",
                )
            ]
        )


def test_validate_answers_requires_full_coverage(disc_engine: DISCEngine):
    """Every question in the bank must be answered."""
    qid = disc_engine.questions[0]["id"]
    with pytest.raises(ValueError, match="Missing answers"):
        disc_engine.validate_answers(
            [
                DISCAnswer(
                    question_id=qid,
                    most_like="A",
                    least_like="B",
                )
            ]
        )


def test_calculate_scores_prefers_dominance(disc_engine: DISCEngine):
    """Always choosing D as Most and C as Least should elevate D over C."""
    answers = _balanced_answers(disc_engine)
    disc_engine.validate_answers(answers)
    scores = disc_engine.calculate_scores(answers)
    by_trait = {s.trait: s for s in scores}
    assert (
        by_trait[DISCTrait.DOMINANCE].raw_score
        > by_trait[DISCTrait.CONSCIENTIOUSNESS].raw_score
    )
    profile = disc_engine.calculate_profile_percentages(scores)
    assert abs(sum(profile.values()) - 100.0) < 0.2
    primary, secondary = disc_engine.determine_profile_type(scores)
    assert primary == DISCTrait.DOMINANCE


def test_job_matcher_returns_sorted_matches(disc_engine: DISCEngine, tmp_path: Path):
    """Top matches are sorted by score and include descriptions."""
    answers = _balanced_answers(disc_engine)
    scores = disc_engine.calculate_scores(answers)
    profile = disc_engine.calculate_profile_percentages(scores)
    matcher = DISCJobMatcher(profiles_path=tmp_path / "disc_job_profiles.json")
    matches = matcher.get_top_matches(profile, limit=3)
    assert len(matches) == 3
    assert matches[0]["match_score"] >= matches[1]["match_score"]
    assert "description" in matches[0]
    assert "job_type" in matches[0]
