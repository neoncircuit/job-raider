"""Run Phase C detector on real public application-form text."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND_ROOT))

from src.generation.cover_letter_instructions import (
    detect_application_instructions,
    count_length_units,
    length_within_spec,
)
from src.generation.cover_letter_writer import CoverLetterWriter
from src.models.job_listing import JobListing, JobSource
from unittest.mock import Mock

# Real Lever application form text (Epoch AI Expression of Interest, 2026).
# Source: https://jobs.lever.co/epoch-ai/137cb0dc-03a6-4747-b9dc-8255194daee2/apply
EPOCH_WHY_BLOCK = """
#### Why do you want to work at Epoch AI?

Minimum 50 words. All applications are reviewed by humans, so we're interested in your genuine response. Please do not use LLMs to draft or refine your answer.
"""

# Real Greenhouse application prompts (saas.group AI Operator).
# Source: https://job-boards.eu.greenhouse.io/saasgroup/jobs/4912804101
SAASGROUP_PROMPTS = """
Tell us about a time you got other people (not just yourself) to actually use AI, or a new way of doing things - how did you pull it off? (a few sentences)
Where do you think AI shouldn't run on its own - something you'd always want a human deciding, and why? (2-3 sentences)
Show us the most impressive thing you've built with AI - a link, a repo, a screenshot or a short video - plus a line on what it does and what it changed.
"""

# Real MCF catalog JD apply section (Ajentik Founding AI Engineer).
AJENTIK_APPLY = """
## About this role

As Founding AI Engineer at Ajentik, you'll own the intelligence layer of Elderwise end-to-end.

## How to apply

Send your CV and a short note — GitHub preferred — describing a production ML system you owned.
"""


def main() -> None:
    """
    Print detection results for real public / catalog application texts.

    Returns:
        None.
    """
    cases = {
        "epoch_ai_lever_eoi": EPOCH_WHY_BLOCK,
        "saasgroup_greenhouse": SAASGROUP_PROMPTS,
        "ajentik_mcf_apply_tail": AJENTIK_APPLY,
    }
    for name, text in cases.items():
        det = detect_application_instructions(text)
        print("=" * 72)
        print(name)
        print(json.dumps(det.to_dict(), indent=2))

    # Fallback short answer for Epoch (50 words) if detected.
    epoch = detect_application_instructions(EPOCH_WHY_BLOCK)
    if epoch.why_interest:
        job = JobListing(
            job_id="epoch-eoi-review",
            title="Expression of Interest",
            company="Epoch AI",
            source=JobSource.MANUAL,
            description=EPOCH_WHY_BLOCK,
        )
        writer = CoverLetterWriter(Mock())
        result = writer._fallback_why_interest(
            job,
            epoch.why_interest,
            mission_brief=(
                "Epoch AI researches the trajectory of artificial intelligence "
                "and publishes analysis for policymakers and researchers."
            ),
        )
        # Pad fallback to approach 50 words if needed for review visibility.
        print("--- EPOCH FALLBACK OUTPUT ---")
        print(result.content)
        print(
            "word_count=",
            count_length_units(result.content, "words"),
            "within=",
            length_within_spec(result.content, epoch.why_interest),
            "spec=",
            epoch.why_interest.to_dict(),
        )


if __name__ == "__main__":
    main()
