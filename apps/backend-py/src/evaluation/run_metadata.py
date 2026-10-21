"""
Metadata that makes an evaluation run reproducible (Step 3.1).

Each run records the git commit (and whether tracked files had changes),
the dataset hash, and the model parameters, so a reported number can be
traced to the exact code and data that produced it.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence, Tuple

from pydantic import BaseModel

from ..utils.logger import Components, get_logger
from .datasets import dataset_sha256

logger = get_logger(Components.SCRAPERS)

BACKEND_DIR = Path(__file__).resolve().parents[2]


class RunMetadata(BaseModel):
    """Code, data, and parameters of one evaluation run."""

    suite: str
    git_sha: str
    git_dirty: Optional[bool]
    dataset_sha256: str
    case_count: int
    started_at: datetime
    prompt_sha256: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    seed: Optional[int] = None


def collect_git_state(repo_dir: Path) -> Tuple[str, Optional[bool]]:
    """
    Read the current commit and whether tracked files have changes.

    The two reads are separate. ``git rev-parse`` is fast. ``git status``
    checks every tracked file and can take many seconds on a slow mount
    (for example ``/mnt/d`` in WSL), so when it fails or times out the SHA
    is kept and only the dirty flag is unknown.

    Args:
        repo_dir: Any directory inside the repository.

    Returns:
        ``(sha, dirty)``. ``sha`` is ``"unknown"`` when git or the repository
        is not available (for example in a container without ``.git``).
        ``dirty`` is None when it cannot be determined.
    """
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown", None
    try:
        # --no-optional-locks: read only. A plain ``git status`` refreshes the
        # index under ``.git/index.lock``; killed at the timeout, it leaves a
        # stale lock that blocks every later git command in the repository.
        status = subprocess.run(
            [
                "git",
                "--no-optional-locks",
                "status",
                "--porcelain",
                "--untracked-files=no",
            ],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=True,
            timeout=120,
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("Could not read git status for run metadata: %s", exc)
        return sha, None
    return sha, bool(status.strip())


def build_run_metadata(
    suite: str,
    dataset_paths: Sequence[Path],
    case_count: int,
    *,
    prompt_sha256: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    seed: Optional[int] = None,
    repo_dir: Optional[Path] = None,
) -> RunMetadata:
    """
    Collect the metadata for one evaluation run.

    Args:
        suite: Suite name, for example ``grounding``.
        dataset_paths: Files that make up the dataset.
        case_count: Number of cases in the run.
        prompt_sha256: Hash of the prompt templates, when the suite uses an LLM.
        model: Model name, when the suite uses a model.
        temperature: Sampling temperature, when the suite uses an LLM.
        seed: Random seed, when the suite samples or splits data.
        repo_dir: Directory for git commands; defaults to the backend folder.

    Returns:
        Run metadata with a UTC start time.
    """
    git_sha, git_dirty = collect_git_state(repo_dir or BACKEND_DIR)
    return RunMetadata(
        suite=suite,
        git_sha=git_sha,
        git_dirty=git_dirty,
        dataset_sha256=dataset_sha256(*dataset_paths),
        case_count=case_count,
        started_at=datetime.now(timezone.utc),
        prompt_sha256=prompt_sha256,
        model=model,
        temperature=temperature,
        seed=seed,
    )
