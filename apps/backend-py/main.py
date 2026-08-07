#!/usr/bin/env python3
"""
Job Raider - Automated Job Application Pipeline

A command-line interface for automated job searching, filtering,
and application generation.

Author: Job Raider
Date: 2026-04-21
"""

import argparse
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
                    print(f"✗ Installation failed:")
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
                    print(f"✗ Installation failed:")
                    print(result.stderr)
                    sys.exit(1)
        except Exception as e:
            print(f"✗ Failed to install dependencies: {e}")
            sys.exit(1)
    else:
        print("✓ All dependencies satisfied")

    # Install Playwright browsers if needed
    try:
        from playwright.sync_api import sync_playwright

        # Just check if we can import, browsers will be downloaded on first use
        pass
    except ImportError:
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
        print(f"Switching to virtual environment...")
        print()
        os.execv(str(venv_python), [str(venv_python)] + sys.argv)

    return True


# Ensure dependencies before importing anything else
# When running as main, check deps before imports to auto-create venv
if __name__ == "__main__":
    ensure_dependencies()

from src.extractors.resume_parser import ResumeParser
from src.generation.resume_analyzer import ResumeAnalyzer
from src.llm.router import LLMRouter
from src.models.job_listing import JobListing
from src.models.user_profile import UserProfile
from src.pipeline.orchestrator import (
    PipelineConfig,
    PipelineOrchestrator,
    PipelineStage,
)
from src.utils.logger import Components, get_logger, setup_logging


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
    profile = parser.parse(resume_path)

    logger.info(f"Loaded profile for: {profile.contact_info.name}")
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
            profile.target_job.keywords.extend(args.target_keywords)
        if args.target_locations:
            profile.target_job.locations.extend(args.target_locations)
        if args.target_experience:
            from src.models.user_profile import ExperienceLevel

            profile.target_job.experience_levels = [
                ExperienceLevel(exp) for exp in args.target_experience
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
            start_from=(
                PipelineStage(args.start_from)
                if args.start_from
                else PipelineStage.SCRAPE
            ),
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
        locations = [l.strip() for l in locations_input.split(",") if l.strip()]

        sources_input = input(
            "Enter sources to search (linkedin,jsearch or blank for all): "
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
        # Parse resume
        logger.info(f"Parsing resume from: {args.resume}")
        parser = ResumeParser()
        profile = parser.parse(args.resume)

        # Verify resume exists
        if not Path(args.resume).exists():
            logger.error(f"Resume not found: {args.resume}")
            return 1

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
            import json
            from pathlib import Path

            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "w") as f:
                json.dump(analysis.model_dump(), f, indent=2, default=str)

            logger.info(f"Analysis saved to: {args.output}")

        return 0

    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}", exc_info=True)
        return 1


def main() -> int:
    """
    Main entry point.

    Returns:
        Exit code
    """
    parser = argparse.ArgumentParser(
        description="Job Raider - Automated Job Application Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Pipeline command (default behavior)
    pipeline_parser = subparsers.add_parser(
        "pipeline",
        help="Run the job application pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic search with dry run
  python main.py pipeline --resume my_resume.pdf --keywords "python engineer" --locations "new york remote"

  # Full pipeline with submission
  python main.py pipeline --resume my_resume.pdf --keywords "fintech AI" --locations "remote" --no-dry-run

  # Resume from specific stage
  python main.py pipeline --resume my_resume.pdf --keywords "SWE" --start-from score_and_rank

  # Run only specific stages
  python main.py pipeline --resume my_resume.pdf --keywords "python" --start-from generate_resumes --stop-at submit_applications
        """,
    )

    # Analyze command
    analyze_parser = subparsers.add_parser(
        "analyze",
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

    # Interactive mode
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Run in interactive mode",
    )

    # Pipeline arguments
    pipeline_parser.add_argument(
        "--resume",
        type=str,
        help="Path to resume file (PDF or DOCX)",
    )
    pipeline_parser.add_argument(
        "--keywords", type=str, nargs="+", help="Job keywords to search for"
    )
    pipeline_parser.add_argument(
        "--locations", type=str, nargs="+", help="Job locations to search in"
    )
    pipeline_parser.add_argument(
        "--sources",
        type=str,
        nargs="+",
        choices=["linkedin", "jsearch"],
        help="Job sources to search (default: all)",
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
        choices=["entry", "mid", "senior", "lead", "executive"],
        help="Target experience levels",
    )
    pipeline_parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Run in dry-run mode (no actual submissions)",
    )
    pipeline_parser.add_argument(
        "--no-dry-run",
        action="store_false",
        dest="dry_run",
        help="Disable dry-run mode",
    )
    pipeline_parser.add_argument(
        "--skip-submission", action="store_true", help="Skip submission stage entirely"
    )
    pipeline_parser.add_argument(
        "--start-from",
        type=str,
        choices=[s.value for s in PipelineStage],
        help="Resume pipeline from this stage",
    )
    pipeline_parser.add_argument(
        "--stop-at",
        type=str,
        choices=[s.value for s in PipelineStage],
        help="Stop pipeline at this stage",
    )
    pipeline_parser.add_argument(
        "--min-score", type=int, default=60, help="Minimum relevance score (0-100)"
    )
    pipeline_parser.add_argument(
        "--scam-threshold",
        type=float,
        default=0.7,
        help="Scam detection threshold (0-1)",
    )
    pipeline_parser.add_argument(
        "--max-jobs", type=int, default=20, help="Maximum jobs to present"
    )
    pipeline_parser.add_argument(
        "--submission-delay",
        type=float,
        default=2.0,
        help="Delay between submissions (seconds)",
    )
    pipeline_parser.add_argument(
        "--max-submissions", type=int, default=30, help="Maximum submissions per hour"
    )
    pipeline_parser.add_argument(
        "--data-dir", type=str, default="data", help="Directory for data storage"
    )
    pipeline_parser.add_argument(
        "--results-dir", type=str, default="data/results", help="Directory for results"
    )
    pipeline_parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level",
    )
    pipeline_parser.add_argument("--log-file", type=str, help="Log file path")

    # Analyze arguments
    analyze_parser.add_argument(
        "--resume", type=str, required=True, help="Path to resume file (PDF or DOCX)"
    )
    analyze_parser.add_argument(
        "--job", type=str, help="Path to job description file (optional)"
    )
    analyze_parser.add_argument("--output", type=str, help="Save analysis to JSON file")
    analyze_parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level",
    )

    # Parse arguments
    args = parser.parse_args()

    # Mode
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Run in interactive mode",
    )

    # Required for non-interactive
    parser.add_argument(
        "--resume",
        type=str,
        help="Path to resume file (PDF or DOCX)",
    )

    # Search parameters
    parser.add_argument(
        "--keywords",
        type=str,
        nargs="+",
        help="Job keywords to search for",
    )
    parser.add_argument(
        "--locations",
        type=str,
        nargs="+",
        help="Job locations to search in",
    )
    parser.add_argument(
        "--sources",
        type=str,
        nargs="+",
        choices=["linkedin", "jsearch"],
        help="Job sources to search (default: all)",
    )

    # Profile overrides
    parser.add_argument(
        "--target-keywords",
        type=str,
        nargs="+",
        help="Additional target keywords for profile",
    )
    parser.add_argument(
        "--target-locations",
        type=str,
        nargs="+",
        help="Additional target locations for profile",
    )
    parser.add_argument(
        "--target-experience",
        type=str,
        nargs="+",
        choices=["entry", "mid", "senior", "lead", "executive"],
        help="Target experience levels",
    )

    # Pipeline options
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Run in dry-run mode (no actual submissions)",
    )
    parser.add_argument(
        "--no-dry-run",
        action="store_false",
        dest="dry_run",
        help="Disable dry-run mode (actual submissions will be made)",
    )
    parser.add_argument(
        "--skip-submission",
        action="store_true",
        help="Skip submission stage entirely",
    )
    parser.add_argument(
        "--start-from",
        type=str,
        choices=[s.value for s in PipelineStage],
        help="Resume pipeline from this stage",
    )
    parser.add_argument(
        "--stop-at",
        type=str,
        choices=[s.value for s in PipelineStage],
        help="Stop pipeline at this stage",
    )

    # Scoring options
    parser.add_argument(
        "--min-score",
        type=int,
        default=60,
        help="Minimum relevance score (0-100, default: 60)",
    )
    parser.add_argument(
        "--scam-threshold",
        type=float,
        default=0.7,
        help="Scam detection threshold (0-1, default: 0.7)",
    )
    parser.add_argument(
        "--max-jobs",
        type=int,
        default=20,
        help="Maximum jobs to present for selection (default: 20)",
    )

    # Submission options
    parser.add_argument(
        "--submission-delay",
        type=float,
        default=2.0,
        help="Delay between submissions in seconds (default: 2.0)",
    )
    parser.add_argument(
        "--max-submissions",
        type=int,
        default=30,
        help="Maximum submissions per hour (default: 30)",
    )

    # Storage options
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data",
        help="Directory for data storage (default: data)",
    )
    parser.add_argument(
        "--results-dir",
        type=str,
        default="data/results",
        help="Directory for results (default: data/results)",
    )

    # Logging options
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level (default: INFO)",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="Log file path (default: stdout only)",
    )

    # Parse arguments
    args = parser.parse_args()

    # Self-healing: Ensure dependencies are installed before running
    # This provides a pnpm-dev-like experience where missing deps are auto-installed
    ensure_dependencies()

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

    # Default to pipeline command
    if args.command == "pipeline" or args.command is None:
        # Validate pipeline arguments
        if not args.resume:
            parser.error("--resume is required for pipeline command")

        if not args.keywords:
            parser.error("--keywords is required for pipeline command")

    if not args.locations:
        parser.error("--locations is required unless using --interactive mode")

    # Verify resume exists
    if not Path(args.resume).exists():
        logger.error(f"Resume not found: {args.resume}")
        return 1

    # Run pipeline
    return run_pipeline(args)


if __name__ == "__main__":
    sys.exit(main())
