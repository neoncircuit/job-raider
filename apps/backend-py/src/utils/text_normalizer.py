"""
Job Raider - Text Normalizer

Normalizes job description text at ingestion time for consistent
formatting across display, RAG chunking, BM25 retrieval, and
LLM generation. Applied once during scraping so all downstream
consumers work with clean text.
"""

import html
import re
from typing import List, Tuple

# Bullet characters to normalize to a consistent dash
_BULLET_CHARS = re.compile(r"[•◦▪▸►‣⋅∙]")

# HTML tags to strip (any remaining after BeautifulSoup extraction)
_HTML_TAG_RE = re.compile(r"<[^>]+>")

# Three or more consecutive newlines -> two
_EXCESSIVE_NEWLINES_RE = re.compile(r"\n{3,}")

# Multiple consecutive spaces -> one (but preserve newlines)
_MULTIPLE_SPACES_RE = re.compile(r"[^\S\n]{2,}")

# Common boilerplate patterns to remove from job descriptions
_BOILERPLATE_PATTERNS: List[Tuple[re.Pattern, str]] = [
    # EEO / diversity statements
    (
        re.compile(
            r"(?i)(we are an equal opportunity employer.*?)(?:\n\n|\Z)",
            re.DOTALL,
        ),
        "",
    ),
    (
        re.compile(
            r"(?i)(is an equal opportunity employer.*?)(?:\n\n|\Z)",
            re.DOTALL,
        ),
        "",
    ),
    (
        re.compile(
            r"(?i)(we celebrate diversity.*?)(?:\n\n|\Z)",
            re.DOTALL,
        ),
        "",
    ),
    # Reasonable accommodation
    (
        re.compile(
            r"(?i)(reasonable accommodation.*?)(?:\n\n|\Z)",
            re.DOTALL,
        ),
        "",
    ),
    # "Apply now" / "Click here" calls to action
    (
        re.compile(r"(?i)(click here to apply.*?)(?:\n|\Z)"),
        "",
    ),
    (
        re.compile(r"(?i)(apply now at https?://\S+)"),
        "",
    ),
    # LinkedIn-specific boilerplate / UI chrome copied with highlight-drag
    (
        re.compile(r"(?i)(see how we're matching job seekers to opportunities)"),
        "",
    ),
    (
        re.compile(r"(?im)^\s*(show more|see more|show less|easy apply)\s*$"),
        "",
    ),
    (
        re.compile(r"(?im)^\s*\d+\s*(applicants?|people clicked apply)\s*$"),
        "",
    ),
    (
        re.compile(r"(?im)^\s*(promoted|actively reviewing applicants?)\s*$"),
        "",
    ),
    (
        re.compile(
            r"(?im)^\s*.+?\s·\s+.+\s·\s+\d+\s+(?:day|days|week|weeks|hour|hours)\s+ago.*$"
        ),
        "",
    ),
]

# Section header keywords that should be separated from content above
_SECTION_KEYWORDS = [
    "requirements",
    "qualifications",
    "responsibilities",
    "what you'll do",
    "what you will do",
    "about the role",
    "about the position",
    "job description",
    "position summary",
    "the basics",
    "required skills",
    "preferred skills",
    "nice to have",
    "required experience",
    "preferred experience",
    "basic qualifications",
    "minimum qualifications",
    "education",
    "benefits",
    "what we offer",
    "compensation",
    "about us",
    "about the company",
    "about the job",
    "who we are",
    "our mission",
]


def normalize_job_description(raw_text: str) -> str:
    """Normalize job description text for clean storage and RAG processing.

    Applies the following transformations in order:
    1. HTML entity decoding and tag stripping
    2. Bullet character normalization
    3. Whitespace collapse
    4. Section header separation
    5. Boilerplate removal
    6. Final trim

    Args:
        raw_text: Raw job description text from scraping.

    Returns:
        Cleaned and consistently formatted description text.
    """
    if not raw_text or not raw_text.strip():
        return ""

    text = raw_text

    # 1. HTML cleanup
    text = html.unescape(text)
    text = _HTML_TAG_RE.sub("", text)

    # 2. Bullet normalization
    text = _BULLET_CHARS.sub("- ", text)
    text = re.sub(r"(-)\s{2,}", r"\1 ", text)

    # 3. Whitespace collapse
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = _MULTIPLE_SPACES_RE.sub(" ", text)
    text = _EXCESSIVE_NEWLINES_RE.sub("\n\n", text)

    # 4. Section header separation
    text = _separate_sections(text)

    # 5. Boilerplate removal
    for pattern, replacement in _BOILERPLATE_PATTERNS:
        text = pattern.sub(replacement, text)
    text = _EXCESSIVE_NEWLINES_RE.sub("\n\n", text)

    # 6. Drop a trailing mid-cut fragment (highlight ended mid-word/hyphen)
    text = _strip_trailing_highlight_cut(text)

    # 7. Final cleanup
    text = text.strip()
    while text.endswith("\n"):
        text = text[:-1].rstrip("\n")

    return text


def _strip_trailing_highlight_cut(text: str) -> str:
    """
    Remove a short final line that looks like a mid-sentence highlight cut.

    Drag-copy often ends on a hanging hyphen (``ownership of-``). Longer
    legitimate bullets ending in a hyphen are left alone.

    Args:
        text: Partially cleaned job description.

    Returns:
        Text with an obvious trailing cut removed when present.
    """
    lines = text.rstrip().split("\n")
    if not lines:
        return text
    last = lines[-1].strip()
    if len(last) <= 80 and re.search(r"\b[\w']+-\s*$", last):
        lines = lines[:-1]
        return "\n".join(lines).rstrip()
    return text.rstrip()


def _separate_sections(text: str) -> str:
    """Ensure section headers are on their own line with a blank line after.

    Args:
        text: Text with potentially inconsistent section formatting.

    Returns:
        Text with consistently separated sections.
    """
    lines = text.split("\n")
    result_lines: List[str] = []

    for i, line in enumerate(lines):
        stripped = line.strip()

        if _is_section_header(stripped):
            if result_lines and result_lines[-1].strip():
                result_lines.append("")
            result_lines.append(stripped)
            if i + 1 < len(lines) and lines[i + 1].strip():
                result_lines.append("")
        else:
            result_lines.append(line)

    return "\n".join(result_lines)


def _is_section_header(line: str) -> bool:
    """Check if a line looks like a section header.

    Args:
        line: A single line of text (already stripped).

    Returns:
        True if the line appears to be a section header.
    """
    if not line:
        return False

    # Lines ending with colon
    if line.endswith(":") and len(line) > 3:
        return True

    # ALL CAPS lines (at least 3 alpha chars, not just separators)
    if line == line.upper() and len(re.findall(r"[A-Z]", line)) >= 3:
        if not re.match(r"^[\s\-_=*]+$", line):
            return True

    # Known section keywords (case-insensitive)
    lower = line.lower().rstrip(":")
    for keyword in _SECTION_KEYWORDS:
        if lower == keyword:
            return True

    return False
