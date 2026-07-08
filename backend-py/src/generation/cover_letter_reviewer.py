"""
Job Raider - Cover Letter Reviewer

Implements the reviewer half of a single-pass drafter-reviewer loop for
cover-letter generation. The reviewer reads a draft cover letter and
emits a concise critique plus a binary signal indicating whether the
draft should be rewritten.

The drafter-reviewer workflow was inspired by Mads Lorentzen's
ai-job-search project (https://github.com/MadsLorentzen/ai-job-search).
This implementation, including the prompts and orchestration logic, was
written independently for Job Raider.

Author: Job Raider
Date: 2026-07-08
"""

import json
import re
from dataclasses import dataclass
from typing import Optional

from ..llm.base import Message, MessageType
from ..llm.router import LLMRouter, TaskType
from ..models.job_listing import JobListing
from ..models.user_profile import UserProfile
from ..utils.logger import Components, get_logger
from .cover_letter_writer import GeneratedCoverLetter
from .selector import SelectionOutput

logger = get_logger(Components.GENERATION)


@dataclass
class CoverLetterReviewResult:
    """Result of reviewing a cover letter draft."""

    critique: str
    rewrite_needed: bool
    model_used: str
    error: Optional[str] = None


class CoverLetterReviewer:
    """
    Critique a cover letter draft and decide whether to rewrite it.

    Uses a cheap, fast local model. On any failure it returns a result
    with ``rewrite_needed=False`` so generation can continue with the
    original draft.
    """

    def __init__(self, llm_router: LLMRouter):
        """
        Initialize the reviewer.

        Args:
            llm_router: LLM router for model selection.
        """
        self.llm_router = llm_router
        self.logger = get_logger(Components.GENERATION)

    def review(
        self,
        cover_letter: GeneratedCoverLetter,
        job: JobListing,
        profile: UserProfile,
        selection: SelectionOutput,
    ) -> CoverLetterReviewResult:
        """
        Review a generated cover letter draft.

        Args:
            cover_letter: The draft cover letter.
            job: Target job listing.
            profile: Candidate profile.
            selection: Selection output used to draft the letter.

        Returns:
            ``CoverLetterReviewResult`` with critique and rewrite guidance.
        """
        messages = [
            Message(
                role=MessageType.SYSTEM,
                content=(
                    "You are a sharp, concise cover letter editor. Read the "
                    "draft cover letter and decide whether it needs a rewrite."
                    "\n\n"
                    "Return ONLY JSON with this exact shape:\n"
                    '{"critique": "brief actionable feedback", '
                    '"rewrite_needed": true/false}\n\n'
                    "Set rewrite_needed=true only if the draft has clear "
                    "problems (missing role/company, wrong tone, generic "
                    "opening, factual gaps, no call to action)."
                ),
            ),
            Message(
                role=MessageType.USER,
                content=(
                    f"Job: {job.title} at {job.company}\n"
                    f"Keywords to emphasize: "
                    f"{', '.join(selection.keywords_to_emphasize)}\n"
                    f"Selected projects: "
                    f"{', '.join(p['name'] for p in selection.selected_projects)}\n\n"
                    f"DRAFT COVER LETTER:\n{cover_letter.content}"
                ),
            ),
        ]

        try:
            response = self.llm_router.generate(
                messages=messages,
                task_type=TaskType.COVER_LETTER_REVIEW,
                temperature=0.3,
                max_tokens=400,
            )

            content = response.content
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if not json_match:
                raise ValueError("Failed to extract JSON from review response")

            data = json.loads(json_match.group(0))
            critique = str(data.get("critique", "")).strip()
            rewrite_needed = bool(data.get("rewrite_needed", False))

            model_used = self.llm_router.routes[
                TaskType.COVER_LETTER_REVIEW
            ].primary_model

            self.logger.info(
                "Cover letter reviewed: rewrite_needed=%s, model=%s",
                rewrite_needed,
                model_used,
            )

            return CoverLetterReviewResult(
                critique=critique,
                rewrite_needed=rewrite_needed,
                model_used=model_used,
            )

        except Exception as exc:
            self.logger.error("Cover letter review failed: %s", exc, exc_info=True)
            return CoverLetterReviewResult(
                critique="Review unavailable.",
                rewrite_needed=False,
                model_used="error",
                error="Review unavailable",
            )
