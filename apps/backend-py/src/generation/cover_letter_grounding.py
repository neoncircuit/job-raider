"""
Job Raider - Cover Letter Grounding Checks

Deterministic post-generation checks that flag cover-letter sentences with
weak overlap against the candidate's resume (and optionally JD terms).

Mirrors the resume-analyzer pattern: profile/JD facts are the source of
truth; the LLM may only restate them. Closing-paragraph flourish that
introduces ungrounded capability claims is the primary failure mode.

Author: Job Raider
Date: 2026-07-28
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from ..models.user_profile import UserProfile
from .selector import SelectionOutput

# Common function words longer than 3 chars — excluded so they do not inflate
# overlap scores against resume vocabulary.
_STOPWORDS: frozenset[str] = frozenset(
    {
        "that",
        "this",
        "with",
        "from",
        "have",
        "been",
        "were",
        "will",
        "would",
        "could",
        "should",
        "about",
        "into",
        "over",
        "under",
        "their",
        "there",
        "these",
        "those",
        "which",
        "while",
        "where",
        "when",
        "your",
        "you",
        "also",
        "than",
        "then",
        "them",
        "they",
        "such",
        "only",
        "both",
        "each",
        "more",
        "most",
        "other",
        "some",
        "such",
        "very",
        "just",
        "like",
        "able",
        "make",
        "made",
        "using",
        "across",
        "through",
        "between",
        "because",
        "during",
        "before",
        "after",
        "above",
        "below",
        "being",
        "having",
        "doing",
        "looking",
        "forward",
        "opportunity",
        "discuss",
        "considering",
        "application",
        "position",
        "role",
        "team",
        "company",
        "letter",
        "please",
        "thank",
        "thanks",
        "sincerely",
        "regards",
    }
)

# Capability verbs that often appear in ungrounded closing flourish.
_OVERCLAIM_TOKENS: frozenset[str] = frozenset(
    {
        "deployed",
        "deployment",
        "production",
        "launched",
        "shipped",
        "shipping",
        "scaled",
        "scaling",
        "proven",
        "delivering",
        "delivered",
    }
)

# Leadership/ownership phrasing that inflates seniority beyond IC bullets.
_SCOPE_INFLATION_PHRASES: tuple[str, ...] = (
    "leading the",
    "led the",
    "leading development",
    "led development",
    "spearheaded",
    "owned entirely",
    "architected the platform",
    "drove the strategy",
    "drove strategy",
)

# Technique terms that must be attributed to the same project they describe.
_TECHNIQUE_TERMS: tuple[str, ...] = (
    "retrieval",
    "fine-tuning",
    "fine tuning",
    "rag",
    "distributed",
    "real-time",
    "realtime",
    "containerized",
)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_WORD_RE = re.compile(r"[a-z0-9+#./-]+", re.IGNORECASE)


def significant_words(text: str) -> List[str]:
    """
    Tokenize text into significant lowercase words for overlap checks.

    Args:
        text: Free-text sentence or resume bullet.

    Returns:
        Tokens longer than 3 characters after stopword filtering.
    """
    words = [match.group(0).lower() for match in _WORD_RE.finditer(text or "")]
    return [word for word in words if len(word) > 3 and word not in _STOPWORDS]


def collect_resume_bullets(
    profile: UserProfile,
    selection: Optional[SelectionOutput] = None,
) -> List[str]:
    """
    Build the resume grounding corpus from profile (and optional selection).

    Args:
        profile: Candidate profile used as the factual source of truth.
        selection: Optional selector output; achievements and keywords are
            included so selected emphasis remains valid grounding.

    Returns:
        List of text snippets treated as resume bullets for overlap checks.
    """
    bullets: List[str] = []

    if profile.summary:
        bullets.append(profile.summary)

    for skill in profile.skills:
        if skill.name:
            bullets.append(skill.name)

    for project in profile.projects:
        parts = [project.name or "", project.description or ""]
        parts.extend(project.technologies or [])
        parts.extend(project.highlights or [])
        bullets.append(" ".join(part for part in parts if part))

    for experience in profile.experience:
        parts = [
            experience.title or "",
            experience.company or "",
            experience.description or "",
        ]
        parts.extend(experience.highlights or [])
        parts.extend(experience.technologies or [])
        bullets.append(" ".join(part for part in parts if part))

    for education in profile.education:
        parts = [
            education.degree or "",
            education.school or "",
        ]
        parts.extend(education.honors or [])
        parts.extend(education.coursework or [])
        bullets.append(" ".join(part for part in parts if part))

    if selection is not None:
        bullets.extend(selection.keywords_to_emphasize or [])
        bullets.extend(selection.key_achievements or [])
        if selection.summary_suggestion:
            bullets.append(selection.summary_suggestion)
        for project in selection.selected_projects or []:
            name = project.get("name") or ""
            reason = project.get("reason") or ""
            bullets.append(f"{name} {reason}".strip())

    return [bullet for bullet in bullets if bullet and bullet.strip()]


def build_project_techniques(profile: UserProfile) -> dict[str, List[str]]:
    """
    Map each profile project to techniques verified from its own text.

    Args:
        profile: Candidate profile containing projects.

    Returns:
        Mapping of project name to technique/tech strings drawn from that
        project's technologies, highlights, and description (including any
        watched technique terms that appear in the project's own corpus).
    """
    techniques_by_project: dict[str, List[str]] = {}
    for project in profile.projects:
        if not project.name:
            continue
        corpus_parts = [project.description or ""]
        corpus_parts.extend(project.technologies or [])
        corpus_parts.extend(project.highlights or [])
        corpus = " ".join(part for part in corpus_parts if part)
        corpus_lower = corpus.lower()
        techniques: List[str] = []
        techniques.extend(project.technologies or [])
        techniques.extend(project.highlights or [])
        if project.description:
            techniques.append(project.description)
        for term in _TECHNIQUE_TERMS:
            if term in corpus_lower:
                techniques.append(term)
        # De-dupe while preserving order.
        seen: Set[str] = set()
        unique: List[str] = []
        for item in techniques:
            key = item.lower().strip()
            if key and key not in seen:
                seen.add(key)
                unique.append(item)
        techniques_by_project[project.name] = unique
    return techniques_by_project


def resolve_project_name(sentence: str, project_names: Sequence[str]) -> Optional[str]:
    """
    Resolve which profile project a sentence is describing.

    Args:
        sentence: Cover-letter sentence.
        project_names: Known project names from the profile.

    Returns:
        The longest project name found in the sentence, or ``None``.
    """
    lowered = (sentence or "").lower()
    matches = [name for name in project_names if name and name.lower() in lowered]
    if not matches:
        return None
    return max(matches, key=len)


def flag_scope_and_technique_overclaims(
    sentence: str,
    project_name: Optional[str],
    project_techniques: dict[str, List[str]],
    resume_bullets: Optional[Sequence[str]] = None,
) -> List[str]:
    """
    Flag scope-inflation and technique-mismatch issues in a single sentence.

    Runs two independent checks that a bag-of-words overlap score cannot
    catch, since both failure modes hide a misleading term inside a
    sentence that is otherwise well-grounded:

    1. Scope inflation: flags verbs implying leadership/ownership beyond an
       individual contribution, unless that exact phrasing already appears
       in the resume corpus.
    2. Technique mismatch: flags a named technique (e.g. ``retrieval``,
       ``fine-tuning``) when the referenced project's known technique list
       does not include it.

    Args:
        sentence: A single sentence from the generated cover letter.
        project_name: The project this sentence is describing, used to
            look up what techniques that project actually uses. May be
            ``None`` when no project is named (technique check is skipped).
        project_techniques: Mapping of project name to the list of
            techniques verified to apply to it.
        resume_bullets: Optional resume corpus; scope phrases present here
            are treated as allowed (the candidate really wrote them).

    Returns:
        A list of human-readable flags describing what was found, empty
        if the sentence raises no concerns.
    """
    flags: List[str] = []
    lowered = (sentence or "").lower()
    if not lowered.strip():
        return flags

    resume_lower = " ".join(resume_bullets or []).lower()

    for phrase in _SCOPE_INFLATION_PHRASES:
        if phrase in lowered and phrase not in resume_lower:
            flags.append(
                "Scope inflation: "
                f"'{phrase}' implies leadership/ownership beyond an "
                "individual contribution"
            )

    if project_name:
        known = project_techniques.get(project_name, [])
        known_lower = " ".join(known).lower()
        for term in _TECHNIQUE_TERMS:
            if term in lowered and term not in known_lower:
                flags.append(
                    f"Technique mismatch: '{term}' not verified for " f"{project_name}"
                )

    return flags


def flag_claim_overclaims(
    letter_text: str,
    profile: UserProfile,
    resume_bullets: Optional[Sequence[str]] = None,
) -> List[dict]:
    """
    Scan a cover letter for scope-inflation and technique-mismatch claims.

    Args:
        letter_text: Full cover letter body.
        profile: Candidate profile used to build per-project techniques.
        resume_bullets: Optional resume corpus for allowing documented
            leadership phrasing.

    Returns:
        A list of ``{"sentence": str, "flags": list[str]}`` entries for
        sentences that raised at least one claim flag.
    """
    if not letter_text or not letter_text.strip():
        return []

    techniques = build_project_techniques(profile)
    project_names = list(techniques.keys())
    bullets = (
        resume_bullets
        if resume_bullets is not None
        else collect_resume_bullets(profile)
    )

    findings: List[dict] = []
    for sentence in _SENTENCE_SPLIT.split(letter_text.strip()):
        cleaned = sentence.strip().rstrip(".")
        if not cleaned:
            continue
        project_name = resolve_project_name(cleaned, project_names)
        flags = flag_scope_and_technique_overclaims(
            cleaned,
            project_name,
            techniques,
            resume_bullets=bullets,
        )
        if flags:
            findings.append({"sentence": cleaned, "flags": flags})
    return findings


def flag_ungrounded_sentences(
    letter_text: str,
    resume_bullets: Sequence[str],
    min_overlap_ratio: float = 0.3,
    jd_terms: Optional[Iterable[str]] = None,
    closing_min_overlap_ratio: float = 0.4,
) -> List[str]:
    """
    Flag sentences in a generated cover letter with weak grounding in the resume.

    Splits the letter into sentences and checks each one's keyword overlap
    against resume bullets (and optional JD terms). Sentences with low overlap
    are likely model-synthesized flourish rather than restated fact, and are
    surfaced for manual review rather than auto-approved.

    Closing-paragraph sentences use a stricter overlap threshold, and sentences
    that introduce overclaim verbs (for example ``deployed``, ``production``,
    ``launched``) absent from the grounding corpus are always flagged.

    Args:
        letter_text: The generated cover letter body.
        resume_bullets: The candidate's resume bullets, used as the source
            of truth for factual grounding.
        min_overlap_ratio: Minimum fraction of a sentence's significant
            words that must appear somewhere in the grounding corpus for
            body sentences to be considered grounded.
        jd_terms: Optional job-description / requirement phrases that are
            also valid grounding (the letter may address JD needs by name).
        closing_min_overlap_ratio: Stricter overlap threshold for sentences
            in the final paragraph.

    Returns:
        A list of sentences from the letter that fall below the overlap
        threshold (or contain ungrounded overclaim verbs) and should be
        reviewed before sending.
    """
    ground_words: Set[str] = set()
    for bullet in resume_bullets:
        ground_words.update(significant_words(bullet))
    if jd_terms:
        for term in jd_terms:
            ground_words.update(significant_words(term))

    if not letter_text or not letter_text.strip():
        return []

    paragraphs = [part.strip() for part in letter_text.split("\n\n") if part.strip()]
    if not paragraphs:
        paragraphs = [letter_text.strip()]
    closing_text = paragraphs[-1]

    flagged: List[str] = []
    for sentence in _SENTENCE_SPLIT.split(letter_text.strip()):
        cleaned = sentence.strip()
        if not cleaned:
            continue
        words = significant_words(cleaned)
        if not words:
            continue

        overlap = sum(1 for word in words if word in ground_words) / len(words)
        in_closing = cleaned in closing_text or cleaned.rstrip(".") in closing_text
        threshold = closing_min_overlap_ratio if in_closing else min_overlap_ratio

        overclaim = [
            word
            for word in words
            if word in _OVERCLAIM_TOKENS and word not in ground_words
        ]
        if overclaim or overlap < threshold:
            flagged.append(cleaned.rstrip("."))

    return flagged


# Content-score deductions per finding. Soft lexical weakness must not equal
# fabricated scope or technique attribution errors.
_PENALTY_SOFT_UNGROUNDED = 3
_PENALTY_HARD_UNGROUNDED = 10
_PENALTY_SCOPE_INFLATION = 12
_PENALTY_TECHNIQUE_MISMATCH = 10
_MAX_GROUNDING_PENALTY = 50


def _normalize_finding_sentence(sentence: str) -> str:
    """
    Normalize a finding sentence for deduplication across check layers.

    Args:
        sentence: Raw sentence text from a grounding check.

    Returns:
        Lowercased, punctuation-trimmed sentence key.
    """
    return sentence.strip().rstrip(".!?").lower()


def _is_hard_ungrounded(sentence: str) -> bool:
    """
    Return whether an ungrounded sentence uses hard overclaim capability verbs.

    Args:
        sentence: Flagged sentence text.

    Returns:
        True when the sentence contains an overclaim token such as deployed
        or shipped that is not merely vague word choice.
    """
    words = significant_words(sentence)
    return any(word in _OVERCLAIM_TOKENS for word in words)


def calc_grounding_penalty(
    ungrounded_sentences: List[str],
    claim_overclaims: List[Dict[str, Any]],
) -> tuple[int, Dict[str, Any]]:
    """
    Score grounding findings by severity instead of a flat per-issue penalty.

    Soft ungrounded sentences (weak lexical overlap / vague phrasing) cost
    little. Hard ungrounded overclaim verbs, scope inflation, and technique
    mismatches cost substantially more. Total deduction is capped so other
    content dimensions remain visible.

    Args:
        ungrounded_sentences: Sentences failing resume/JD overlap checks.
        claim_overclaims: Scope/technique findings with per-sentence flags.

    Returns:
        Tuple of (penalty points to subtract from content score, breakdown
        dict with soft/hard/scope/technique counts and raw vs capped penalty).
    """
    overclaim_keys = {
        _normalize_finding_sentence(item["sentence"])
        for item in claim_overclaims
        if item.get("sentence")
    }

    soft_count = 0
    hard_count = 0
    for sentence in ungrounded_sentences:
        key = _normalize_finding_sentence(sentence)
        # Scope/technique findings already carry harder penalties; do not
        # double-count the same sentence as soft/hard ungrounded.
        if key in overclaim_keys:
            continue
        if _is_hard_ungrounded(sentence):
            hard_count += 1
        else:
            soft_count += 1

    scope_count = 0
    technique_count = 0
    for item in claim_overclaims:
        for flag in item.get("flags", []):
            lowered = flag.lower()
            if lowered.startswith("scope inflation"):
                scope_count += 1
            elif lowered.startswith("technique mismatch"):
                technique_count += 1

    raw = (
        soft_count * _PENALTY_SOFT_UNGROUNDED
        + hard_count * _PENALTY_HARD_UNGROUNDED
        + scope_count * _PENALTY_SCOPE_INFLATION
        + technique_count * _PENALTY_TECHNIQUE_MISMATCH
    )
    penalty = min(raw, _MAX_GROUNDING_PENALTY)
    breakdown: Dict[str, Any] = {
        "soft_ungrounded": soft_count,
        "hard_ungrounded": hard_count,
        "scope_inflation": scope_count,
        "technique_mismatch": technique_count,
        "raw_penalty": raw,
        "capped_penalty": penalty,
        "weights": {
            "soft_ungrounded": _PENALTY_SOFT_UNGROUNDED,
            "hard_ungrounded": _PENALTY_HARD_UNGROUNDED,
            "scope_inflation": _PENALTY_SCOPE_INFLATION,
            "technique_mismatch": _PENALTY_TECHNIQUE_MISMATCH,
            "max_penalty": _MAX_GROUNDING_PENALTY,
        },
    }
    return penalty, breakdown
