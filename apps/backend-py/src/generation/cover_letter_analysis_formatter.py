"""
Job Raider - Cover Letter Analysis Export Formatter

Renders a structured cover-letter analysis export as JSON or a
human-readable PDF. Reuses reportlab (same stack as letter PDF export).

Author: Job Raider
Date: 2026-08-25
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from xml.sax.saxutils import escape

try:
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

from ..utils.logger import Components, get_logger

logger = get_logger(Components.GENERATION)

JD_SNIPPET_MAX = 500


@dataclass
class AnalysisExportResult:
    """
    Result of an analysis export attempt.

    Attributes:
        path: Path to the generated file, or None.
        success: Whether export succeeded.
        errors: Human-readable errors.
        media_type: MIME type for the response.
        download_name: Suggested download filename.
    """

    path: Optional[str] = None
    success: bool = False
    errors: List[str] = field(default_factory=list)
    media_type: str = "application/json"
    download_name: str = "cover_letter_analysis.json"


def jd_snippet(description: str, max_chars: int = JD_SNIPPET_MAX) -> str:
    """
    Truncate a job description for export payloads.

    Args:
        description: Full JD text.
        max_chars: Maximum characters to keep.

    Returns:
        Truncated snippet with an ellipsis when shortened.
    """
    text = (description or "").strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def _escape(text: str) -> str:
    """
    Escape text for reportlab Paragraph XML.

    Args:
        text: Raw text.

    Returns:
        XML-safe string with newlines converted to ``<br/>``.
    """
    return escape(text or "").replace("\n", "<br/>")


class CoverLetterAnalysisFormatter:
    """
    Export a cover-letter analysis payload as JSON or PDF.
    """

    def __init__(self, output_dir: Optional[str] = None):
        """
        Initialize the formatter.

        Args:
            output_dir: Directory for exported files. Defaults to
                ``data/outputs`` under the backend package root.
        """
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            base_dir = Path(__file__).resolve().parents[3]
            self.output_dir = base_dir / "data" / "outputs"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export(
        self,
        payload: Dict[str, Any],
        filename: str,
        export_format: str,
    ) -> AnalysisExportResult:
        """
        Write the analysis payload to JSON or PDF.

        Args:
            payload: Structured analysis dict (schema versioned).
            filename: Base filename without extension.
            export_format: ``json`` or ``pdf``.

        Returns:
            ``AnalysisExportResult`` with path and media type.
        """
        fmt = (export_format or "json").lower().strip()
        result = AnalysisExportResult()
        if fmt == "json":
            return self._export_json(payload, filename, result)
        if fmt == "pdf":
            return self._export_pdf(payload, filename, result)
        result.errors.append("format must be 'json' or 'pdf'")
        return result

    def _export_json(
        self,
        payload: Dict[str, Any],
        filename: str,
        result: AnalysisExportResult,
    ) -> AnalysisExportResult:
        """
        Write pretty-printed JSON for diff-friendly model-run compares.

        Args:
            payload: Analysis dict.
            filename: Base filename.
            result: Mutable result object.

        Returns:
            Filled ``AnalysisExportResult``.
        """
        filepath = self.output_dir / f"{filename}.json"
        try:
            filepath.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            result.path = str(filepath)
            result.success = True
            result.media_type = "application/json"
            result.download_name = filepath.name
            logger.info("Generated cover-letter analysis JSON: %s", filepath)
        except Exception as exc:
            message = f"JSON export failed: {exc}"
            result.errors.append(message)
            logger.error(message)
        return result

    def _export_pdf(
        self,
        payload: Dict[str, Any],
        filename: str,
        result: AnalysisExportResult,
    ) -> AnalysisExportResult:
        """
        Write a human-readable analysis PDF via reportlab.

        Args:
            payload: Analysis dict.
            filename: Base filename.
            result: Mutable result object.

        Returns:
            Filled ``AnalysisExportResult``.
        """
        if not REPORTLAB_AVAILABLE:
            result.errors.append("PDF generation unavailable: reportlab not installed")
            return result

        filepath = self.output_dir / f"{filename}.pdf"
        try:
            self._build_pdf(payload, filepath)
            result.path = str(filepath)
            result.success = True
            result.media_type = "application/pdf"
            result.download_name = filepath.name
            logger.info("Generated cover-letter analysis PDF: %s", filepath)
        except Exception as exc:
            message = f"PDF export failed: {exc}"
            result.errors.append(message)
            logger.error(message)
        return result

    def _build_pdf(self, payload: Dict[str, Any], filepath: Path) -> None:
        """
        Build the analysis PDF story.

        Args:
            payload: Analysis dict.
            filepath: Destination PDF path.
        """
        doc = SimpleDocTemplate(
            str(filepath),
            pagesize=LETTER,
            leftMargin=0.75 * inch,
            rightMargin=0.75 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
        )
        styles = getSampleStyleSheet()
        normal = ParagraphStyle(
            "AnalysisBody",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=13,
            spaceAfter=4,
        )
        title_style = ParagraphStyle(
            "AnalysisTitle",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            spaceAfter=8,
        )
        heading = ParagraphStyle(
            "AnalysisHeading",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            spaceBefore=10,
            spaceAfter=4,
        )
        mono = ParagraphStyle(
            "AnalysisMono",
            parent=normal,
            fontName="Courier",
            fontSize=9,
            leading=11,
        )

        job = payload.get("job") or {}
        fit = payload.get("job_fit") or {}
        settings = payload.get("settings") or {}
        timing = payload.get("timing") or {}
        tokens = payload.get("token_usage") or {}
        proofread = payload.get("proofread") or {}
        review = payload.get("review") or {}
        letter = (payload.get("letter_text") or "").strip()

        story: List[Any] = []
        story.append(Paragraph("Cover Letter Analysis Export", title_style))
        exported_at = payload.get("exported_at") or datetime.now().isoformat(
            timespec="seconds"
        )
        story.append(Paragraph(_escape(f"Exported: {exported_at}"), normal))
        story.append(Spacer(1, 0.08 * inch))

        story.append(Paragraph("Job", heading))
        story.append(
            Paragraph(
                _escape(
                    f"{job.get('title') or '—'} at {job.get('company') or '—'}"
                ),
                normal,
            )
        )
        if job.get("location"):
            story.append(Paragraph(_escape(f"Location: {job['location']}"), normal))
        if job.get("jd_snippet"):
            story.append(Paragraph(_escape(str(job["jd_snippet"])), normal))

        story.append(Paragraph("Job fit", heading))
        if fit:
            story.append(
                Paragraph(
                    _escape(
                        f"Score: {fit.get('score', '—')}/100 · "
                        f"{(fit.get('recommendation') or '—')}"
                    ),
                    normal,
                )
            )
            breakdown = fit.get("breakdown") or {}
            if breakdown:
                parts = [
                    f"{key}={value}" for key, value in sorted(breakdown.items())
                ]
                story.append(Paragraph(_escape("Breakdown: " + ", ".join(parts)), normal))
            matched = fit.get("matched_keywords") or []
            missing = fit.get("missing_skills") or []
            if matched:
                story.append(
                    Paragraph(
                        _escape("Matched: " + ", ".join(str(m) for m in matched)),
                        normal,
                    )
                )
            if missing:
                story.append(
                    Paragraph(
                        _escape("Missing: " + ", ".join(str(m) for m in missing)),
                        normal,
                    )
                )
        else:
            story.append(Paragraph("No job-fit assessment available.", normal))

        story.append(Paragraph("Settings", heading))
        story.append(
            Paragraph(
                _escape(
                    f"Model: {settings.get('writer_model') or '—'} · "
                    f"Style: {settings.get('style') or '—'} · "
                    f"Deep: {settings.get('deep_validation')} · "
                    f"Review & rewrite: {settings.get('review_rewrite')}"
                ),
                normal,
            )
        )

        story.append(Paragraph("Timing & tokens", heading))
        timing_parts = []
        for key in (
            "generation_ms",
            "review_ms",
            "rewrite_ms",
            "selection_ms",
            "validation_ms",
            "total_ms",
        ):
            if timing.get(key) is not None:
                timing_parts.append(f"{key}={timing[key]}")
        if timing_parts:
            story.append(Paragraph(_escape("; ".join(timing_parts)), mono))
        token_parts = []
        for key in (
            "total_tokens",
            "prompt_tokens",
            "completion_tokens",
            "generation_tokens",
            "review_tokens",
            "rewrite_tokens",
        ):
            if tokens.get(key) is not None:
                token_parts.append(f"{key}={tokens[key]}")
        if token_parts:
            story.append(Paragraph(_escape("; ".join(token_parts)), mono))
        if not timing_parts and not token_parts:
            story.append(Paragraph("No timing/token metadata.", normal))

        story.append(Paragraph("Proofread", heading))
        story.append(
            Paragraph(
                _escape(
                    f"Score: {proofread.get('score', '—')}/100 · "
                    f"{proofread.get('recommendation') or '—'} · "
                    f"structure={proofread.get('structure_score', '—')} "
                    f"content={proofread.get('content_score', '—')} "
                    f"tone={proofread.get('tone_score', '—')}"
                ),
                normal,
            )
        )
        issues = proofread.get("issues") or []
        if issues:
            story.append(
                Paragraph(
                    _escape("Issues: " + ", ".join(str(i) for i in issues)),
                    normal,
                )
            )

        story.append(Paragraph("Reviewer", heading))
        if review:
            story.append(
                Paragraph(
                    _escape(
                        f"Rewrite triggered: {review.get('rewrite_needed')} · "
                        f"count={review.get('rewrite_count')} · "
                        f"model={review.get('model_used') or '—'}"
                    ),
                    normal,
                )
            )
            if review.get("critique"):
                story.append(Paragraph(_escape(str(review["critique"])), normal))
        else:
            story.append(Paragraph("No reviewer feedback for this run.", normal))

        story.append(Paragraph("Generated letter", heading))
        if letter:
            for block in [p for p in letter.split("\n\n") if p.strip()]:
                story.append(Paragraph(_escape(block.strip()), normal))
                story.append(Spacer(1, 0.06 * inch))
        else:
            story.append(Paragraph("No letter text.", normal))

        doc.build(story)
