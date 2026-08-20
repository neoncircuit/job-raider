"""One-shot Phase C review-gate script (fixture JD, fallback writer)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import Mock

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from src.generation.cover_letter_instructions import (  # noqa: E402
    count_length_units,
    detect_application_instructions,
    inclusion_present_in_text,
    length_within_spec,
    resolve_inclusion_urls,
)
from src.generation.cover_letter_writer import CoverLetterWriter  # noqa: E402
from src.generation.selector import SelectionOutput  # noqa: E402
from src.models.job_listing import JobListing, JobSource  # noqa: E402
from src.models.user_profile import ContactInfo, UserProfile  # noqa: E402


def main() -> None:
    """
    Run detection + fallback short answer on a realistic fixture JD.

    Returns:
        None. Prints review artifacts to stdout.
    """
    jd = (
        "Acme Document Intelligence is hiring a Software Engineer in Singapore. "
        "Please send your CV plus 3-4 lines on why this mission excites you. "
        "Also include a link to your GitHub. "
        "You will build document intelligence features for enterprise customers."
    )
    detected = detect_application_instructions(jd)
    print("DETECT why_interest:", detected.why_interest)
    print("DETECT inclusions:", [i.to_dict() for i in detected.inclusions])

    urls = resolve_inclusion_urls(
        detected.inclusions,
        github="https://github.com/example-user",
    )
    print("URLS:", urls)

    job = JobListing(
        job_id="review-phase-c",
        title="Software Engineer",
        company="Acme Document Intelligence",
        source=JobSource.MANUAL,
        description=jd,
        location="Singapore",
    )
    profile = UserProfile(
        name="Review Candidate",
        contact=ContactInfo(
            email="review@example.com",
            location="Singapore",
            github="https://github.com/example-user",
        ),
        summary="Software engineer",
    )
    _ = profile  # profile available for future LLM review runs
    selection = SelectionOutput(
        selected_projects=[],
        keywords_to_emphasize=[],
        key_achievements=[],
        summary_suggestion="",
        raw_response="",
    )
    _ = selection
    assert detected.why_interest is not None
    writer = CoverLetterWriter(Mock())
    result = writer._fallback_why_interest(
        job,
        detected.why_interest,
        mission_brief=(
            "Acme focuses on document intelligence for enterprises in Singapore."
        ),
        inclusion_urls=urls,
    )
    print("--- SHORT ANSWER OUTPUT ---")
    print(result.content)
    print("--- METRICS ---")
    count = count_length_units(result.content, detected.why_interest.unit)
    print(
        "count:",
        count,
        "within:",
        length_within_spec(result.content, detected.why_interest),
    )
    print(
        "github present:",
        inclusion_present_in_text(result.content, urls["github"] or ""),
    )


if __name__ == "__main__":
    main()
