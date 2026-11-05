"""Tests for the demo seed and its committed data (Step 4, MH-2)."""

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterator, List

import pytest

from scripts import build_demo_data as seed
from src.api.routes import profile as profile_route
from src.evaluation.suites import ranking
from src.generation.cover_letter_grounding import flag_unfilled_placeholders
from src.scoring.matcher import JobMatcher

FILES = ("applications", "history", "letter", "metrics", "profile", "shortlist")


def load(stem: str) -> Dict[str, Any]:
    """
    Load one committed data file.

    Args:
        stem: The file name without its extension.

    Returns:
        The parsed file.
    """
    return json.loads((seed.OUTPUT_DIR / f"{stem}.json").read_text(encoding="utf-8"))


def strings(value: Any) -> Iterator[str]:
    """
    Walk every string in a JSON value, keys included.

    Args:
        value: The parsed JSON value.

    Yields:
        Each string.
    """
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


def test_every_constructed_company_has_a_clear_demo_name() -> None:
    """A new company in the ranking set must get a demo name too."""
    names = {job.company for job in ranking.load_ranking_set().jobs}
    assert all(
        name in seed.COMPANY_NAMES or name.startswith("Fictional") for name in names
    )
    assert all(new.startswith("Example") for new in seed.COMPANY_NAMES.values())


def test_demo_jobs_lose_the_constructed_names_and_get_a_fixed_time() -> None:
    """Names go from every field, and the output is stable between runs."""
    jobs = seed.demo_jobs(ranking.load_ranking_set().jobs)
    text = " ".join(job.model_dump_json() for job in jobs)

    assert not [name for name in seed.COMPANY_NAMES if name in text]
    assert {job.scraped_at.isoformat() for job in jobs} == {seed.FIXED_TIME}


def test_demo_profile_has_the_sample_identity() -> None:
    """The profile has no name of the fixture and no constructed company."""
    source = ranking.load_ranking_set().profiles[seed.PROFILE_ID]
    profile = seed.demo_profile(source)
    text = profile.model_dump_json()

    assert (profile.name, profile.contact.email) == (
        seed.SAMPLE_NAME,
        seed.SAMPLE_EMAIL,
    )
    assert seed.SOURCE_NAME not in text and seed.SOURCE_EMAIL not in text
    assert not [name for name in seed.COMPANY_NAMES if name in text]


def test_the_script_stops_when_the_data_folder_has_a_file(tmp_path: Path) -> None:
    """A file under data/ could be personal data."""
    target = tmp_path / "data" / "profiles" / "store.json"
    target.parent.mkdir(parents=True)
    target.write_text("{}", encoding="utf-8")

    with pytest.raises(SystemExit, match="clean clone"):
        seed.require_clean_clone(tmp_path)


def test_the_script_runs_with_no_data_or_empty_folders(tmp_path: Path) -> None:
    """A clean clone has no data folder; the app makes empty folders on import."""
    seed.require_clean_clone(tmp_path)
    (tmp_path / "data" / "profiles").mkdir(parents=True)
    seed.require_clean_clone(tmp_path)


def letter_with(provider: Any, model: str, mission: str) -> Dict[str, Any]:
    """
    A small cover-letter response.

    Args:
        provider: The provider.
        model: The model.
        mission: The mission status.

    Returns:
        The response.
    """
    return {
        "cover_letter": {"provider_used": provider, "model_used": model},
        "mission_context": {"status": mission},
    }


def test_check_letter_accepts_the_local_writer() -> None:
    """The expected provider, model, and mission status pass."""
    seed.check_letter(letter_with("ollama", seed.WRITER_MODEL, "disabled"))


@pytest.mark.parametrize(
    "letter",
    [
        letter_with("anthropic", seed.WRITER_MODEL, "disabled"),
        letter_with(None, seed.WRITER_MODEL, "disabled"),
        letter_with("ollama", "other-model", "disabled"),
        letter_with("ollama", seed.WRITER_MODEL, "pass"),
    ],
)
def test_check_letter_refuses_any_other_source(letter: Dict[str, Any]) -> None:
    """A cloud letter or a web search must not reach the demo."""
    with pytest.raises(ValueError):
        seed.check_letter(letter)


def test_rank_jobs_uses_the_heuristic_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only the jobs that pass the gate reach the ranker, as in the pipeline."""
    data = ranking.load_ranking_set()
    profile = seed.demo_profile(data.profiles[seed.PROFILE_ID])
    jobs = seed.demo_jobs(data.jobs)
    seen: List[Any] = []

    class FakeRanker:
        """A ranker that records its input."""

        def re_rank(self, scored: List[Any], given: Any) -> List[Any]:
            """
            Record the scored jobs.

            Args:
                scored: The scored jobs.
                given: The profile.

            Returns:
                No jobs.
            """
            seen.extend(scored)
            return []

    monkeypatch.setattr(ranking, "default_embedding_client", lambda config: None)
    monkeypatch.setattr(ranking, "rag_ranker", lambda *args: FakeRanker())

    seed.rank_jobs(profile, jobs, data.modes[seed.PROFILE_ID])

    assert 0 < len(seen) < len(jobs)
    assert all(score.passed_threshold for _, score in seen)


def test_unload_model_asks_ollama_to_unload(monkeypatch: pytest.MonkeyPatch) -> None:
    """The script unloads each model, so one model is on the GPU."""
    calls: List[Dict[str, Any]] = []
    monkeypatch.setattr(
        seed.requests, "post", lambda url, json, timeout: calls.append(json)
    )

    seed.unload_model("a-model")

    assert calls == [{"model": "a-model", "keep_alive": 0}]


def test_profile_payload_does_not_change_the_route_state() -> None:
    """The real route serves the demo profile, and its state comes back."""
    source = ranking.load_ranking_set().profiles[seed.PROFILE_ID]
    before = (profile_route.active_profile_id, profile_route.stored_profiles)

    payload = seed.profile_payload(seed.demo_profile(source))

    assert payload["contact_info"]["name"] == seed.SAMPLE_NAME
    assert payload["created_at"] == seed.FIXED_TIME
    assert (profile_route.active_profile_id, profile_route.stored_profiles) == before


def test_write_files_gives_stable_json(tmp_path: Path) -> None:
    """Sorted keys and a final newline keep the diff small."""
    seed.write_files({"one": {"b": 1, "a": "é"}}, tmp_path / "out")

    text = (tmp_path / "out" / "one.json").read_text(encoding="utf-8")
    assert text == '{\n  "a": "é",\n  "b": 1\n}\n'


def test_each_file_is_committed() -> None:
    """The handlers of MH-3 read these files."""
    assert sorted(path.stem for path in seed.OUTPUT_DIR.glob("*.json")) == list(FILES)


def test_the_data_is_synthetic() -> None:
    """No constructed name, no other mail domain, and no web address."""
    text = " ".join(string for stem in FILES for string in strings(load(stem)))

    assert not [name for name in seed.COMPANY_NAMES if name in text]
    assert seed.SOURCE_NAME not in text
    assert set(re.findall(r"[\w.+-]+@([\w.-]+)", text)) == {"example.com"}
    assert not re.findall(r"https?://", text)


def test_the_shortlist_has_clear_fictional_companies() -> None:
    """A public page must not look like a real listing."""
    jobs = load("shortlist")["jobs"]

    assert len(jobs) >= 10
    assert all(job["job_id"].startswith("rk-") for job in jobs)
    assert all(job["company"].startswith(("Example", "Fictional")) for job in jobs)


def test_the_shortlist_is_best_first() -> None:
    """The order is the order of the ranker."""
    scores = [job["relevance_score"] for job in load("shortlist")["jobs"]]
    assert scores == sorted(scores, reverse=True)


def test_the_scores_are_real_matcher_output() -> None:
    """Each committed breakdown is what the matcher gives today.

    A failure here after a matcher change means: run the seed again.
    """
    data = ranking.load_ranking_set()
    profile = seed.demo_profile(data.profiles[seed.PROFILE_ID])
    jobs = {job.job_id: job for job in seed.demo_jobs(data.jobs)}
    matcher = JobMatcher(fresh_grad_mode=True)

    for row in load("shortlist")["jobs"]:
        score = matcher.score_job(jobs[row["job_id"]], profile)
        assert row["match_breakdown"] == score.breakdown, row["job_id"]
        # The matcher builds this list from a set, so its order changes.
        assert sorted(row["missing_skills"]) == sorted(score.missing_skills)


def test_the_letter_comes_from_the_local_writer_for_the_top_job() -> None:
    """The letter is for the first job, from the default writer."""
    letter = load("letter")
    top = load("shortlist")["jobs"][0]

    seed.check_letter(letter)
    assert letter["job_id"] == top["job_id"]
    assert top["company"] in letter["cover_letter"]["content"]
    assert flag_unfilled_placeholders(letter["cover_letter"]["content"]) == []


def test_the_constructed_files_follow_the_shortlist_and_the_letter() -> None:
    """Applications, metrics, and history stay in step with their sources."""
    expected = seed.derived_files(load("shortlist"), load("letter"))

    assert expected == {stem: load(stem) for stem in expected}


def test_the_sample_rates_come_from_the_applications() -> None:
    """Two of five sample applications reached screening."""
    metrics = load("metrics")
    summary = load("applications")["summary"]

    assert summary["total_applications"] == len(seed.SAMPLE_APPLICATIONS)
    assert metrics["outcomes"]["screening_rate"] == 0.4
    assert metrics["cost"]["total_tokens"] > 0
