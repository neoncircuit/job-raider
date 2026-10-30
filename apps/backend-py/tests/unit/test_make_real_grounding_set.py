"""Tests for the real-letter grounding set generator (Step 3.2 real letters, MH-A)."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

import pytest

from scripts import make_real_grounding_set as gen
from src.generation.selector import SelectionOutput
from src.models.job_listing import JobListing
from src.models.user_profile import UserProfile

LONG_TEXT = "We build payment services in Python and run them on PostgreSQL. " * 5


def shortlist_job(
    base: Dict[str, Any], job_id: str, company: str, description: str = LONG_TEXT
) -> Dict[str, Any]:
    """Build one shortlist item from the sample job.

    Args:
        base: The sample job as a JSON dict.
        job_id: The job ID.
        company: The company name.
        description: The job description.

    Returns:
        A shortlist item with a score field, as the Jobs page stores it.
    """
    return dict(
        base,
        job_id=job_id,
        company=company,
        description=description,
        relevance_score=72,
    )


def selection_for(job: JobListing) -> SelectionOutput:
    """Build a fixed selection for one job.

    Args:
        job: The job.

    Returns:
        A selection whose raw response is the job ID.
    """
    return SelectionOutput(
        selected_projects=[],
        keywords_to_emphasize=["Python"],
        key_achievements=[],
        summary_suggestion="",
        raw_response=job.job_id,
    )


class FakeApp:
    """Fake selector and writer that record the call order."""

    def __init__(self, empty_for: str = "") -> None:
        """Start with no calls.

        Args:
            empty_for: The job ID whose letter is empty.
        """
        self.calls: List[str] = []
        self.empty_for = empty_for

    def select(self, job: JobListing, profile: UserProfile) -> SelectionOutput:
        """Record a selection call.

        Args:
            job: The job.
            profile: The profile.

        Returns:
            A fixed selection for the job.
        """
        self.calls.append(f"select {job.job_id}")
        return selection_for(job)

    def write(
        self, job: JobListing, profile: UserProfile, selection: SelectionOutput
    ) -> str:
        """Record a letter call.

        Args:
            job: The job.
            profile: The profile.
            selection: The selection of the job.

        Returns:
            A letter with spaces at the ends, or only spaces for ``empty_for``.
        """
        self.calls.append(f"write {job.job_id}")
        if job.job_id == self.empty_for:
            return "   "
        return f"  Dear team, this letter is for {selection.raw_response}.  "

    def between(self) -> None:
        """Record the step between the selections and the letters."""
        self.calls.append("between")


def test_pick_jobs_takes_one_job_per_company_in_order(
    sample_job_listing: JobListing,
) -> None:
    """Jobs keep the shortlist order; a repeated company or a short text is skipped."""
    base = sample_job_listing.model_dump(mode="json")
    items = [
        shortlist_job(base, "j1", "Acme Pay"),
        shortlist_job(base, "j2", " acme  PAY "),
        shortlist_job(base, "j3", "Beta Labs", description="Short text."),
        "not a job",
        shortlist_job(base, "j4", "Gamma Data"),
        shortlist_job(base, "j5", "Delta Cloud"),
    ]

    assert [job.job_id for job in gen.pick_jobs(items, limit=3)] == ["j1", "j4", "j5"]
    assert [job.job_id for job in gen.pick_jobs(items, limit=2)] == ["j1", "j4"]


def test_make_records_selects_every_job_before_the_first_letter(
    sample_job_listing: JobListing, sample_user_profile: UserProfile
) -> None:
    """All selections run first, then the between step, then the letters."""
    jobs = [
        sample_job_listing.model_copy(update={"job_id": f"j{i}"}) for i in (1, 2, 3)
    ]
    app = FakeApp(empty_for="j2")

    records = gen.make_records(
        jobs, sample_user_profile, app.select, app.write, between=app.between
    )

    assert app.calls == [
        "select j1",
        "select j2",
        "select j3",
        "between",
        "write j1",
        "write j2",
        "write j3",
    ]
    assert [r["case_id"] for r in records] == ["real__01", "real__02"]
    assert [r["letter"] for r in records] == [
        "Dear team, this letter is for j1.",
        "Dear team, this letter is for j3.",
    ]


def test_records_hold_no_validator_output(
    sample_job_listing: JobListing, sample_user_profile: UserProfile
) -> None:
    """A record has only the case fields, and its job and selection load again."""
    app = FakeApp()
    records = gen.make_records(
        [sample_job_listing], sample_user_profile, app.select, app.write
    )

    record = json.loads(json.dumps(records[0]))
    assert set(record) == {"case_id", "profile_id", "job", "selection", "letter"}
    assert record["profile_id"] == "real"
    assert JobListing.model_validate(record["job"]).job_id == sample_job_listing.job_id
    assert SelectionOutput(**record["selection"]) == selection_for(sample_job_listing)


def test_write_dataset_writes_profiles_and_letters_only(
    tmp_path: Path, sample_job_listing: JobListing, sample_user_profile: UserProfile
) -> None:
    """The folder gets profiles.json and letters.jsonl, and is kept without force."""
    app = FakeApp()
    records = gen.make_records(
        [sample_job_listing], sample_user_profile, app.select, app.write
    )
    out = tmp_path / "grounding_real"

    path = gen.write_dataset(out, sample_user_profile, records)

    assert sorted(p.name for p in out.iterdir()) == ["letters.jsonl", "profiles.json"]
    lines = path.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["case_id"] for line in lines] == ["real__01"]
    profiles = json.loads((out / "profiles.json").read_text(encoding="utf-8"))
    assert UserProfile.model_validate(profiles["real"]).name == sample_user_profile.name
    with pytest.raises(FileExistsError):
        gen.write_dataset(out, sample_user_profile, records)
    gen.write_dataset(out, sample_user_profile, [], force=True)
    assert path.read_text(encoding="utf-8") == ""


def test_quiet_app_logs_hides_the_warnings_of_the_app() -> None:
    """After quiet_app_logs, an app logger shows errors only."""
    child = logging.getLogger("job_raider.generation")
    previous = gen.quiet_app_logs()
    try:
        assert not child.isEnabledFor(logging.WARNING)
        assert child.isEnabledFor(logging.ERROR)
    finally:
        for name, level in previous.items():
            logging.getLogger(name).setLevel(level)


def test_unload_models_unloads_each_loaded_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every model that /api/ps lists is unloaded."""

    class Response:
        """Fake /api/ps response."""

        def raise_for_status(self) -> None:
            """Accept the response."""

        def json(self) -> Dict[str, Any]:
            """Return two loaded models.

            Returns:
                The /api/ps body.
            """
            return {"models": [{"name": "qwen2.5:3b"}, {"name": "qwen2.5:7b"}]}

    unloaded: List[str] = []
    monkeypatch.setattr(gen.requests, "get", lambda url, timeout: Response())
    monkeypatch.setattr(gen, "unload_model", lambda url, name: unloaded.append(name))

    gen.unload_models("http://ollama.test")

    assert unloaded == ["qwen2.5:3b", "qwen2.5:7b"]


def test_main_stops_when_the_letters_exist(tmp_path: Path) -> None:
    """main does not replace letters.jsonl without --force."""
    out = tmp_path / "grounding_real"
    out.mkdir()
    (out / "letters.jsonl").write_text("keep\n", encoding="utf-8")

    code = gen.main(["--out", str(out), "--shortlist", str(tmp_path / "none.json")])

    assert code == 1
    assert (out / "letters.jsonl").read_text(encoding="utf-8") == "keep\n"


def test_main_stops_when_a_model_is_loaded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """main does not start while another model is on the GPU."""
    monkeypatch.setattr(gen, "loaded_models", lambda url: ["agent-model:9b"])
    out = tmp_path / "grounding_real"

    code = gen.main(["--out", str(out), "--shortlist", str(tmp_path / "none.json")])

    assert code == 1
    assert not out.exists()
