"""
Job Raider - Assessment Models

Pydantic models for the technical assessment trainer feature.
Supports both job-targeted and skill-based practice modes with
dynamic LLM-generated questions and adaptive difficulty.

Author: Job Raider
Date: 2026-05-22
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class AssessmentMode(str, Enum):
    """Mode of assessment session."""
    JOB_TARGETED = "job_targeted"
    SKILL_BASED = "skill_based"


class QuestionType(str, Enum):
    """Type of assessment question."""
    CONCEPTUAL = "conceptual"
    SCENARIO = "scenario"
    CODING = "coding"
    SYSTEM_DESIGN = "system_design"


class AnswerFormat(str, Enum):
    """Format of the expected answer."""
    FREEFORM = "freeform"
    MULTIPLE_CHOICE = "multiple_choice"


class DifficultyLevel(str, Enum):
    """Difficulty level for questions."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class SessionStatus(str, Enum):
    """Status of an assessment session."""
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class MultipleChoiceOption(BaseModel):
    """A single option in a multiple-choice question.

    Attributes:
        label: Display label (e.g. "A", "B", "C", "D").
        text: The option text.
        is_correct: Whether this is the correct answer.
    """
    label: str
    text: str
    is_correct: bool = False


class Question(BaseModel):
    """A single assessment question.

    Attributes:
        question_id: Unique identifier for the question.
        question_type: Category of question (conceptual, coding, etc.).
        answer_format: Whether the answer is freeform or multiple-choice.
        difficulty: Difficulty level.
        topic: Topic area (e.g. "Python decorators", "REST API design").
        question_text: The actual question text.
        options: Multiple-choice options (empty for freeform questions).
        correct_answer_hint: Guidance for evaluation (not shown to user).
        time_limit_seconds: Optional time limit for the question.
        order_index: Display order within the session.
    """
    question_id: str = Field(default_factory=lambda: str(uuid4()))
    question_type: QuestionType
    answer_format: AnswerFormat
    difficulty: DifficultyLevel
    topic: str
    question_text: str
    options: List[MultipleChoiceOption] = Field(default_factory=list)
    correct_answer_hint: str = ""
    time_limit_seconds: Optional[int] = None
    order_index: int = 0


class Answer(BaseModel):
    """A user's answer to a question.

    Attributes:
        question_id: The question being answered.
        selected_option: Selected option label (for MC questions).
        freeform_text: Freeform text answer.
        answered_at: Timestamp when the answer was submitted.
        time_taken_seconds: Time spent on the question.
    """
    question_id: str
    selected_option: Optional[str] = None
    freeform_text: Optional[str] = None
    answered_at: datetime = Field(default_factory=datetime.now)
    time_taken_seconds: Optional[int] = None


class QuestionScore(BaseModel):
    """Score and feedback for a single question.

    Attributes:
        question_id: The question that was scored.
        score: Numeric score (0-100).
        is_correct: Whether the answer is correct (for MC questions).
        feedback: Written feedback on the answer.
        strengths: What the user did well.
        improvements: Areas for improvement.
        model_answer: The ideal answer for learning.
    """
    question_id: str
    score: float = Field(ge=0, le=100)
    is_correct: Optional[bool] = None
    feedback: str = ""
    strengths: List[str] = Field(default_factory=list)
    improvements: List[str] = Field(default_factory=list)
    model_answer: str = ""


class AssessmentSession(BaseModel):
    """A complete assessment session.

    Attributes:
        session_id: Unique session identifier.
        mode: Whether the session is job-targeted or skill-based.
        status: Current session status.
        difficulty: Starting difficulty level.
        target_job_ids: Job IDs for job-targeted mode.
        target_skills: Skills for skill-based mode.
        skill_categories: Skill categories to focus on.
        questions: Generated questions.
        answers: User-provided answers.
        scores: Score and feedback for each answered question.
        overall_score: Aggregate score across all questions.
        topic_breakdown: Average score per topic.
        current_difficulty: Adapted difficulty level.
        difficulty_history: Record of difficulty adjustments.
        created_at: Session creation timestamp.
        completed_at: Session completion timestamp.
        question_count: Total number of questions in the session.
        metadata: Additional session metadata.
    """
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    mode: AssessmentMode
    status: SessionStatus = SessionStatus.IN_PROGRESS
    difficulty: DifficultyLevel = DifficultyLevel.INTERMEDIATE

    target_job_ids: List[str] = Field(default_factory=list)
    target_skills: List[str] = Field(default_factory=list)
    skill_categories: List[str] = Field(default_factory=list)

    questions: List[Question] = Field(default_factory=list)
    answers: List[Answer] = Field(default_factory=list)
    scores: List[QuestionScore] = Field(default_factory=list)

    overall_score: Optional[float] = None
    topic_breakdown: Dict[str, float] = Field(default_factory=dict)

    current_difficulty: DifficultyLevel = DifficultyLevel.INTERMEDIATE
    difficulty_history: List[Dict[str, Any]] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    question_count: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)
