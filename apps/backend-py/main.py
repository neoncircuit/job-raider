#!/usr/bin/env python3
"""
Job Raider - Automated Job Application Pipeline

A command-line interface for automated job searching, filtering,
and application generation.

Author: Job Raider
Date: 2026-04-21
"""

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional


# Check for dependencies first
def ensure_dependencies():
    """
    Ensure all dependencies are installed.
    Creates venv and installs packages if missing.
    This provides self-healing behavior like pnpm dev.
    """
    project_root = Path.cwd()
    venv_dir = project_root / ".venv"
    venv_python = venv_dir / "bin" / "python3"
    requirements_file = project_root / "requirements.txt"

    # First, check if we're running inside the venv
    # If not, re-exec this script using the venv python
    if venv_python.exists() and sys.prefix != str(venv_dir):
        print("Job Raider - Auto-activating virtual environment...")
        print("-" * 40)
        print(f"✓ Switching to: {venv_python}")
        print()

        # Re-exec this script with the venv python
        os.execv(str(venv_python), [str(venv_python)] + sys.argv)

    print("Job Raider - Dependency Check")
    print("-" * 40)

    # Check if .venv exists
    if not venv_dir.exists():
        print("⚠ Virtual environment not found")
        print("→ Creating virtual environment...")

        try:
            subprocess.run(
                [sys.executable, "-m", "venv", str(venv_dir)],
                check=True,
                capture_output=True,
            )
            print("✓ Virtual environment created")
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to create venv: {e}")
            print("  Please ensure python3-venv is installed")
            sys.exit(1)

    # Check if key packages are available
    missing_packages = []
    required_packages = [
        "pydantic",
        "yaml",
        "playwright",
        "anthropic",
    ]

    # Try importing to check if packages are installed
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)

    if missing_packages:
        print(f"⚠ Missing packages: {', '.join(missing_packages)}")
        print("→ Installing dependencies...")

        pip_path = venv_dir / "bin" / "pip"

        if not pip_path.exists():
            print("✗ pip not found in venv")
            sys.exit(1)

        try:
            # Check if requirements.txt exists
            if requirements_file.exists():
                result = subprocess.run(
                    [str(pip_path), "install", "-r", str(requirements_file)],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    print("✓ Dependencies installed")
                else:
                    print("✗ Installation failed:")
                    print(result.stderr)
                    sys.exit(1)
            else:
                print("⚠ requirements.txt not found, installing core packages...")
                core_packages = [
                    "pydantic",
                    "pyyaml",
                    "requests",
                    "beautifulsoup4",
                ]
                result = subprocess.run(
                    [str(pip_path), "install"] + core_packages,
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    print("✓ Core dependencies installed")
                else:
                    print("✗ Installation failed:")
                    print(result.stderr)
                    sys.exit(1)
        except Exception as e:
            print(f"✗ Failed to install dependencies: {e}")
            sys.exit(1)
    else:
        print("✓ All dependencies satisfied")

    # Install Playwright browsers if needed. Only check that the package is
    # importable; browsers are downloaded on first use.
    if importlib.util.find_spec("playwright") is None:
        print("⚠ Playwright not installed, installing browsers...")
        try:
            subprocess.run(
                ["playwright", "install", "chromium"],
                env={**os.environ, "PLAYWRIGHT_BROWSERS_PATH": "0"},
                capture_output=True,
            )
            print("✓ Playwright browsers installed")
        except Exception as e:
            print(f"⚠ Could not install Playwright browsers: {e}")
            print("  They will be installed on first use")

    # Ensure data directories exist
    data_dirs = [
        "data/listings",
        "data/cache",
        "data/results",
        "data/applications",
        "data/metrics",
        "data/experiments",
        "data/logs",
        "data/profiles",
        "data/outputs",
    ]

    missing_dirs = []
    for dir_path in data_dirs:
        if not Path(dir_path).exists():
            missing_dirs.append(dir_path)

    if missing_dirs:
        print("⚠ Some data directories missing")
        print("→ Creating data directories...")
        for dir_path in missing_dirs:
            Path(dir_path).mkdir(parents=True, exist_ok=True)
        print(f"✓ Created {len(missing_dirs)} directories")

    print("-" * 40)
    print()

    # Re-exec this script with the venv python if needed
    # This ensures we're running from within the venv
    venv_python = venv_dir / "bin" / "python3"
    if sys.executable != str(venv_python):
        print("Switching to virtual environment...")
        print()
        os.execv(str(venv_python), [str(venv_python)] + sys.argv)

    return True


# Ensure dependencies before importing anything else. The project imports
# below must stay after this call, so they carry ``noqa: E402``.
# When running as main, check deps before imports to auto-create venv
if __name__ == "__main__":
    ensure_dependencies()

from src.evaluation.suites import SUITE_NAMES  # noqa: E402
from src.extractors.resume_parser import ResumeParser  # noqa: E402
from src.generation.resume_analyzer import ResumeAnalyzer  # noqa: E402
from src.llm.router import LLMRouter  # noqa: E402
from src.models.job_listing import ExperienceLevel  # noqa: E402
from src.models.user_profile import UserProfile  # noqa: E402
from src.pipeline.orchestrator import (  # noqa: E402
    PipelineConfig,
    PipelineOrchestrator,
    PipelineStage,
)
from src.scoring.scam_detector import DEFAULT_SCAM_THRESHOLD  # noqa: E402
from src.scrapers.manager import available_sources  # noqa: E402
from src.utils.logger import Components, get_logger, setup_logging  # noqa: E402

# CLI names for --target-experience, mapped to ExperienceLevel by member name.
EXPERIENCE_CHOICES = [
    level.name.lower()
    for level in ExperienceLevel
    if level is not ExperienceLevel.NOT_SPECIFIED
]


def load_user_profile(resume_path: str) -> UserProfile:
    """
    Load user profile from resume.

    Args:
        resume_path: Path to resume file (PDF or DOCX)

    Returns:
        UserProfile object
    """
    logger = get_logger(Components.SCRAPERS)

    logger.info(f"Parsing resume from: {resume_path}")

    parser = ResumeParser()
    profile = parser.parse_file(resume_path)

    logger.info(f"Loaded profile for: {profile.name}")
    logger.info(f"Skills: {len(profile.skills)} categories")
    logger.info(f"Projects: {len(profile.projects)}")
    logger.info(f"Experience: {profile.years_of_experience:.1f} years")

    return profile


def create_pipeline_config(args) -> PipelineConfig:
    """
    Create pipeline configuration from CLI arguments.

    Args:
        args: Parsed CLI arguments

    Returns:
        PipelineConfig object
    """
    return PipelineConfig(
        keywords=args.keywords,
        locations=args.locations,
        sources=args.sources,
        dry_run=args.dry_run,
        skip_submission=args.skip_submission,
        min_score=args.min_score,
        scam_threshold=args.scam_threshold,
        fresh_grad_mode=getattr(args, "fresh_grad", False),
        max_jobs_to_present=args.max_jobs,
        data_dir=args.data_dir,
        results_dir=args.results_dir,
        log_level=args.log_level,
        log_file=args.log_file,
        submission_delay=args.submission_delay,
        max_submissions_per_hour=args.max_submissions,
    )


def run_pipeline(args) -> int:
    """
    Run the job application pipeline.

    Args:
        args: Parsed CLI arguments

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    logger = get_logger(Components.SCRAPERS)

    try:
        # Load user profile
        profile = load_user_profile(args.resume)

        # Update profile if targets provided
        if args.target_keywords:
            profile.targets.keywords.extend(args.target_keywords)
        if args.target_locations:
            profile.targets.locations.extend(args.target_locations)
        if args.target_experience:
            profile.targets.experience_levels = [
                ExperienceLevel[exp.upper()] for exp in args.target_experience
            ]

        # Create pipeline config
        config = create_pipeline_config(args)

        # Create orchestrator
        orchestrator = PipelineOrchestrator(
            config=config,
            user_profile=profile,
        )

        # Run pipeline
        result = orchestrator.run(
            stop_at=PipelineStage(args.stop_at) if args.stop_at else None,
        )

        # Print summary
        print("\n" + "=" * 60)
        print("PIPELINE SUMMARY")
        print("=" * 60)
        print(f"Status: {'SUCCESS' if result.success else 'FAILED'}")
        print(f"Duration: {result.duration_seconds:.1f} seconds")
        print(f"Jobs scraped: {result.jobs_scraped}")
        print(f"Jobs applied: {result.jobs_applied}")
        print(f"Stages completed: {len(result.stages_completed)}")

        for stage in result.stages_completed:
            stage_result = result.stage_results.get(stage)
            if stage_result and stage_result.metadata:
                print(f"\n{stage.upper()}:")
                for key, value in stage_result.metadata.items():
                    if key != "scam_reports":  # Skip verbose data
                        print(f"  {key}: {value}")

        print("=" * 60 + "\n")

        return 0 if result.success else 1

    except Exception as e:
        logger.error(f"Pipeline failed: {str(e)}", exc_info=True)
        return 1


def interactive_mode() -> int:
    """
    Run pipeline in interactive mode.

    Returns:
        Exit code
    """
    logger = get_logger(Components.SCRAPERS)

    print("\n" + "=" * 60)
    print("Job Raider - Interactive Mode")
    print("=" * 60 + "\n")

    try:
        # Get resume path
        resume_path = input("Enter path to your resume (PDF or DOCX): ").strip()
        if not Path(resume_path).exists():
            print(f"Error: Resume not found at {resume_path}")
            return 1

        # Load profile
        profile = load_user_profile(resume_path)

        # Get search parameters
        print("\n--- Search Parameters ---")
        keywords_input = input("Enter job keywords (comma-separated): ").strip()
        keywords = [k.strip() for k in keywords_input.split(",") if k.strip()]

        locations_input = input("Enter locations (comma-separated): ").strip()
        locations = [loc.strip() for loc in locations_input.split(",") if loc.strip()]

        source_names = ",".join(source.value for source in available_sources())
        sources_input = input(
            f"Enter sources to search ({source_names} or blank for all): "
        ).strip()
        sources = (
            [s.strip().lower() for s in sources_input.split(",") if s.strip()]
            if sources_input
            else None
        )

        # Get options
        print("\n--- Options ---")
        dry_run = input("Dry run mode? (Y/n): ").strip().lower() != "n"
        skip_submission = (
            not dry_run
            and input("Skip actual submission? (Y/n): ").strip().lower() != "n"
        )

        # Create config
        config = PipelineConfig(
            keywords=keywords,
            locations=locations,
            sources=sources,
            dry_run=dry_run,
            skip_submission=skip_submission,
        )

        # Run pipeline
        orchestrator = PipelineOrchestrator(
            config=config,
            user_profile=profile,
        )

        result = orchestrator.run()

        # Print summary
        print("\n" + "=" * 60)
        print("PIPELINE COMPLETE")
        print("=" * 60)
        print(f"Status: {'SUCCESS' if result.success else 'FAILED'}")
        print(f"Duration: {result.duration_seconds:.1f} seconds")
        print("=" * 60 + "\n")

        return 0 if result.success else 1

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Interactive mode failed: {str(e)}", exc_info=True)
        return 1


def run_analyze_command(args) -> int:
    """
    Run the resume analysis command.

    Args:
        args: Parsed CLI arguments

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    logger = get_logger(Components.GENERATION)

    try:
        # Verify resume exists before parsing it
        if not Path(args.resume).exists():
            logger.error(f"Resume not found: {args.resume}")
            return 1

        # Parse resume
        logger.info(f"Parsing resume from: {args.resume}")
        parser = ResumeParser()
        profile = parser.parse_file(args.resume)

        # Create analyzer
        llm_router = LLMRouter()
        analyzer = ResumeAnalyzer(llm_router)

        # Run analysis
        if args.job:
            # Job-specific analysis
            logger.info(f"Running job-specific analysis against: {args.job}")

            # Load job description file and structure like a paste
            with open(args.job, "r") as f:
                job_text = f.read()

            from src.extractors.paste_job import build_job_listing_from_paste

            job = build_job_listing_from_paste(
                title="Target Position",
                company="Target Company",
                description=job_text,
                location=None,
                job_id="cli-analyze",
            )

            analysis = analyzer.analyze_job_specific(
                profile, job, resume_path=args.resume
            )
        else:
            # General analysis
            logger.info("Running general resume analysis")
            analysis = analyzer.analyze_general(profile, resume_path=args.resume)

        # Display results
        print("\n" + "=" * 60)
        print("RESUME ANALYSIS")
        print("=" * 60)
        print(f"Overall Score: {analysis.overall_score:.1f}/100")
        print(f"Competitive Edge: {analysis.competitive_edge}")
        print()
        print(f"Summary: {analysis.summary}")
        print()

        if analysis.key_strengths:
            print("Key Strengths:")
            for strength in analysis.key_strengths:
                print(f"  • {strength}")
            print()

        if analysis.key_improvements:
            print("Key Improvements:")
            for improvement in analysis.key_improvements:
                print(f"  • {improvement}")
            print()

        if analysis.target_alignment_score:
            print(f"Target Alignment: {analysis.target_alignment_score:.1f}/100")

        if analysis.competitive_advantages:
            print("Competitive Advantages:")
            for advantage in analysis.competitive_advantages:
                print(f"  • {advantage}")
            print()

        if analysis.competitive_gaps:
            print("Competitive Gaps:")
            for gap in analysis.competitive_gaps:
                print(f"  • {gap}")
            print()

        print("=" * 60 + "\n")

        # Save to file if requested
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "w") as f:
                json.dump(analysis.model_dump(), f, indent=2, default=str)

            logger.info(f"Analysis saved to: {args.output}")

        return 0

    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}", exc_info=True)
        return 1


def run_eval_command(args) -> int:
    """
    Run an offline evaluation suite, write its report, and log it to MLflow.

    Args:
        args: Parsed arguments with ``suite``, ``dataset``, ``out``,
            ``no_mlflow``, and ``part``.

    Returns:
        Exit code: 0 on success, 1 when the dataset is missing or invalid.
    """
    from src.evaluation.report import log_report_to_mlflow, write_report
    from src.evaluation.suites import emscad as emscad_suite
    from src.evaluation.suites import get_suite

    logger = get_logger(Components.SCRAPERS)
    if args.suite == "emscad" and args.part == "heldout":
        marker = emscad_suite.HELDOUT_USED_MARKER
        if marker.is_file():
            message = (
                f"Held-out EMSCAD already ran. Marker exists at {marker}. "
                "Do not run --part heldout again."
            )
            logger.error(message)
            print(message)
            return 1
    runner, default_dataset = get_suite(args.suite)
    dataset = Path(args.dataset) if args.dataset else default_dataset
    runner_kwargs = {}
    if args.suite == "emscad":
        runner_kwargs["part"] = args.part
    try:
        report = runner(dataset, **runner_kwargs)
    except (FileNotFoundError, ValueError) as exc:
        logger.error(f"Eval suite {args.suite} failed: {exc}")
        return 1

    path = write_report(report, Path(args.out) if args.out else None)
    print(f"Eval suite: {report.suite} ({report.metadata.case_count} cases)")
    print(f"Git SHA: {report.metadata.git_sha} (dirty: {report.metadata.git_dirty})")
    print(f"Dataset SHA-256: {report.metadata.dataset_sha256}")
    for key in sorted(report.metrics):
        value = report.metrics[key]
        print(f"  {key}: {'n/a' if value is None else round(value, 4)}")
    print(f"Report: {path}")

    if args.suite == "emscad" and args.part == "heldout":
        emscad_suite.write_heldout_used_marker(
            report, path, marker=emscad_suite.HELDOUT_USED_MARKER
        )

    if not args.no_mlflow:
        run_id = log_report_to_mlflow(report, path)
        print(f"MLflow run: {run_id}" if run_id else "MLflow run: not logged")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """
    Build the command-line parser.

    The parser has three commands, ``pipeline``, ``analyze``, and ``eval``,
    plus the top-level ``-i/--interactive`` flag. Logging options are shared by every
    command through a parent parser, so each option is defined one time.

    Returns:
        Configured argument parser.
    """
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level (default: INFO)",
    )
    common.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="Log file path (default: stdout only)",
    )

    parser = argparse.ArgumentParser(
        description="Job Raider - Automated Job Application Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Run in interactive mode",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Pipeline command
    pipeline_parser = subparsers.add_parser(
        "pipeline",
        parents=[common],
        help="Run the job application pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic search with dry run (dry run is the default)
  python main.py pipeline --resume my_resume.pdf --keywords "python engineer" --locations "New York" "Remote"

  # Stop after scoring
  python main.py pipeline --resume my_resume.pdf --keywords "software engineer" --locations "Singapore" --stop-at score_and_rank

  # Fresh graduate scoring
  python main.py pipeline --resume my_resume.pdf --keywords "python" --locations "Singapore" --fresh-grad

Each value after --keywords or --locations is one search term. Quote a
term that contains spaces.
        """,
    )
    pipeline_parser.add_argument(
        "--resume",
        type=str,
        required=True,
        help="Path to resume file (PDF or DOCX)",
    )
    pipeline_parser.add_argument(
        "--keywords",
        type=str,
        nargs="+",
        required=True,
        help="Job keywords to search for",
    )
    pipeline_parser.add_argument(
        "--locations",
        type=str,
        nargs="+",
        required=True,
        help="Job locations to search in",
    )
    pipeline_parser.add_argument(
        "--sources",
        type=str,
        nargs="+",
        choices=[source.value for source in available_sources()],
        help="Job sources to search (default: all available sources)",
    )
    pipeline_parser.add_argument(
        "--target-keywords",
        type=str,
        nargs="+",
        help="Additional target keywords for profile",
    )
    pipeline_parser.add_argument(
        "--target-locations",
        type=str,
        nargs="+",
        help="Additional target locations for profile",
    )
    pipeline_parser.add_argument(
        "--target-experience",
        type=str,
        nargs="+",
        choices=EXPERIENCE_CHOICES,
        help="Target experience levels",
    )
    pipeline_parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Run in dry-run mode (no actual submissions; default)",
    )
    pipeline_parser.add_argument(
        "--no-dry-run",
        action="store_false",
        dest="dry_run",
        help="Disable dry-run mode (actual submissions will be made)",
    )
    pipeline_parser.add_argument(
        "--skip-submission",
        action="store_true",
        help="Skip submission stage entirely",
    )
    pipeline_parser.add_argument(
        "--stop-at",
        type=str,
        choices=[s.value for s in PipelineStage],
        help="Stop pipeline at this stage",
    )
    pipeline_parser.add_argument(
        "--min-score",
        type=int,
        default=60,
        help="Minimum relevance score (0-100, default: 60)",
    )
    pipeline_parser.add_argument(
        "--scam-threshold",
        type=float,
        default=DEFAULT_SCAM_THRESHOLD,
        help="Scam detection threshold (0-1, default: shared DEFAULT_SCAM_THRESHOLD)",
    )
    pipeline_parser.add_argument(
        "--max-jobs",
        type=int,
        default=20,
        help="Maximum jobs to present for selection (default: 20)",
    )
    pipeline_parser.add_argument(
        "--fresh-grad",
        action="store_true",
        help="Score with fresh graduate weights (projects/education over experience)",
    )
    pipeline_parser.add_argument(
        "--submission-delay",
        type=float,
        default=2.0,
        help="Delay between submissions in seconds (default: 2.0)",
    )
    pipeline_parser.add_argument(
        "--max-submissions",
        type=int,
        default=30,
        help="Maximum submissions per hour (default: 30)",
    )
    pipeline_parser.add_argument(
        "--data-dir",
        type=str,
        default="data",
        help="Directory for data storage (default: data)",
    )
    pipeline_parser.add_argument(
        "--results-dir",
        type=str,
        default="data/results",
        help="Directory for results (default: data/results)",
    )

    # Analyze command
    analyze_parser = subparsers.add_parser(
        "analyze",
        parents=[common],
        help="Analyze a resume and provide insights",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # General resume analysis
  python main.py analyze --resume my_resume.pdf

  # Job-specific analysis
  python main.py analyze --resume my_resume.pdf --job job_description.txt

  # Save analysis to file
  python main.py analyze --resume my_resume.pdf --output analysis.json
        """,
    )
    analyze_parser.add_argument(
        "--resume", type=str, required=True, help="Path to resume file (PDF or DOCX)"
    )
    analyze_parser.add_argument(
        "--job", type=str, help="Path to job description file (optional)"
    )
    analyze_parser.add_argument("--output", type=str, help="Save analysis to JSON file")

    # Eval command
    eval_parser = subparsers.add_parser(
        "eval",
        parents=[common],
        help="Run an offline evaluation suite on a labeled dataset",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Score the cover-letter grounding validator on the committed labeled set
  python main.py eval grounding

  # Score the scam pipeline on the committed labeled set
  python main.py eval scam

  # Score the EMSCAD tuning part (local CSV; held-out is Stage B)
  python main.py eval emscad --part tuning

  # Use another dataset folder and write only the JSON report
  python main.py eval grounding --dataset path/to/set --no-mlflow
        """,
    )
    eval_parser.add_argument("suite", choices=SUITE_NAMES, help="Suite to run")
    eval_parser.add_argument(
        "--dataset",
        type=str,
        default=None,
        help="Dataset folder (default: the suite's set in tests/fixtures/eval)",
    )
    eval_parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Report folder (default: apps/backend-py/data/eval)",
    )
    eval_parser.add_argument(
        "--no-mlflow",
        action="store_true",
        help="Write the JSON report only; do not log an MLflow run",
    )
    eval_parser.add_argument(
        "--part",
        choices=("tuning", "heldout"),
        default="tuning",
        help="EMSCAD part (emscad only; default: tuning)",
    )

    return parser


def with_default_command(argv: List[str]) -> List[str]:
    """
    Insert the default ``pipeline`` command when no command is given.

    ``pipeline`` is the default command, so ``main.py --resume r.pdf ...``
    works the same as ``main.py pipeline --resume r.pdf ...``. Help and
    interactive mode keep their top-level meaning.

    Args:
        argv: Command-line arguments without the program name.

    Returns:
        Arguments with ``pipeline`` first when the first argument is a
        pipeline option.
    """
    top_level = {"-h", "--help", "-i", "--interactive"}
    if argv and argv[0].startswith("-") and argv[0] not in top_level:
        return ["pipeline", *argv]
    return argv


def main(argv: Optional[List[str]] = None) -> int:
    """
    Main entry point.

    Args:
        argv: Command-line arguments without the program name. ``None``
            reads ``sys.argv``.

    Returns:
        Exit code
    """
    parser = build_parser()
    raw_argv = sys.argv[1:] if argv is None else argv
    args = parser.parse_args(with_default_command(raw_argv))

    # Setup logging
    log_level = getattr(args, "log_level", "INFO")
    log_dir = Path("data/logs")
    setup_logging(log_level=log_level, log_dir=log_dir)
    logger = get_logger(Components.SCRAPERS)

    # Route to appropriate command
    if args.interactive:
        return interactive_mode()

    if args.command == "analyze":
        return run_analyze_command(args)

    if args.command == "eval":
        return run_eval_command(args)

    if args.command != "pipeline":
        parser.error(
            "choose a command (pipeline, analyze, or eval), or use --interactive"
        )

    # Verify resume exists
    if not Path(args.resume).exists():
        logger.error(f"Resume not found: {args.resume}")
        return 1

    return run_pipeline(args)


if __name__ == "__main__":
    sys.exit(main())
