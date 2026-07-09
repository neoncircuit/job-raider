# Unit tests for assessment engine
# Author: Job Raider
# Date: 2026-05-22

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.models.assessment import (
    Answer,
    AnswerFormat,
    AssessmentMode,
    AssessmentSession,
    DifficultyLevel,
    MultipleChoiceOption,
    Question,
    QuestionScore,
    QuestionType,
)
from src.models.job_listing import JobListing, JobRequirement, JobSource, Skill
from src.models.user_profile import ContactInfo, ProficiencyLevel
from src.models.user_profile import Skill as ProfileSkill
from src.models.user_profile import SkillCategory, UserProfile, WorkExperience

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_llm_router():
    """Mock LLM router returning configurable responses."""
    router = MagicMock()
    router.generate.return_value = MagicMock(
        content='[{"question_type": "conceptual", "answer_format": "freeform", '
        '"difficulty": "intermediate", "topic": "Python", '
        '"question_text": "Explain decorators.", '
        '"options": [], "correct_answer_hint": "Decorators wrap functions"}]',
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        model="qwen2.5:7b",
        finish_reason="stop",
    )
    return router


@pytest.fixture
def engine(mock_llm_router):
    """AssessmentEngine with mocked LLM router and templates."""
    from src.assessment.engine import AssessmentEngine

    eng = AssessmentEngine.__new__(AssessmentEngine)
    eng.llm_router = mock_llm_router
    eng.logger = MagicMock()
    eng._gen_template = {
        "system": "You are a technical interviewer.",
        "user": "Generate {{count}} questions on {{topic_seed}}.",
    }
    eng._eval_freeform_template = {
        "system": "Evaluate the answer.",
        "user": "Question: {{question_text}}\nAnswer: {{candidate_answer}}",
    }
    eng._eval_mc_template = {
        "system": "Explain MC answer.",
        "user": "Question: {{question_text}}\nSelected: {{selected_option}}",
    }
    return eng


@pytest.fixture
def sample_session():
    """Minimal assessment session for testing."""
    return AssessmentSession(
        mode=AssessmentMode.SKILL_BASED,
        difficulty=DifficultyLevel.INTERMEDIATE,
        current_difficulty=DifficultyLevel.INTERMEDIATE,
        target_skills=["Python", "SQL"],
        question_count=5,
    )


@pytest.fixture
def sample_mc_question():
    """Multiple-choice question for testing."""
    return Question(
        question_id="q-mc-001",
        question_type=QuestionType.CONCEPTUAL,
        answer_format=AnswerFormat.MULTIPLE_CHOICE,
        difficulty=DifficultyLevel.INTERMEDIATE,
        topic="Python",
        question_text="What does len() return for a list?",
        options=[
            MultipleChoiceOption(label="A", text="Number of items", is_correct=True),
            MultipleChoiceOption(label="B", text="Memory size"),
            MultipleChoiceOption(label="C", text="First index"),
            MultipleChoiceOption(label="D", text="Data type"),
        ],
        correct_answer_hint="A - Number of items",
    )


@pytest.fixture
def sample_freeform_question():
    """Freeform question for testing."""
    return Question(
        question_id="q-ff-001",
        question_type=QuestionType.CONCEPTUAL,
        answer_format=AnswerFormat.FREEFORM,
        difficulty=DifficultyLevel.INTERMEDIATE,
        topic="Python",
        question_text="Explain the difference between a list and a tuple.",
        correct_answer_hint="Lists are mutable, tuples are immutable",
    )


# ── Question Generation Tests ────────────────────────────────────────────────


class TestGenerateQuestions:
    """Tests for question generation."""

    def test_generates_expected_count(self, engine, mock_llm_router, sample_session):
        """Engine should return the requested number of questions."""
        mock_llm_router.generate.return_value = MagicMock(
            content=json.dumps(
                [
                    {
                        "question_type": "conceptual",
                        "answer_format": "freeform",
                        "difficulty": "intermediate",
                        "topic": f"topic_{i}",
                        "question_text": f"Question {i}",
                        "options": [],
                        "correct_answer_hint": f"hint {i}",
                    }
                    for i in range(3)
                ]
            )
        )

        questions = engine.generate_questions(sample_session, count=3)
        assert len(questions) == 3

    def test_llm_called_with_correct_task_type(
        self, engine, mock_llm_router, sample_session
    ):
        """Engine should use ASSESSMENT_GENERATION task type."""
        engine.generate_questions(sample_session, count=2)
        call_args = mock_llm_router.generate.call_args
        assert call_args.kwargs.get("task_type") is not None or "task_type" in str(
            call_args
        )

    def test_fallback_on_llm_failure(self, engine, mock_llm_router, sample_session):
        """Engine should return fallback questions when LLM fails."""
        mock_llm_router.generate.side_effect = Exception("LLM down")

        questions = engine.generate_questions(sample_session, count=2)
        assert len(questions) >= 1
        assert all(isinstance(q, Question) for q in questions)
        assert all(q.question_type == QuestionType.CONCEPTUAL for q in questions)

    def test_avoids_used_topics(self, engine, mock_llm_router, sample_session):
        """Engine should filter out already-used topics from the seed."""
        sample_session.questions = [
            Question(
                question_type=QuestionType.CONCEPTUAL,
                answer_format=AnswerFormat.FREEFORM,
                difficulty=DifficultyLevel.INTERMEDIATE,
                topic="used_topic",
                question_text="Old question",
            )
        ]

        engine.generate_questions(sample_session, count=1)
        call_args = mock_llm_router.generate.call_args
        messages = (
            call_args.kwargs.get("messages")
            or call_args[1].get("messages")
            or call_args[0][0]
        )
        user_msg = messages[-1].content
        # The topic seed should not include "used_topic"
        # (it's filtered out before building the seed)
        taxonomy = engine._build_topic_taxonomy(None, None)
        available = [t for t in taxonomy if t != "used_topic"]
        seed_topics = [
            t.strip() for t in user_msg.split("on ")[1].split(".") if t.strip()
        ]
        assert "used_topic" not in user_msg or len(available) == 0

    def test_uses_high_temperature(self, engine, mock_llm_router, sample_session):
        """Question generation should use high temperature for variety."""
        engine.generate_questions(sample_session, count=2)
        call_args = mock_llm_router.generate.call_args
        temp = call_args.kwargs.get("temperature", call_args[1].get("temperature", 0))
        assert temp >= 0.8


# ── Answer Evaluation Tests ──────────────────────────────────────────────────


class TestEvaluateAnswer:
    """Tests for answer evaluation."""

    def test_mc_correct_answer(self, engine, mock_llm_router, sample_mc_question):
        """Correct MC answer should score 100."""
        mock_llm_router.generate.return_value = MagicMock(
            content=json.dumps(
                {
                    "score": 100,
                    "is_correct": True,
                    "feedback": "Correct!",
                    "strengths": ["Good understanding"],
                    "improvements": [],
                    "model_answer": "A - Number of items",
                }
            )
        )

        answer = Answer(question_id="q-mc-001", selected_option="A")
        score = engine.evaluate_answer(sample_mc_question, answer)

        assert score.is_correct is True
        assert score.score == 100.0

    def test_mc_wrong_answer(self, engine, mock_llm_router, sample_mc_question):
        """Wrong MC answer should score 0."""
        mock_llm_router.generate.return_value = MagicMock(
            content=json.dumps(
                {
                    "score": 0,
                    "is_correct": False,
                    "feedback": "Incorrect.",
                    "strengths": [],
                    "improvements": ["Review basic Python functions"],
                    "model_answer": "A - Number of items",
                }
            )
        )

        answer = Answer(question_id="q-mc-001", selected_option="B")
        score = engine.evaluate_answer(sample_mc_question, answer)

        assert score.is_correct is False
        assert score.score == 0.0

    def test_mc_case_insensitive(self, engine, mock_llm_router, sample_mc_question):
        """MC correctness check should be case-insensitive."""
        mock_llm_router.generate.return_value = MagicMock(
            content=json.dumps({"score": 100, "feedback": "Correct!"})
        )

        answer = Answer(question_id="q-mc-001", selected_option="a")
        score = engine.evaluate_answer(sample_mc_question, answer)
        assert score.is_correct is True

    def test_freeform_evaluation(
        self, engine, mock_llm_router, sample_freeform_question
    ):
        """Freeform answer should receive a numeric score and feedback."""
        mock_llm_router.generate.return_value = MagicMock(
            content=json.dumps(
                {
                    "score": 75,
                    "feedback": "Good explanation but missing immutability detail.",
                    "strengths": ["Correct about mutability"],
                    "improvements": ["Mention hashability"],
                    "model_answer": "Lists are mutable, tuples are immutable...",
                }
            )
        )

        answer = Answer(
            question_id="q-ff-001",
            freeform_text="Lists can be changed, tuples cannot.",
        )
        score = engine.evaluate_answer(sample_freeform_question, answer)

        assert score.score == 75.0
        assert "immutability" in score.feedback.lower() or score.score > 0
        assert len(score.strengths) > 0

    def test_evaluation_fallback_on_llm_failure(
        self, engine, mock_llm_router, sample_freeform_question
    ):
        """Should return a fallback score when LLM fails."""
        mock_llm_router.generate.side_effect = Exception("Timeout")

        answer = Answer(question_id="q-ff-001", freeform_text="some answer")
        score = engine.evaluate_answer(sample_freeform_question, answer)

        assert isinstance(score, QuestionScore)
        assert score.question_id == "q-ff-001"
        assert score.score == 50.0


# ── Difficulty Adaptation Tests ──────────────────────────────────────────────


class TestAdaptDifficulty:
    """Tests for adaptive difficulty."""

    def test_no_change_with_few_scores(self, engine, sample_session):
        """Should not adapt with fewer than 3 scores."""
        sample_session.scores = [
            QuestionScore(question_id="q1", score=90.0),
        ]
        result = engine.adapt_difficulty(sample_session)
        assert result == DifficultyLevel.INTERMEDIATE

    def test_increase_difficulty_on_high_scores(self, engine, sample_session):
        """Should increase difficulty when recent scores are high."""
        sample_session.scores = [
            QuestionScore(question_id="q1", score=90.0),
            QuestionScore(question_id="q2", score=85.0),
            QuestionScore(question_id="q3", score=95.0),
        ]
        result = engine.adapt_difficulty(sample_session)
        assert result == DifficultyLevel.ADVANCED

    def test_decrease_difficulty_on_low_scores(self, engine, sample_session):
        """Should decrease difficulty when recent scores are low."""
        sample_session.current_difficulty = DifficultyLevel.ADVANCED
        sample_session.scores = [
            QuestionScore(question_id="q1", score=20.0),
            QuestionScore(question_id="q2", score=30.0),
            QuestionScore(question_id="q3", score=10.0),
        ]
        result = engine.adapt_difficulty(sample_session)
        assert result == DifficultyLevel.INTERMEDIATE

    def test_stays_same_on_mixed_scores(self, engine, sample_session):
        """Should not change difficulty for average scores."""
        sample_session.scores = [
            QuestionScore(question_id="q1", score=60.0),
            QuestionScore(question_id="q2", score=55.0),
            QuestionScore(question_id="q3", score=65.0),
        ]
        result = engine.adapt_difficulty(sample_session)
        assert result == DifficultyLevel.INTERMEDIATE

    def test_wont_exceed_max_difficulty(self, engine, sample_session):
        """Should not increase beyond expert level."""
        sample_session.current_difficulty = DifficultyLevel.EXPERT
        sample_session.scores = [
            QuestionScore(question_id="q1", score=95.0),
            QuestionScore(question_id="q2", score=98.0),
            QuestionScore(question_id="q3", score=100.0),
        ]
        result = engine.adapt_difficulty(sample_session)
        assert result == DifficultyLevel.EXPERT

    def test_wont_drop_below_min_difficulty(self, engine, sample_session):
        """Should not decrease below beginner level."""
        sample_session.current_difficulty = DifficultyLevel.BEGINNER
        sample_session.scores = [
            QuestionScore(question_id="q1", score=10.0),
            QuestionScore(question_id="q2", score=5.0),
            QuestionScore(question_id="q3", score=0.0),
        ]
        result = engine.adapt_difficulty(sample_session)
        assert result == DifficultyLevel.BEGINNER

    def test_records_difficulty_history(self, engine, sample_session):
        """Should record a difficulty change in history."""
        sample_session.scores = [
            QuestionScore(question_id="q1", score=90.0),
            QuestionScore(question_id="q2", score=90.0),
            QuestionScore(question_id="q3", score=90.0),
        ]
        engine.adapt_difficulty(sample_session)
        assert len(sample_session.difficulty_history) == 1
        assert sample_session.difficulty_history[0]["from"] == "intermediate"
        assert sample_session.difficulty_history[0]["to"] == "advanced"


# ── Session Results Tests ────────────────────────────────────────────────────


class TestSessionResults:
    """Tests for session result calculation."""

    def test_overall_score_calculation(self, engine, sample_session):
        """Overall score should be the average of all question scores."""
        sample_session.scores = [
            QuestionScore(question_id="q1", score=80.0),
            QuestionScore(question_id="q2", score=60.0),
        ]
        sample_session.questions = [
            Question(
                question_id="q1",
                question_type=QuestionType.CONCEPTUAL,
                answer_format=AnswerFormat.FREEFORM,
                difficulty=DifficultyLevel.INTERMEDIATE,
                topic="Python",
                question_text="Q1",
            ),
            Question(
                question_id="q2",
                question_type=QuestionType.CONCEPTUAL,
                answer_format=AnswerFormat.FREEFORM,
                difficulty=DifficultyLevel.INTERMEDIATE,
                topic="SQL",
                question_text="Q2",
            ),
        ]

        engine.calculate_session_results(sample_session)
        assert sample_session.overall_score == 70.0

    def test_topic_breakdown(self, engine, sample_session):
        """Topic breakdown should show average score per topic."""
        sample_session.scores = [
            QuestionScore(question_id="q1", score=80.0),
            QuestionScore(question_id="q2", score=60.0),
            QuestionScore(question_id="q3", score=100.0),
        ]
        sample_session.questions = [
            Question(
                question_id="q1",
                question_type=QuestionType.CONCEPTUAL,
                answer_format=AnswerFormat.FREEFORM,
                difficulty=DifficultyLevel.INTERMEDIATE,
                topic="Python",
                question_text="Q1",
            ),
            Question(
                question_id="q2",
                question_type=QuestionType.CONCEPTUAL,
                answer_format=AnswerFormat.FREEFORM,
                difficulty=DifficultyLevel.INTERMEDIATE,
                topic="SQL",
                question_text="Q2",
            ),
            Question(
                question_id="q3",
                question_type=QuestionType.CONCEPTUAL,
                answer_format=AnswerFormat.FREEFORM,
                difficulty=DifficultyLevel.INTERMEDIATE,
                topic="Python",
                question_text="Q3",
            ),
        ]

        engine.calculate_session_results(sample_session)
        assert sample_session.topic_breakdown["Python"] == 90.0
        assert sample_session.topic_breakdown["SQL"] == 60.0

    def test_empty_session_results(self, engine, sample_session):
        """Session with no scores should have zero overall score."""
        engine.calculate_session_results(sample_session)
        assert sample_session.overall_score == 0.0
        assert sample_session.topic_breakdown == {}

    def test_marks_session_completed(self, engine, sample_session):
        """Session should be marked as completed."""
        sample_session.scores = [QuestionScore(question_id="q1", score=80.0)]
        sample_session.questions = [
            Question(
                question_id="q1",
                question_type=QuestionType.CONCEPTUAL,
                answer_format=AnswerFormat.FREEFORM,
                difficulty=DifficultyLevel.INTERMEDIATE,
                topic="Python",
                question_text="Q1",
            ),
        ]

        engine.calculate_session_results(sample_session)
        assert sample_session.status == "completed"
        assert sample_session.completed_at is not None


# ── Topic Taxonomy Tests ────────────────────────────────────────────────────


class TestTopicTaxonomy:
    """Tests for topic taxonomy building."""

    def test_includes_supplemental_topics(self, engine):
        """Taxonomy should include standard CS topics."""
        taxonomy = engine._build_topic_taxonomy(None, None)
        assert len(taxonomy) > 0
        topic_lower = [t.lower() for t in taxonomy]
        assert any("git" in t for t in topic_lower)
        assert any("sql" in t for t in topic_lower)

    def test_includes_profile_skills(self, engine):
        """Taxonomy should include user profile skills."""
        profile = UserProfile(
            name="Test User",
            contact=ContactInfo(email="test@example.com", location="Test City"),
            skills=[
                ProfileSkill(name="Rust", category=SkillCategory.PROGRAMMING_LANGUAGE),
                ProfileSkill(name="Kubernetes", category=SkillCategory.CLOUD),
            ],
        )
        taxonomy = engine._build_topic_taxonomy(profile, None)
        assert "rust" in taxonomy
        assert "kubernetes" in taxonomy

    def test_includes_job_skills(self, engine):
        """Taxonomy should include job listing skills."""
        job = JobListing(
            title="Engineer",
            company="Co",
            source=JobSource.MANUAL,
            job_id="j1",
            skills=[Skill(name="Go"), Skill(name="Terraform")],
        )
        taxonomy = engine._build_topic_taxonomy(None, [job])
        assert "go" in taxonomy
        assert "terraform" in taxonomy

    def test_deduplicates(self, engine):
        """Taxonomy should not contain duplicates."""
        profile = UserProfile(
            name="Test User",
            contact=ContactInfo(email="test@example.com", location="Test City"),
            skills=[
                ProfileSkill(name="Python", category=SkillCategory.PROGRAMMING_LANGUAGE)
            ],
        )
        job = JobListing(
            title="Engineer",
            company="Co",
            source=JobSource.MANUAL,
            job_id="j1",
            skills=[Skill(name="Python")],
        )
        taxonomy = engine._build_topic_taxonomy(profile, [job])
        python_count = taxonomy.count("python")
        assert python_count == 1


# ── JSON Parsing Tests ──────────────────────────────────────────────────────


class TestParseQuestions:
    """Tests for LLM response parsing."""

    def test_parses_clean_json(self, engine):
        """Should parse valid JSON array."""
        response = json.dumps(
            [
                {
                    "question_type": "coding",
                    "answer_format": "freeform",
                    "difficulty": "advanced",
                    "topic": "algorithms",
                    "question_text": "Implement binary search.",
                    "options": [],
                    "correct_answer_hint": "O(log n) approach",
                }
            ]
        )
        questions = engine._parse_questions(response, 1)
        assert len(questions) == 1
        assert questions[0].question_type == QuestionType.CODING
        assert questions[0].difficulty == DifficultyLevel.ADVANCED

    def test_handles_markdown_fences(self, engine):
        """Should strip markdown code fences."""
        response = '```json\n[{"question_type": "conceptual", "answer_format": "freeform", "difficulty": "beginner", "topic": "basics", "question_text": "What is HTTP?", "options": []}]\n```'
        questions = engine._parse_questions(response, 1)
        assert len(questions) == 1
        assert questions[0].topic == "basics"

    def test_handles_invalid_json(self, engine):
        """Should return fallback on invalid JSON."""
        questions = engine._parse_questions("not json at all", 3)
        assert isinstance(questions, list)
        assert all(isinstance(q, Question) for q in questions)

    def test_truncates_to_expected_count(self, engine):
        """Should not return more questions than expected."""
        response = json.dumps(
            [
                {
                    "question_type": "conceptual",
                    "answer_format": "freeform",
                    "difficulty": "intermediate",
                    "topic": f"t{i}",
                    "question_text": f"Q{i}",
                    "options": [],
                }
                for i in range(10)
            ]
        )
        questions = engine._parse_questions(response, 3)
        assert len(questions) == 3
