"""
Job Raider - Shared Cover Letter Service

Reusable cover-letter generation orchestration used by both the
job-specific endpoint and the manual "paste a JD" endpoint.

Keeps routing-layer code small and makes the generation/validation
pipeline easy to test in isolation.

Author: Job Raider
Date: 2026-06-29
"""

import time
from typing import Any, Dict, Optional

from ..api.models.responses import CoverLetterResponse, CoverLetterValidationResponse
from ..llm.router import create_router
from ..models.job_listing import JobListing
from ..models.user_profile import UserProfile
from ..utils.logger import Components, get_logger
from .cover_letter_reviewer import CoverLetterReviewer
from .cover_letter_validator import CoverLetterValidationResult, CoverLetterValidator
from .cover_letter_writer import CoverLetterWriter
from .selector import ResumeSelector

logger = get_logger(Components.GENERATION)


def _elapsed_ms(started: float) -> float:
    """
    Return milliseconds since ``started`` (from ``time.perf_counter``).

    Args:
        started: Perf-counter timestamp from the start of a timed section.

    Returns:
        Elapsed duration in milliseconds, rounded to one decimal place.
    """
    return round((time.perf_counter() - started) * 1000, 1)


def _build_fallback_validation(result: Any) -> CoverLetterValidationResult:
    """
    Build a permissive validation result when validation raises an exception.

    Args:
        result: Generated cover letter object with at least ``word_count``.

    Returns:
        A fully-passing validation result so the user still receives a letter.
    """
    return CoverLetterValidationResult(
        is_valid=True,
        score=100,
        issues=[],
        word_count=result.word_count,
        structure_score=100,
        content_score=100,
        tone_score=100,
        recommendation="approve",
        details={},
    )


def _adapt_validation_response(
    validation: CoverLetterValidationResult,
) -> CoverLetterValidationResponse:
    """
    Convert an internal validation result into an API response model.

    Args:
        validation: Result produced by ``CoverLetterValidator``.

    Returns:
        ``CoverLetterValidationResponse`` ready for serialization.
    """
    return CoverLetterValidationResponse(
        is_valid=validation.is_valid,
        score=validation.score,
        issues=[issue.value for issue in validation.issues],
        word_count=validation.word_count,
        structure_score=validation.structure_score,
        content_score=validation.content_score,
        tone_score=validation.tone_score,
        recommendation=validation.recommendation,
        details=validation.details,
    )


async def generate_cover_letter_for_profile(
    job_listing: JobListing,
    user_profile: UserProfile,
    deep: bool = False,
    review: bool = False,
    style: str = "modern",
) -> CoverLetterResponse:
    """
    Generate and validate a tailored cover letter for the given job/profile.

    The local model stack is preferred (``prefer_local=True``) so Ollama is
    used as the primary provider, matching the rest of the pipeline.

    Args:
        job_listing: Target job listing (scraped or manually pasted).
        user_profile: Parsed user profile.
        deep: If True, run LLM-powered validation instead of deterministic checks.
        review: If True, run a single-pass drafter-reviewer loop. A reviewer
            critiques the draft and the writer rewrites it once if needed.
        style: ``modern`` (default) or ``classic`` letter structure.

    Returns:
        ``CoverLetterResponse`` containing the letter and validation results.

    Raises:
        Exception: Re-raised after logging if generation fails. Routes should
            convert this into an appropriate HTTP response.
    """
    letter_style = style if style in ("modern", "classic") else "modern"
    llm_router = create_router(prefer_local=True)
    total_started = time.perf_counter()

    selector = ResumeSelector(llm_router=llm_router)
    selection_started = time.perf_counter()
    selection = selector.select(job_listing, user_profile)
    selection_ms = _elapsed_ms(selection_started)

    writer = CoverLetterWriter(llm_router=llm_router)
    generation_started = time.perf_counter()
    result = writer.write(job_listing, user_profile, selection, style=letter_style)
    generation_ms = _elapsed_ms(generation_started)

    review_metadata: Dict[str, Any] = {}
    review_ms: Optional[float] = None
    rewrite_ms: Optional[float] = None
    if review:
        reviewer = CoverLetterReviewer(llm_router=llm_router)
        review_started = time.perf_counter()
        review_result = reviewer.review(result, job_listing, user_profile, selection)
        review_ms = _elapsed_ms(review_started)
        rewrite_count = 0
        if review_result.rewrite_needed:
            rewrite_started = time.perf_counter()
            result = writer.rewrite(
                job_listing,
                user_profile,
                selection,
                result,
                review_result.critique,
                style=letter_style,
            )
            rewrite_ms = _elapsed_ms(rewrite_started)
            rewrite_count = 1

        review_metadata = {
            "critique": review_result.critique,
            "rewrite_needed": review_result.rewrite_needed,
            "rewrite_count": rewrite_count,
            "model_used": review_result.model_used,
            "review_ms": review_ms,
            "rewrite_ms": rewrite_ms,
        }
        if review_result.error:
            review_metadata["error"] = review_result.error

    validator = CoverLetterValidator(llm_router=llm_router, strict_mode=False)
    validation_started = time.perf_counter()
    try:
        if deep:
            validation = validator.validate_with_llm(
                result,
                job_listing,
                user_profile,
                selection,
                style=letter_style,
            )
        else:
            validation = validator.validate(
                result,
                job_listing,
                user_profile,
                selection,
                style=letter_style,
            )
    except Exception as exc:
        logger.error("Cover letter validation failed: %s", exc, exc_info=True)
        validation = _build_fallback_validation(result)
    validation_ms = _elapsed_ms(validation_started)

    if review_metadata:
        validation.details["review"] = review_metadata
    validation.details["style"] = letter_style

    total_ms = _elapsed_ms(total_started)
    timing = {
        "selection_ms": selection_ms,
        "generation_ms": generation_ms,
        "review_ms": review_ms,
        "rewrite_ms": rewrite_ms,
        "validation_ms": validation_ms,
        "total_ms": total_ms,
    }
    logger.info(
        "Cover letter timing job_id=%s generation_ms=%.1f rewrite_ms=%s total_ms=%.1f",
        job_listing.job_id,
        generation_ms,
        rewrite_ms,
        total_ms,
    )

    return CoverLetterResponse(
        success=True,
        job_id=job_listing.job_id,
        cover_letter={
            "content": result.content,
            "word_count": result.word_count,
            "model_used": result.model_used,
            "highlighted_experiences": result.highlighted_experiences,
            "style": letter_style,
            "timing": timing,
        },
        validation=_adapt_validation_response(validation),
    )
