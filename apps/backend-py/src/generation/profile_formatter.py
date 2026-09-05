"""
Job Raider - Profile PDF Formatter

Exports the active user profile as a structured summary PDF.
This is a readable profile report, not a resume rewrite.

Author: Job Raider
Date: 2026-08-25
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional
from xml.sax.saxutils import escape

try:
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

from ..models.user_profile import UserProfile
from ..utils.logger import Components, get_logger

logger = get_logger(Components.GENERATION)

# Cap bullets per experience entry so the PDF stays scannable.
MAX_EXPERIENCE_HIGHLIGHTS = 5


@dataclass
class FormattedProfile:
    """
    Result of a profile PDF export attempt.

    Attributes:
        pdf_path: Path to the generated PDF, or None.
        success: Whether PDF generation succeeded.
        errors: Human-readable errors from failed generation.
        sections_included: Section titles that were written into the PDF.
    """

    pdf_path: Optional[str] = None
    success: bool = False
    errors: List[str] = field(default_factory=list)
    sections_included: List[str] = field(default_factory=list)


def _fmt_date(value: Optional[datetime]) -> str:
    """
    Format an optional datetime as a short month-year string.

    Args:
        value: Datetime to format, or None.

    Returns:
        Formatted date string, or an empty string when ``value`` is None.
    """
    if value is None:
        return ""
    return value.strftime("%b %Y")


def _escape(text: str) -> str:
    """
    Escape text for reportlab Paragraph XML.

    Args:
        text: Raw user-profile text.

    Returns:
        XML-safe string.
    """
    return escape(text or "").replace("\n", "<br/>")


def _url_str(value: Any) -> Optional[str]:
    """
    Convert an optional URL field to a plain string.

    Args:
        value: HttpUrl, string, or None.

    Returns:
        String URL, or None when empty.
    """
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def collect_included_sections(profile: UserProfile) -> List[str]:
    """
    List section titles that would appear in a PDF for this profile.

    Empty sections are omitted. Identity is always included when a name
    is present.

    Args:
        profile: Active user profile.

    Returns:
        Ordered list of section titles that will be rendered.
    """
    sections: List[str] = []
    if (profile.name or "").strip():
        sections.append("Identity")
    if (profile.summary or "").strip():
        sections.append("Summary")
    if profile.experience:
        sections.append("Experience")
    if profile.education:
        sections.append("Education")
    skills = profile.core_skills or [s.name for s in profile.skills if s.name]
    if skills:
        sections.append("Skills")
    if profile.certifications:
        sections.append("Certifications")
    return sections


class ProfileFormatter:
    """
    Format a user profile as a structured summary PDF.

    Skips empty sections. Does not invent content beyond what is stored
    on the profile.
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
            base_dir = Path(__file__).resolve().parents[3]  # apps/backend-py/
            self.output_dir = base_dir / "data" / "outputs"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def format_pdf(
        self,
        profile: UserProfile,
        filename: str,
    ) -> FormattedProfile:
        """
        Export a profile summary PDF.

        Args:
            profile: Active user profile to export.
            filename: Base filename without extension.

        Returns:
            ``FormattedProfile`` with path, section list, and any errors.
        """
        result = FormattedProfile()
        result.sections_included = collect_included_sections(profile)

        if not REPORTLAB_AVAILABLE:
            message = "PDF generation unavailable: reportlab not installed"
            result.errors.append(message)
            logger.warning(message)
            return result

        try:
            result.pdf_path = self._build_pdf(profile, filename)
            result.success = True
        except Exception as exc:
            message = f"PDF generation failed: {exc}"
            result.errors.append(message)
            logger.error(message)

        return result

    def _build_pdf(self, profile: UserProfile, filename: str) -> str:
        """
        Build the profile summary PDF file.

        Args:
            profile: Profile to render.
            filename: Base filename without extension.

        Returns:
            Absolute path to the generated PDF.
        """
        filepath = self.output_dir / f"{filename}.pdf"
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
            "ProfileBody",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=13,
            spaceAfter=4,
        )
        title_style = ParagraphStyle(
            "ProfileTitle",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            spaceAfter=6,
        )
        heading_style = ParagraphStyle(
            "ProfileHeading",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            spaceBefore=10,
            spaceAfter=6,
        )
        subhead_style = ParagraphStyle(
            "ProfileSubhead",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            spaceBefore=4,
            spaceAfter=2,
        )
        meta_style = ParagraphStyle(
            "ProfileMeta",
            parent=normal,
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor="#444444",
        )

        story: List[Any] = []
        story.append(Paragraph(_escape(profile.name or "Profile Summary"), title_style))
        story.append(
            Paragraph(
                f"Exported {datetime.now().strftime('%B %d, %Y')}",
                meta_style,
            )
        )
        story.append(Spacer(1, 0.12 * inch))

        contact_lines = self._contact_lines(profile)
        if contact_lines:
            story.append(Paragraph("Identity", heading_style))
            for line in contact_lines:
                story.append(Paragraph(_escape(line), normal))

        if (profile.summary or "").strip():
            story.append(Paragraph("Summary", heading_style))
            story.append(Paragraph(_escape(profile.summary.strip()), normal))

        if profile.experience:
            story.append(Paragraph("Experience", heading_style))
            for entry in profile.experience:
                start = _fmt_date(entry.start_date)
                end = (
                    "Present"
                    if entry.current or not entry.end_date
                    else _fmt_date(entry.end_date)
                )
                date_range = " – ".join(part for part in (start, end) if part)
                headline = f"{entry.title} · {entry.company}"
                if date_range:
                    headline = f"{headline} ({date_range})"
                story.append(Paragraph(_escape(headline), subhead_style))
                if entry.location:
                    story.append(Paragraph(_escape(entry.location), meta_style))
                if (entry.description or "").strip():
                    story.append(Paragraph(_escape(entry.description.strip()), normal))
                highlights = (entry.highlights or [])[:MAX_EXPERIENCE_HIGHLIGHTS]
                for bullet in highlights:
                    text = (bullet or "").strip()
                    if text:
                        story.append(Paragraph(f"• {_escape(text)}", normal))

        if profile.education:
            story.append(Paragraph("Education", heading_style))
            for edu in profile.education:
                parts = [edu.degree, edu.school]
                headline = " · ".join(p for p in parts if p)
                end = _fmt_date(edu.end_date)
                if end:
                    headline = f"{headline} ({end})"
                story.append(Paragraph(_escape(headline), subhead_style))
                if edu.location:
                    story.append(Paragraph(_escape(edu.location), meta_style))
                if edu.gpa is not None:
                    story.append(Paragraph(f"GPA: {edu.gpa}", normal))
                if edu.honors:
                    story.append(
                        Paragraph(
                            _escape("Honors: " + ", ".join(edu.honors)),
                            normal,
                        )
                    )

        skills = profile.core_skills or [s.name for s in profile.skills if s.name]
        if skills:
            story.append(Paragraph("Skills", heading_style))
            story.append(Paragraph(_escape(", ".join(skills)), normal))

        if profile.certifications:
            story.append(Paragraph("Certifications", heading_style))
            for cert in profile.certifications:
                line = cert.name
                if cert.issuer:
                    line = f"{line} · {cert.issuer}"
                issued = _fmt_date(cert.issue_date)
                if issued:
                    line = f"{line} ({issued})"
                story.append(Paragraph(_escape(line), normal))

        doc.build(story)
        logger.info("Generated profile PDF: %s", filepath)
        return str(filepath)

    def _contact_lines(self, profile: UserProfile) -> List[str]:
        """
        Build identity/contact lines for the PDF header block.

        Args:
            profile: Profile with contact fields.

        Returns:
            Non-empty contact lines in display order.
        """
        contact = profile.contact
        lines: List[str] = []
        if contact.email:
            lines.append(str(contact.email))
        if contact.phone:
            lines.append(contact.phone)
        if contact.location:
            lines.append(contact.location)
        for label, value in (
            ("LinkedIn", _url_str(contact.linkedin)),
            ("GitHub", _url_str(contact.github)),
            ("Portfolio", _url_str(contact.portfolio)),
            ("Website", _url_str(contact.website)),
        ):
            if value:
                lines.append(f"{label}: {value}")
        return lines
