"""
Job Raider - Application Files

Paths of the generated application files for a job: the tailored CV (PDF and
DOCX) and the saved cover letter. The pipeline writes them to the results
folder with fixed names, ``resumes/<job_id>.pdf``, ``resumes/<job_id>.docx``,
and ``cover_letters/<job_id>.txt``.

Author: Job Raider
Date: 2026-11-20
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

DEFAULT_RESULTS_DIR = Path("data/results")
_SAFE_JOB_ID = re.compile(r"[A-Za-z0-9_-]{1,80}")

APPLICATION_FILE_KINDS: Dict[str, Dict[str, str]] = {
    "cv_pdf": {"subdir": "resumes", "suffix": ".pdf", "label": "CV (PDF)"},
    "cv_docx": {"subdir": "resumes", "suffix": ".docx", "label": "CV (DOCX)"},
    "cover_letter": {
        "subdir": "cover_letters",
        "suffix": ".txt",
        "label": "Cover letter",
    },
}


def application_file_path(
    results_dir: Union[str, Path],
    job_id: str,
    kind: str,
) -> Optional[Path]:
    """
    Return the path of a generated application file, when it exists.

    Args:
        results_dir: Pipeline results folder.
        job_id: Job ID. Only plain IDs (letters, digits, dash, underscore)
            are accepted, so a request cannot point outside the folder.
        kind: One of the keys of ``APPLICATION_FILE_KINDS``.

    Returns:
        The file path, or None when the kind is unknown, the job ID is not
        plain, or the file does not exist.
    """
    spec = APPLICATION_FILE_KINDS.get(kind)
    if spec is None or not _SAFE_JOB_ID.fullmatch(job_id):
        return None
    path = Path(results_dir) / spec["subdir"] / f"{job_id}{spec['suffix']}"
    return path if path.is_file() else None


def list_application_files(
    results_dir: Union[str, Path],
    job_id: str,
) -> List[Dict[str, Any]]:
    """
    List the application file kinds for a job, with availability.

    Args:
        results_dir: Pipeline results folder.
        job_id: Job ID.

    Returns:
        One dict per kind with kind, label, filename, available, and the
        API path to download it.
    """
    files: List[Dict[str, Any]] = []
    for kind, spec in APPLICATION_FILE_KINDS.items():
        files.append(
            {
                "kind": kind,
                "label": spec["label"],
                "filename": f"{job_id}{spec['suffix']}",
                "available": application_file_path(results_dir, job_id, kind)
                is not None,
                "download_path": f"/jobs/{job_id}/application-files/{kind}",
            }
        )
    return files
