"""
Job Raider - Company Site Cache

Per-job cache of company site results and the service that serves them.
A cached result is reused until the user asks for a refresh.

Author: Job Raider
Date: 2026-11-20
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Union

from ..utils.logger import Components, get_logger
from .company_site import CompanySiteResult, find_company_site

logger = get_logger(Components.SCRAPERS)

DEFAULT_CACHE_DIR = Path("data/company_sites")
_SAFE_ID = re.compile(r"[A-Za-z0-9_-]{1,80}")


class CompanySiteCache:
    """File cache with one JSON file per job."""

    def __init__(self, directory: Union[str, Path] = DEFAULT_CACHE_DIR) -> None:
        """
        Create the cache folder if it does not exist.

        Args:
            directory: Folder that holds the cache files.
        """
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def path_for(self, job_id: str) -> Path:
        """
        Return the cache file for a job.

        Job IDs that are not plain, short names are hashed, so a job ID can
        never point outside the cache folder.

        Args:
            job_id: Job ID from the catalog.

        Returns:
            Path of the JSON file inside the cache folder.
        """
        if _SAFE_ID.fullmatch(job_id):
            key = job_id
        else:
            key = hashlib.sha256(job_id.encode("utf-8")).hexdigest()[:32]
        return self.directory / f"{key}.json"

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Read a cached result.

        Args:
            job_id: Job ID from the catalog.

        Returns:
            The cached payload, or None when missing or unreadable.
        """
        path = self.path_for(job_id)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            logger.warning("Ignoring unreadable company site cache %s: %s", path, exc)
            return None
        return payload if isinstance(payload, dict) else None

    def put(self, job_id: str, payload: Dict[str, Any]) -> None:
        """
        Store a result for a job, replacing any earlier one.

        Args:
            job_id: Job ID from the catalog.
            payload: JSON-ready result dict.
        """
        self.path_for(job_id).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def get_company_site(
    job_id: str,
    company: str,
    job_title: str,
    *,
    refresh: bool = False,
    cache: Optional[CompanySiteCache] = None,
    finder: Callable[..., CompanySiteResult] = find_company_site,
) -> Dict[str, Any]:
    """
    Return the company site result for a job, from the cache when possible.

    Args:
        job_id: Job ID from the catalog.
        company: Company name from the listing.
        job_title: Job title from the listing.
        refresh: When True, search again even if a result is cached.
        cache: Cache to use; the default folder when None.
        finder: Finder function (injected for tests).

    Returns:
        Result dict with a ``cached`` flag.
    """
    store = cache if cache is not None else CompanySiteCache()
    if not refresh:
        cached = store.get(job_id)
        if cached is not None:
            return {**cached, "cached": True}
    payload = finder(company, job_title).to_dict()
    if _is_real_outcome(payload):
        store.put(job_id, payload)
    return {**payload, "cached": False}


def _is_real_outcome(payload: Dict[str, Any]) -> bool:
    """
    Tell whether a finder result is a real answer that may be cached.

    A failed search is not an answer. A "none" where every fetched candidate
    page failed to load checked nothing, so it is not an answer either.

    Args:
        payload: Result dict from the finder.

    Returns:
        True when the result may be cached.
    """
    if payload.get("search_failed"):
        return False
    if payload.get("level") == "none" and int(payload.get("pages_attempted", 0)) > 0:
        return int(payload.get("pages_loaded", 0)) > 0
    return True
