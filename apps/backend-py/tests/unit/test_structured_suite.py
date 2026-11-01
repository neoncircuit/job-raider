"""Tests for the structured-output eval suite (Step 3.7, MH-2)."""

import json
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Dict, List

import pytest

import src.evaluation.suites.structured as structured_module
from src.evaluation.datasets import load_jsonl
from src.evaluation.suites import SUITE_NAMES, get_suite
from src.evaluation.suites.structured import (
    DEFAULT_DATASET_DIR,
    RecordingRouter,
    StructuredCase,
    check_references,
    classify_answer,
    fixed_resume,
    fixed_selection,
    load_suite_data,
    render_job_text,
    render_resume_text,
    run_structured_suite,
    skill_names,
)
from src.llm.base import LLMResponse
from src.llm.router import LLMRouter, TaskType
from src.llm.structured import OUTPUT_MODELS, CoverLetterReviewAnswer
from src.models.job_listing import JobListing

VALID: Dict[TaskType, Dict[str, Any]] = {
    TaskType.SELECTION: {
        "selected_projects": [{"name": "Ledger", "reason": "Payments work"}],
        "keywords_to_emphasize": ["Python"],
        "key_achievements": ["Cut batch time by half"],
        "summary_suggestion": "Backend engineer.",
    },
    TaskType.RESUME_WRITING: {
        "summary": "Backend engineer.",
        "skills": ["Python"],
        "experience": [
            {"title": "Engineer", "company": "Acme", "dates": "2024", "highlights": []}
        ],
        "projects": [
            {
                "name": "Ledger",
                "description": "A ledger.",
                "technologies": ["Python"],
                "highlights": [],
            }
        ],
        "education": [{"degree": "BSc", "school": "NUS", "year": "2025"}],
    },
    TaskType.VALIDATION: {
        "is_valid": True,
        "missing_projects": [],
        "missing_keywords": [],
        "fabricated_content": [],
        "date_inconsistencies": [],
        "overall_score": 80,
        "recommendation": "approve",
        "structure_score": 80,
        "content_score": 80,
        "tone_score": 80,
        "issues": [],
    },
    TaskType.RESUME_ANALYSIS: {
        "overall_score": 70,
        "summary": "Solid.",
        "key_strengths": ["Python"],
        "key_improvements": ["Metrics"],
        "resume_improvements": [],
        "skill_gaps": [],
        "next_steps": [],
    },
    TaskType.COVER_LETTER_REVIEW: {"critique": "Fine.", "rewrite_needed": False},
    TaskType.RESUME_PARSING: {
        "basics": {
            "name": "Mara Chen",
            "email": None,
            "phone": None,
            "location": "Singapore, Singapore",
            "linkedin": None,
            "github": None,
        },
        "summary": None,
        "skills": {
            "programming_languages": ["Python"],
            "frameworks": [],
            "tools": [],
            "databases": [],
            "cloud": [],
            "domains": [],
        },
        "experience": [],
        "projects": [],
        "education": [],
        "certifications": [],
        "target_job": {
            "keywords": ["Software Engineer"],
            "locations": ["Singapore"],
            "experience_levels": ["Entry Level"],
            "remote_preference": None,
            "industries": [],
        },
        "apprenticeship": None,
    },
    TaskType.JD_EXTRACTION: {
        "title": "Backend Engineer",
        "company": "Acme",
        "location": "Singapore",
        "requirements": [],
        "responsibilities": [],
        "skills": ["Python"],
        "experience_level": "Mid",
        "salary_range": None,
    },
    TaskType.CLASSIFICATION: {
        "industry": "Technology",
        "role_category": "Engineering",
        "company_size": "Unknown",
        "company_stage": None,
        "work_pace": "Unknown",
        "team_structure": "Unknown",
        "technical_skills": [],
        "soft_skills": [],
        "domain_skills": [],
        "experience_level_confidence": 0.5,
        "actual_experience_years": None,
        "management_level": None,
        "impact_scope": None,
        "classification_confidence": 0.5,
        "tags": [],
        "red_flags": [],
    },
}

CASES = load_jsonl(DEFAULT_DATASET_DIR / "cases.jsonl", StructuredCase)
SITE_COUNTS = Counter(case.site for case in CASES)


def make_router(
    monkeypatch: pytest.MonkeyPatch,
    answer: Callable[[TaskType], str],
    prompt_tokens: int = 50,
) -> LLMRouter:
    """
    Build a router whose ``generate`` returns a fixed answer per task type.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
        answer: Gives the answer text for a task type.
        prompt_tokens: The prompt token count of each answer.

    Returns:
        A router with the default routes and a fake ``generate``.
    """
    router = LLMRouter()

    def generate(
        messages: List[Any],
        task_type: TaskType = TaskType.GENERAL,
        model: Any = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Return the fixed answer of the task type.

        Args:
            messages: Not used.
            task_type: The task type.
            model: Not used.
            **kwargs: Not used.

        Returns:
            The answer.
        """
        return LLMResponse(
            content=answer(task_type),
            model=router.resolve_primary_model(task_type)[1],
            provider="ollama",
            prompt_tokens=prompt_tokens,
            completion_tokens=10,
        )

    monkeypatch.setattr(router, "generate", generate)
    return router


def run(router: LLMRouter, **kwargs: Any) -> Any:
    """
    Run the suite with fake probes.

    Args:
        router: The fake router.
        **kwargs: Other suite arguments.

    Returns:
        The report.
    """
    options: Dict[str, Any] = {
        "samples": 1,
        "unload": lambda router, model: None,
        "context_probe": lambda router, model: 4096,
        "vram_probe": lambda: 1000,
    }
    options.update(kwargs)
    return run_structured_suite(DEFAULT_DATASET_DIR, router=router, **options)


def test_committed_set_covers_each_site_with_existing_inputs() -> None:
    """Each of the 9 sites has at least 3 cases, and every input exists."""
    assert set(SITE_COUNTS) == set(OUTPUT_MODELS)
    assert min(SITE_COUNTS.values()) >= 3
    assert len({case.case_id for case in CASES}) == len(CASES)
    check_references(CASES, load_suite_data())


@pytest.mark.parametrize(
    "case",
    [
        {"case_id": "translation__x", "site": "translation", "grounding_case": "a"},
        {"case_id": "x__y", "site": "selection", "grounding_case": "a"},
        {"case_id": "selection__x", "site": "selection"},
        {"case_id": "resume_parsing__x", "site": "resume_parsing"},
        {
            "case_id": "jd_extraction__x",
            "site": "jd_extraction",
            "text_file": "a.txt",
            "grounding_case": "a",
        },
        {"case_id": "jd_extraction__x", "site": "jd_extraction"},
        {
            "case_id": "resume_analysis__x",
            "site": "resume_analysis",
            "mode": "general",
            "grounding_case": "a",
        },
        {
            "case_id": "resume_analysis__x",
            "site": "resume_analysis",
            "mode": "job_specific",
            "profile_id": "backend",
        },
    ],
)
def test_case_rules(case: Dict[str, Any]) -> None:
    """A case needs a known site, a matching ID, and the inputs of its site."""
    with pytest.raises(ValueError):
        StructuredCase.model_validate(case)


def test_check_references_finds_a_missing_input() -> None:
    """A case that names a missing grounding case is refused."""
    bad = StructuredCase(
        case_id="selection__x", site="selection", grounding_case="no__such_case"
    )

    with pytest.raises(ValueError, match="unknown grounding case"):
        check_references([bad], load_suite_data())


REVIEW = json.dumps(VALID[TaskType.COVER_LETTER_REVIEW])


@pytest.mark.parametrize(
    "content, expected",
    [
        (REVIEW, ("strict", None, False)),
        ("Sure: " + REVIEW + " Done.", ("rescued", "not_json", False)),
        ("I cannot help with that.", ("failed", "not_json", True)),
        ('Sure: {"critique": "x"} Done.', ("failed", "not_json", False)),
        ('{"critique": "x"}', ("failed", "schema", False)),
        ("Sure: {critique} Done.", ("failed", "not_json", True)),
        ("[" + REVIEW + "]", ("rescued", "not_object", False)),
    ],
)
def test_classify_answer(content: str, expected: tuple) -> None:
    """Strict, rescued, and failed answers, with the old parsing's result."""
    assert classify_answer(content, CoverLetterReviewAnswer) == expected


def test_valid_answers_are_strict_for_every_site(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Valid JSON answers give a strict rate of 1.0 at each site."""
    router = make_router(monkeypatch, lambda task: json.dumps(VALID[task]))

    report = run(router, samples=2)

    for site, count in SITE_COUNTS.items():
        assert report.metrics[f"calls.{site}"] == 2 * count
        assert report.metrics[f"strict_rate.{site}"] == 1.0
        assert report.metrics[f"failed_rate.{site}"] == 0.0
        assert report.metrics[f"no_call.{site}"] == 0.0
    assert report.metrics["calls"] == 2 * len(CASES)
    assert report.metrics["peak_vram_mib"] == 1000.0
    assert report.metrics["non_local_calls"] == 0.0
    assert report.metadata.case_count == len(CASES)
    assert all(row["content"] is None for row in report.details["rows"])


def test_text_around_the_json_is_rescued(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prose around a valid object counts as rescued, not strict."""
    router = make_router(
        monkeypatch, lambda task: "Here it is:\n" + json.dumps(VALID[task]) + "\nOK"
    )

    report = run(router)

    assert report.metrics["rescued_rate"] == 1.0
    assert report.metrics["strict_rate"] == 0.0
    assert report.metrics["legacy_no_json_rate"] == 0.0


def test_answers_without_json_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    """An answer without JSON fails, and the old parsing found nothing."""
    router = make_router(monkeypatch, lambda task: "I cannot help with that.")

    report = run(router)

    assert report.metrics["failed_rate"] == 1.0
    assert report.metrics["legacy_no_json_rate"] == 1.0
    sites = report.details["sites"]
    assert sites["selection"]["reasons"] == {"not_json": SITE_COUNTS["selection"]}
    failed = report.details["rows"][0]
    assert failed["content"] == "I cannot help with that."


def test_full_prompts_count_as_truncated(monkeypatch: pytest.MonkeyPatch) -> None:
    """A prompt at 98% of the context length or more counts as truncated."""
    router = make_router(
        monkeypatch, lambda task: json.dumps(VALID[task]), prompt_tokens=98
    )

    full = run(router, context_probe=lambda router, model: 100)
    roomy = run(router, context_probe=lambda router, model: 200)

    assert full.metrics["truncated"] == float(len(CASES))
    assert roomy.metrics["truncated"] == 0.0


def test_each_model_is_unloaded_once_after_its_cases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The suite runs the cases model by model and unloads each model once."""
    router = make_router(monkeypatch, lambda task: json.dumps(VALID[task]))
    unloaded: List[str] = []

    report = run(router, unload=lambda router, model: unloaded.append(model))

    models = [row["group_model"] for row in report.details["rows"]]
    assert unloaded == sorted(set(models))
    assert models == sorted(models)


def test_the_peak_vram_is_the_highest_reading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The report keeps the highest GPU memory reading of the run."""
    router = make_router(monkeypatch, lambda task: json.dumps(VALID[task]))
    readings = iter([700, 2500, 900] + [800] * len(CASES))

    report = run(router, vram_probe=lambda: next(readings))

    assert report.metrics["peak_vram_mib"] == 2500.0


def test_only_the_sites_task_type_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    """A call of another task type in the same case is not counted for the site."""
    router = make_router(monkeypatch, lambda task: "not JSON")
    real_run_case = structured_module.run_case

    def run_case_with_extra_call(case: Any, data: Any, recorder: Any) -> None:
        """
        Make one unrelated call, then run the case.

        Args:
            case: The case.
            data: The grounding data.
            recorder: The recording router.
        """
        recorder.generate([], task_type=TaskType.GENERAL)
        real_run_case(case, data, recorder)

    monkeypatch.setattr(structured_module, "run_case", run_case_with_extra_call)

    report = run(router)

    assert report.metrics["calls"] == float(len(CASES))


def test_run_refuses_a_missing_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A case that names a missing input stops the run before any call."""
    (tmp_path / "cases.jsonl").write_text(
        json.dumps(
            {
                "case_id": "selection__x",
                "site": "selection",
                "grounding_case": "no__such_case",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    router = make_router(monkeypatch, lambda task: REVIEW)

    with pytest.raises(ValueError, match="unknown grounding case"):
        run_structured_suite(tmp_path, router=router, samples=1)


def test_a_router_error_gives_no_call(monkeypatch: pytest.MonkeyPatch) -> None:
    """When no answer comes back, the case counts as no_call, not as a parse result."""

    def broken(task: TaskType) -> str:
        """
        Fail like an unreachable Ollama.

        Args:
            task: Not used.

        Raises:
            RuntimeError: Always.
        """
        raise RuntimeError("Ollama is not running")

    report = run(make_router(monkeypatch, broken))

    assert report.metrics["calls"] == 0.0
    assert report.metrics["no_call"] == float(len(CASES))
    assert report.metrics["strict_rate"] is None


def test_recording_router_records_and_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The recorder keeps each answer and gives the router's other attributes."""
    router = make_router(monkeypatch, lambda task: REVIEW)
    recorder = RecordingRouter(router)

    recorder.generate([], task_type=TaskType.COVER_LETTER_REVIEW)

    assert recorder.routes is router.routes
    assert recorder.calls[0].task_type == "cover_letter_review"
    assert recorder.calls[0].content == REVIEW
    assert recorder.calls[0].provider == "ollama"


def test_fixed_inputs_use_only_profile_facts() -> None:
    """The fixed selection, resume, and texts come from the grounding data."""
    data = load_suite_data()
    case = data.grounding["clean__ledger_hours"]
    profile = data.profiles[case.profile_id]
    job = JobListing.model_validate(case.job)

    selection = fixed_selection(profile, job)
    resume = fixed_resume(profile, selection)
    resume_text = render_resume_text(profile)

    profile_projects = {project.name for project in profile.projects}
    job_text = " ".join(
        [job.title, job.description or "", *(skill.name for skill in job.skills)]
    ).lower()
    assert 0 < len(selection.selected_projects) <= 3
    assert {p["name"] for p in selection.selected_projects} <= profile_projects
    assert set(selection.keywords_to_emphasize) <= set(skill_names(profile))
    assert all(k.lower() in job_text for k in selection.keywords_to_emphasize)
    assert {p["name"] for p in resume.projects} <= profile_projects
    assert profile.name in resume_text
    assert all(name in resume_text for name in profile_projects)
    assert job.title in render_job_text(job)


def test_the_suite_is_registered() -> None:
    """``main.py eval structured`` finds the suite and its default set."""
    runner, dataset = get_suite("structured")

    assert "structured" in SUITE_NAMES
    assert runner is run_structured_suite
    assert dataset == DEFAULT_DATASET_DIR
