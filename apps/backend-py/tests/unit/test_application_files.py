"""
Unit tests for the application files endpoints (company-site-apply, S2).

The tailored CV (PDF and DOCX) and the saved cover letter are served only
from fixed file names inside the results folder. Job IDs are checked, so a
request cannot point outside that folder.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.submission.application_files import (
    application_file_path,
    list_application_files,
)


@pytest.fixture
def results(tmp_path: Path) -> Path:
    """
    Results folder with the files of job-1 and nothing for job-2.

    Args:
        tmp_path: Pytest temp directory.

    Returns:
        The results folder.
    """
    (tmp_path / "resumes").mkdir()
    (tmp_path / "cover_letters").mkdir()
    (tmp_path / "resumes" / "job-1.pdf").write_bytes(b"%PDF-1.4 test")
    (tmp_path / "resumes" / "job-1.docx").write_bytes(b"PK docx test")
    (tmp_path / "cover_letters" / "job-1.txt").write_text(
        "Dear Hiring Manager", encoding="utf-8"
    )
    return tmp_path


@pytest.fixture
def client(results: Path):
    """
    FastAPI client with the results folder pointed at the temp folder.

    Args:
        results: Temp results folder.

    Yields:
        A TestClient with API auth disabled.
    """
    with patch("src.api.routes.jobs._results_root", lambda: results):
        from src.api.auth import verify_api_key
        from src.api.main import app

        app.dependency_overrides[verify_api_key] = lambda: None
        yield TestClient(app, raise_server_exceptions=False)
        app.dependency_overrides.clear()


def test_list_reports_which_files_exist(results: Path) -> None:
    """Each kind is reported as available only when its file exists.

    Args:
        results: Temp results folder.
    """
    files = {f["kind"]: f for f in list_application_files(results, "job-1")}
    assert files["cv_pdf"]["available"] is True
    assert files["cv_docx"]["available"] is True
    assert files["cover_letter"]["available"] is True
    none_yet = list_application_files(results, "job-2")
    assert all(f["available"] is False for f in none_yet)


def test_unsafe_job_id_has_no_path(results: Path) -> None:
    """A job ID with path characters never resolves to a file.

    Args:
        results: Temp results folder.
    """
    assert application_file_path(results, "../job-1", "cv_pdf") is None
    assert application_file_path(results, "job-1/../../x", "cover_letter") is None


def test_unknown_kind_has_no_path(results: Path) -> None:
    """Only the three known kinds resolve to a file.

    Args:
        results: Temp results folder.
    """
    assert application_file_path(results, "job-1", "exe") is None


def test_list_route_gives_download_paths(client: TestClient) -> None:
    """The list endpoint reports availability and a download path per kind.

    Args:
        client: API test client.
    """
    response = client.get("/api/jobs/job-1/application-files")
    assert response.status_code == 200
    files = {f["kind"]: f for f in response.json()["files"]}
    assert files["cv_pdf"]["available"] is True
    assert files["cv_pdf"]["download_path"] == ("/jobs/job-1/application-files/cv_pdf")


def test_download_returns_the_cover_letter(client: TestClient) -> None:
    """A saved cover letter is served as an attachment.

    Args:
        client: API test client.
    """
    response = client.get("/api/jobs/job-1/application-files/cover_letter")
    assert response.status_code == 200
    assert response.content == b"Dear Hiring Manager"
    assert response.headers["content-disposition"].startswith("attachment")


def test_missing_file_is_404(client: TestClient) -> None:
    """A file that was not generated gives 404.

    Args:
        client: API test client.
    """
    response = client.get("/api/jobs/job-2/application-files/cv_pdf")
    assert response.status_code == 404


def test_unknown_kind_route_is_404(client: TestClient) -> None:
    """An unknown kind gives 404.

    Args:
        client: API test client.
    """
    response = client.get("/api/jobs/job-1/application-files/exe")
    assert response.status_code == 404
