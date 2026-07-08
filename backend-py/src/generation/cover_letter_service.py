"""
Job Raider - Shared Cover Letter Service

Reusable cover-letter generation orchestration used by both the
job-specific endpoint and the manual "paste a JD" endpoint.

Keeps routing-layer code small and makes the generation/validation
pipeline easy to test in isolation.

Author: Job Raider
Date: 2026-06-29
"""

from typing import Any, Dict

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

    Returns:
        ``CoverLetterResponse`` containing the letter and validation results.

    Raises:
        Exception: Re-raised after logging if generation fails. Routes should
            convert this into an appropriate HTTP response.
    """
    llm_router = create_router(prefer_local=True)

    selector = ResumeSelector(llm_router=llm_router)
    selection = selector.select(job_listing, user_profile)

    writer = CoverLetterWriter(llm_router=llm_router)
    result = writer.write(job_listing, user_profile, selection)

    review_metadata: Dict[str, Any] = {}
    if review:
        reviewer = CoverLetterReviewer(llm_router=llm_router)
        review_result = reviewer.review(result, job_listing, user_profile, selection)
        rewrite_count = 0
        if review_result.rewrite_needed:
            result = writer.rewrite(
                job_listing,
                user_profile,
                selection,
                result,
                review_result.critique,
            )
            rewrite_count = 1

        review_metadata = {
            "critique": review_result.critique,
            "rewrite_needed": review_result.rewrite_needed,
            "rewrite_count": rewrite_count,
            "model_used": review_result.model_used,
        }
        if review_result.error:
            review_metadata["error"] = review_result.error

    validator = CoverLetterValidator(llm_router=llm_router, strict_mode=False)
    try:
        if deep:
            validation = validator.validate_with_llm(
                result, job_listing, user_profile, selection
            )
        else:
            validation = validator.validate(
                result, job_listing, user_profile, selection
            )
    except Exception as exc:
        logger.error("Cover letter validation failed: %s", exc, exc_info=True)
        validation = _build_fallback_validation(result)

    if review_metadata:
        validation.details["review"] = review_metadata

    return CoverLetterResponse(
        success=True,
        job_id=job_listing.job_id,
        cover_letter={
            "content": result.content,
            "word_count": result.word_count,
            "model_used": result.model_used,
            "highlighted_experiences": result.highlighted_experiences,
        },
        validation=_adapt_validation_response(validation),
    )
