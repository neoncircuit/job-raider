"""
Unit tests for JD document text extraction and POST /api/cover-letter/parse-jd.

Covers happy-path PDF/DOCX extract, unsupported types, and empty-extract warnings.
Fixtures are generated in-memory (no LLM).

Author: Job Raider
Date: 2026-08-20
"""

from __future__ import annotations

import io

import pytest
from docx import Document
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from reportlab.pdfgen import canvas

from src.extractors.jd_document import (
    MIN_USEFUL_CHARS,
    extract_jd_document,
    is_supported_jd_filename,
)


def _make_docx_bytes(text: str) -> bytes:
    """Build a minimal DOCX containing ``text``.

    Args:
        text: Paragraph body to embed.

    Returns:
        Raw DOCX bytes.
    """
    buffer = io.BytesIO()
    doc = Document()
    doc.add_paragraph(text)
    doc.save(buffer)
    return buffer.getvalue()


def _make_pdf_bytes(text: str) -> bytes:
    """Build a minimal single-page PDF with a text layer via reportlab.

    Args:
        text: Text to draw on the page.

    Returns:
        Raw PDF bytes.
    """
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer)
    y = 750
    for line in text.splitlines() or [text]:
        c.drawString(72, y, line[:100])
        y -= 14
    c.save()
    return buffer.getvalue()


def _make_empty_pdf_bytes() -> bytes:
    """Build a PDF with no text layer.

    Returns:
        Raw PDF bytes from a blank page.
    """
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


SAMPLE_JD = (
    "Senior Software Engineer at Acme Corp. "
    "Requirements: 5+ years Python and FastAPI experience. "
    "Build scalable APIs and mentor junior engineers."
)


class TestJdDocumentExtractor:
    """Unit tests for the pure extractor helpers."""

    def test_supported_extensions_case_insensitive(self) -> None:
        """PDF and DOCX extensions are accepted regardless of case."""
        assert is_supported_jd_filename("jd.PDF") is True
        assert is_supported_jd_filename("role.Docx") is True
        assert is_supported_jd_filename("role.doc") is False
        assert is_supported_jd_filename("role.txt") is False

    def test_extract_docx_happy_path(self) -> None:
        """DOCX bytes yield the embedded paragraph text."""
        data = _make_docx_bytes(SAMPLE_JD)
        result = extract_jd_document(data, "sample.docx")
        assert SAMPLE_JD in result.text
        assert result.filename == "sample.docx"
        assert result.char_count == len(result.text)
        assert result.warnings == []

    def test_extract_pdf_happy_path(self) -> None:
        """PDF with a text layer yields readable content."""
        data = _make_pdf_bytes(SAMPLE_JD)
        result = extract_jd_document(data, "sample.pdf")
        # reportlab may wrap or truncate; require key tokens, not exact match.
        assert "Senior Software Engineer" in result.text or "Acme" in result.text
        assert result.char_count == len(result.text)
        if result.char_count >= MIN_USEFUL_CHARS:
            assert result.warnings == []

    def test_extract_empty_pdf_warns(self) -> None:
        """Blank PDF returns empty text and a scanned/no-text-layer warning."""
        data = _make_empty_pdf_bytes()
        result = extract_jd_document(data, "scanned.pdf")
        assert result.text == ""
        assert result.char_count == 0
        assert result.warnings
        assert any(
            "scanned" in w.lower() or "text layer" in w.lower() for w in result.warnings
        )

    def test_unsupported_extension_raises(self) -> None:
        """Non-PDF/DOCX filenames raise ValueError."""
        with pytest.raises(ValueError, match="Unsupported"):
            extract_jd_document(b"not-a-real-file", "notes.txt")


class TestParseJdRoute:
    """API tests for POST /api/cover-letter/parse-jd."""

    @pytest.fixture
    def client(self) -> TestClient:
        """FastAPI TestClient with server exceptions suppressed."""
        from src.api.main import app

        return TestClient(app, raise_server_exceptions=False)

    def test_parse_docx_happy_path(self, client: TestClient) -> None:
        """Upload DOCX returns text and no generate side effects."""
        data = _make_docx_bytes(SAMPLE_JD)
        resp = client.post(
            "/api/cover-letter/parse-jd",
            files={
                "file": (
                    "jd.docx",
                    data,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert SAMPLE_JD in body["text"]
        assert body["filename"] == "jd.docx"
        assert body["char_count"] == len(body["text"])
        assert body["warnings"] == []

    def test_parse_pdf_happy_path(self, client: TestClient) -> None:
        """Upload PDF returns extracted text JSON."""
        data = _make_pdf_bytes(SAMPLE_JD)
        resp = client.post(
            "/api/cover-letter/parse-jd",
            files={"file": ("jd.pdf", data, "application/pdf")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["filename"] == "jd.pdf"
        assert "text" in body
        assert "char_count" in body
        assert isinstance(body["warnings"], list)

    def test_unsupported_type_400(self, client: TestClient) -> None:
        """Unsupported extension is rejected with 400."""
        resp = client.post(
            "/api/cover-letter/parse-jd",
            files={"file": ("notes.txt", b"hello world", "text/plain")},
        )
        assert resp.status_code == 400
        body = resp.json()
        message = body.get("detail") or body.get("message") or ""
        assert "PDF" in message or "DOCX" in message

    def test_empty_pdf_returns_200_with_warning(self, client: TestClient) -> None:
        """Empty extract still returns 200 with warning, never invented text."""
        data = _make_empty_pdf_bytes()
        resp = client.post(
            "/api/cover-letter/parse-jd",
            files={"file": ("empty.pdf", data, "application/pdf")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["text"] == ""
        assert body["char_count"] == 0
        assert body["warnings"]
