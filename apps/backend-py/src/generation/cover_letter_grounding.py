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
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from ..models.job_listing import JobListing
from ..models.user_profile import SkillCategory, UserProfile
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

# Canonical tech names for letter-vs-resume Technical Skills checks.
# Only known tools/languages/clouds/databases are matched so ordinary
# English is not flagged. Aliases map onto these keys (see ``_TECH_ALIASES``).
_KNOWN_TECHNOLOGIES: frozenset[str] = frozenset(
    {
        "python",
        "javascript",
        "typescript",
        "java",
        "c++",
        "c#",
        "golang",
        "rust",
        "ruby",
        "php",
        "swift",
        "kotlin",
        "scala",
        "matlab",
        "sql",
        "html",
        "css",
        "react",
        "angular",
        "vue",
        "next.js",
        "svelte",
        "django",
        "flask",
        "fastapi",
        "express",
        "spring",
        "rails",
        "laravel",
        "node.js",
        ".net",
        "docker",
        "kubernetes",
        "aws",
        "azure",
        "gcp",
        "git",
        "linux",
        "postgresql",
        "mysql",
        "mongodb",
        "redis",
        "elasticsearch",
        "kafka",
        "rabbitmq",
        "graphql",
        "terraform",
        "ansible",
        "jenkins",
        "github actions",
        "gitlab ci",
        "pytorch",
        "tensorflow",
        "pandas",
        "numpy",
        "scikit-learn",
        "spark",
        "hadoop",
        "airflow",
        "dbt",
        "snowflake",
        "bigquery",
        "redshift",
        "dynamodb",
        "cassandra",
        "neo4j",
        "sqlite",
        "celery",
        "nginx",
        "helm",
        "prometheus",
        "grafana",
        "datadog",
        "sentry",
        "openai",
        "langchain",
        "huggingface",
        "ollama",
        "mlflow",
        "keras",
        "opencv",
        "powershell",
        "pulumi",
        "cloudformation",
        "ecs",
        "eks",
        "lambda",
        "cloudflare",
        "vercel",
        "heroku",
        "firebase",
        "supabase",
        "prisma",
        "sqlalchemy",
        "webpack",
        "vite",
        "tailwind",
        "bootstrap",
        "jquery",
        "redux",
        "zustand",
        "grpc",
        "oauth",
        "jwt",
        "splunk",
        "kibana",
        "logstash",
        "consul",
        "istio",
        "envoy",
        "traefik",
        "selenium",
        "cypress",
        "playwright",
        "jest",
        "pytest",
        "junit",
        "storybook",
        "tableau",
        "power bi",
        "looker",
        "protobuf",
        "gradle",
        "maven",
        "npm",
        "yarn",
        "pnpm",
        "conda",
        "poetry",
        "flutter",
        "react native",
        "xamarin",
        "electron",
        "opentelemetry",
        "jaeger",
        "new relic",
        "pagerduty",
        "salesforce",
        "okta",
        "auth0",
        "cognito",
        "keycloak",
        "pydantic",
        "matplotlib",
        "seaborn",
        "plotly",
        "three.js",
        "cuda",
        "onnx",
        "vllm",
        "spacy",
        "nltk",
        "xgboost",
        "lightgbm",
        "catboost",
        "scipy",
        "memcached",
        "flink",
        "kinesis",
        "cloudwatch",
        "sagemaker",
        "bedrock",
        "argocd",
        "circleci",
        "azure devops",
        "cicd",
        "mlops",
    }
)

# Alternate spellings / short names -> lexicon canonical keys.
_TECH_ALIASES: dict[str, str] = {
    "k8s": "kubernetes",
    "kube": "kubernetes",
    "postgres": "postgresql",
    "psql": "postgresql",
    "nodejs": "node.js",
    "node.js": "node.js",
    "nextjs": "next.js",
    "reactjs": "react",
    "vuejs": "vue",
    "go": "golang",
    "google cloud": "gcp",
    "google cloud platform": "gcp",
    "amazon web services": "aws",
    "microsoft azure": "azure",
    "cplusplus": "c++",
    "csharp": "c#",
    "dotnet": ".net",
    "sklearn": "scikit-learn",
    "scikit learn": "scikit-learn",
    "gh actions": "github actions",
    "githubactions": "github actions",
    "ci/cd": "cicd",
    "ci-cd": "cicd",
    "mongo": "mongodb",
    "elastic search": "elasticsearch",
    "powerbi": "power bi",
    "power-bi": "power bi",
    "reactnative": "react native",
    "react-native": "react native",
    "threejs": "three.js",
    "tf": "tensorflow",
    "torch": "pytorch",
}

# Aliases that are also common English / too short for free-text matching.
# Still used when normalizing profile skill names.
_AMBIGUOUS_TEXT_ALIASES: frozenset[str] = frozenset(
    {
        "go",
        "tf",
        "torch",
    }
)

_NON_TECH_SKILL_CATEGORIES = frozenset(
    {
        SkillCategory.SOFT_SKILL,
        SkillCategory.LANGUAGE,
    }
)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_WORD_RE = re.compile(r"[a-z0-9+#./-]+", re.IGNORECASE)

# Glue phrases that map resume facts onto JD-only duties. The left-hand
# side is often resume-true; the right-hand side is the overclaim.
_ANALOGY_MARKER_RE = re.compile(
    r"\b(?:"
    r"similar to|akin to|analogous to|comparable to|"
    r"much like|just like|"
    r"maps onto|maps to|"
    r"translates to|translates into|"
    r"transferable to|"
    r"prepared me for|prepares me for|"
    r"equipped me (?:to|for)|"
    r"positions me to|position me to|"
    r"ready me for|readies me for|"
    r"mirrors the|parallels the|"
    r"(?:is|are|was|were) like"
    r")\b",
    re.IGNORECASE,
)

# Fraction of JD domain tokens that must also appear on the resume before
# the writer is allowed to "connect" experience to job duties.
_DOMAIN_MISMATCH_THRESHOLD = 0.15


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


def normalize_tech_name(name: str) -> str:
    """
    Normalize a technology name for allowlist comparison.

    Applies lowercasing, light cleanup, and alias folding (for example
    ``K8s`` -> ``kubernetes``, ``Postgres`` -> ``postgresql``).

    Args:
        name: Raw skill or technology string from profile or letter text.

    Returns:
        Canonical lowercase technology key.
    """
    cleaned = re.sub(r"\s+", " ", (name or "").strip().lower().replace("_", " "))
    if cleaned in _TECH_ALIASES:
        return _TECH_ALIASES[cleaned]
    return cleaned


def collect_profile_technical_skills(profile: UserProfile) -> Set[str]:
    """
    Build the Technical Skills allowlist from the candidate profile.

    Uses ``profile.skills`` entries whose category is not a soft skill or
    spoken language. Names are alias-normalized so resume ``Kubernetes``
    covers letter ``K8s``.

    Args:
        profile: Candidate profile whose skills section is the source of truth.

    Returns:
        Set of normalized technical skill names.
    """
    allowed: Set[str] = set()
    for skill in profile.skills or []:
        if skill.category in _NON_TECH_SKILL_CATEGORIES:
            continue
        if not skill.name:
            continue
        allowed.add(normalize_tech_name(skill.name))
    return allowed


def _technology_search_terms() -> List[tuple[str, str]]:
    """
    Return lexicon terms for free-text matching, longest first.

    Ambiguous short aliases such as ``go`` are omitted.

    Returns:
        List of (surface_form, canonical_key) pairs.
    """
    candidates: List[tuple[str, str]] = []
    for tech in _KNOWN_TECHNOLOGIES:
        candidates.append((tech, tech))
    for alias, canonical in _TECH_ALIASES.items():
        if alias in _AMBIGUOUS_TEXT_ALIASES:
            continue
        if alias in _KNOWN_TECHNOLOGIES:
            continue
        candidates.append((alias, canonical))
    candidates.sort(key=lambda item: len(item[0]), reverse=True)
    return candidates


def extract_technologies(text: str) -> Set[str]:
    """
    Extract known technology names from free text via the curated lexicon.

    Matches are case-insensitive and respect token boundaries so ordinary
    English is not treated as a technology. Ambiguous short aliases such as
    ``go`` are excluded from free-text matching.

    Presence-based: includes disclaimed and learn-intent mentions. Use
    ``extract_claimed_technologies`` when claim direction matters.

    Args:
        text: Cover-letter body or other free text.

    Returns:
        Set of canonical technology keys found in the text.
    """
    lowered = (text or "").lower()
    if not lowered.strip():
        return set()

    found: Set[str] = set()
    for term, canonical in _technology_search_terms():
        escaped = re.escape(term)
        pattern = re.compile(
            rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])",
            re.IGNORECASE,
        )
        if pattern.search(lowered):
            found.add(normalize_tech_name(canonical))
    return found


# Left-context cues that mean the following technology is disclaimed or
# framed as a learning goal, not a skill the candidate claims to have.
_TECH_DISCLAIMER_BEFORE_RE = re.compile(
    r"(?:^|[\s,;:(])(?:"
    r"rather\s+than|"
    r"instead\s+of|"
    r"other\s+than|"
    r"aside\s+from|"
    r"except(?:\s+for)?|"
    r"without|"
    r"not(?:\s+(?:with|using|in|proficient\s+in|"
    r"experienced\s+(?:in|with)|familiar\s+with))?|"
    r"no(?:\s+(?:prior|hands[- ]on|professional))?"
    r"(?:\s+experience\s+(?:in|with))?|"
    r"(?:do|does)\s+not\s+have|"
    r"don'?t\s+have|"
    r"haven'?t\s+(?:used|worked\s+with)|"
    r"have\s+not\s+(?:used|worked\s+with)|"
    r"never\s+(?:used|worked\s+with|touched)|"
    r"lacking|"
    r"lack\s+of|"
    r"unfamiliar\s+with|"
    r"new\s+to|"
    r"limited(?:\s+experience)?\s+(?:with|in)|"
    r"learn(?:ing|t)?|"
    r"pick(?:ing)?\s+up|"
    r"study(?:ing)?|"
    r"transition(?:ing)?\s+to|"
    r"switch(?:ing)?\s+to|"
    r"migrate(?:ing)?\s+to|"
    r"willing\s+to\s+learn|"
    r"eager\s+to\s+(?:learn|pick\s+up)"
    r")\s+$",
    re.IGNORECASE,
)


def _is_technology_mention_disclaimed(text: str, start: int, end: int) -> bool:
    """
    Return whether a technology span is in a disclaimer or learn-intent context.

    Inspects a short left window before ``start`` for phrases such as
    ``rather than``, ``don't have``, or ``pick up``.

    Args:
        text: Lowercased letter body (same casing used for the span).
        start: Inclusive start index of the technology match.
        end: Exclusive end index of the technology match.

    Returns:
        True when the mention should not count as a skill claim.
    """
    del end  # Span end reserved for future right-context checks.
    left = text[max(0, start - 96) : start]
    left = re.sub(r"\s+", " ", left)
    return bool(_TECH_DISCLAIMER_BEFORE_RE.search(left))


def extract_claimed_technologies(text: str) -> Set[str]:
    """
    Extract technologies the letter presents as skills the candidate has.

    Same lexicon and token boundaries as ``extract_technologies``, but skips
    mentions that only appear in disclaimer or learn-intent contexts (for
    example ``rather than Java`` or ``eager to pick up Java``). If any
    non-disclaimed mention of a technology remains, that technology is kept.

    Args:
        text: Cover-letter body or other free text.

    Returns:
        Set of canonical technology keys claimed (not merely mentioned).
    """
    lowered = (text or "").lower()
    if not lowered.strip():
        return set()

    claimed: Set[str] = set()
    for term, canonical in _technology_search_terms():
        escaped = re.escape(term)
        pattern = re.compile(
            rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])",
            re.IGNORECASE,
        )
        for match in pattern.finditer(lowered):
            if not _is_technology_mention_disclaimed(
                lowered, match.start(), match.end()
            ):
                claimed.add(normalize_tech_name(canonical))
                break
    return claimed


def redact_unsupported_technologies(text: str, profile: UserProfile) -> str:
    """
    Remove known technologies from JD text that are absent from the resume.

    Prevents the writer prompt from teaching the model JD-only stacks.
    Resume-supported names (Technical Skills plus project/experience tech)
    are left in place.

    Args:
        text: Job description or requirement text.
        profile: Candidate profile used as the allowlist.

    Returns:
        Text with unsupported technology names removed.
    """
    if not text or not text.strip():
        return text or ""
    allowed = collect_resume_supported_names(profile)
    redacted = text
    for term, canonical in _technology_search_terms():
        if normalize_tech_name(canonical) in allowed:
            continue
        escaped = re.escape(term)
        pattern = re.compile(
            rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])",
            re.IGNORECASE,
        )
        redacted = pattern.sub("", redacted)
    redacted = re.sub(r"[ \t]{2,}", " ", redacted)
    redacted = re.sub(r"\s+,", ",", redacted)
    redacted = re.sub(r",\s*,+", ",", redacted)
    redacted = re.sub(r"\(\s*\)", "", redacted)
    return redacted.strip()


def flag_fabricated_technologies(
    letter_text: str,
    profile: UserProfile,
) -> List[str]:
    """
    Flag technologies the letter claims that are absent from the resume.

    Detection is limited to the curated tech lexicon so ordinary English is
    not flagged. Mentions in disclaimer or learn-intent contexts (for
    example ``rather than Java`` or ``pick up Java``) are ignored. The
    allowlist is Technical Skills plus technologies listed on experience
    and projects (same set as writer keyword filtering). JD-only names such
    as AWS that never appear on the resume are returned as hard grounding
    findings when claimed.

    Args:
        letter_text: Generated cover-letter body.
        profile: Candidate profile providing the Technical Skills allowlist.

    Returns:
        Sorted list of fabricated canonical technology names.
    """
    claimed = extract_claimed_technologies(letter_text)
    allowed = collect_resume_supported_names(profile)
    fabricated = sorted(tech for tech in claimed if tech not in allowed)
    return fabricated


def collect_resume_supported_names(profile: UserProfile) -> Set[str]:
    """
    Build normalized names that selection keywords may safely emphasize.

    Includes Technical Skills plus technologies listed on experience and
    project entities (so project-stack keywords remain usable without
    inventing JD-only tools).

    Args:
        profile: Candidate profile.

    Returns:
        Set of normalized technology / skill names.
    """
    allowed = set(collect_profile_technical_skills(profile))
    for skill in profile.skills or []:
        if skill.name:
            allowed.add(normalize_tech_name(skill.name))
    for exp in profile.experience or []:
        for tech in exp.technologies or []:
            if tech:
                allowed.add(normalize_tech_name(tech))
    for project in profile.projects or []:
        for tech in project.technologies or []:
            if tech:
                allowed.add(normalize_tech_name(tech))
    return allowed


def filter_resume_supported_keywords(
    keywords: Sequence[str],
    profile: UserProfile,
) -> List[str]:
    """
    Keep selection keywords that are supported by the resume corpus.

    A keyword is kept when its normalized form is a known profile tech/skill
    name, or when the keyword (or its significant words) appears in the
    resume bullet corpus. JD-only stacks that fail both checks are dropped
    before they reach the writer prompt.

    Args:
        keywords: Keywords proposed by the selector stage.
        profile: Candidate profile used as the source of truth.

    Returns:
        Filtered keyword list preserving original order and casing.
    """
    if not keywords:
        return []

    allowed_names = collect_resume_supported_names(profile)
    resume_bullets = collect_resume_bullets(profile)
    corpus_lower = " ".join(resume_bullets).lower()
    corpus_words = set()
    for bullet in resume_bullets:
        corpus_words.update(significant_words(bullet))

    kept: List[str] = []
    seen: Set[str] = set()
    for raw in keywords:
        keyword = (raw or "").strip()
        if not keyword:
            continue
        key = keyword.lower()
        if key in seen:
            continue
        normalized = normalize_tech_name(keyword)
        words = significant_words(keyword)
        supported = (
            normalized in allowed_names
            or key in corpus_lower
            or (bool(words) and all(word in corpus_words for word in words))
        )
        if supported:
            kept.append(keyword)
            seen.add(key)
    return kept


def merged_experience_years(profile: UserProfile) -> float:
    """
    Compute total years of work experience from merged date intervals.

    Overlapping roles are merged so concurrent positions do not double-count.
    Non-overlapping roles (for example an internship plus a later program)
    add together. End date ``None`` is treated as today.

    Args:
        profile: Candidate profile with dated ``experience`` entries.

    Returns:
        Total years of coverage rounded to one decimal place.
    """
    intervals: List[tuple[datetime, datetime]] = []
    now = datetime.now()
    for exp in profile.experience or []:
        start = getattr(exp, "start_date", None)
        if start is None:
            continue
        end = exp.end_date or now
        if end < start:
            continue
        intervals.append((start, end))

    if not intervals:
        return 0.0

    intervals.sort(key=lambda item: item[0])
    merged: List[tuple[datetime, datetime]] = [intervals[0]]
    for start, end in intervals[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))

    total_days = sum((end - start).days for start, end in merged)
    return round(total_days / 365.25, 1)


_WORD_YEAR_VALUES: dict[str, float] = {
    "one": 1.0,
    "two": 2.0,
    "three": 3.0,
    "four": 4.0,
    "five": 5.0,
    "six": 6.0,
    "seven": 7.0,
    "eight": 8.0,
    "nine": 9.0,
    "ten": 10.0,
}

_DURATION_CLAIM_RE = re.compile(
    r"(?P<prefix>over|more than|nearly|about|approximately|around|at least)?"
    r"\s*"
    r"(?P<low>\d+(?:\.\d+)?|" + "|".join(_WORD_YEAR_VALUES.keys()) + r")"
    r"(?:\s*(?:[-–—]|to)\s*"
    r"(?P<high>\d+(?:\.\d+)?|" + "|".join(_WORD_YEAR_VALUES.keys()) + r"))?"
    r"\s*\+?\s*years?(?:\s+of)?",
    re.IGNORECASE,
)

_FROM_TO_PERCENT_RE = re.compile(
    r"(?:from\s+)?(?P<a>\d+(?:\.\d+)?)\s*%\s*(?:to|->|–|-)\s*(?P<b>\d+(?:\.\d+)?)\s*%",
    re.IGNORECASE,
)

_CLAIMED_GAIN_PERCENT_RE = re.compile(
    r"(?:"
    r"(?:by|of)\s+(?:nearly|almost|approximately|about|roughly|over)?\s*"
    r"(?P<z1>\d+(?:\.\d+)?)\s*%"
    r"|"
    r"(?:improved|increased|enhanced|boosted|grew)\s+(?:by\s+)?"
    r"(?:nearly|almost|approximately|about|roughly|over)?\s*"
    r"(?P<z2>\d+(?:\.\d+)?)\s*%"
    r"|"
    r"(?P<z3>\d+(?:\.\d+)?)\s*%\s*"
    r"(?:increase|improvement|gain|enhancement|boost)"
    r")",
    re.IGNORECASE,
)

_DURATION_TOLERANCE_YEARS = 0.5
_PERCENT_TOLERANCE = 2.0


def _parse_year_token(token: str) -> Optional[float]:
    """
    Parse a numeric or word year token into a float.

    Args:
        token: Digits or English year word (e.g. ``five``).

    Returns:
        Years as float, or ``None`` when the token is not recognized.
    """
    cleaned = (token or "").strip().lower()
    if not cleaned:
        return None
    if cleaned in _WORD_YEAR_VALUES:
        return _WORD_YEAR_VALUES[cleaned]
    try:
        return float(cleaned)
    except ValueError:
        return None


def flag_inflated_duration_claims(
    letter_text: str,
    profile: UserProfile,
) -> List[dict]:
    """
    Flag duration claims that exceed merged resume experience (or skill years).

    Extracts patterns such as ``over 2 years``, ``2-3 years``, and
    ``five years of``. The default cap is total years from merged,
    non-overlapping experience intervals. When a sentence also names a
    skill that has ``years_of_experience`` set, that skill-specific cap
    is applied for the claim.

    Args:
        letter_text: Generated cover-letter body.
        profile: Candidate profile with dated experience and optional
            per-skill years.

    Returns:
        List of ``{"sentence": str, "claimed_years": float, "cap_years": float,
        "flags": list[str]}`` findings.
    """
    if not letter_text or not letter_text.strip():
        return []

    total_cap = merged_experience_years(profile)
    skill_caps: List[tuple[str, float]] = []
    for skill in profile.skills or []:
        if not skill.name or skill.years_of_experience is None:
            continue
        skill_caps.append((skill.name.lower(), float(skill.years_of_experience)))

    findings: List[dict] = []
    for sentence in _SENTENCE_SPLIT.split(letter_text.strip()):
        cleaned = sentence.strip().rstrip(".")
        if not cleaned:
            continue
        lowered = cleaned.lower()
        for match in _DURATION_CLAIM_RE.finditer(lowered):
            low = _parse_year_token(match.group("low") or "")
            if low is None:
                continue
            prefix = (match.group("prefix") or "").lower()
            # Range lower bound is the conservative claim amount.
            claimed = low
            if prefix in {"over", "more than", "at least"}:
                claimed = low
            elif prefix == "nearly":
                claimed = low

            cap = total_cap
            for skill_name, skill_years in skill_caps:
                if skill_name in lowered:
                    cap = min(cap, skill_years) if cap > 0 else skill_years

            if claimed > cap + _DURATION_TOLERANCE_YEARS:
                flag = (
                    f"Inflated duration: claimed {claimed:g} years exceeds "
                    f"resume cap of {cap:g} years"
                )
                findings.append(
                    {
                        "sentence": cleaned,
                        "claimed_years": claimed,
                        "cap_years": cap,
                        "flags": [flag],
                    }
                )
                break
    return findings


def flag_inconsistent_percent_claims(letter_text: str) -> List[dict]:
    """
    Flag percentage gains that disagree with stated from/to endpoints.

    When a sentence (or adjacent clause) states ``from A% to B%`` and also
    claims a gain of ``Z%``, accept Z if it matches the absolute point
    change (B−A) or the relative change ((B−A)/A×100) within two points.
    Otherwise hard-flag the sentence.

    Coverage boundary (v1): qualitative inflation without numeric endpoints
    (for example ``nearly doubled my accuracy``) is not checked.

    Args:
        letter_text: Generated cover-letter body.

    Returns:
        List of ``{"sentence": str, "from_pct": float, "to_pct": float,
        "claimed_pct": float, "flags": list[str]}`` findings.
    """
    if not letter_text or not letter_text.strip():
        return []

    findings: List[dict] = []
    for sentence in _SENTENCE_SPLIT.split(letter_text.strip()):
        cleaned = sentence.strip().rstrip(".")
        if not cleaned:
            continue
        endpoints = _FROM_TO_PERCENT_RE.search(cleaned)
        if not endpoints:
            continue
        start_pct = float(endpoints.group("a"))
        end_pct = float(endpoints.group("b"))
        gain_match = _CLAIMED_GAIN_PERCENT_RE.search(cleaned)
        if not gain_match:
            continue
        claimed_raw = (
            gain_match.group("z1") or gain_match.group("z2") or gain_match.group("z3")
        )
        if claimed_raw is None:
            continue
        claimed = float(claimed_raw)
        absolute = abs(end_pct - start_pct)
        relative = abs((end_pct - start_pct) / start_pct) * 100.0 if start_pct else None
        matches_absolute = abs(claimed - absolute) <= _PERCENT_TOLERANCE
        matches_relative = (
            relative is not None and abs(claimed - relative) <= _PERCENT_TOLERANCE
        )
        if matches_absolute or matches_relative:
            continue
        expected = f"{absolute:g} pp"
        if relative is not None:
            expected += f" or ~{relative:.0f}% relative"
        flag = (
            f"Inconsistent metric: claimed {claimed:g}% gain from "
            f"{start_pct:g}% to {end_pct:g}% (expected {expected})"
        )
        findings.append(
            {
                "sentence": cleaned,
                "from_pct": start_pct,
                "to_pct": end_pct,
                "claimed_pct": claimed,
                "flags": [flag],
            }
        )
    return findings


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


def _whole_term_in_text(text: str, term: str) -> bool:
    """
    Return True when ``term`` appears as a whole token in ``text``.

    Args:
        text: Haystack (already lowercased is fine).
        term: Needle, such as ``rag``.

    Returns:
        True when the term is bounded by non-alphanumeric characters.
    """
    if not text or not term:
        return False
    return (
        re.search(
            rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])",
            text,
            re.IGNORECASE,
        )
        is not None
    )


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
            if _whole_term_in_text(lowered, term) and not _whole_term_in_text(
                known_lower, term
            ):
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


def collect_jd_domain_text(job: JobListing) -> str:
    """
    Build the JD text used for domain-overlap and analogical checks.

    Prefers title, structured skills, and requirement bullets. Falls back
    to the start of the description when those fields are too thin (typical
    of a pasted JD).

    Args:
        job: Target job listing.

    Returns:
        Concatenated domain text. Company name is omitted so unique
        employer tokens do not dominate the overlap denominator.
    """
    parts: List[str] = [job.title or ""]
    for skill in job.skills or []:
        name = getattr(skill, "name", None)
        if name:
            parts.append(str(name))
    for req in job.requirements or []:
        text = getattr(req, "text", None)
        if text:
            parts.append(str(text))
    body = " ".join(part for part in parts if part).strip()
    if len(significant_words(body)) >= 6:
        return body
    description = (job.description or "")[:800]
    return f"{body} {description}".strip()


def jd_resume_overlap_ratio(job: JobListing, profile: UserProfile) -> float:
    """
    Return the fraction of JD domain tokens that also appear on the resume.

    Args:
        job: Target job listing.
        profile: Candidate profile used as the resume corpus.

    Returns:
        Overlap in ``[0.0, 1.0]``. Returns ``1.0`` when the JD has no
        significant tokens so mismatch mode does not fire on empty jobs.
    """
    jd_words = set(significant_words(collect_jd_domain_text(job)))
    if not jd_words:
        return 1.0
    resume_words: Set[str] = set()
    for bullet in collect_resume_bullets(profile):
        resume_words.update(significant_words(bullet))
    return len(jd_words & resume_words) / len(jd_words)


def is_domain_mismatch(
    job: JobListing,
    profile: UserProfile,
    threshold: float = _DOMAIN_MISMATCH_THRESHOLD,
) -> bool:
    """
    Return whether JD duties have little lexical overlap with the resume.

    Args:
        job: Target job listing.
        profile: Candidate profile.
        threshold: Maximum overlap ratio treated as a mismatch.

    Returns:
        True when overlap is below ``threshold``.
    """
    return jd_resume_overlap_ratio(job, profile) < threshold


def flag_analogical_claims(
    letter_text: str,
    profile: UserProfile,
    job: JobListing,
    resume_bullets: Optional[Sequence[str]] = None,
) -> List[dict]:
    """
    Flag sentences that analogize resume facts onto JD-only duties.

    Whole-sentence overlap cannot catch this: the resume half of
    "evaluation pipelines are like work orders" keeps the ratio high.
    The analogized target (text after the glue phrase) must be grounded
    in the resume. Job title and company may appear in the target.

    Args:
        letter_text: Full cover letter body.
        profile: Candidate profile used as the factual source of truth.
        job: Target job listing (JD-only duty vocabulary).
        resume_bullets: Optional resume corpus. Selection reasons must not
            be passed in; they can invent JD alignment.

    Returns:
        A list of ``{"sentence": str, "flags": list[str]}`` entries.
    """
    if not letter_text or not letter_text.strip():
        return []

    bullets = (
        list(resume_bullets)
        if resume_bullets is not None
        else collect_resume_bullets(profile)
    )
    resume_words: Set[str] = set()
    for bullet in bullets:
        resume_words.update(significant_words(bullet))

    allowed = set(resume_words)
    allowed.update(significant_words(job.title or ""))
    allowed.update(significant_words(job.company or ""))

    jd_words = set(significant_words(collect_jd_domain_text(job)))
    jd_words.update(significant_words(job.description or ""))
    for req in job.requirements or []:
        text = getattr(req, "text", None)
        if text:
            jd_words.update(significant_words(str(text)))

    findings: List[dict] = []
    for sentence in _SENTENCE_SPLIT.split(letter_text.strip()):
        cleaned = sentence.strip().rstrip(".")
        if not cleaned:
            continue
        match = _ANALOGY_MARKER_RE.search(cleaned)
        if not match:
            continue
        target = cleaned[match.end() :]
        target_words = significant_words(target)
        if not target_words:
            continue
        jd_only = [
            word for word in target_words if word in jd_words and word not in allowed
        ]
        if not jd_only:
            continue
        joined = ", ".join(jd_only)
        findings.append(
            {
                "sentence": cleaned,
                "flags": [
                    "Analogical claim: resume work is mapped onto JD-only "
                    f"duties ({joined})"
                ],
            }
        )
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
_PENALTY_FABRICATED_TECH = 10
_PENALTY_INFLATED_DURATION = 10
_PENALTY_INCONSISTENT_METRIC = 10
_PENALTY_ANALOGICAL_CLAIM = 12
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
    fabricated_technologies: Optional[Sequence[str]] = None,
    inflated_duration_claims: Optional[Sequence[Dict[str, Any]]] = None,
    inconsistent_percent_claims: Optional[Sequence[Dict[str, Any]]] = None,
    analogical_claims: Optional[Sequence[Dict[str, Any]]] = None,
) -> tuple[int, Dict[str, Any]]:
    """
    Score grounding findings by severity instead of a flat per-issue penalty.

    Soft ungrounded sentences (weak lexical overlap / vague phrasing) cost
    little. Hard ungrounded overclaim verbs, scope inflation, technique
    mismatches, fabricated technologies, inflated duration claims, and
    inconsistent percentage arithmetic cost substantially more. Total
    deduction is capped so other content dimensions remain visible.

    Args:
        ungrounded_sentences: Sentences failing resume overlap checks.
        claim_overclaims: Scope/technique findings with per-sentence flags.
        fabricated_technologies: Tech names claimed in the letter but absent
            from the resume Technical Skills allowlist.
        inflated_duration_claims: Duration findings that exceed merged
            resume experience (or skill-specific years).
        inconsistent_percent_claims: From/to percentage claims whose stated
            gain Z% matches neither absolute nor relative math.
        analogical_claims: Sentences that map resume facts onto JD-only
            duties via analogy glue phrases.

    Returns:
        Tuple of (penalty points to subtract from content score, breakdown
        dict with soft/hard/scope/technique/fabricated_tech/inflated_duration/
        inconsistent_metric/analogical_claim counts and raw vs capped penalty).
    """
    overclaim_keys = {
        _normalize_finding_sentence(item["sentence"])
        for item in claim_overclaims
        if item.get("sentence")
    }
    for item in inflated_duration_claims or []:
        if item.get("sentence"):
            overclaim_keys.add(_normalize_finding_sentence(item["sentence"]))
    for item in inconsistent_percent_claims or []:
        if item.get("sentence"):
            overclaim_keys.add(_normalize_finding_sentence(item["sentence"]))
    for item in analogical_claims or []:
        if item.get("sentence"):
            overclaim_keys.add(_normalize_finding_sentence(item["sentence"]))

    soft_count = 0
    hard_count = 0
    for sentence in ungrounded_sentences:
        key = _normalize_finding_sentence(sentence)
        # Scope/technique/duration/metric findings already carry harder
        # penalties; do not double-count the same sentence as soft/hard.
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

    fabricated_count = len(fabricated_technologies or [])
    inflated_count = len(inflated_duration_claims or [])
    metric_count = len(inconsistent_percent_claims or [])
    analogical_count = len(analogical_claims or [])

    raw = (
        soft_count * _PENALTY_SOFT_UNGROUNDED
        + hard_count * _PENALTY_HARD_UNGROUNDED
        + scope_count * _PENALTY_SCOPE_INFLATION
        + technique_count * _PENALTY_TECHNIQUE_MISMATCH
        + fabricated_count * _PENALTY_FABRICATED_TECH
        + inflated_count * _PENALTY_INFLATED_DURATION
        + metric_count * _PENALTY_INCONSISTENT_METRIC
        + analogical_count * _PENALTY_ANALOGICAL_CLAIM
    )
    penalty = min(raw, _MAX_GROUNDING_PENALTY)
    breakdown: Dict[str, Any] = {
        "soft_ungrounded": soft_count,
        "hard_ungrounded": hard_count,
        "scope_inflation": scope_count,
        "technique_mismatch": technique_count,
        "fabricated_tech": fabricated_count,
        "inflated_duration": inflated_count,
        "inconsistent_metric": metric_count,
        "analogical_claim": analogical_count,
        "raw_penalty": raw,
        "capped_penalty": penalty,
        "weights": {
            "soft_ungrounded": _PENALTY_SOFT_UNGROUNDED,
            "hard_ungrounded": _PENALTY_HARD_UNGROUNDED,
            "scope_inflation": _PENALTY_SCOPE_INFLATION,
            "technique_mismatch": _PENALTY_TECHNIQUE_MISMATCH,
            "fabricated_tech": _PENALTY_FABRICATED_TECH,
            "inflated_duration": _PENALTY_INFLATED_DURATION,
            "inconsistent_metric": _PENALTY_INCONSISTENT_METRIC,
            "analogical_claim": _PENALTY_ANALOGICAL_CLAIM,
            "max_penalty": _MAX_GROUNDING_PENALTY,
        },
    }
    return penalty, breakdown
