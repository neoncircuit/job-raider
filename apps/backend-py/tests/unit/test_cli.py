"""
Tests for the command-line interface in ``main.py``.

These tests parse arguments and route commands without running the pipeline,
the resume parser, or the dependency bootstrap. Heavy collaborators are
replaced with small fakes.
"""

import argparse
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

import main as cli
from src.models.job_listing import ExperienceLevel, JobSource
from src.models.user_profile import TargetJob
from src.scrapers import manager as scraper_manager

PIPELINE_BASE = [
    "pipeline",
    "--resume",
    "resume.pdf",
    "--keywords",
    "python engineer",
    "--locations",
    "New York",
    "Remote",
]


def parse(argv: List[str]) -> argparse.Namespace:
    """Parse CLI arguments with a freshly built parser.

    Args:
        argv: Arguments without the program name.

    Returns:
        Parsed namespace.
    """
    return cli.build_parser().parse_args(argv)


@pytest.fixture
def no_logging_setup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stop ``main()`` from configuring file logging under the working directory.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.
    """
    monkeypatch.setattr(cli, "setup_logging", lambda **_: None)


class TestParser:
    """Argument parsing for every command."""

    def test_build_parser_defines_each_option_once(self) -> None:
        """Building the parser must not raise an argparse option conflict."""
        assert isinstance(cli.build_parser(), argparse.ArgumentParser)

    @pytest.mark.parametrize(
        "argv",
        [["--help"], ["pipeline", "--help"], ["analyze", "--help"], ["eval", "--help"]],
    )
    def test_help_exits_zero(self, argv: List[str]) -> None:
        """Help for the top level and each command exits with code 0.

        Args:
            argv: Help arguments to parse.
        """
        with pytest.raises(SystemExit) as exc:
            parse(argv)
        assert exc.value.code == 0

    def test_pipeline_example_keeps_quoted_terms_whole(self) -> None:
        """Each quoted value after --keywords or --locations is one search term."""
        args = parse(PIPELINE_BASE)

        assert args.command == "pipeline"
        assert args.keywords == ["python engineer"]
        assert args.locations == ["New York", "Remote"]
        assert args.dry_run is True
        assert args.log_level == "INFO"
        assert args.log_file is None

    def test_no_dry_run_turns_dry_run_off(self) -> None:
        """--no-dry-run sets dry_run to False."""
        assert parse(PIPELINE_BASE + ["--no-dry-run"]).dry_run is False

    @pytest.mark.parametrize(
        "argv",
        [
            PIPELINE_BASE + ["--log-level", "DEBUG", "--log-file", "run.log"],
            ["analyze", "--resume", "resume.pdf", "--log-level", "DEBUG"],
        ],
    )
    def test_logging_options_follow_the_command(self, argv: List[str]) -> None:
        """--log-level is accepted after either command.

        Args:
            argv: Command arguments that include --log-level.
        """
        assert parse(argv).log_level == "DEBUG"

    def test_pipeline_requires_keywords(self) -> None:
        """The pipeline command fails without --keywords."""
        with pytest.raises(SystemExit) as exc:
            parse(["pipeline", "--resume", "r.pdf", "--locations", "Remote"])
        assert exc.value.code == 2

    def test_stop_at_accepts_pipeline_stages(self) -> None:
        """--stop-at accepts a pipeline stage value."""
        args = parse(PIPELINE_BASE + ["--stop-at", "score_and_rank"])
        assert args.stop_at == "score_and_rank"


class TestSources:
    """--sources choices come from the scraper registry."""

    def test_every_registered_source_is_accepted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """All sources that the manager registers are valid CLI choices.

        Args:
            monkeypatch: Pytest monkeypatch fixture.
        """
        every_source = [
            JobSource.LINKEDIN,
            JobSource.JSEARCH,
            JobSource.MYCAREERSFUTURE,
            JobSource.JOBSTREET,
            JobSource.CAREERSATGOV,
        ]
        monkeypatch.setattr(cli, "available_sources", lambda: every_source)

        names = [source.value for source in every_source]
        args = parse(PIPELINE_BASE + ["--sources", *names])

        assert args.sources == names

    def test_unknown_source_is_rejected(self) -> None:
        """A source that the manager does not register is an argparse error."""
        with pytest.raises(SystemExit) as exc:
            parse(PIPELINE_BASE + ["--sources", "indeed"])
        assert exc.value.code == 2

    def test_available_sources_honors_kill_switches(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Disabled Singapore boards are not listed.

        Args:
            monkeypatch: Pytest monkeypatch fixture.
        """
        monkeypatch.setattr(scraper_manager, "mcf_enabled", lambda: False)
        monkeypatch.setattr(scraper_manager, "jobstreet_enabled", lambda: True)
        monkeypatch.setattr(scraper_manager, "careersatgov_enabled", lambda: False)

        assert scraper_manager.available_sources() == [
            JobSource.LINKEDIN,
            JobSource.JSEARCH,
            JobSource.JOBSTREET,
        ]

    def test_manager_registers_exactly_the_available_sources(
        self, tmp_path: Path
    ) -> None:
        """ScraperManager and available_sources() list the same sources.

        Args:
            tmp_path: Temporary output directory for the manager.
        """
        manager = scraper_manager.ScraperManager(output_dir=str(tmp_path))
        assert list(manager.scrapers) == scraper_manager.available_sources()


class TestRunPipeline:
    """run_pipeline applies profile targets and reports the result."""

    def test_target_options_extend_profile_targets(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Target keywords, locations, and experience land on profile.targets.

        Args:
            monkeypatch: Pytest monkeypatch fixture.
        """
        profile = SimpleNamespace(targets=TargetJob(keywords=["existing"]))
        captured: Dict[str, Any] = {}

        class FakeOrchestrator:
            """Records the profile and returns a successful result."""

            def __init__(self, config: Any, user_profile: Any) -> None:
                """Store the profile passed by run_pipeline.

                Args:
                    config: Pipeline configuration.
                    user_profile: Profile to run with.
                """
                captured["config"] = config
                captured["profile"] = user_profile

            def run(self, stop_at: Any = None, **_kwargs: Any) -> SimpleNamespace:
                """Return a minimal successful pipeline result.

                Args:
                    stop_at: Optional last stage.

                Returns:
                    Result with the fields that run_pipeline prints.
                """
                return SimpleNamespace(
                    success=True,
                    duration_seconds=1.0,
                    jobs_scraped=0,
                    jobs_applied=0,
                    stages_completed=[],
                    stage_results={},
                )

        monkeypatch.setattr(cli, "load_user_profile", lambda _path: profile)
        monkeypatch.setattr(cli, "PipelineOrchestrator", FakeOrchestrator)

        args = parse(
            PIPELINE_BASE
            + [
                "--target-keywords",
                "backend",
                "--target-locations",
                "Singapore",
                "--target-experience",
                "entry",
                "senior",
            ]
        )

        assert cli.run_pipeline(args) == 0
        assert captured["profile"] is profile
        assert profile.targets.keywords == ["existing", "backend"]
        assert profile.targets.locations == ["Singapore"]
        assert profile.targets.experience_levels == [
            ExperienceLevel.ENTRY,
            ExperienceLevel.SENIOR,
        ]
        assert captured["config"].keywords == ["python engineer"]

    @pytest.mark.parametrize("choice", cli.EXPERIENCE_CHOICES)
    def test_every_experience_choice_maps_to_the_enum(self, choice: str) -> None:
        """Each --target-experience choice names an ExperienceLevel member.

        Args:
            choice: One CLI experience choice.
        """
        assert isinstance(ExperienceLevel[choice.upper()], ExperienceLevel)

    def test_load_user_profile_uses_parse_file(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """load_user_profile calls ResumeParser.parse_file and logs real fields.

        Args:
            monkeypatch: Pytest monkeypatch fixture.
        """
        profile = SimpleNamespace(
            name="Test User", skills=[], projects=[], years_of_experience=1.5
        )

        class FakeParser:
            """Stand-in for ResumeParser."""

            def parse_file(self, file_path: str) -> SimpleNamespace:
                """Return the fake profile.

                Args:
                    file_path: Resume path.

                Returns:
                    The fake profile.
                """
                return profile

        monkeypatch.setattr(cli, "ResumeParser", FakeParser)

        assert cli.load_user_profile("resume.pdf") is profile


class TestMainRouting:
    """main() routes each command and validates input."""

    def test_no_command_is_a_usage_error(self, no_logging_setup: None) -> None:
        """Running with no command and no -i exits with code 2.

        Args:
            no_logging_setup: Fixture that disables logging setup.
        """
        with pytest.raises(SystemExit) as exc:
            cli.main([])
        assert exc.value.code == 2

    def test_interactive_flag_routes_to_interactive_mode(
        self, monkeypatch: pytest.MonkeyPatch, no_logging_setup: None
    ) -> None:
        """-i runs interactive mode.

        Args:
            monkeypatch: Pytest monkeypatch fixture.
            no_logging_setup: Fixture that disables logging setup.
        """
        monkeypatch.setattr(cli, "interactive_mode", lambda: 7)
        assert cli.main(["-i"]) == 7

    def test_pipeline_routes_to_run_pipeline(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        no_logging_setup: None,
    ) -> None:
        """The pipeline command calls run_pipeline when the resume exists.

        Args:
            monkeypatch: Pytest monkeypatch fixture.
            tmp_path: Temporary directory for the resume file.
            no_logging_setup: Fixture that disables logging setup.
        """
        resume = tmp_path / "resume.pdf"
        resume.write_bytes(b"%PDF-1.4")
        seen: List[argparse.Namespace] = []
        monkeypatch.setattr(cli, "run_pipeline", lambda a: seen.append(a) or 0)

        argv = ["pipeline", "--resume", str(resume), "--keywords", "python"]
        assert cli.main(argv + ["--locations", "Singapore"]) == 0
        assert seen[0].keywords == ["python"]

    def test_pipeline_with_missing_resume_returns_1(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        no_logging_setup: None,
    ) -> None:
        """A resume path that does not exist returns exit code 1.

        Args:
            monkeypatch: Pytest monkeypatch fixture.
            tmp_path: Temporary directory without a resume file.
            no_logging_setup: Fixture that disables logging setup.
        """
        monkeypatch.setattr(cli, "run_pipeline", lambda _a: pytest.fail("ran"))
        missing = str(tmp_path / "missing.pdf")

        argv = ["pipeline", "--resume", missing, "--keywords", "python"]
        assert cli.main(argv + ["--locations", "Singapore"]) == 1

    def test_options_without_a_command_default_to_pipeline(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        no_logging_setup: None,
    ) -> None:
        """The documented form without a command runs the pipeline command.

        Args:
            monkeypatch: Pytest monkeypatch fixture.
            tmp_path: Temporary directory for the resume file.
            no_logging_setup: Fixture that disables logging setup.
        """
        resume = tmp_path / "resume.pdf"
        resume.write_bytes(b"%PDF-1.4")
        seen: List[argparse.Namespace] = []
        monkeypatch.setattr(cli, "run_pipeline", lambda a: seen.append(a) or 0)

        argv = ["--resume", str(resume), "--keywords", "python", "--dry-run"]
        assert cli.main(argv + ["--locations", "Remote"]) == 0
        assert seen[0].command == "pipeline"
        assert seen[0].locations == ["Remote"]

    @pytest.mark.parametrize(
        "argv, expected",
        [
            (["--help"], ["--help"]),
            (["-i"], ["-i"]),
            (["analyze", "--resume", "r.pdf"], ["analyze", "--resume", "r.pdf"]),
            (["--resume", "r.pdf"], ["pipeline", "--resume", "r.pdf"]),
            ([], []),
        ],
    )
    def test_with_default_command(self, argv: List[str], expected: List[str]) -> None:
        """Only a leading pipeline option gets the default command.

        Args:
            argv: Input arguments.
            expected: Arguments after the default command is applied.
        """
        assert cli.with_default_command(argv) == expected

    def test_analyze_routes_to_run_analyze_command(
        self, monkeypatch: pytest.MonkeyPatch, no_logging_setup: None
    ) -> None:
        """The analyze command calls run_analyze_command.

        Args:
            monkeypatch: Pytest monkeypatch fixture.
            no_logging_setup: Fixture that disables logging setup.
        """
        monkeypatch.setattr(cli, "run_analyze_command", lambda a: 3)
        assert cli.main(["analyze", "--resume", "resume.pdf"]) == 3


class RecordingLogger:
    """Logger stand-in that keeps error messages for assertions."""

    def __init__(self) -> None:
        """Start with no recorded messages."""
        self.errors: List[str] = []

    def info(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Ignore info messages.

        Args:
            message: Log message.
            *args: Format arguments.
            **kwargs: Logging keyword arguments.
        """

    def error(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Record an error message.

        Args:
            message: Log message.
            *args: Format arguments.
            **kwargs: Logging keyword arguments.
        """
        self.errors.append(message)


class FakeAnalysis:
    """Minimal resume analysis with the fields that the CLI prints."""

    overall_score = 72.0
    competitive_edge = "Strong projects"
    summary = "Solid early-career profile."
    key_strengths = ["Python"]
    key_improvements = ["Add metrics"]
    target_alignment_score = 65.0
    competitive_advantages = ["Open-source work"]
    competitive_gaps = ["No cloud experience"]

    def model_dump(self) -> Dict[str, Any]:
        """Return the analysis as a dictionary.

        Returns:
            Serializable analysis fields.
        """
        return {"overall_score": self.overall_score, "summary": self.summary}


class TestAnalyzeCommand:
    """run_analyze_command checks input and writes the analysis."""

    def test_missing_resume_is_reported_before_parsing(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A missing resume logs "Resume not found" and never reaches the parser.

        Args:
            monkeypatch: Pytest monkeypatch fixture.
            tmp_path: Temporary directory without a resume file.
        """
        logger = RecordingLogger()
        monkeypatch.setattr(cli, "get_logger", lambda _component: logger)
        monkeypatch.setattr(cli, "ResumeParser", lambda: pytest.fail("parsed"))

        args = parse(["analyze", "--resume", str(tmp_path / "missing.pdf")])

        assert cli.run_analyze_command(args) == 1
        assert logger.errors and logger.errors[0].startswith("Resume not found")

    def test_general_analysis_writes_json_output(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A general analysis succeeds and saves the JSON file.

        Args:
            monkeypatch: Pytest monkeypatch fixture.
            tmp_path: Temporary directory for the resume and the output.
        """
        resume = tmp_path / "resume.pdf"
        resume.write_bytes(b"%PDF-1.4")
        output = tmp_path / "out" / "analysis.json"
        profile = SimpleNamespace(name="Test User")

        class FakeParser:
            """Stand-in for ResumeParser."""

            def parse_file(self, file_path: str) -> SimpleNamespace:
                """Return the fake profile.

                Args:
                    file_path: Resume path.

                Returns:
                    The fake profile.
                """
                return profile

        class FakeAnalyzer:
            """Stand-in for ResumeAnalyzer."""

            def __init__(self, llm_router: Any) -> None:
                """Accept the router like the real analyzer.

                Args:
                    llm_router: LLM router.
                """

            def analyze_general(
                self, user_profile: Any, resume_path: str
            ) -> FakeAnalysis:
                """Return a fixed analysis.

                Args:
                    user_profile: Parsed profile.
                    resume_path: Resume path.

                Returns:
                    The fake analysis.
                """
                assert user_profile is profile
                return FakeAnalysis()

        monkeypatch.setattr(cli, "ResumeParser", FakeParser)
        monkeypatch.setattr(cli, "ResumeAnalyzer", FakeAnalyzer)
        monkeypatch.setattr(cli, "LLMRouter", lambda: object())

        args = parse(["analyze", "--resume", str(resume), "--output", str(output)])

        assert cli.run_analyze_command(args) == 0
        assert '"overall_score": 72.0' in output.read_text(encoding="utf-8")


class TestEvalCommand:
    """``main.py eval <suite>`` runs an offline evaluation suite."""

    def test_unknown_suite_is_rejected(self) -> None:
        """Only registered suites are accepted."""
        with pytest.raises(SystemExit) as exc:
            parse(["eval", "no-such-suite"])
        assert exc.value.code == 2

    def test_eval_grounding_writes_a_report(
        self, tmp_path: Path, no_logging_setup: None
    ) -> None:
        """The grounding suite runs on a dataset and writes one JSON report.

        Args:
            tmp_path: Pytest temporary directory.
            no_logging_setup: Fixture that stops file logging setup.
        """
        dataset = tmp_path / "grounding"
        dataset.mkdir()
        profile = {
            "name": "Alex Chen",
            "contact": {"email": "alex@example.com", "location": "Singapore"},
            "skills": [{"name": "Python", "category": "programming_language"}],
        }
        job = {
            "title": "Backend Engineer",
            "company": "Harbor Labs",
            "job_id": "eval-job-1",
            "source": "manual",
        }
        (dataset / "profiles.json").write_text(
            json.dumps({"alex": profile}), encoding="utf-8"
        )
        case = {
            "case_id": "clean",
            "profile_id": "alex",
            "job": job,
            "letter": "I write Python at work.",
            "expected_issues": [],
        }
        (dataset / "cases.jsonl").write_text(json.dumps(case) + "\n", encoding="utf-8")
        out_dir = tmp_path / "out"

        code = cli.main(
            [
                "eval",
                "grounding",
                "--dataset",
                str(dataset),
                "--out",
                str(out_dir),
                "--no-mlflow",
            ]
        )

        assert code == 0
        reports = list((out_dir / "grounding").glob("*.json"))
        assert len(reports) == 1
        data = json.loads(reports[0].read_text(encoding="utf-8"))
        assert data["metadata"]["case_count"] == 1
