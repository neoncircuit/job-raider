"""
Job Raider - Assessment Engine

Core engine for the technical assessment trainer. Generates dynamic
questions via LLM, evaluates answers, and adapts difficulty based
on performance.

Questions are never reused -- each generation call uses a random nonce,
shuffled topic seed, and tracks previously used topics to ensure
freshness across sessions.

Author: Job Raider
Date: 2026-05-22
"""

import json
import random
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

import yaml

from ..llm.base import Message, MessageType
from ..llm.router import LLMRouter, TaskType
from ..models.assessment import (
    Answer,
    AnswerFormat,
    AssessmentSession,
    DifficultyLevel,
    MultipleChoiceOption,
    Question,
    QuestionScore,
    QuestionType,
)
from ..models.job_listing import JobListing
from ..models.user_profile import UserProfile
from ..utils.logger import get_logger, Components

# Standard CS/SE topics to supplement profile and job skills
_SUPPLEMENTAL_TOPICS = [
    "data structures and algorithms",
    "object-oriented programming",
    "database design and SQL",
    "REST API design",
    "software testing",
    "version control with Git",
    "design patterns",
    "system architecture",
    "cloud computing fundamentals",
    "networking basics",
    "security best practices",
    "agile methodologies",
    "code review practices",
    "debugging techniques",
    "performance optimization",
]

# Difficulty ordering for adaptation
_DIFFICULTY_ORDER = [
    DifficultyLevel.BEGINNER,
    DifficultyLevel.INTERMEDIATE,
    DifficultyLevel.ADVANCED,
    DifficultyLevel.EXPERT,
]


class AssessmentEngine:
    """Generates dynamic assessment questions and evaluates answers.

    Uses LLM to create fresh questions each time, with a random nonce
    and shuffled topic taxonomy to prevent predictability. Adapts
    difficulty based on cumulative performance.

    Args:
        llm_router: LLM router for model selection and fallback.
    """

    def __init__(self, llm_router: LLMRouter):
        """Initialize the assessment engine.

        Args:
            llm_router: LLM router for model selection.
        """
        self.llm_router = llm_router
        self.logger = get_logger(Components.GENERATION)
        self._load_templates()

    def _load_templates(self) -> None:
        """Load prompt templates from the YAML configuration."""
        config_path = (
            Path(__file__).parent.parent.parent / "config" / "prompt_templates.yaml"
        )
        with open(config_path, "r") as f:
            templates = yaml.safe_load(f)
        prompts = templates["prompts"]
        self._gen_template = prompts["assessment_generation"]
        self._eval_freeform_template = prompts["assessment_evaluation_freeform"]
        self._eval_mc_template = prompts["assessment_evaluation_mc"]

    def generate_questions(
        self,
        session: AssessmentSession,
        profile: Optional[UserProfile] = None,
        jobs: Optional[List[JobListing]] = None,
        count: int = 5,
    ) -> List[Question]:
        """Generate a batch of fresh assessment questions.

        Builds a topic taxonomy from profile skills, job requirements,
        and supplemental topics. Each call uses a random nonce and
        shuffled seed to ensure uniqueness.

        Args:
            session: The current assessment session.
            profile: Optional user profile for personalization.
            jobs: Optional job listings for job-targeted mode.
            count: Number of questions to generate.

        Returns:
            List of generated Question objects.
        """
        taxonomy = self._build_topic_taxonomy(profile, jobs)
        used_topics = {q.topic for q in session.questions}

        # Shuffle and pick topics, avoiding already-used ones
        random.shuffle(taxonomy)
        available_topics = [t for t in taxonomy if t not in used_topics]
        if not available_topics:
            available_topics = taxonomy  # reuse if exhausted

        topic_seed = ", ".join(available_topics[:10])
        session_nonce = str(uuid4())
        avoid_topics = ", ".join(used_topics) if used_topics else "none"

        # Determine question types and formats
        question_types = ", ".join([qt.value for qt in QuestionType])
        answer_formats = "mix of freeform and multiple_choice"

        # Build context
        context = self._build_context(session, profile, jobs)

        # Determine candidate level
        candidate_level = "fresh graduate"
        if profile and profile.experience:
            total_years = sum(
                (exp.end_date or datetime.now()).year - exp.start_date.year
                for exp in profile.experience
                if exp.start_date
            )
            if total_years > 5:
                candidate_level = "experienced professional"
            elif total_years > 2:
                candidate_level = "junior developer"

        # Fill template
        user_content = (
            self._gen_template["user"]
            .replace("{{session_nonce}}", session_nonce)
            .replace("{{topic_seed}}", topic_seed)
            .replace("{{candidate_level}}", candidate_level)
            .replace("{{difficulty}}", session.current_difficulty.value)
            .replace("{{question_types}}", question_types)
            .replace("{{answer_formats}}", answer_formats)
            .replace("{{count}}", str(count))
            .replace("{{avoid_topics}}", avoid_topics)
            .replace("{{context}}", context)
        )

        messages = [
            Message(role=MessageType.SYSTEM, content=self._gen_template["system"]),
            Message(role=MessageType.USER, content=user_content),
        ]

        try:
            response = self.llm_router.generate(
                messages=messages,
                task_type=TaskType.ASSESSMENT_GENERATION,
                temperature=0.9,
                max_tokens=3000,
            )

            questions = self._parse_questions(response.content, count)

            for i, q in enumerate(questions):
                q.order_index = len(session.questions) + i

            self.logger.info(
                "Generated %d assessment questions (nonce=%s)",
                len(questions),
                session_nonce[:8],
            )
            return questions

        except Exception as e:
            self.logger.error("Question generation failed: %s", e)
            return self._fallback_questions(session, count)

    def evaluate_answer(
        self,
        question: Question,
        answer: Answer,
    ) -> QuestionScore:
        """Evaluate a user's answer to a question.

        For multiple-choice: directly checks correctness, then uses LLM
        for explanation. For freeform: uses LLM to score and provide
        detailed feedback.

        Args:
            question: The question being answered.
            answer: The user's answer.

        Returns:
            QuestionScore with score, feedback, and model answer.
        """
        if question.answer_format == AnswerFormat.MULTIPLE_CHOICE:
            return self._evaluate_mc(question, answer)
        return self._evaluate_freeform(question, answer)

    def adapt_difficulty(self, session: AssessmentSession) -> DifficultyLevel:
        """Adjust difficulty based on recent performance.

        After every 3 answered questions, checks the average score.
        If average > 80, bumps difficulty up. If < 40, bumps down.

        Args:
            session: The current session with scores.

        Returns:
            The new difficulty level (may be unchanged).
        """
        recent_scores = session.scores[-3:]
        if len(recent_scores) < 3:
            return session.current_difficulty

        avg = sum(s.score for s in recent_scores) / len(recent_scores)
        current_idx = _DIFFICULTY_ORDER.index(session.current_difficulty)

        new_level = session.current_difficulty
        if avg > 80 and current_idx < len(_DIFFICULTY_ORDER) - 1:
            new_level = _DIFFICULTY_ORDER[current_idx + 1]
        elif avg < 40 and current_idx > 0:
            new_level = _DIFFICULTY_ORDER[current_idx - 1]

        if new_level != session.current_difficulty:
            session.difficulty_history.append(
                {
                    "from": session.current_difficulty.value,
                    "to": new_level.value,
                    "avg_score": avg,
                    "triggered_at": len(session.scores),
                }
            )
            self.logger.info(
                "Difficulty adapted: %s -> %s (avg=%.1f)",
                session.current_difficulty.value,
                new_level.value,
                avg,
            )

        return new_level

    def calculate_session_results(self, session: AssessmentSession) -> None:
        """Compute final results for a completed session.

        Calculates overall score as a simple average and breaks down
        scores by topic. Sets completed_at and status.

        Args:
            session: The session to finalize (modified in place).
        """
        if not session.scores:
            session.overall_score = 0.0
            session.topic_breakdown = {}
            session.completed_at = datetime.now()
            session.status = "completed"
            return

        session.overall_score = round(
            sum(s.score for s in session.scores) / len(session.scores), 1
        )

        # Group by topic
        topic_scores: Dict[str, List[float]] = {}
        for score in session.scores:
            question = next(
                (q for q in session.questions if q.question_id == score.question_id),
                None,
            )
            if question:
                topic_scores.setdefault(question.topic, []).append(score.score)

        session.topic_breakdown = {
            topic: round(sum(scores) / len(scores), 1)
            for topic, scores in topic_scores.items()
        }

        session.completed_at = datetime.now()
        session.status = "completed"

    def _build_topic_taxonomy(
        self,
        profile: Optional[UserProfile],
        jobs: Optional[List[JobListing]],
    ) -> List[str]:
        """Build a shuffled topic taxonomy from profile, jobs, and supplemental topics.

        Args:
            profile: User profile with skills.
            jobs: Job listings with required skills.

        Returns:
            Deduplicated, combined list of topic strings.
        """
        topics = set()

        if profile:
            for skill in profile.skills:
                topics.add(skill.name.lower())

        if jobs:
            for job in jobs:
                for skill in job.skills:
                    topics.add(skill.name.lower())
                for req in (job.requirements or []):
                    words = req.text.lower().split()
                    if len(words) <= 4:
                        topics.add(req.text.lower())

        for topic in _SUPPLEMENTAL_TOPICS:
            topics.add(topic)

        return list(topics)

    def _build_context(
        self,
        session: AssessmentSession,
        profile: Optional[UserProfile],
        jobs: Optional[List[JobListing]],
    ) -> str:
        """Build context string for question generation prompt.

        Args:
            session: Assessment session with mode and targets.
            profile: User profile.
            jobs: Job listings.

        Returns:
            Formatted context string.
        """
        parts = []

        if session.mode.value == "job_targeted" and jobs:
            for job in jobs:
                parts.append(f"Target Role: {job.title} at {job.company}")
                if job.description:
                    parts.append(f"Role Description: {job.description[:300]}")
                if job.skills:
                    skill_names = [s.name for s in job.skills[:10]]
                    parts.append(f"Required Skills: {', '.join(skill_names)}")
                parts.append("")
        elif session.target_skills:
            parts.append(f"Focus Skills: {', '.join(session.target_skills)}")

        if profile:
            if profile.skills:
                names = [s.name for s in profile.skills[:10]]
                parts.append(f"Candidate Skills: {', '.join(names)}")
            if profile.experience:
                parts.append(f"Experience: {len(profile.experience)} positions")
            if profile.education:
                for edu in profile.education:
                    parts.append(f"Education: {edu.degree} from {edu.school}")

        return "\n".join(parts) if parts else "General software engineering assessment"

    def _parse_questions(self, response_content: str, expected: int) -> List[Question]:
        """Parse LLM JSON response into Question objects.

        Args:
            response_content: Raw LLM response text.
            expected: Expected number of questions.

        Returns:
            List of parsed Question objects.
        """
        try:
            # Extract JSON from response (may have markdown fences)
            text = response_content.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()

            data = json.loads(text)
            if not isinstance(data, list):
                data = [data]

            questions = []
            for item in data[:expected]:
                options = []
                for opt in item.get("options", []):
                    options.append(
                        MultipleChoiceOption(
                            label=opt.get("label", ""),
                            text=opt.get("text", ""),
                            is_correct=opt.get("is_correct", False),
                        )
                    )

                questions.append(
                    Question(
                        question_type=QuestionType(
                            item.get("question_type", "conceptual")
                        ),
                        answer_format=AnswerFormat(
                            item.get("answer_format", "freeform")
                        ),
                        difficulty=DifficultyLevel(
                            item.get("difficulty", "intermediate")
                        ),
                        topic=item.get("topic", "general"),
                        question_text=item.get("question_text", ""),
                        options=options,
                        correct_answer_hint=item.get("correct_answer_hint", ""),
                        time_limit_seconds=item.get("time_limit_seconds"),
                    )
                )

            return questions

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            self.logger.error("Failed to parse question response: %s", e)
            return self._fallback_questions(
                AssessmentSession(mode="skill_based"), expected
            )

    def _evaluate_freeform(
        self, question: Question, answer: Answer
    ) -> QuestionScore:
        """Evaluate a freeform answer using LLM.

        Args:
            question: The question.
            answer: The user's freeform answer.

        Returns:
            QuestionScore with LLM-generated feedback.
        """
        user_content = (
            self._eval_freeform_template["user"]
            .replace("{{question_text}}", question.question_text)
            .replace("{{question_type}}", question.question_type.value)
            .replace("{{topic}}", question.topic)
            .replace("{{difficulty}}", question.difficulty.value)
            .replace("{{correct_answer_hint}}", question.correct_answer_hint)
            .replace("{{candidate_answer}}", answer.freeform_text or "(no answer)")
        )

        messages = [
            Message(
                role=MessageType.SYSTEM,
                content=self._eval_freeform_template["system"],
            ),
            Message(role=MessageType.USER, content=user_content),
        ]

        try:
            response = self.llm_router.generate(
                messages=messages,
                task_type=TaskType.ASSESSMENT_EVALUATION,
                temperature=0.3,
                max_tokens=1000,
            )
            return self._parse_score(response.content, question.question_id)
        except Exception as e:
            self.logger.error("Freeform evaluation failed: %s", e)
            return QuestionScore(
                question_id=question.question_id,
                score=50.0,
                feedback="Evaluation unavailable. Please try again.",
                model_answer=question.correct_answer_hint,
            )

    def _evaluate_mc(self, question: Question, answer: Answer) -> QuestionScore:
        """Evaluate a multiple-choice answer.

        Directly checks correctness, then uses LLM for explanation.

        Args:
            question: The question with options.
            answer: The user's selected option.

        Returns:
            QuestionScore with correctness and explanation.
        """
        correct_option = next(
            (o for o in question.options if o.is_correct), None
        )
        selected = answer.selected_option or ""
        is_correct = (
            correct_option is not None
            and correct_option.label.upper() == selected.upper()
        )

        options_text = "\n".join(
            f"  {o.label}: {o.text}" for o in question.options
        )
        correct_label = correct_option.label if correct_option else "?"

        user_content = (
            self._eval_mc_template["user"]
            .replace("{{question_text}}", question.question_text)
            .replace("{{topic}}", question.topic)
            .replace("{{options_text}}", options_text)
            .replace("{{selected_option}}", selected)
            .replace("{{correct_option}}", correct_label)
        )

        messages = [
            Message(
                role=MessageType.SYSTEM,
                content=self._eval_mc_template["system"],
            ),
            Message(role=MessageType.USER, content=user_content),
        ]

        try:
            response = self.llm_router.generate(
                messages=messages,
                task_type=TaskType.ASSESSMENT_EVALUATION,
                temperature=0.3,
                max_tokens=600,
            )
            score = self._parse_score(response.content, question.question_id)
            score.is_correct = is_correct
            score.score = 100.0 if is_correct else 0.0
            return score
        except Exception as e:
            self.logger.error("MC evaluation failed: %s", e)
            return QuestionScore(
                question_id=question.question_id,
                score=100.0 if is_correct else 0.0,
                is_correct=is_correct,
                feedback="Correct!" if is_correct else f"Incorrect. The answer was {correct_label}.",
                model_answer=correct_option.text if correct_option else "",
            )

    def _parse_score(self, response_content: str, question_id: str) -> QuestionScore:
        """Parse LLM evaluation response into a QuestionScore.

        Args:
            response_content: Raw LLM response.
            question_id: The question being scored.

        Returns:
            Parsed QuestionScore object.
        """
        try:
            text = response_content.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()

            data = json.loads(text)

            return QuestionScore(
                question_id=question_id,
                score=float(data.get("score", 50)),
                is_correct=data.get("is_correct"),
                feedback=data.get("feedback", ""),
                strengths=data.get("strengths", []),
                improvements=data.get("improvements", []),
                model_answer=data.get("model_answer", ""),
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            self.logger.error("Failed to parse score response: %s", e)
            return QuestionScore(
                question_id=question_id,
                score=50.0,
                feedback="Could not parse evaluation response.",
            )

    def _fallback_questions(
        self, session: AssessmentSession, count: int
    ) -> List[Question]:
        """Generate simple fallback questions when LLM fails.

        Args:
            session: Current session for context.
            count: Number of questions.

        Returns:
            List of basic conceptual questions.
        """
        topics = session.target_skills[:count] if session.target_skills else [
            "software engineering fundamentals"
        ]
        questions = []
        for i, topic in enumerate(topics):
            questions.append(
                Question(
                    question_type=QuestionType.CONCEPTUAL,
                    answer_format=AnswerFormat.FREEFORM,
                    difficulty=session.current_difficulty,
                    topic=topic,
                    question_text=(
                        f"Explain a key concept in {topic} that would be "
                        f"important for a {session.current_difficulty.value} "
                        f"level software engineer to understand."
                    ),
                    correct_answer_hint=f"Understanding of {topic} fundamentals",
                    order_index=len(session.questions) + i,
                )
            )
        return questions
