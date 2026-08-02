"""
Job Raider - Assessment API Routes

REST API endpoints for the technical assessment trainer.
Supports session lifecycle: create, generate questions, submit
answers, receive feedback, and track progress.

Author: Job Raider
Date: 2026-05-22
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...assessment.disc_engine import DISCEngine, DISCJobMatcher
from ...assessment.engine import AssessmentEngine
from ...assessment.storage import AssessmentStorage
from ...models.assessment import (
    Answer,
    AssessmentMode,
    AssessmentSession,
    DifficultyLevel,
    DISCAnswer,
    DISCResult,
)
from ...utils.logger import Components, get_logger

router = APIRouter()
logger = get_logger(Components.GENERATION)

# Shared storage instance
_storage = AssessmentStorage()


# ── Request Models ─────────────────────────────────────────────────────────────


class AssessmentStartRequest(BaseModel):
    """Request to start a new assessment session.

    Attributes:
        mode: Whether to target specific jobs or practice specific skills.
        target_job_ids: Job IDs for job_targeted mode.
        target_skills: Skill names for skill_based mode.
        difficulty: Starting difficulty level.
        question_count: Number of questions to generate.
    """

    mode: AssessmentMode = AssessmentMode.SKILL_BASED
    target_job_ids: List[str] = Field(default_factory=list)
    target_skills: List[str] = Field(default_factory=list)
    difficulty: DifficultyLevel = DifficultyLevel.INTERMEDIATE
    question_count: int = Field(default=5, ge=1, le=20)


class SubmitAnswerRequest(BaseModel):
    """Request to submit an answer to a question.

    Attributes:
        question_id: The question being answered.
        selected_option: Option label for MC questions.
        freeform_text: Text answer for freeform questions.
        time_taken_seconds: Time spent on the question.
    """

    question_id: str
    selected_option: Optional[str] = None
    freeform_text: Optional[str] = None
    time_taken_seconds: Optional[int] = None


class DISCStartRequest(BaseModel):
    """Request to start a DISC assessment session.

    Empty request - DISC assessments have fixed configuration.
    """

    pass


class DISCSubmitRequest(BaseModel):
    """Request to submit DISC assessment answers.

    Attributes:
        session_id: The assessment session identifier.
        answers: List of Most/Least answers for all 24 questions.
    """

    session_id: str
    answers: List[DISCAnswer]


# ── Helper Functions ───────────────────────────────────────────────────────────


def _session_to_response(session: AssessmentSession) -> Dict[str, Any]:
    """Convert a session to a safe API response (strips correct_answer_hint).

    Args:
        session: The assessment session.

    Returns:
        Dict suitable for JSON response.
    """
    data = session.model_dump(mode="json")

    # Strip correct_answer_hint from active sessions
    if session.status.value == "in_progress":
        for q in data.get("questions", []):
            q.pop("correct_answer_hint", None)

    return data


def _get_engine() -> AssessmentEngine:
    """Create an AssessmentEngine with a fresh LLM router.

    Returns:
        Configured AssessmentEngine instance.
    """
    from ...llm.router import create_router

    llm_router = create_router(prefer_local=True)
    return AssessmentEngine(llm_router=llm_router)


# ── Endpoints ──────────────────────────────────────────────────────────────────


@router.post("/")
async def start_session(request: AssessmentStartRequest):
    """Start a new assessment session with generated questions.

    Creates a session, generates an initial batch of questions based
    on the selected mode and targets, and returns the session state.

    Args:
        request: Session configuration.

    Returns:
        New assessment session with questions.
    """
    from ..routes.profile import active_profile_id, stored_profiles

    session = AssessmentSession(
        mode=request.mode,
        difficulty=request.difficulty,
        current_difficulty=request.difficulty,
        target_job_ids=request.target_job_ids,
        target_skills=request.target_skills,
        question_count=request.question_count,
    )

    # Load profile if available
    profile = None
    if active_profile_id and active_profile_id in stored_profiles:
        from ...models.user_profile import UserProfile

        profile_data = stored_profiles[active_profile_id].get("profile")
        if profile_data:
            try:
                profile = (
                    profile_data
                    if isinstance(profile_data, UserProfile)
                    else UserProfile(**profile_data)
                )
            except Exception:
                pass

    # Load jobs for job-targeted mode
    jobs = None
    if request.mode == AssessmentMode.JOB_TARGETED and request.target_job_ids:
        from ...models.job_listing import JobListing, JobSource

        jobs = []
        for job_id in request.target_job_ids:
            jobs.append(
                JobListing(
                    title="Software Engineer",
                    company="Unknown",
                    job_id=job_id,
                    source=JobSource.MANUAL,
                )
            )

    engine = _get_engine()
    questions = engine.generate_questions(
        session=session,
        profile=profile,
        jobs=jobs,
        count=request.question_count,
    )
    session.questions = questions

    _storage.save_session(session)

    return _session_to_response(session)


@router.get("/")
async def list_sessions():
    """List recent assessment sessions.

    Returns:
        List of session summaries (most recent first).
    """
    sessions = _storage.get_recent_sessions(limit=20)
    return [_session_to_response(s) for s in sessions]


@router.get("/progress")
async def get_progress():
    """Get aggregate progress statistics across all sessions.

    Returns:
        Progress stats including average score, trend, and topic strengths.
    """
    return _storage.get_progress_stats()


@router.get("/skills")
async def get_available_skills():
    """Get skills available for skill-based practice mode.

    Returns:
        List of skill names derived from the user profile.
    """
    from ..routes.profile import active_profile_id, stored_profiles

    skills = []
    if active_profile_id and active_profile_id in stored_profiles:
        profile_data = stored_profiles[active_profile_id].get("profile", {})
        if hasattr(profile_data, "model_dump"):
            # Stored as a UserProfile object; normalize to a dict.
            profile_data = profile_data.model_dump()
        for skill in profile_data.get("skills", []):
            if isinstance(skill, dict) and skill.get("name"):
                skills.append(skill["name"])

    # Add common technical skills if profile is sparse
    if len(skills) < 5:
        defaults = [
            "Python",
            "JavaScript",
            "SQL",
            "Git",
            "Docker",
            "REST APIs",
            "Data Structures",
            "Algorithms",
            "System Design",
            "Testing",
        ]
        for s in defaults:
            if s not in skills:
                skills.append(s)

    return {"skills": skills}


@router.get("/jobs")
async def get_available_jobs():
    """Get saved jobs available for job-targeted mode.

    Returns:
        List of saved jobs with ID, title, and company.
    """
    from ...metrics.outcome_tracker import OutcomeTracker

    tracker = OutcomeTracker()
    bookmarked = tracker.get_bookmarked_jobs()

    jobs = []
    for app in bookmarked:
        jobs.append(
            {
                "job_id": app.job_id,
                "title": app.job_title or "Unknown",
                "company": app.company or "Unknown",
            }
        )

    return {"jobs": jobs}


@router.get("/{session_id}")
async def get_session(session_id: str):
    """Get full session state including questions, answers, and scores.

    Args:
        session_id: The session identifier.

    Returns:
        Complete session data.
    """
    session = _storage.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return _session_to_response(session)


@router.post("/{session_id}/next")
async def generate_next_questions(session_id: str):
    """Generate the next batch of questions for an in-progress session.

    Adapts difficulty based on recent performance before generating.

    Args:
        session_id: The session identifier.

    Returns:
        Updated session with new questions.
    """
    session = _storage.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status.value != "in_progress":
        raise HTTPException(status_code=400, detail="Session is not in progress")

    engine = _get_engine()

    # Adapt difficulty
    new_difficulty = engine.adapt_difficulty(session)
    session.current_difficulty = new_difficulty

    questions = engine.generate_questions(session, count=session.question_count or 5)
    session.questions.extend(questions)

    _storage.save_session(session)
    return _session_to_response(session)


@router.post("/{session_id}/answer")
async def submit_answer(session_id: str, request: SubmitAnswerRequest):
    """Submit an answer and receive evaluation feedback.

    Evaluates the answer using the LLM, updates the session with
    the score and feedback, and returns the evaluation result.

    Args:
        session_id: The session identifier.
        request: The answer submission.

    Returns:
        QuestionScore with feedback and model answer.
    """
    session = _storage.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status.value != "in_progress":
        raise HTTPException(status_code=400, detail="Session is not in progress")

    # Find the question
    question = next(
        (q for q in session.questions if q.question_id == request.question_id),
        None,
    )
    if not question:
        raise HTTPException(status_code=404, detail="Question not found in session")

    # Check if already answered
    if any(a.question_id == request.question_id for a in session.answers):
        raise HTTPException(status_code=400, detail="Question already answered")

    answer = Answer(
        question_id=request.question_id,
        selected_option=request.selected_option,
        freeform_text=request.freeform_text,
        time_taken_seconds=request.time_taken_seconds,
    )

    engine = _get_engine()
    score = engine.evaluate_answer(question, answer)

    session.answers.append(answer)
    session.scores.append(score)

    # Check if all questions are answered
    if len(session.answers) >= len(session.questions):
        engine.calculate_session_results(session)

    _storage.save_session(session)

    return {
        "score": score.model_dump(mode="json"),
        "session_completed": session.status.value == "completed",
        "overall_score": session.overall_score,
    }


@router.post("/{session_id}/complete")
async def complete_session(session_id: str):
    """Mark a session as complete and calculate final results.

    Args:
        session_id: The session identifier.

    Returns:
        Completed session with final scores and topic breakdown.
    """
    session = _storage.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status.value != "in_progress":
        raise HTTPException(status_code=400, detail="Session is not in progress")

    engine = _get_engine()
    engine.calculate_session_results(session)

    _storage.save_session(session)
    return _session_to_response(session)


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    """Delete an assessment session.

    Args:
        session_id: The session to delete.

    Returns:
        Confirmation of deletion.
    """
    deleted = _storage.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"success": True, "message": "Session deleted"}


# ── DISC Assessment Endpoints ───────────────────────────────────────────────────


@router.post("/disc/start")
async def start_disc_session():
    """Start a new DISC workplace-style assessment session.

    Returns a new session with 24 questions in Most/Least format.

    Returns:
        Dictionary containing session_id and list of DISC questions.
    """
    engine = DISCEngine()
    session = engine.generate_session()
    return session


@router.post("/disc/submit")
async def submit_disc_answers(request: DISCSubmitRequest):
    """Submit all DISC assessment answers and receive results.

    Calculates trait scores, determines the D/I/S/C work-style profile, and
    returns heuristic job-type match recommendations.

    Args:
        request: DISC submission with session_id and answers.

    Returns:
        DISCResult with scores, profile, and job matches.
    """
    engine = DISCEngine()
    matcher = DISCJobMatcher()

    try:
        engine.validate_session_id(request.session_id)
        engine.validate_answers(request.answers)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Calculate scores
    scores = engine.calculate_scores(request.answers)

    # Determine profile type
    primary, secondary = engine.determine_profile_type(scores)

    # Calculate profile percentages
    profile = engine.calculate_profile_percentages(scores)

    # Get job matches
    job_matches = matcher.get_top_matches(profile, limit=5)

    # Create result
    result = DISCResult(
        session_id=request.session_id,
        answers=request.answers,
        scores=scores,
        profile=profile,
        primary_type=primary,
        secondary_type=secondary,
        completed_at=datetime.now(),
        job_matches=job_matches,
    )

    # Save result
    engine.save_result(result)

    return result.model_dump(mode="json")


@router.get("/disc/profile")
async def get_disc_profile():
    """Get the most recent DISC assessment result.

    Returns the latest completed DISC profile including scores,
    personality type, and job matches.

    Returns:
        DISCResult if found, 404 if no assessments completed.
    """
    engine = DISCEngine()
    result = engine.load_latest_result()

    if not result:
        raise HTTPException(
            status_code=404,
            detail="No DISC assessment found. Complete an assessment first.",
        )

    return result.model_dump(mode="json")
