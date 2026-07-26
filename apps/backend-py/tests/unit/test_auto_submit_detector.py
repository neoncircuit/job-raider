"""
Unit tests for AutoSubmitDetector URL handling.
"""

from pydantic import HttpUrl

from src.models.job_listing import JobListing, JobSource
from src.submission.detector import AutoSubmitDetector


class TestAutoSubmitDetectorHttpUrl:
    """HttpUrl source_url must not crash external-ATS detection."""

    def test_httpurl_source_does_not_raise(self):
        """
        Pydantic HttpUrl lacks .lower(); detector must coerce to str.
        """
        job = JobListing(
            job_id="job-1",
            title="Engineer",
            company="Acme",
            source=JobSource.LINKEDIN,
            source_url=HttpUrl("https://boards.greenhouse.io/acme/jobs/123"),
        )
        detector = AutoSubmitDetector()
        info = detector.detect_submission_method(job)
        assert info.apply_method.value == "external_site"

    def test_string_url_still_works(self):
        """Plain string URLs keep working for ATS detection."""
        detector = AutoSubmitDetector()
        assert detector._is_external_application("https://jobs.lever.co/acme/abc")
        assert not detector._is_external_application(
            "https://www.linkedin.com/jobs/view/123"
        )
