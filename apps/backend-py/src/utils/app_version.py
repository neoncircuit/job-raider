"""
Job Raider application version helpers.

The monorepo root ``VERSION`` file is the single source of truth for the
product version (semver). Docker images copy that file to ``/app/VERSION``.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

_FALLBACK = "0.0.0-dev"


def _candidate_version_paths() -> list[Path]:
    """
    Build ordered paths that may contain the product VERSION file.

    Returns:
        Candidate paths from env override, Docker layout, and repo layout.
    """
    paths: list[Path] = []
    env_path = os.environ.get("JOB_RAIDER_VERSION_FILE", "").strip()
    if env_path:
        paths.append(Path(env_path))

    paths.append(Path("/app/VERSION"))

    # main.py lives at apps/backend-py/src/api/main.py → repo root is parents[4]
    here = Path(__file__).resolve()
    for parent in here.parents:
        paths.append(parent / "VERSION")

    cwd = Path.cwd()
    paths.append(cwd / "VERSION")
    for parent in cwd.parents:
        paths.append(parent / "VERSION")

    return paths


@lru_cache(maxsize=1)
def get_app_version() -> str:
    """
    Read the product semver from the root VERSION file.

    Args:
        None.

    Returns:
        Semver string such as ``0.1.0``, or ``0.0.0-dev`` when no file is found.
    """
    for path in _candidate_version_paths():
        try:
            if path.is_file():
                text = path.read_text(encoding="utf-8").strip()
                if text:
                    return text.splitlines()[0].strip()
        except OSError:
            continue
    return _FALLBACK


def clear_app_version_cache() -> None:
    """
    Clear the cached version string (for tests).

    Returns:
        None.
    """
    get_app_version.cache_clear()
