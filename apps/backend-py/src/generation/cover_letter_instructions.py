"""
Job Raider - Cover Letter Application-Instruction Detection (Phase C)

Conservative regex/keyword extraction of two JD instruction types:
1. Length-constrained "why this interests / excites you" asks
2. Explicit inclusion asks (GitHub / portfolio / LinkedIn / project link)

Ambiguous matches are treated as not detected. Never invent instructions.

Author: Job Raider
Date: 2026-08-21
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Literal, Optional, Sequence

LengthUnit = Literal["lines", "sentences", "words"]
InclusionKind = Literal["github", "portfolio", "linkedin", "project_link"]

# Window (chars) around a length+unit match that must also contain interest cues.
_INTEREST_WINDOW = 120

_INTEREST_CUES = re.compile(
    r"\b(?:why|interest(?:s|ed)?|excites?|excited|mission|company)\b",
    re.IGNORECASE,
)

# Ranges: "3-4 lines", "3 to 4 sentences".
# Floor: "minimum 50 words", "at least 2 sentences".
# Approx / bare: "about 50 words", "2 sentences" (treated as exact target).
# “3-4 lines” is only an example — any confident unit may match.
_LENGTH_PATTERN = re.compile(
    r"(?P<a>\d{1,3})\s*(?:-|–|—|to)\s*(?P<b>\d{1,3})\s+"
    r"(?P<unit>lines?|sentences?|words?)"
    r"|"
    r"(?:"
    r"(?P<floor>minimum|at\s+least|no\s+fewer\s+than)"
    r"|"
    r"(?P<approx>about|approximately|around|roughly)"
    r")?\s*"
    r"(?P<n>\d{1,3})\s+(?P<unit2>lines?|sentences?|words?)",
    re.IGNORECASE,
)

_INCLUSION_PATTERN = re.compile(
    r"\b(?:include|attach|provide|add|send)\b"
    r".{0,60}?"
    r"\b(?P<kind>github|portfolio|linkedin|personal\s+website|project\s+(?:url|link)|website)\b",
    re.IGNORECASE | re.DOTALL,
)

_MAX_REASONABLE = {
    "lines": 12,
    "sentences": 12,
    "words": 200,
}


@dataclass
class WhyInterestSpec:
    """
    Detected length-constrained interest instruction.

    Attributes:
        min_n: Inclusive lower bound for the length unit.
        max_n: Inclusive upper bound, or ``None`` for min-only floors
            (e.g. ``minimum 50 words`` → at least 50, no exact ceiling).
        unit: ``lines``, ``sentences``, or ``words``.
        matched_span: Exact JD substring that triggered detection.
    """

    min_n: int
    max_n: Optional[int]
    unit: LengthUnit
    matched_span: str

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize for API / validation details.

        Returns:
            Plain dict (``max_n`` may be null for min-only floors).
        """
        return asdict(self)


@dataclass
class InclusionSpec:
    """
    Detected explicit inclusion instruction.

    Attributes:
        kind: Normalized inclusion kind.
        matched_span: Exact JD substring that triggered detection.
    """

    kind: InclusionKind
    matched_span: str

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize for API / validation details.

        Returns:
            Plain dict.
        """
        return asdict(self)


@dataclass
class DetectedInstructions:
    """
    Outcome of conservative JD instruction detection.

    Attributes:
        why_interest: Length-constrained interest ask, if confidently detected.
        inclusions: Explicit inclusion asks (may be empty).
    """

    why_interest: Optional[WhyInterestSpec] = None
    inclusions: List[InclusionSpec] = field(default_factory=list)

    @property
    def has_why_interest(self) -> bool:
        """
        Return True when a why-interest instruction was detected.

        Returns:
            Whether short-answer replace mode should run.
        """
        return self.why_interest is not None

    @property
    def has_inclusions(self) -> bool:
        """
        Return True when at least one inclusion instruction was detected.

        Returns:
            Whether inclusion injection / checks should run.
        """
        return bool(self.inclusions)

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize for API / validation details.

        Returns:
            Plain dict with optional why_interest and inclusions list.
        """
        return {
            "why_interest": self.why_interest.to_dict() if self.why_interest else None,
            "inclusions": [item.to_dict() for item in self.inclusions],
        }


def _normalize_unit(raw: str) -> Optional[LengthUnit]:
    """
    Map a matched unit token to a canonical LengthUnit.

    Args:
        raw: Matched unit string (e.g. ``Lines``, ``sentence``).

    Returns:
        Canonical unit, or None if unrecognized.
    """
    token = (raw or "").strip().lower()
    if token.startswith("line"):
        return "lines"
    if token.startswith("sentence"):
        return "sentences"
    if token.startswith("word"):
        return "words"
    return None


def _normalize_inclusion_kind(raw: str) -> Optional[InclusionKind]:
    """
    Map a matched inclusion token to a canonical InclusionKind.

    Args:
        raw: Matched kind string from the inclusion pattern.

    Returns:
        Canonical kind, or None if unrecognized.
    """
    token = re.sub(r"\s+", " ", (raw or "").strip().lower())
    if token == "github":
        return "github"
    if token in {"portfolio", "personal website", "website"}:
        return "portfolio"
    if token == "linkedin":
        return "linkedin"
    if token.startswith("project"):
        return "project_link"
    return None


def _window_has_interest_cue(text: str, start: int, end: int) -> bool:
    """
    Return True if interest/mission cues appear near the length match.

    Args:
        text: Full JD text.
        start: Match start index.
        end: Match end index.

    Returns:
        Whether the local window contains an interest cue.
    """
    lo = max(0, start - _INTEREST_WINDOW)
    hi = min(len(text), end + _INTEREST_WINDOW)
    return bool(_INTEREST_CUES.search(text[lo:hi]))


def _parse_length_match(match: re.Match[str]) -> Optional[WhyInterestSpec]:
    """
    Build a WhyInterestSpec from a length regex match, or None if invalid.

    Floor cues (``minimum`` / ``at least`` / ``no fewer than``) yield
    ``max_n=None`` (min-only). Explicit ranges and bare/approx singles stay
    bounded (exact target for a single number).

    Args:
        match: Regex match from ``_LENGTH_PATTERN``.

    Returns:
        Spec when bounds are sane; otherwise None (ambiguous → drop).
    """
    unit_raw = match.group("unit") or match.group("unit2")
    unit = _normalize_unit(unit_raw or "")
    if unit is None:
        return None

    max_n: Optional[int]
    if match.group("a") and match.group("b"):
        a = int(match.group("a"))
        b = int(match.group("b"))
        min_n, max_n = (a, b) if a <= b else (b, a)
    else:
        n = int(match.group("n"))
        min_n = n
        if match.group("floor"):
            max_n = None
        else:
            max_n = n

    if min_n < 1:
        return None
    if max_n is not None and max_n < 1:
        return None
    if min_n > _MAX_REASONABLE[unit]:
        return None
    if max_n is not None and max_n > _MAX_REASONABLE[unit]:
        return None
    if max_n is not None:
        if max_n - min_n > 8 and unit != "words":
            return None
        if unit == "words" and max_n - min_n > 100:
            return None

    return WhyInterestSpec(
        min_n=min_n,
        max_n=max_n,
        unit=unit,
        matched_span=match.group(0).strip(),
    )


def detect_why_interest(jd_text: str) -> Optional[WhyInterestSpec]:
    """
    Detect a length-constrained why-interest instruction in JD text.

    Requires both a length+unit phrase and a nearby interest/mission cue.
    If multiple candidates match, keep the first confident one.

    Args:
        jd_text: Job description text.

    Returns:
        ``WhyInterestSpec`` or None when not confidently detected.
    """
    text = jd_text or ""
    if not text.strip():
        return None

    for match in _LENGTH_PATTERN.finditer(text):
        if not _window_has_interest_cue(text, match.start(), match.end()):
            continue
        spec = _parse_length_match(match)
        if spec is not None:
            return spec
    return None


def detect_inclusions(jd_text: str) -> List[InclusionSpec]:
    """
    Detect explicit inclusion instructions in JD text.

    Args:
        jd_text: Job description text.

    Returns:
        Deduplicated list of inclusion specs (stable order).
    """
    text = jd_text or ""
    found: List[InclusionSpec] = []
    seen: set[InclusionKind] = set()
    for match in _INCLUSION_PATTERN.finditer(text):
        kind = _normalize_inclusion_kind(match.group("kind") or "")
        if kind is None or kind in seen:
            continue
        seen.add(kind)
        found.append(
            InclusionSpec(kind=kind, matched_span=match.group(0).strip()[:160])
        )
    return found


def detect_application_instructions(jd_text: str) -> DetectedInstructions:
    """
    Run conservative detection for Phase C instruction types.

    Args:
        jd_text: Job description text.

    Returns:
        ``DetectedInstructions`` (empty fields when nothing confident matched).
    """
    return DetectedInstructions(
        why_interest=detect_why_interest(jd_text),
        inclusions=detect_inclusions(jd_text),
    )


def count_length_units(text: str, unit: LengthUnit) -> int:
    """
    Count lines, sentences, or words in generated text for validation.

    Args:
        text: Generated cover-letter / short-answer content.
        unit: Length unit to count.

    Returns:
        Non-negative count.
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return 0
    if unit == "words":
        return len(cleaned.split())
    if unit == "lines":
        lines = [ln.strip() for ln in cleaned.splitlines() if ln.strip()]
        if len(lines) >= 2:
            return len(lines)
        sentences = _split_sentences(cleaned)
        return max(len(sentences), 1)
    return len(_split_sentences(cleaned))


def _split_sentences(text: str) -> List[str]:
    """
    Split text into non-empty sentence-like chunks.

    Args:
        text: Input text.

    Returns:
        List of sentence strings.
    """
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def length_within_spec(text: str, spec: WhyInterestSpec) -> bool:
    """
    Return True if text length satisfies the detected length constraint.

    Bounded specs require ``min_n <= count <= max_n``. Min-only floors
    (``max_n is None``, e.g. ``minimum 50 words``) require ``count >= min_n``.

    Args:
        text: Generated short-answer content.
        spec: Detected why-interest length spec.

    Returns:
        Whether the count satisfies the floor and optional ceiling.
    """
    count = count_length_units(text, spec.unit)
    if count < spec.min_n:
        return False
    if spec.max_n is None:
        return True
    return count <= spec.max_n


def resolve_inclusion_urls(
    inclusions: Sequence[InclusionSpec],
    *,
    github: Optional[str] = None,
    portfolio: Optional[str] = None,
    linkedin: Optional[str] = None,
    website: Optional[str] = None,
) -> Dict[InclusionKind, Optional[str]]:
    """
    Map inclusion kinds to profile URLs (None when missing — never invent).

    Args:
        inclusions: Detected inclusion specs.
        github: Profile GitHub URL string.
        portfolio: Profile portfolio URL string.
        linkedin: Profile LinkedIn URL string.
        website: Profile personal website URL string.

    Returns:
        Dict of kind → URL or None for each requested inclusion.
    """
    portfolio_url = portfolio or website
    mapping: Dict[InclusionKind, Optional[str]] = {}
    for item in inclusions:
        if item.kind == "github":
            mapping["github"] = github or None
        elif item.kind == "portfolio":
            mapping["portfolio"] = portfolio_url or None
        elif item.kind == "linkedin":
            mapping["linkedin"] = linkedin or None
        elif item.kind == "project_link":
            mapping["project_link"] = portfolio_url or github or None
    return mapping


def inclusion_present_in_text(text: str, url: str) -> bool:
    """
    Return True if the required URL (or distinctive host path) appears in text.

    Args:
        text: Generated letter content.
        url: Required absolute URL from the profile.

    Returns:
        Whether the inclusion is present.
    """
    if not url or not text:
        return False
    hay = text.lower()
    needle = url.strip().lower().rstrip("/")
    if needle in hay:
        return True
    host_path = re.sub(r"^https?://", "", needle)
    return bool(host_path) and host_path in hay
