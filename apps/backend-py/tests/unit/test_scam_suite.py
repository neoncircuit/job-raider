"""
Tests for the scam and EMSCAD evaluation suites (Step 3.3 Stage A).

Each test writes a small dataset under ``tmp_path``. The tests do not read
the committed scam set or the local EMSCAD CSV.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Sequence, Tuple

import pytest

from src.evaluation.report import EvalReport
from src.evaluation.run_metadata import build_run_metadata
from src.evaluation.suites import SUITE_NAMES, get_suite
from src.evaluation.suites.emscad import (
    EMSCAD_CSV_NAME,
    EMSCAD_SPLIT_SEED,
    load_emscad,
    run_emscad_suite,
    split_emscad,
)
from src.evaluation.suites.scam import run_scam_suite
from src.models.job_listing import ExperienceLevel, JobListing, JobType
from src.scoring.scam_detector import JobScamDetector


class _FakeDetector:
    """Detector stand-in with a fixed report per job_id."""

    def __init__(
        self,
        threshold: float = 0.7,
        mapping: Dict[str, Tuple[bool, float, List[str]]] | None = None,
    ) -> None:
        """
        Store the threshold and the per-job reports.

        Args:
            threshold: Unused production threshold, kept for call shape.
            mapping: ``job_id`` to ``(is_scam, confidence, reasons)``.
        """
        self.threshold = threshold
        self.mapping = mapping or {}

    def detect(self, job: JobListing) -> SimpleNamespace:
        """
        Return the scripted report for ``job.job_id``.

        Args:
            job: Listing under test.

        Returns:
            A report-shaped namespace.
        """
        is_scam, confidence, reasons = self.mapping.get(job.job_id, (False, 0.0, []))
        return SimpleNamespace(
            is_scam=is_scam,
            confidence=confidence,
            reasons=reasons,
            indicators=[],
            risk_score=int(confidence * 100),
        )


def _job(
    job_id: str,
    *,
    title: str = "Clerk",
    company: str = "Example Co",
    description: str = "Ordinary office work on weekdays.",
    **extra: Any,
) -> Dict[str, Any]:
    """
    Build a ``JobListing`` dict for a temporary case.

    Args:
        job_id: Listing identifier.
        title: Job title.
        company: Company name.
        description: Posting text.
        **extra: Other ``JobListing`` fields.

    Returns:
        A dict that ``JobListing`` accepts.
    """
    payload: Dict[str, Any] = {
        "title": title,
        "company": company,
        "job_id": job_id,
        "source": "manual",
        "description": description,
    }
    payload.update(extra)
    return payload


def _write_cases(folder: Path, rows: Sequence[Dict[str, Any]]) -> Path:
    """
    Write ``cases.jsonl`` under ``folder``.

    Args:
        folder: Dataset directory.
        rows: Case objects.

    Returns:
        Path of the JSONL file.
    """
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "cases.jsonl"
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )
    return path


def _patch_detector(
    monkeypatch: pytest.MonkeyPatch,
    mapping: Dict[str, Tuple[bool, float, List[str]]],
) -> None:
    """
    Replace ``JobScamDetector`` in the scam suite with a fake.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        mapping: Scripted reports by job_id.

    Returns:
        None.
    """
    fake = _FakeDetector(mapping=mapping)
    monkeypatch.setattr(
        "src.evaluation.suites.scam.JobScamDetector",
        lambda threshold=0.7: fake,
    )


class TestScamSuite:
    """Pipeline decision, metrics, per-group recall, and the sweep."""

    def test_quick_filter_hit_is_scam_when_detector_is_low(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        A ``ScamFilter`` hit is a scam even when detector confidence is low.

        Args:
            tmp_path: Temporary dataset folder.
            monkeypatch: Detector replacement.
        """
        dataset = tmp_path / "scam"
        _write_cases(
            dataset,
            [
                {
                    "case_id": "scam_payment__wire_fee",
                    "job": _job(
                        "wire-1",
                        description="Send a wire transfer before the first day.",
                    ),
                    "expected": "scam",
                    "indicator_groups": ["payment"],
                    "source": "written",
                    "note": "Fee by wire.",
                }
            ],
        )
        _patch_detector(
            monkeypatch, {"wire-1": (False, 0.05, ["mocked low confidence"])}
        )

        report = run_scam_suite(dataset)

        row = report.details["cases"][0]
        assert row["predicted"] == "scam"
        assert row["quick_filter"] is True
        assert row["detector_confidence"] == pytest.approx(0.05)
        assert report.metrics["recall"] == pytest.approx(1.0)

    def test_metrics_on_a_known_small_set(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Precision, recall, F1, and the false-positive rate match hand counts.

        Args:
            tmp_path: Temporary dataset folder.
            monkeypatch: Detector replacement.
        """
        dataset = tmp_path / "scam"
        _write_cases(
            dataset,
            [
                {
                    "case_id": "scam_payment__tp",
                    "job": _job("tp", description="Pay a kit fee to begin."),
                    "expected": "scam",
                    "indicator_groups": ["payment"],
                    "source": "written",
                    "note": "True positive.",
                },
                {
                    "case_id": "scam_contact__fn",
                    "job": _job("fn", description="Message only on a private app."),
                    "expected": "scam",
                    "indicator_groups": ["contact"],
                    "source": "written",
                    "note": "False negative.",
                },
                {
                    "case_id": "legit_written__fp",
                    "job": _job("fp", description="Keep the shop ledger current."),
                    "expected": "legit",
                    "indicator_groups": [],
                    "source": "written",
                    "note": "False positive.",
                },
                {
                    "case_id": "legit_written__tn",
                    "job": _job("tn", description="Catalog the new accession boxes."),
                    "expected": "legit",
                    "indicator_groups": [],
                    "source": "written",
                    "note": "True negative.",
                },
            ],
        )
        _patch_detector(
            monkeypatch,
            {
                "tp": (True, 0.9, ["payment"]),
                "fn": (False, 0.1, []),
                "fp": (True, 0.8, ["flagged"]),
                "tn": (False, 0.1, []),
            },
        )

        report = run_scam_suite(dataset)

        assert report.metrics["precision"] == pytest.approx(0.5)
        assert report.metrics["recall"] == pytest.approx(0.5)
        assert report.metrics["f1"] == pytest.approx(0.5)
        assert report.metrics["false_positive_rate"] == pytest.approx(0.5)
        counts = report.details["confusion"]
        assert counts == {
            "true_positives": 1,
            "false_positives": 1,
            "false_negatives": 1,
            "true_negatives": 1,
        }

    def test_per_group_recall(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        ``recall.<group>`` is the hit rate among scams that list that group.

        Args:
            tmp_path: Temporary dataset folder.
            monkeypatch: Detector replacement.
        """
        dataset = tmp_path / "scam"
        _write_cases(
            dataset,
            [
                {
                    "case_id": "scam_payment__one",
                    "job": _job("p1", description="Fee before the first login."),
                    "expected": "scam",
                    "indicator_groups": ["payment"],
                    "source": "written",
                    "note": "Payment hit.",
                },
                {
                    "case_id": "scam_payment__two",
                    "job": _job("p2", description="Buy the kit from the vendor."),
                    "expected": "scam",
                    "indicator_groups": ["payment"],
                    "source": "written",
                    "note": "Payment miss.",
                },
                {
                    "case_id": "scam_contact__one",
                    "job": _job("c1", description="Chat only on a private number."),
                    "expected": "scam",
                    "indicator_groups": ["contact"],
                    "source": "written",
                    "note": "Contact hit.",
                },
            ],
        )
        _patch_detector(
            monkeypatch,
            {
                "p1": (True, 0.9, []),
                "p2": (False, 0.1, []),
                "c1": (True, 0.9, []),
            },
        )

        report = run_scam_suite(dataset)

        assert report.metrics["recall.payment"] == pytest.approx(0.5)
        assert report.metrics["recall.contact"] == pytest.approx(1.0)
        assert report.metrics["recall.urgency"] is None

    def test_threshold_sweep_uses_detector_alone(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        The sweep ignores the quick filter and steps from 0.00 to 1.00.

        Args:
            tmp_path: Temporary dataset folder.
            monkeypatch: Detector replacement.
        """
        dataset = tmp_path / "scam"
        _write_cases(
            dataset,
            [
                {
                    "case_id": "scam_payment__wire",
                    "job": _job(
                        "s1",
                        description="Send a wire transfer to hold the seat.",
                    ),
                    "expected": "scam",
                    "indicator_groups": ["payment"],
                    "source": "written",
                    "note": "Filter would fire; sweep must not use it.",
                },
                {
                    "case_id": "legit_written__clean",
                    "job": _job("l1", description="Keep the quay chart current."),
                    "expected": "legit",
                    "indicator_groups": [],
                    "source": "written",
                    "note": "Clean legit.",
                },
            ],
        )
        _patch_detector(
            monkeypatch,
            {
                "s1": (False, 0.4, ["low"]),
                "l1": (False, 0.1, []),
            },
        )

        report = run_scam_suite(dataset)

        sweep = report.details["threshold_sweep"]
        thresholds = [row["threshold"] for row in sweep]
        assert thresholds == [round(i / 20, 2) for i in range(21)]
        at_zero = next(row for row in sweep if row["threshold"] == 0.0)
        assert at_zero["recall"] == pytest.approx(1.0)
        assert at_zero["false_positive_rate"] == pytest.approx(1.0)
        at_half = next(row for row in sweep if row["threshold"] == 0.5)
        assert at_half["recall"] == pytest.approx(0.0)
        assert at_half["false_positive_rate"] == pytest.approx(0.0)
        case_row = next(
            row for row in report.details["cases"] if row["case_id"].endswith("wire")
        )
        assert case_row["quick_filter"] is True
        assert case_row["predicted"] == "scam"

    def test_sweep_flags_confidence_equal_to_threshold(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        A confidence of 0.70 is flagged in the 0.70 sweep row (T4).

        Args:
            tmp_path: Temporary dataset folder.
            monkeypatch: Detector replacement.
        """
        dataset = tmp_path / "scam"
        _write_cases(
            dataset,
            [
                {
                    "case_id": "scam_payment__on_threshold",
                    "job": _job("eq", description="Pay a fee to begin the week."),
                    "expected": "scam",
                    "indicator_groups": ["payment"],
                    "source": "written",
                    "note": "Exact 0.70 confidence.",
                },
                {
                    "case_id": "legit_written__clean_sweep",
                    "job": _job("cl", description="Keep the quay chart current."),
                    "expected": "legit",
                    "indicator_groups": [],
                    "source": "written",
                    "note": "Low confidence.",
                },
            ],
        )
        _patch_detector(
            monkeypatch,
            {
                "eq": (True, 0.70, ["on the line"]),
                "cl": (False, 0.10, []),
            },
        )

        report = run_scam_suite(dataset)

        at_threshold = next(
            row for row in report.details["threshold_sweep"] if row["threshold"] == 0.7
        )
        detector = JobScamDetector(threshold=0.7)
        on_line_is_scam = 0.70 >= detector.threshold
        assert on_line_is_scam is True
        assert at_threshold["recall"] == pytest.approx(1.0)
        assert at_threshold["false_positive_rate"] == pytest.approx(0.0)


class TestEmscadSuite:
    """CSV mapping, seeded split, missing file, and the runner."""

    def _write_csv(self, folder: Path, rows: Sequence[Dict[str, str]]) -> Path:
        """
        Write a small EMSCAD-shaped CSV.

        Args:
            folder: Dataset directory.
            rows: CSV rows.

        Returns:
            Path of the CSV.
        """
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / EMSCAD_CSV_NAME
        fieldnames = [
            "job_id",
            "title",
            "company",
            "location",
            "description",
            "company_profile",
            "requirements",
            "salary_range",
            "telecommuting",
            "required_experience",
            "employment_type",
            "has_company_logo",
            "has_questions",
            "industry",
            "function",
            "benefits",
            "fraudulent",
        ]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
        return path

    def _row(self, job_id: str, fraudulent: str, **overrides: str) -> Dict[str, str]:
        """
        One EMSCAD-shaped row.

        Args:
            job_id: Row id.
            fraudulent: ``0`` or ``1``.
            **overrides: Column replacements.

        Returns:
            A complete CSV row.
        """
        payload = {
            "job_id": job_id,
            "title": "Engineer",
            "company": "Acme",
            "location": "New York, NY, US",
            "description": "Build APIs.",
            "company_profile": "We ship software.",
            "requirements": "Python\nDocker",
            "salary_range": "50000-80000",
            "telecommuting": "0",
            "required_experience": "Mid-Senior level",
            "employment_type": "Full-time",
            "has_company_logo": "1",
            "has_questions": "0",
            "industry": "IT",
            "function": "Engineering",
            "benefits": "Health",
            "fraudulent": fraudulent,
        }
        payload.update(overrides)
        return payload

    def test_load_emscad_maps_notebook_fields(self, tmp_path: Path) -> None:
        """
        Mapping follows notebook cell 8: combined text, salary, maps.

        Args:
            tmp_path: Temporary CSV folder.
        """
        path = self._write_csv(
            tmp_path,
            [
                self._row(
                    "42",
                    "1",
                    company="",
                    required_experience="Entry level",
                    employment_type="Contract",
                    telecommuting="1",
                )
            ],
        )

        rows = load_emscad(path)

        assert len(rows) == 1
        listing = rows[0].job
        assert listing.job_id == "42"
        assert listing.company == "Unknown"
        assert listing.description == "Build APIs.\n\nWe ship software."
        assert [item.text for item in listing.requirements] == ["Python", "Docker"]
        assert listing.salary_range is not None
        assert listing.salary_range.min_amount == 50000
        assert listing.salary_range.max_amount == 80000
        assert listing.experience_level == ExperienceLevel.ENTRY.value
        assert listing.job_type == JobType.CONTRACT.value
        assert listing.is_remote is True
        assert rows[0].expected == "scam"

    def test_split_is_seeded_stratified_and_disjoint(self, tmp_path: Path) -> None:
        """
        The same seed returns the same parts; parts share no row; both labels.

        Args:
            tmp_path: Temporary CSV folder.
        """
        rows = load_emscad(
            self._write_csv(
                tmp_path,
                [self._row(f"L{i}", "0") for i in range(6)]
                + [self._row(f"S{i}", "1") for i in range(6)],
            )
        )

        first_tune, first_held = split_emscad(rows, seed=EMSCAD_SPLIT_SEED)
        second_tune, second_held = split_emscad(rows, seed=EMSCAD_SPLIT_SEED)

        def ids(part: Sequence[Any]) -> List[str]:
            return [item.job.job_id for item in part]

        assert ids(first_tune) == ids(second_tune)
        assert ids(first_held) == ids(second_held)
        assert set(ids(first_tune)).isdisjoint(ids(first_held))
        assert len(first_tune) + len(first_held) == 12
        for part in (first_tune, first_held):
            labels = {item.expected for item in part}
            assert labels == {"scam", "legit"}

    def test_missing_csv_names_path_and_decision(self, tmp_path: Path) -> None:
        """
        A missing CSV raises ``FileNotFoundError`` with the path and decision 3.

        Args:
            tmp_path: Empty dataset folder.
        """
        with pytest.raises(FileNotFoundError, match="decision 3") as exc:
            run_emscad_suite(tmp_path, part="tuning")
        assert EMSCAD_CSV_NAME in str(exc.value)
        assert str(tmp_path) in str(exc.value) or tmp_path.as_posix() in str(
            exc.value
        ).replace("\\", "/")

    def test_run_emscad_suite_records_part_and_seed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        The tuning part runs the same decision and records split metadata.

        Args:
            tmp_path: Temporary CSV folder.
            monkeypatch: Detector replacement.
        """
        self._write_csv(
            tmp_path,
            [self._row(f"L{i}", "0") for i in range(4)]
            + [self._row(f"S{i}", "1") for i in range(4)],
        )
        monkeypatch.setattr(
            "src.evaluation.suites.emscad.JobScamDetector",
            lambda threshold=0.7: _FakeDetector(),
        )
        monkeypatch.setattr(
            "src.evaluation.suites.emscad.ScamFilter.is_potential_scam",
            lambda job: job.job_id.startswith("S"),
        )

        report = run_emscad_suite(tmp_path, part="tuning")

        assert report.suite == "emscad"
        assert report.metadata.seed == EMSCAD_SPLIT_SEED
        assert report.details["part"] == "tuning"
        assert report.details["csv_rows"] == 8
        assert report.details["tuning_rows"] + report.details["heldout_rows"] == 8
        assert report.metrics["case_count"] == float(report.details["part_rows"])

    def test_run_emscad_suite_uses_the_requested_part(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Tuning and held-out reports use the matching split IDs (T1).

        Args:
            tmp_path: Temporary CSV folder.
            monkeypatch: Detector replacement.
        """
        self._write_csv(
            tmp_path,
            [self._row(f"L{i}", "0") for i in range(6)]
            + [self._row(f"S{i}", "1") for i in range(6)],
        )
        monkeypatch.setattr(
            "src.evaluation.suites.emscad.JobScamDetector",
            lambda threshold=0.7: _FakeDetector(),
        )
        monkeypatch.setattr(
            "src.evaluation.suites.emscad.ScamFilter.is_potential_scam",
            lambda job: False,
        )
        rows = load_emscad(tmp_path / EMSCAD_CSV_NAME)
        tuning, heldout = split_emscad(rows, seed=EMSCAD_SPLIT_SEED)

        tuning_report = run_emscad_suite(tmp_path, part="tuning")
        held_report = run_emscad_suite(tmp_path, part="heldout")

        tuning_ids = [row.job.job_id for row in tuning]
        held_ids = [row.job.job_id for row in heldout]
        assert [row["case_id"] for row in tuning_report.details["cases"]] == tuning_ids
        assert [row["case_id"] for row in held_report.details["cases"]] == held_ids
        assert set(tuning_ids).isdisjoint(held_ids)
        assert tuning_report.tags == {"part": "tuning"}
        assert held_report.tags == {"part": "heldout"}

    def test_split_keeps_label_counts_on_uneven_classes(self, tmp_path: Path) -> None:
        """
        A 10/4 split at 0.5 puts 5 and 2 of each label in each part (T3).

        Args:
            tmp_path: Temporary CSV folder.
        """
        rows = load_emscad(
            self._write_csv(
                tmp_path,
                [self._row(f"L{i}", "0") for i in range(10)]
                + [self._row(f"S{i}", "1") for i in range(4)],
            )
        )

        tuning, heldout = split_emscad(
            rows, seed=EMSCAD_SPLIT_SEED, held_out_fraction=0.5
        )

        def counts(part: Sequence[Any]) -> tuple[int, int]:
            legit = sum(1 for item in part if item.expected == "legit")
            scam = sum(1 for item in part if item.expected == "scam")
            return legit, scam

        assert counts(tuning) == (5, 2)
        assert counts(heldout) == (5, 2)


class TestRegistryAndPart:
    """Suite registry and the ``--part`` CLI flag."""

    def test_registry_lists_scam_and_emscad(self) -> None:
        """``scam`` and ``emscad`` resolve to their default folders."""
        assert SUITE_NAMES == ("grounding", "scam", "emscad")
        scam_runner, scam_dir = get_suite("scam")
        emscad_runner, emscad_dir = get_suite("emscad")
        assert scam_runner is run_scam_suite
        assert emscad_runner is run_emscad_suite
        assert scam_dir.name == "scam"
        assert emscad_dir.name == "kaggle"

    def test_cli_part_default_and_heldout(self) -> None:
        """``--part`` defaults to tuning and accepts heldout."""
        from tests.unit.test_cli import parse

        default_args = parse(["eval", "emscad"])
        assert default_args.part == "tuning"
        held = parse(["eval", "emscad", "--part", "heldout"])
        assert held.part == "heldout"
        scam_args = parse(["eval", "scam"])
        assert scam_args.part == "tuning"

    def test_run_eval_command_passes_part_only_to_emscad(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        ``run_eval_command`` forwards ``--part`` only to the emscad runner (T2).

        Args:
            tmp_path: Temporary output folder.
            monkeypatch: Suite registry replacement.
        """
        import main as cli
        from tests.unit.test_cli import parse

        seen: Dict[str, Dict[str, Any]] = {}

        def _tiny(suite: str) -> EvalReport:
            path = tmp_path / f"{suite}.jsonl"
            path.write_text("{}\n", encoding="utf-8")
            return EvalReport(
                suite=suite,
                metadata=build_run_metadata(suite, [path], 1, repo_dir=tmp_path),
                metrics={"precision": 1.0},
                details={},
            )

        def fake_emscad(dataset: Path, **kwargs: Any) -> EvalReport:
            seen["emscad"] = dict(kwargs)
            return _tiny("emscad")

        def fake_scam(dataset: Path, **kwargs: Any) -> EvalReport:
            seen["scam"] = dict(kwargs)
            return _tiny("scam")

        def fake_get_suite(name: str) -> tuple:
            if name == "emscad":
                return fake_emscad, tmp_path
            return fake_scam, tmp_path

        monkeypatch.setattr("src.evaluation.suites.get_suite", fake_get_suite)
        out = tmp_path / "out"
        emscad_args = parse(
            [
                "eval",
                "emscad",
                "--dataset",
                str(tmp_path),
                "--out",
                str(out),
                "--no-mlflow",
                "--part",
                "heldout",
            ]
        )
        scam_args = parse(
            [
                "eval",
                "scam",
                "--dataset",
                str(tmp_path),
                "--out",
                str(out),
                "--no-mlflow",
            ]
        )
        assert cli.run_eval_command(emscad_args) == 0
        assert seen["emscad"] == {"part": "heldout"}
        assert cli.run_eval_command(scam_args) == 0
        assert seen["scam"] == {}
