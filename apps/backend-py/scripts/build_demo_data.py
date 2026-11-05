"""
Build the data of the public demo (Step 4).

The demo shows real output on synthetic input: this script runs the real
matcher, the hybrid ranker, the cover-letter service, and the API serializers
on the synthetic `fresh_ml` profile and the constructed jobs of the ranking
set. It writes JSON files for the frontend. Application records and metrics
are constructed sample data, because a demo has no real applications.

Every company gets an `Example` name, and the profile gets a sample name, so a
public page cannot look like a real employer or a real person. The ranking set
itself does not change.

The script needs `nomic-embed-text` and `qwen2.5:7b` in Ollama, and it loads
one model at a time. Close other GPU-heavy apps first. It runs by hand, not
in CI.

It must run on a clean clone. The app reads `data/` from the working folder,
and a clean clone has no such folder, so no personal data and no saved setting
can reach the output. The script stops when it finds files there. A run writes
files to `data/`, so each run needs a new clone.

Run it from `apps/backend-py` of a clean clone:

    python -m scripts.build_demo_data
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

import requests

from src.evaluation.run_metadata import BACKEND_DIR
from src.evaluation.suites import ranking
from src.models.job_listing import JobListing
from src.models.user_profile import UserProfile
from src.pipeline.shortlist import save_latest_shortlist
from src.rag.config import RAGConfig
from src.rag.ranker import RAGMatchScore
from src.scoring.matcher import JobMatcher

OUTPUT_DIR = BACKEND_DIR.parent / "frontend-ts" / "src" / "demo" / "seed"
PROFILE_ID = "fresh_ml"
WRITER_MODEL = "qwen2.5:7b"
OLLAMA_URL = "http://localhost:11434"
RUN_ID = "demo-run"
FIXED_TIME = "2026-11-04T12:00:00"
SAMPLE_NAME = "Sample Candidate"
SAMPLE_EMAIL = "sample.candidate@example.com"
SOURCE_NAME = "Rina Tan"
SOURCE_EMAIL = "rina.tan@example.com"
SAMPLE_RESUME = "sample-resume.pdf"

# Each constructed company gets a name that cannot be read as a real employer.
# Names that start with "Fictional" are clear already.
COMPANY_NAMES: Dict[str, str] = {
    "Brightloop Software": "Example Software",
    "Coralpoint Hotels": "Example Hotels",
    "Corvid Cloud": "Example Cloud",
    "Crestline Payments": "Example Payments",
    "Fleetbridge": "Example Fleet",
    "Harbourline Logistics": "Example Logistics",
    "Harrowgate Bank": "Example Bank",
    "Kestrel Insurance": "Example Insurance",
    "Lumen Analytics": "Example Analytics",
    "Meridian Capital": "Example Capital",
    "Northgate Institute for AI": "Example AI Institute",
    "Orchid Mobility": "Example Mobility",
    "Pinewave Media": "Example Media",
    "Seastar Retail Group": "Example Retail",
    "Tidepool Cloud": "Example Hosting",
    "Visiontrack Robotics": "Example Robotics",
    "Wordwise Labs": "Example Labs",
}

# Constructed sample: one status for each of the first shortlist jobs, with the
# days since the application.
SAMPLE_APPLICATIONS = (
    ("technical_scheduled", 14),
    ("screening_completed", 10),
    ("under_review", 6),
    ("applied", 2),
    ("rejected", 21),
)
SCREENED_STATUSES = frozenset({"technical_scheduled", "screening_completed"})
PIPELINE_STAGES = ("scrape", "deduplicate", "filter_scams", "score", "rag_rank")


def require_clean_clone(folder: Path) -> None:
    """
    Stop when the working folder has app data.

    Args:
        folder: The working folder.

    Raises:
        SystemExit: When a file exists under ``data/``.
    """
    data = folder / "data"
    if data.exists() and any(path.is_file() for path in data.rglob("*")):
        raise SystemExit(
            f"{data} has files. Run this script on a clean clone, so that no "
            "personal data and no saved setting can reach the demo."
        )


def rename_text(text: str) -> str:
    """
    Replace each constructed company name.

    Args:
        text: Any text.

    Returns:
        The text with the `Example` names.
    """
    for old, new in COMPANY_NAMES.items():
        text = text.replace(old, new)
    return text


def demo_jobs(jobs: Iterable[JobListing]) -> List[JobListing]:
    """
    Copy the jobs with the demo company names and a fixed time.

    Args:
        jobs: The jobs of the ranking set.

    Returns:
        New jobs. A fixed `scraped_at` keeps the output stable between runs.
    """
    result: List[JobListing] = []
    for job in jobs:
        data = json.loads(rename_text(job.model_dump_json()))
        data["scraped_at"] = FIXED_TIME
        result.append(JobListing.model_validate(data))
    return result


def demo_profile(profile: UserProfile) -> UserProfile:
    """
    Copy the profile with the sample name and the demo company names.

    Args:
        profile: The synthetic profile.

    Returns:
        A new profile.
    """
    text = rename_text(profile.model_dump_json())
    text = text.replace(SOURCE_NAME, SAMPLE_NAME).replace(SOURCE_EMAIL, SAMPLE_EMAIL)
    return UserProfile.model_validate(json.loads(text))


def rank_jobs(
    profile: UserProfile, jobs: Sequence[JobListing], mode: Dict[str, bool]
) -> List[RAGMatchScore]:
    """
    Rank the jobs as the pipeline does: the heuristic gate, then the hybrid ranker.

    Args:
        profile: The demo profile.
        jobs: The demo jobs.
        mode: The profile's matcher settings.

    Returns:
        The ranked jobs, best first.
    """
    matcher = JobMatcher(fresh_grad_mode=bool(mode.get("fresh_grad_mode", False)))
    scored = [(job, matcher.score_job(job, profile)) for job in jobs]
    passed = [item for item in scored if item[1].passed_threshold]
    config = RAGConfig.from_yaml(str(ranking.RAG_CONFIG_PATH))
    client = ranking.default_embedding_client(config)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
        ranker = ranking.rag_ranker(config, client, Path(folder))
        return ranker.re_rank(passed, profile)


def unload_model(model: str) -> None:
    """
    Unload a model from Ollama, so one model at a time is on the GPU.

    Args:
        model: The model name.
    """
    requests.post(
        f"{OLLAMA_URL}/api/generate",
        json={"model": model, "keep_alive": 0},
        timeout=60,
    )


def check_letter(payload: Dict[str, Any]) -> None:
    """
    Stop when the letter does not come from the local writer alone.

    Args:
        payload: The cover-letter response.

    Raises:
        ValueError: When another model wrote the letter, or when a web search
            for the company mission ran.
    """
    letter = payload["cover_letter"]
    used = (letter.get("provider_used"), letter.get("model_used"))
    if used != ("ollama", WRITER_MODEL):
        raise ValueError(f"expected ollama and {WRITER_MODEL}, got {used}")
    status = (payload.get("mission_context") or {}).get("status")
    if status != "disabled":
        raise ValueError(f"the company mission must be off, got {status}")


def letter_payload(job: JobListing, profile: UserProfile) -> Dict[str, Any]:
    """
    Write one letter with the real service, with the validator result.

    The letter stays as the service gives it, flags included: the demo must
    show the validator as it is.

    Args:
        job: The job.
        profile: The demo profile.

    Returns:
        The API response for a cover letter.
    """
    from src.generation.cover_letter_service import generate_cover_letter_sync

    response = generate_cover_letter_sync(job, profile, writer_model=WRITER_MODEL)
    payload = response.model_dump(mode="json")
    check_letter(payload)
    return payload


def profile_payload(profile: UserProfile) -> Dict[str, Any]:
    """
    Serialize the profile with the real route.

    The route module is imported here, not at the top of this file, because it
    reads `data/` on import, and `require_clean_clone` must run first.

    Args:
        profile: The demo profile.

    Returns:
        The API response of ``GET /profile``.
    """
    from src.api.routes import profile as route

    saved = (route.active_profile_id, route.stored_profiles)
    route.active_profile_id = "demo"
    route.stored_profiles = {
        "demo": {
            "profile": profile,
            "resume_path": SAMPLE_RESUME,
            "original_filename": SAMPLE_RESUME,
            "created_at": datetime.fromisoformat(FIXED_TIME),
            "updated_at": datetime.fromisoformat(FIXED_TIME),
        }
    }
    try:
        return asyncio.run(route.get_profile())
    finally:
        route.active_profile_id, route.stored_profiles = saved


def shortlist_payload(
    results: Sequence[RAGMatchScore], profile: UserProfile, jobs_scraped: int
) -> Dict[str, Any]:
    """
    Serialize the ranked jobs with the real shortlist code.

    Args:
        results: The ranked jobs.
        profile: The demo profile.
        jobs_scraped: The size of the job pool.

    Returns:
        The API response of ``GET /pipeline/shortlist/latest``.
    """
    with tempfile.TemporaryDirectory() as folder:
        path = save_latest_shortlist(
            run_id=RUN_ID,
            mode="discover",
            keywords=profile.targets.keywords,
            locations=profile.targets.locations,
            scored_listings=list(results),
            results_dir=folder,
            jobs_scraped=jobs_scraped,
        )
        payload = json.loads(path.read_text(encoding="utf-8"))
    payload["created_at"] = FIXED_TIME
    return payload


def applications_payload(shortlist: Dict[str, Any]) -> Dict[str, Any]:
    """
    Construct the sample application records from the first shortlist jobs.

    Args:
        shortlist: The shortlist response.

    Returns:
        The API response of ``GET /applications/dashboard``.
    """
    applications = [
        {
            "application_id": f"demo-{job['job_id']}",
            "job_title": job["title"],
            "company": job["company"],
            "applied_date": FIXED_TIME,
            "current_status": status,
            "custom_status": None,
            "is_bookmarked": False,
            "is_hidden": False,
            "days_since_application": days,
            "source_url": None,
            "listing_status": "active",
            "has_job_description": True,
            "previous_status": None,
            "application_method": "external",
        }
        for job, (status, days) in zip(shortlist["jobs"], SAMPLE_APPLICATIONS)
    ]
    return {
        "applications": applications,
        "summary": {
            "total_applications": len(applications),
            "bookmarked": 0,
            "hidden": 0,
            "external": len(applications),
            "expired": 0,
            "by_status": dict(Counter(row["current_status"] for row in applications)),
        },
        "custom_statuses": [],
        "filters_applied": {},
    }


def metrics_payload(
    applications: Dict[str, Any], letter: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Construct the sample metrics.

    The token counts are real, from the demo letter. The outcome rates come
    from the sample applications.

    Args:
        applications: The applications response.
        letter: The cover-letter response.

    Returns:
        The API response of ``GET /metrics/summary``.
    """
    usage = letter["cover_letter"].get("token_usage") or {}
    prompt_tokens = int(usage.get("prompt_tokens") or 0)
    completion_tokens = int(usage.get("completion_tokens") or 0)
    total_tokens = int(usage.get("total_tokens") or 0)
    rows = applications["applications"]
    screened = sum(row["current_status"] in SCREENED_STATUSES for row in rows)
    return {
        "cost": {
            "total_usd": 0.0,
            "per_application": 0.0,
            "total_calls": 1,
            "local_usage_percent": 100,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "estimated_counts": 0,
            "last_run": {
                "run_id": RUN_ID,
                "end_time": FIXED_TIME,
                "calls": 1,
                "total_tokens": total_tokens,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            },
        },
        "outcomes": {
            "total_applications": len(rows),
            "screening_rate": screened / len(rows),
            "offer_rate": 0.0,
            "acceptance_rate": 0.0,
        },
        "health": {"status": "healthy", "healthy": 4, "degraded": 0, "unhealthy": 0},
        "recent_calls": [
            {
                "task_type": "cover_letter_writing",
                "provider": "ollama",
                "model": WRITER_MODEL,
                "cost_usd": 0.0,
                "timestamp": FIXED_TIME,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            }
        ],
    }


def history_payload(shortlist: Dict[str, Any]) -> Dict[str, Any]:
    """
    Construct the sample run history: one discover run.

    Args:
        shortlist: The shortlist response.

    Returns:
        The API response of ``GET /pipeline/history``.
    """
    return {
        "runs": [
            {
                "run_id": RUN_ID,
                "status": "completed",
                "created_at": FIXED_TIME,
                "completed_at": FIXED_TIME,
                "jobs_scraped": shortlist["jobs_scraped"],
                "jobs_scored": shortlist["jobs_scraped"],
                "jobs_applied": 0,
                "mode": "discover",
                "stages_completed": list(PIPELINE_STAGES),
            }
        ],
        "total": 1,
    }


def derived_files(
    shortlist: Dict[str, Any], letter: Dict[str, Any]
) -> Dict[str, Dict[str, Any]]:
    """
    Build the files that follow from the shortlist and the letter.

    Args:
        shortlist: The shortlist response.
        letter: The cover-letter response.

    Returns:
        File stem to content.
    """
    applications = applications_payload(shortlist)
    return {
        "applications": applications,
        "metrics": metrics_payload(applications, letter),
        "history": history_payload(shortlist),
    }


def write_files(files: Dict[str, Dict[str, Any]], folder: Path) -> None:
    """
    Write each file as stable JSON.

    Args:
        files: File stem to content.
        folder: The output folder.
    """
    folder.mkdir(parents=True, exist_ok=True)
    for stem, content in files.items():
        text = json.dumps(content, indent=2, sort_keys=True, ensure_ascii=False)
        (folder / f"{stem}.json").write_text(text + "\n", encoding="utf-8")


def main() -> None:
    """Build every demo file."""
    require_clean_clone(Path.cwd())
    data = ranking.load_ranking_set()
    profile = demo_profile(data.profiles[PROFILE_ID])
    jobs = demo_jobs(data.jobs)
    profile_file = profile_payload(profile)  # Before any model loads.
    results = rank_jobs(profile, jobs, data.modes[PROFILE_ID])
    unload_model(RAGConfig.from_yaml(str(ranking.RAG_CONFIG_PATH)).embedding.model)
    letter = letter_payload(results[0].job, profile)
    unload_model(WRITER_MODEL)
    shortlist = shortlist_payload(results, profile, len(jobs))
    write_files(
        {
            "profile": profile_file,
            "shortlist": shortlist,
            "letter": letter,
            **derived_files(shortlist, letter),
        },
        OUTPUT_DIR,
    )


if __name__ == "__main__":
    main()
