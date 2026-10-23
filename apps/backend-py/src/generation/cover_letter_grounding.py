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
# Bare verbs (led, managed, headed, oversaw) are matched with the object
# that follows them. "called the" does not match "led the".
_SCOPE_INFLATION_PHRASES: tuple[str, ...] = (
    "leading the development",
    "led the development",
    "leading development",
    "led development",
    "architected the platform",
    "drove the strategy",
    "drove strategy",
    "owned entirely",
    "spearheaded",
    "leading the",
    "led the",
    "owned the",
    "managed",
    "headed",
    "oversaw",
    "leading",
    "led",
)

# A bare verb needs an object. A longer phrase is a claim by itself.
_SCOPE_BARE_VERBS: frozenset[str] = frozenset(
    {"led", "leading", "managed", "headed", "oversaw"}
)

# Words that do not start the object of a bare leadership verb.
_SCOPE_NON_OBJECT_STARTS: frozenset[str] = frozenset({"to", "me", "us", "them"})

# An article before "leading" marks an adjective ("a leading lab").
_ADJECTIVE_LEADING_PREFIX_RE = re.compile(r"\b(?:a|an|the)\s+$", re.IGNORECASE)

# Words that end the object of a leadership claim.
_SCOPE_OBJECT_STOPS: frozenset[str] = frozenset(
    {
        "at",
        "for",
        "on",
        "in",
        "with",
        "using",
        "while",
        "before",
        "after",
        "during",
        "because",
        "and",
        "then",
        "so",
        "but",
        "when",
        "where",
        "to",
        "that",
        "which",
        "who",
        "whose",
    }
)

_SCOPE_HEAD_RE = re.compile(
    r"\b(?P<head>"
    + "|".join(re.escape(phrase) for phrase in _SCOPE_INFLATION_PHRASES)
    + r")\b",
    re.IGNORECASE,
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
    "reinforcement learning",
    "reranking",
    "distillation",
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


# Ordinary English words that are also product names. They count only in a
# technology context (a product name, or a neighboring technology word).
_CONTEXTUAL_HOMONYMS: frozenset[str] = frozenset(
    {"swift", "express", "spring", "spark"}
)

# Right-hand words that keep the homonym in ordinary English.
_HOMONYM_ORDINARY_RIGHT: dict[str, frozenset[str]] = {
    "swift": frozenset({"reply", "response", "pace", "action"}),
    "express": frozenset({"my", "our", "interest", "gratitude", "concern"}),
    "spring": frozenset({"semester", "term", "break", "season", "flowers"}),
    "spark": frozenset({"curiosity", "interest", "joy", "debate"}),
}

_HOMONYM_LEFT_TECH_RE = re.compile(
    r"(?:"
    r"\bapache\s+|"
    r"(?:\bbuilt|\bwritten|\bdeveloped|\bimplemented|\bcoded|"
    r"\bshipped|\bwrote|\bused|\busing)"
    r"(?:\s+(?:with|in|using))?\s+"
    r")$",
    re.IGNORECASE,
)

_HOMONYM_RIGHT_TECH_RE: dict[str, re.Pattern[str]] = {
    "spring": re.compile(
        r"^\s*(?:boot|framework|mvc|cloud|data|security|batch|services?)\b",
        re.IGNORECASE,
    ),
    "express": re.compile(
        r"^\s*(?:\.js|js|server|servers|framework|middleware)\b",
        re.IGNORECASE,
    ),
    "spark": re.compile(
        r"^\s*(?:sql|streaming|cluster|jobs?)\b",
        re.IGNORECASE,
    ),
    "swift": re.compile(
        r"^(?:ui\b|\s*(?:for\s+ios|on\s+ios))\b",
        re.IGNORECASE,
    ),
}

# Product names with no token boundary inside the name (SwiftUI, ExpressJS).
_COMPOUND_PRODUCT_RES: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"(?<![A-Za-z0-9])swiftui(?![A-Za-z0-9])", re.IGNORECASE),
        "swift",
    ),
    (
        re.compile(r"(?<![A-Za-z0-9])expressjs(?![A-Za-z0-9])", re.IGNORECASE),
        "express",
    ),
)

# "in Go" / "written in Go" / "using Go". The next word must not be an
# ordinary "go" phrase such as "go live" or "go through".
_GO_IN_CONTEXT_RE = re.compile(
    r"(?:"
    r"(?:written|built|coded|developed|implemented)\s+in\s+|"
    r"(?:using|with)\s+|"
    r"(?<![A-Za-z])in\s+"
    r")(?P<go>go)(?![A-Za-z0-9])",
    re.IGNORECASE,
)
_GO_NOT_TECH_NEXT_RE = re.compile(
    r"^\s*(?:live|through|ahead|back|on|out|away|home|for|to)\b",
    re.IGNORECASE,
)
_GO_SERVICE_RE = re.compile(
    r"(?<![A-Za-z0-9])(?P<go>go)(?=\s+services?(?![A-Za-z0-9]))",
    re.IGNORECASE,
)

# A SQL database on the resume supports a letter that says SQL.
# The reverse is not implied: a letter that says PostgreSQL still needs
# PostgreSQL (or an alias) on the resume. SQL does not stand in for the
# database name.
_SQL_DATABASES: frozenset[str] = frozenset(
    {
        "postgresql",
        "mysql",
        "sqlite",
        "mariadb",
        "sql server",
        "oracle",
    }
)


def _homonym_in_tech_context(
    text: str,
    start: int,
    end: int,
    canonical: str,
) -> bool:
    """
    Return whether a homonym span is a technology mention.

    ``swift``, ``express``, ``spring``, and ``spark`` stay ordinary English
    unless they are a product name or sit next to a technology word.

    Args:
        text: Source text. Matching is case-insensitive.
        start: Inclusive start index of the homonym.
        end: Exclusive end index of the homonym.
        canonical: Lexicon key for the matched term.

    Returns:
        True when the span should count as a technology.
    """
    left = text[max(0, start - 64) : start]
    right = text[end : end + 32]
    ordinary = _HOMONYM_ORDINARY_RIGHT.get(canonical, frozenset())
    right_word = re.match(r"^\s*([A-Za-z]+)", right)
    if right_word is not None and right_word.group(1).lower() in ordinary:
        return False
    if _HOMONYM_LEFT_TECH_RE.search(left):
        return True
    right_re = _HOMONYM_RIGHT_TECH_RE.get(canonical)
    if right_re is not None and right_re.search(right):
        return True
    if canonical == "swift" and re.search(r"(?:^|\s)in\s+$", left, re.IGNORECASE):
        return True
    return False


def _iter_contextual_go_spans(text: str) -> list[tuple[int, int]]:
    """
    Return spans of bare ``Go`` that sit in a technology context.

    Matches ``in Go``, ``written in Go``, ``using Go``, ``with Go``, and
    ``Go service`` / ``Go services``. ``go live``, ``go through``, and
    ``ready to go`` do not match. ``Golang`` is a lexicon term and is not
    handled here.

    Args:
        text: Source text. Matching is case-insensitive.

    Returns:
        ``(start, end)`` pairs for the word ``Go`` only.
    """
    spans: list[tuple[int, int]] = []
    for match in _GO_IN_CONTEXT_RE.finditer(text):
        end = match.end("go")
        if _GO_NOT_TECH_NEXT_RE.match(text[end:]):
            continue
        spans.append((match.start("go"), end))
    for match in _GO_SERVICE_RE.finditer(text):
        spans.append((match.start("go"), match.end("go")))
    return spans


def _iter_technology_matches(text: str) -> list[tuple[int, int, str]]:
    """
    Return accepted technology spans in ``text``.

    Homonyms count only in a technology context. Bare ``Go`` counts only in
    a technology context. Other lexicon terms use token boundaries.

    Args:
        text: Cover-letter body or other free text.

    Returns:
        ``(start, end, canonical)`` triples. Indexes refer to ``text``.
    """
    if not text or not text.strip():
        return []
    matches: list[tuple[int, int, str]] = []
    for term, canonical in _technology_search_terms():
        key = normalize_tech_name(canonical)
        pattern = re.compile(
            rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])",
            re.IGNORECASE,
        )
        for match in pattern.finditer(text):
            if canonical in _CONTEXTUAL_HOMONYMS and not _homonym_in_tech_context(
                text, match.start(), match.end(), canonical
            ):
                continue
            matches.append((match.start(), match.end(), key))
    for pattern, canonical in _COMPOUND_PRODUCT_RES:
        for match in pattern.finditer(text):
            matches.append((match.start(), match.end(), canonical))
    for start, end in _iter_contextual_go_spans(text):
        matches.append((start, end, "golang"))
    return matches


def _allow_sql_when_database_present(allowed: Set[str]) -> Set[str]:
    """
    Add SQL when the resume lists a SQL database.

    PostgreSQL, MySQL, SQLite, MariaDB, SQL Server, and Oracle are SQL.
    A letter that names one of those databases still needs that database
    on the resume.

    Args:
        allowed: Normalized resume technology names.

    Returns:
        The same names, plus ``sql`` when a SQL database is present.
    """
    if allowed & _SQL_DATABASES:
        return set(allowed) | {"sql"}
    return set(allowed)


def extract_technologies(text: str) -> Set[str]:
    """
    Extract known technology names from free text via the curated lexicon.

    Matches are case-insensitive and respect token boundaries so ordinary
    English is not treated as a technology. The homonyms ``swift``,
    ``express``, ``spring``, and ``spark`` count only in a technology
    context. Bare ``Go`` counts only in a technology context (``in Go``,
    ``written in Go``, ``Go services``). ``Golang`` is a normal lexicon term.

    Presence-based: includes disclaimed and learn-intent mentions. Use
    ``extract_claimed_technologies`` when claim direction matters.

    Args:
        text: Cover-letter body or other free text.

    Returns:
        Set of canonical technology keys found in the text.
    """
    return {canonical for _, _, canonical in _iter_technology_matches(text or "")}


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
    r"haven'?t\s+(?:used|worked\s+with|run)|"
    r"have\s+not\s+(?:used|worked\s+with|run)|"
    r"never\s+(?:used|worked\s+with|touched|run)|"
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

    Same lexicon, homonym context, and token boundaries as
    ``extract_technologies``, but skips mentions that only appear in
    disclaimer or learn-intent contexts (for example ``rather than Java``,
    ``I have not run Kubernetes``, or ``eager to pick up Java``). If any
    non-disclaimed mention of a technology remains, that technology is kept.

    Args:
        text: Cover-letter body or other free text.

    Returns:
        Set of canonical technology keys claimed (not merely mentioned).
    """
    if not text or not text.strip():
        return set()

    claimed: Set[str] = set()
    for start, end, canonical in _iter_technology_matches(text):
        if canonical in claimed:
            continue
        if not _is_technology_mention_disclaimed(text, start, end):
            claimed.add(canonical)
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
    seen: set[tuple[int, int]] = set()
    spans: list[tuple[int, int]] = []
    for start, end, canonical in _iter_technology_matches(text):
        if canonical in allowed or (start, end) in seen:
            continue
        seen.add((start, end))
        spans.append((start, end))
    redacted = text
    for start, end in sorted(spans, reverse=True):
        redacted = redacted[:start] + redacted[end:]
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
    not flagged. Homonyms and bare ``Go`` count only in a technology
    context. Mentions in disclaimer or learn-intent contexts (for example
    ``rather than Java``, ``I have not run Kubernetes``, or ``pick up
    Java``) are ignored. The allowlist is Technical Skills plus technologies
    listed on experience and projects (same set as writer keyword filtering).
    A SQL database on that allowlist also supports a claim of SQL. The
    reverse is not implied. JD-only names such as AWS that never appear on
    the resume are returned as hard grounding findings when claimed.

    Args:
        letter_text: Generated cover-letter body.
        profile: Candidate profile providing the Technical Skills allowlist.

    Returns:
        Sorted list of fabricated canonical technology names.
    """
    claimed = extract_claimed_technologies(letter_text)
    allowed = _allow_sql_when_database_present(collect_resume_supported_names(profile))
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
    ``five years of``. A range is compared by its top: the guide counts
    a range as inflated when that top is longer than the cap, and a
    reader takes the top as the claim. A single number, including
    ``over 5 years``, stays that number. The default cap is total years
    from merged, non-overlapping experience intervals. When a sentence
    also names a skill that has ``years_of_experience`` set, that
    skill-specific cap is applied for the claim.

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
            high = _parse_year_token(match.group("high") or "")
            # The top of a range is the claim. The guide counts a range
            # as inflated when its top is longer than the cap, and a
            # reader takes the top as the claim. A single number,
            # including "over 5 years", stays that number.
            claimed = high if high is not None else low

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


def _normalize_scope_text(text: str) -> str:
    """
    Lowercase a leadership claim and write number words as digits.

    ``twelve`` and ``12`` become the same token, so a claim and a resume
    bullet can match when only the number spelling differs.

    Args:
        text: Claim or resume text.

    Returns:
        Normalized text with one space between words.
    """
    lowered = re.sub(r"\s+", " ", (text or "").lower()).strip()
    for word in sorted(_CLAIM_NUMBER_VALUES, key=len, reverse=True):
        value = _CLAIM_NUMBER_VALUES[word]
        digits = str(int(value)) if float(value).is_integer() else str(value)
        lowered = re.sub(rf"\b{re.escape(word)}\b", digits, lowered)
    return lowered


def _leadership_claims(text: str) -> List[str]:
    """
    Return leadership claims in ``text``, each with its object.

    A bare verb such as ``led`` or ``managed`` counts only with a noun
    phrase after it: ``to``, ``me``, ``us``, and ``them`` do not start
    an object. ``leading`` after ``a``, ``an``, ``the``, or a hyphen is
    an adjective, not a claim. The object stops at a preposition or a
    clause word such as ``to`` or ``that``, and it is at most six words.
    ``called the`` does not match ``led the``.

    Args:
        text: One sentence, any case.

    Returns:
        Claim strings such as ``led a team of 3 engineers``.
    """
    claims: List[str] = []
    for match in _SCOPE_HEAD_RE.finditer(text or ""):
        head = match.group("head")
        prefix = (text or "")[: match.start()]
        if head.lower().startswith("leading") and (
            prefix.endswith("-") or _ADJECTIVE_LEADING_PREFIX_RE.search(prefix)
        ):
            continue
        words: List[str] = []
        for word in (text or "")[match.end() :].split():
            bare = word.strip(".,;:").lower()
            if (
                not words
                and head.lower() in _SCOPE_BARE_VERBS
                and bare in _SCOPE_NON_OBJECT_STARTS
            ):
                break
            if not bare or bare in _SCOPE_OBJECT_STOPS:
                break
            words.append(word.strip(".,;:"))
            if len(words) >= 6:
                break
        if not words:
            if head.lower() in _SCOPE_BARE_VERBS:
                continue
            claims.append(head)
            continue
        claims.append(f"{head} {' '.join(words)}")
    return claims


def _resume_has_leadership_claim(claim: str, resume_text: str) -> bool:
    """
    Return whether the resume states the same leadership claim.

    The comparison is the whole claim, including the object. Number words
    and digits are equal. The verb on a different object does not match.

    Args:
        claim: Leadership claim from the letter.
        resume_text: Resume corpus.

    Returns:
        True when the normalized claim appears in the resume text.
    """
    normalized = _normalize_scope_text(claim)
    if not normalized:
        return False
    return normalized in _normalize_scope_text(resume_text)


def _project_name_spans(
    sentence: str, project_names: Sequence[str]
) -> List[tuple[int, int, str]]:
    """
    Find project-name spans in a sentence.

    A shorter name that sits inside a longer name is dropped, so
    ``Desk`` does not steal a span from ``North Desk``.

    Args:
        sentence: Cover-letter sentence.
        project_names: Known project names.

    Returns:
        ``(start, end, name)`` spans in the sentence.
    """
    lowered = (sentence or "").lower()
    raw: List[tuple[int, int, str]] = []
    for name in project_names:
        if not name:
            continue
        pattern = re.compile(
            rf"(?<![A-Za-z0-9]){re.escape(name.lower())}(?![A-Za-z0-9])"
        )
        for match in pattern.finditer(lowered):
            raw.append((match.start(), match.end(), name))
    kept: List[tuple[int, int, str]] = []
    for span in raw:
        covered = any(
            other[0] <= span[0] and span[1] <= other[1] and len(other[2]) > len(span[2])
            for other in raw
        )
        if not covered:
            kept.append(span)
    return kept


def _nearest_project_name(
    term_start: int,
    term_end: int,
    spans: Sequence[tuple[int, int, str]],
) -> Optional[str]:
    """
    Return the project name closest to a technique mention.

    Args:
        term_start: Start index of the technique in the sentence.
        term_end: End index of the technique in the sentence.
        spans: Project-name spans from ``_project_name_spans``.

    Returns:
        The nearest project name, or ``None`` when ``spans`` is empty.
        A tie goes to the longer name.
    """
    if not spans:
        return None

    def _distance(span: tuple[int, int, str]) -> tuple[int, int]:
        start, end, name = span
        if term_end <= start:
            gap = start - term_end
        elif end <= term_start:
            gap = term_start - end
        else:
            gap = 0
        return (gap, -len(name))

    return min(spans, key=_distance)[2]


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

    1. Scope inflation: a leadership claim is flagged unless the resume has
       the same claim and the same object. Number words and digits are
       equal. The verb alone, on a different object, is not enough.
    2. Technique mismatch: flags a named technique (e.g. ``retrieval``,
       ``fine-tuning``, ``distillation``) when the nearest named project's
       technique list does not include it. Each mention is checked against
       the project closest to it, so two projects in one sentence do not
       share one technique list.

    Args:
        sentence: A single sentence from the generated cover letter.
        project_name: Fallback project when the sentence names none.
            When the sentence names one or more projects, each technique
            is checked against the project nearest to that mention.
        project_techniques: Mapping of project name to the list of
            techniques verified to apply to it.
        resume_bullets: Optional resume corpus. A leadership claim is
            allowed only when this text has the same claim and the same
            object.

    Returns:
        A list of human-readable flags describing what was found, empty
        if the sentence raises no concerns.
    """
    flags: List[str] = []
    lowered = (sentence or "").lower()
    if not lowered.strip():
        return flags

    resume_lower = " ".join(resume_bullets or []).lower()

    for claim in _leadership_claims(lowered):
        if not _resume_has_leadership_claim(claim, resume_lower):
            flags.append(
                "Scope inflation: "
                f"'{claim}' implies leadership/ownership beyond an "
                "individual contribution"
            )

    spans = _project_name_spans(sentence, list(project_techniques.keys()))
    seen_terms: Set[tuple[str, str]] = set()
    for term in _TECHNIQUE_TERMS:
        pattern = re.compile(
            rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])",
            re.IGNORECASE,
        )
        for match in pattern.finditer(sentence or ""):
            named = (
                _nearest_project_name(match.start(), match.end(), spans)
                if spans
                else project_name
            )
            if not named or (term, named) in seen_terms:
                continue
            seen_terms.add((term, named))
            known = project_techniques.get(named, [])
            known_lower = " ".join(known).lower()
            if not _whole_term_in_text(known_lower, term):
                flags.append(f"Technique mismatch: '{term}' not verified for {named}")

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


def _normalize_proper_name(name: str) -> str:
    """
    Normalize an organization, title, or school name for comparison.

    Comparison ignores case and punctuation. Suffixes such as ``Inc.`` and
    ``Ltd.`` are removed.

    Args:
        name: Raw name from a letter or a profile.

    Returns:
        Lowercase name with one space between words.
    """
    cleaned = re.sub(r"[^\w\s]", " ", (name or "").lower())
    suffixes = {
        "inc",
        "incorporated",
        "ltd",
        "limited",
        "llc",
        "corp",
        "corporation",
        "co",
        "plc",
    }
    words = [word for word in cleaned.split() if word and word not in suffixes]
    return " ".join(words)


def _same_proper_name(left: str, right: str) -> bool:
    """
    Return whether two proper names are the same after normalization.

    Args:
        left: First name.
        right: Second name.

    Returns:
        True when both normalize to the same non-empty text.
    """
    normalized_left = _normalize_proper_name(left)
    normalized_right = _normalize_proper_name(right)
    return bool(normalized_left) and normalized_left == normalized_right


# Capitalized organization token that is never the first-person pronoun "I".
_ORG_TOKEN = r"(?!I\b)[A-Z][\w&.'-]*"
_ORG_NAME = rf"{_ORG_TOKEN}(?:\s+{_ORG_TOKEN}){{0,3}}"
_EMPLOYER_RES: tuple[re.Pattern[str], ...] = (
    re.compile(rf"\b(?:[Ww]orked|[Ii]nterned)\s+at\s+(?P<org>{_ORG_NAME})"),
    re.compile(rf"\b[Jj]oined\s+(?P<org>{_ORG_NAME})"),
)
_AT_ORG_I_RE = re.compile(
    rf"\b[Aa]t\s+(?P<org>{_ORG_NAME})\s+I\s+(?P<verb>[A-Za-z]+)\b"
)
# Short list of role nouns that mark a job title in "as a <title> at <company>".
_TITLE_ROLE_NOUNS: frozenset[str] = frozenset(
    {
        "administrator",
        "analyst",
        "architect",
        "consultant",
        "developer",
        "director",
        "engineer",
        "intern",
        "lead",
        "manager",
        "officer",
        "researcher",
        "scientist",
        "specialist",
        "designer",
    }
)
_TITLE_WAS_RE = re.compile(
    rf"\bmy title(?:\s+at\s+(?P<company>{_ORG_NAME}))?\s+was\s+"
    r"(?P<title>[A-Z][^.,;\n]+)",
    re.IGNORECASE,
)
_AS_TITLE_RE = re.compile(
    r"\b[Aa]s\s+an?\s+(?P<title>[A-Za-z][\w/&+' .-]{1,60}?)\s+at\s+"
    rf"(?P<company>{_ORG_NAME})"
)
_DEGREE_LEVEL_RE = re.compile(
    r"\b(?P<level>ph\.?d|doctorate|doctoral|mba|bachelor|master|"
    r"b\.sc|b\.s|m\.sc|m\.a|m\.s)(?![A-Za-z])",
    re.IGNORECASE,
)
_DEGREE_WORD_CONTEXT_RE = re.compile(
    r"^(?:'s\b|\s+(?:of|in|degree)\b)",
    re.IGNORECASE,
)
_DEGREE_TAIL_RE = re.compile(
    r"(?:'s)?(?:\s+degree)?"
    r"(?:\s+of\s+(?:arts|science|engineering))?"
    r"(?:\s+in\s+(?P<field>(?:(?!from\b|at\b)[A-Za-z][A-Za-z-]*)"
    r"(?:\s+(?!from\b|at\b)[A-Za-z][A-Za-z-]*){0,5}))?"
    rf"(?:\s+(?:from|at)\s+(?P<school>{_ORG_NAME}))?",
    re.IGNORECASE,
)
_BARE_DEGREE_IN_RE = re.compile(
    r"\bdegree\s+in\s+(?P<field>(?:(?!from\b|at\b)[A-Za-z][A-Za-z-]*)"
    r"(?:\s+(?!from\b|at\b)[A-Za-z][A-Za-z-]*){0,5})"
    rf"(?:\s+(?:from|at)\s+(?P<school>{_ORG_NAME}))?",
    re.IGNORECASE,
)
_CERT_WORD_RE = re.compile(
    r"\b(?:certified|certificate|certification)\b",
    re.IGNORECASE,
)
# Short list of job-requirement and future-plan phrases that skip a certificate mention.
_CERT_REQUIREMENT_OR_PLAN_RE = re.compile(
    r"\b(?:"
    r"asks\s+for|requires|required|preferred|"
    r"plan\s+to|hope\s+to|want\s+to|would\s+like\s+to|intend\s+to"
    r")\b",
    re.IGNORECASE,
)
_CERT_NAME_SKIP = frozenset(
    {
        "the",
        "a",
        "an",
        "my",
        "our",
        "i",
        "am",
        "is",
        "was",
        "were",
        "be",
        "been",
        "as",
        "in",
        "on",
        "for",
        "with",
        "from",
        "at",
        "by",
        "to",
        "earned",
        "hold",
        "holds",
        "holding",
        "received",
        "got",
        "completed",
        "complete",
    }
)


def _canonical_degree_level(raw: str) -> str:
    """
    Map a degree word or abbreviation to a level name.

    ``B.Sc.`` and ``Bachelor`` are both ``bachelor``. ``PhD`` and
    ``doctorate`` are both ``doctorate``.

    Args:
        raw: Matched degree token.

    Returns:
        A level name: bachelor, master, mba, or doctorate.
    """
    compact = re.sub(r"[^a-z]", "", (raw or "").lower())
    if compact in {"phd", "doctorate", "doctoral"}:
        return "doctorate"
    if compact == "mba":
        return "mba"
    if compact in {"bsc", "bs", "bachelor"}:
        return "bachelor"
    if compact in {"msc", "ma", "ms", "master"}:
        return "master"
    return compact


def _field_in_text(field: str, text: str) -> bool:
    """
    Return whether every content word of ``field`` appears in ``text``.

    Args:
        field: Field of study from the letter.
        text: Profile degree text.

    Returns:
        True when each content word is present as a whole word.
    """
    words = [
        word
        for word in (field or "").lower().split()
        if word not in {"of", "in", "and", "the"}
    ]
    if not words:
        return True
    haystack = text or ""
    return all(
        re.search(rf"\b{re.escape(word)}\b", haystack, re.IGNORECASE) for word in words
    )


def _profile_has_employer(profile: UserProfile, org: str) -> bool:
    """
    Return whether ``org`` is a company on the profile.

    Args:
        profile: Candidate profile.
        org: Employer named in the letter.

    Returns:
        True when an experience company normalizes to the same name.
    """
    for experience in profile.experience or []:
        if _same_proper_name(org, experience.company or ""):
            return True
    return False


def _title_words_in_text(claimed: str, candidate: str) -> bool:
    """
    Return whether every word of ``claimed`` is in ``candidate``.

    Args:
        claimed: Title from the letter.
        candidate: Title from the profile or the job listing.

    Returns:
        True when ``claimed`` is non-empty and all its words appear in ``candidate``.
    """
    claimed_words = _normalize_proper_name(claimed).split()
    if not claimed_words:
        return False
    candidate_words = set(_normalize_proper_name(candidate).split())
    return all(word in candidate_words for word in claimed_words)


def _title_ends_with_role_noun(title: str) -> bool:
    """
    Return whether ``title`` ends with a known role noun.

    Args:
        title: Candidate title from ``as a <title> at <company>``.

    Returns:
        True when the last word is in ``_TITLE_ROLE_NOUNS``.
    """
    words = _normalize_proper_name(title).split()
    return bool(words) and words[-1] in _TITLE_ROLE_NOUNS


def _profile_has_title(profile: UserProfile, title: str) -> bool:
    """
    Return whether ``title`` is supported by a job title on the profile.

    A shorter title such as ``backend consultant`` is supported when all
    its words appear in one profile title such as ``Senior Backend
    Consultant``.

    Args:
        profile: Candidate profile.
        title: Title named in the letter.

    Returns:
        True when all words of ``title`` are in one profile experience title.
    """
    for experience in profile.experience or []:
        if _title_words_in_text(title, experience.title or ""):
            return True
    return False


def _profile_has_degree(
    profile: UserProfile,
    level: str,
    field: str,
    school: str,
) -> bool:
    """
    Return whether the profile has this degree.

    The level, the field, and the school must agree when the letter
    states them. ``B.Sc. in Statistics`` agrees with ``Bachelor of
    Science in Statistics``.

    Args:
        profile: Candidate profile.
        level: Canonical degree level, or empty.
        field: Field of study, or empty.
        school: School name, or empty.

    Returns:
        True when one education entry supports the claim.
    """
    for education in profile.education or []:
        degree = education.degree or ""
        level_match = _DEGREE_LEVEL_RE.search(degree)
        profile_level = (
            _canonical_degree_level(level_match.group("level")) if level_match else ""
        )
        if level and profile_level != level:
            continue
        if field and not _field_in_text(field, degree):
            continue
        if school and not _same_proper_name(school, education.school or ""):
            continue
        if level or field or school:
            return True
    return False


def _profile_has_certificate(profile: UserProfile, name: str) -> bool:
    """
    Return whether the profile lists this certificate.

    A certificate name is supported when all its normalized words appear
    in one profile certification name, or when it equals the issuer.

    Args:
        profile: Candidate profile.
        name: Certificate name from the letter.

    Returns:
        True when the name matches a certification name or issuer.
    """
    name_words = _normalize_proper_name(name).split()
    if not name_words:
        return False
    for certification in profile.certifications or []:
        cert_words = set(_normalize_proper_name(certification.name or "").split())
        if all(word in cert_words for word in name_words):
            return True
        if _same_proper_name(name, certification.issuer or ""):
            return True
    return False


def _certificate_name(sentence: str, start: int, end: int) -> str:
    """
    Return the capitalized name around a certificate word.

    Capitalized words are read before and after the certificate word.
    The certificate word itself is included when it is capitalized in a
    title such as ``Redwood Certified Network Specialist``.

    Args:
        sentence: Sentence that contains the certificate word.
        start: Start index of that word.
        end: End index of that word.

    Returns:
        The name, or an empty string when none is visible.
    """
    before: List[str] = []
    for token in sentence[:start].split()[-6:]:
        bare = token.strip(".,;:")
        if not bare or bare.lower() in _CERT_NAME_SKIP:
            if not before:
                continue
            before = []
            continue
        if bare[:1].isupper() or (before and bare.lower() in {"of", "and"}):
            before.append(bare)
            continue
        before = []
    while before and before[-1].lower() in {"of", "and"}:
        before.pop()

    after: List[str] = []
    for token in sentence[end:].split()[:6]:
        bare = token.strip(".,;:")
        if not bare or bare.lower() in _CERT_NAME_SKIP:
            break
        if bare[:1].isupper() or (after and bare.lower() in {"of", "and"}):
            after.append(bare)
            continue
        break
    while after and after[-1].lower() in {"of", "and"}:
        after.pop()

    cert_word = sentence[start:end].strip(".,;:")
    parts: List[str] = list(before)
    if cert_word[:1].isupper() and cert_word.lower() == "certified" and after:
        parts.append(cert_word)
    parts.extend(after)
    return " ".join(parts)


def _experience_claim_is_supported(
    kind: str,
    claim: str,
    profile: UserProfile,
    level: str = "",
    field: str = "",
    school: str = "",
) -> bool:
    """
    Return whether the profile supports one experience claim.

    Args:
        kind: ``employer``, ``title``, ``degree``, or ``certificate``.
        claim: Display text of the claim.
        profile: Candidate profile.
        level: Degree level when ``kind`` is ``degree``.
        field: Field of study when ``kind`` is ``degree``.
        school: School when ``kind`` is ``degree``.

    Returns:
        True when the profile contains the claim.
    """
    if kind == "employer":
        return _profile_has_employer(profile, claim)
    if kind == "title":
        return _profile_has_title(profile, claim)
    if kind == "degree":
        return _profile_has_degree(profile, level, field, school)
    if kind == "certificate":
        return _profile_has_certificate(profile, claim)
    return False


def flag_fabricated_experience_claims(
    letter_text: str,
    profile: UserProfile,
    job: JobListing,
) -> List[dict]:
    """
    Flag employers, titles, degrees, and certificates the profile lacks.

    Patterns are narrow: ``worked at``, ``joined``, ``interned at``, and
    ``at <Organization> I``. The target company and the target job title
    are not claims. ``at the start`` is not an employer. A degree
    abbreviation such as ``B.Sc.`` matches ``Bachelor of Science``.
    ``at <school>`` names the school in the same way as ``from <school>``.

    The selected-project check in the validator stays in place.

    Args:
        letter_text: Cover-letter body.
        profile: Candidate profile.
        job: Target job. Its company and title are not claims.

    Returns:
        A list of ``{"sentence", "kind", "claim", "flags"}`` findings.
    """
    if not letter_text or not letter_text.strip():
        return []

    target_company = job.company or ""
    target_title = job.title or ""
    findings: List[dict] = []
    for sentence in _SENTENCE_SPLIT.split(letter_text.strip()):
        cleaned = sentence.strip().rstrip(".")
        if not cleaned:
            continue
        claims: List[tuple[str, str, str, str, str]] = []
        for pattern in _EMPLOYER_RES:
            for match in pattern.finditer(cleaned):
                org = match.group("org").strip()
                if _same_proper_name(org, target_company):
                    continue
                claims.append(("employer", org, "", "", ""))
        for match in _AT_ORG_I_RE.finditer(cleaned):
            if match.group("verb").lower() not in _PAST_CLAIM_VERBS:
                continue
            org = match.group("org").strip()
            if _same_proper_name(org, target_company):
                continue
            claims.append(("employer", org, "", "", ""))
        title_match = _TITLE_WAS_RE.search(cleaned)
        if title_match:
            title = title_match.group("title").strip()
            if not _same_proper_name(title, target_title):
                claims.append(("title", title, "", "", ""))
        for as_title in _AS_TITLE_RE.finditer(cleaned):
            title = as_title.group("title").strip()
            company = as_title.group("company").strip()
            if not _title_ends_with_role_noun(title):
                continue
            is_target_title = _same_proper_name(title, target_title)
            is_target_company = not company or _same_proper_name(
                company, target_company
            )
            if is_target_title and is_target_company:
                continue
            if not is_target_title:
                claims.append(("title", title, "", "", ""))
            if company and not is_target_company:
                claims.append(("employer", company, "", "", ""))
        degree_spans: List[tuple[int, int]] = []
        for match in _DEGREE_LEVEL_RE.finditer(cleaned):
            raw_level = match.group("level")
            rest_raw = cleaned[match.end() :]
            if raw_level.lower() in {
                "bachelor",
                "master",
            } and not _DEGREE_WORD_CONTEXT_RE.match(rest_raw):
                continue
            rest = rest_raw.lstrip(".")
            tail = _DEGREE_TAIL_RE.match(rest)
            field = (tail.group("field") or "").strip() if tail else ""
            school = (tail.group("school") or "").strip() if tail else ""
            level = _canonical_degree_level(raw_level)
            text = " ".join(part for part in (level, field, school) if part)
            tail_end = match.end() + (tail.end() if tail else 0)
            degree_spans.append((match.start(), tail_end))
            claims.append(("degree", text, level, field, school))
        for match in _BARE_DEGREE_IN_RE.finditer(cleaned):
            if any(start <= match.start() < end for start, end in degree_spans):
                continue
            field = (match.group("field") or "").strip()
            school = (match.group("school") or "").strip()
            text = " ".join(part for part in ("degree", field, school) if part)
            claims.append(("degree", text, "", field, school))
        if not (
            _CERT_REQUIREMENT_OR_PLAN_RE.search(cleaned)
            or _is_skippable_non_claim(cleaned)
        ):
            for match in _CERT_WORD_RE.finditer(cleaned):
                name = _certificate_name(cleaned, match.start(), match.end())
                if name:
                    claims.append(("certificate", name, "", "", ""))
        for kind, claim, level, field, school in claims:
            if _experience_claim_is_supported(
                kind, claim, profile, level=level, field=field, school=school
            ):
                continue
            findings.append(
                {
                    "sentence": cleaned,
                    "kind": kind,
                    "claim": claim,
                    "flags": [
                        "Fabricated experience: "
                        f"{kind} '{claim}' is not on the resume"
                    ],
                }
            )
    return findings


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
        # ``significant_words`` keeps a hyphenated compound as one token.
        # A job duty written as two words (``penetration testing``) would
        # otherwise miss ``penetration-testing`` in the letter. The parts
        # count only when each of them is a job word. The split stays here
        # so overlap checks keep the compound as one token.
        for word in list(target_words):
            if "-" not in word:
                continue
            parts = [
                part
                for part in word.split("-")
                if len(part) > 3 and part not in _STOPWORDS
            ]
            if parts and all(part in jd_words for part in parts):
                target_words.extend(parts)
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


# Number words that mark a checkable quantity. "one" through "ten" are
# also year words; the longer list is for the non-claim guard and for
# number checks that compare "four" with "4".
_CLAIM_NUMBER_WORDS: frozenset[str] = frozenset(
    {
        "zero",
        "one",
        "two",
        "three",
        "four",
        "five",
        "six",
        "seven",
        "eight",
        "nine",
        "ten",
        "eleven",
        "twelve",
        "thirteen",
        "fourteen",
        "fifteen",
        "sixteen",
        "seventeen",
        "eighteen",
        "nineteen",
        "twenty",
        "thirty",
        "forty",
        "fifty",
        "sixty",
        "seventy",
        "eighty",
        "ninety",
        "hundred",
        "thousand",
        "million",
    }
)

# Past-tense verbs that state a fact about work the candidate did.
# "hired me" is removed before this list is applied: that phrase is the
# plan "if <company> hired me", not a claim that the candidate hired anyone.
_PAST_CLAIM_VERBS: frozenset[str] = frozenset(
    {
        "added",
        "architected",
        "automated",
        "boosted",
        "built",
        "completed",
        "created",
        "cut",
        "decreased",
        "delivered",
        "deployed",
        "designed",
        "developed",
        "earned",
        "established",
        "finished",
        "fixed",
        "grew",
        "headed",
        "hired",
        "implemented",
        "improved",
        "increased",
        "introduced",
        "invented",
        "joined",
        "launched",
        "led",
        "lowered",
        "maintained",
        "managed",
        "measured",
        "mentored",
        "migrated",
        "operated",
        "optimized",
        "oversaw",
        "owned",
        "produced",
        "published",
        "raised",
        "ran",
        "received",
        "reduced",
        "refactored",
        "removed",
        "rewrote",
        "rewritten",
        "saved",
        "shipped",
        "spearheaded",
        "split",
        "started",
        "supervised",
        "took",
        "trained",
        "used",
        "wrote",
    }
)

_LEADING_GREETING_RE = re.compile(
    r"^(?:"
    r"dear\s+[a-z]+(?:\s+[a-z]+){0,3}\s*,\s*"
    r"|"
    r"(?:hello|hi|hey|good\s+(?:day|morning|afternoon|evening))"
    r"(?:\s+[a-z]+){0,2}\s*[.!?]\s*"
    r")",
    re.IGNORECASE,
)

_PURE_GREETING_RE = re.compile(
    r"^(?:hello|hi|hey|good\s+(?:day|morning|afternoon|evening)|"
    r"dear\s+[a-z]+(?:\s+[a-z]+){0,3})\s*[.!?]?$",
    re.IGNORECASE,
)

_SIGN_OFF_RE = re.compile(
    r"^(?:sincerely|best\s+regards|kind\s+regards|warm\s+regards|"
    r"regards|yours\s+sincerely|yours\s+truly|respectfully)\b",
    re.IGNORECASE,
)

_THANKS_RE = re.compile(r"\b(?:thank\s+you|thanks)\b", re.IGNORECASE)

_INTEREST_OR_VALUE_RE = re.compile(
    r"^(?:"
    r"i(?:\s+am|'m)\s+(?:excited|interested|eager|happy|glad|pleased|"
    r"writing|applying|motivated|passionate)\b|"
    r"i\s+(?:value|enjoy|prefer|appreciate)\b|"
    r"i\s+care\s+(?:about|more)\b"
    r")",
    re.IGNORECASE,
)

_PLAN_RE = re.compile(
    r"^(?:"
    r"i\s+would\b|"
    r"i'?d\b|"
    r"if\b.{0,80}?\bhired\s+me\b|"
    r"in\s+(?:my|a|the)\s+first\s+(?:month|months|week|weeks)\b|"
    r"(?:an|a)\s+early\s+week\b|"
    r"i\s+(?:plan|intend|hope)\s+to\b"
    r")",
    re.IGNORECASE,
)

_HIRED_ME_RE = re.compile(r"\bhired\s+me\b", re.IGNORECASE)


def _strip_leading_greeting(sentence: str) -> str:
    """
    Remove a greeting clause from the start of a sentence.

    A clause such as "Dear Hiring Team," stays on the same sentence as the
    claim that follows it, because the splitter only breaks on ``.!?``.
    The clause is removed so its words cannot raise the overlap of that claim.

    Args:
        sentence: One sentence from the letter, already stripped.

    Returns:
        The sentence without a leading greeting. Empty when the sentence
        is only a greeting.
    """
    text = sentence.strip()
    match = _LEADING_GREETING_RE.match(text)
    if not match:
        return text
    return text[match.end() :].strip()


def _has_past_claim_verb(sentence: str) -> bool:
    """
    Return whether the sentence uses a past-tense claim verb.

    ``hired me`` is removed first. That phrase is a plan, not a claim that
    the candidate hired someone.

    Args:
        sentence: Sentence text.

    Returns:
        True when a verb from the claim list is present.
    """
    scrubbed = _HIRED_ME_RE.sub(" ", sentence or "")
    tokens = [match.group(0).lower() for match in _WORD_RE.finditer(scrubbed)]
    return any(token in _PAST_CLAIM_VERBS for token in tokens)


def _sentence_has_claim_guard(sentence: str) -> bool:
    """
    Return whether a sentence may state a checkable fact.

    A number, a duration, a technology from the lexicon, or a past-tense
    claim verb blocks the non-claim skip. "hired me" is not a claim verb:
    it is the plan "if the company hired me".

    Args:
        sentence: Sentence text after a leading greeting has been removed.

    Returns:
        True when the sentence must stay in the overlap check.
    """
    text = (sentence or "").strip()
    if not text:
        return False
    if re.search(r"\d", text):
        return True
    tokens = [match.group(0).lower() for match in _WORD_RE.finditer(text)]
    if any(token in _CLAIM_NUMBER_WORDS for token in tokens) or _has_past_claim_verb(
        text
    ):
        return True
    if _DURATION_CLAIM_RE.search(text):
        return True
    return bool(extract_technologies(text))


def _call_to_action_phrases() -> Sequence[str]:
    """
    Return the validator's call-to-action phrases.

    Imported lazily so this module and the validator do not import each
    other while either module is still loading.

    Returns:
        Phrase list from ``CoverLetterValidator.CALL_TO_ACTION_PHRASES``.
    """
    from .cover_letter_validator import CoverLetterValidator

    return CoverLetterValidator.CALL_TO_ACTION_PHRASES


def _is_skippable_non_claim(sentence: str) -> bool:
    """
    Return whether a sentence states no fact about the candidate.

    Skipped types are a greeting, a sign-off, thanks, a call to action,
    a statement of interest, motivation, values, or working style, and a
    plan or intention. The claim guard overrides every one of those types.

    Args:
        sentence: Sentence text after a leading greeting has been removed.

    Returns:
        True when the overlap check should ignore the sentence.
    """
    text = sentence.strip()
    if not text:
        return True
    if _sentence_has_claim_guard(text):
        return False
    if _SIGN_OFF_RE.match(text) or _PURE_GREETING_RE.match(text):
        return True
    if _THANKS_RE.search(text):
        return True
    lowered = text.lower()
    if any(phrase in lowered for phrase in _call_to_action_phrases()):
        return True
    if _INTEREST_OR_VALUE_RE.match(text) or _PLAN_RE.match(text):
        return True
    return False


# Word forms of quantities. Keys match ``_CLAIM_NUMBER_WORDS``.
_CLAIM_NUMBER_VALUES: dict[str, float] = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
    "hundred": 100,
    "thousand": 1000,
    "million": 1000000,
}

_NUMBER_WORD_PATTERN = "|".join(sorted(_CLAIM_NUMBER_VALUES, key=len, reverse=True))
_NUMBER_TOKEN = rf"(?:\d+(?:\.\d+)?|{_NUMBER_WORD_PATTERN})"

_PERCENT_NUMBER_RE = re.compile(
    rf"(?<![A-Za-z0-9])(?P<num>{_NUMBER_TOKEN})"
    rf"(?:\s*%|\s*percent(?:age)?(?:[-\s]*points?)?\b)",
    re.IGNORECASE,
)
_MULTIPLIER_NUMBER_RE = re.compile(
    rf"(?<![A-Za-z0-9])(?P<num>{_NUMBER_TOKEN})(?:\s*x\b|\s+times\b)",
    re.IGNORECASE,
)
_COUNT_WITH_NOUN_RE = re.compile(
    rf"(?<![A-Za-z0-9])(?P<num>{_NUMBER_TOKEN})\s+(?P<noun>[A-Za-z][A-Za-z-]*)\b",
    re.IGNORECASE,
)
_BARE_NUMBER_RE = re.compile(
    rf"(?<![A-Za-z0-9])(?P<num>{_NUMBER_TOKEN})(?![A-Za-z0-9])",
    re.IGNORECASE,
)
_SPAN_DURATION_RE = re.compile(
    rf"(?<![A-Za-z0-9]){_NUMBER_TOKEN}"
    rf"(?:\s*(?:[-–—]|to)\s*{_NUMBER_TOKEN})?\s*(?:years?|months?)\b",
    re.IGNORECASE,
)
_CALENDAR_YEAR_RE = re.compile(
    r"\b(?:in|during|since|from|before|after|until|circa|year)\s+(?:19|20)\d{2}\b",
    re.IGNORECASE,
)
_COUNT_NOUNS_TO_SKIP: frozenset[str] = frozenset(
    {
        "month",
        "months",
        "percent",
        "percentage",
        "point",
        "points",
        "time",
        "times",
        "year",
        "years",
    }
)


def _mask_pattern(text: str, pattern: re.Pattern[str]) -> str:
    """
    Replace each match with spaces of the same length.

    Args:
        text: Source text.
        pattern: Compiled pattern whose matches should be hidden.

    Returns:
        Text with those matches blanked out.
    """
    return pattern.sub(lambda match: " " * len(match.group(0)), text)


def _parse_number_token(token: str) -> Optional[float]:
    """
    Convert a digit or number word to a float.

    Args:
        token: A token such as ``90`` or ``ninety``.

    Returns:
        The numeric value, or None when the token is not a number.
        Integral values are returned as whole floats so ``4`` and ``4.0`` match.
    """
    lowered = (token or "").strip().lower()
    if lowered in _CLAIM_NUMBER_VALUES:
        return float(_CLAIM_NUMBER_VALUES[lowered])
    try:
        value = float(lowered)
    except ValueError:
        return None
    if value.is_integer():
        return float(int(value))
    return value


def _collect_checkable_numbers(
    text: str, *, counts_need_noun: bool
) -> tuple[Set[float], Set[float], Set[float]]:
    """
    Collect percents, multipliers, and counts from fact text.

    Durations (``five years``, ``3 months``) and calendar years (``in 2021``)
    are removed before the collection. ``90%``, ``90 percent``, and
    ``ninety percent`` are the same percent. ``3x`` and ``3 times`` are the
    same multiplier. ``four`` and ``4`` are the same count.

    Args:
        text: Profile fact text or one letter sentence.
        counts_need_noun: When True, a count is kept only when a noun follows
            it. Profile text uses False so a bare ``4`` can support
            ``four engineers``.

    Returns:
        Three sets: percent values, multiplier values, and count values.
    """
    working = text or ""
    for pattern in (_DURATION_CLAIM_RE, _SPAN_DURATION_RE, _CALENDAR_YEAR_RE):
        working = _mask_pattern(working, pattern)

    percents: Set[float] = set()
    for match in _PERCENT_NUMBER_RE.finditer(working):
        value = _parse_number_token(match.group("num"))
        if value is not None:
            percents.add(value)
    working = _mask_pattern(working, _PERCENT_NUMBER_RE)

    multipliers: Set[float] = set()
    for match in _MULTIPLIER_NUMBER_RE.finditer(working):
        value = _parse_number_token(match.group("num"))
        if value is not None:
            multipliers.add(value)
    working = _mask_pattern(working, _MULTIPLIER_NUMBER_RE)

    counts: Set[float] = set()
    if counts_need_noun:
        for match in _COUNT_WITH_NOUN_RE.finditer(working):
            noun = match.group("noun").lower()
            if noun in _COUNT_NOUNS_TO_SKIP:
                continue
            value = _parse_number_token(match.group("num"))
            if value is not None:
                counts.add(value)
    else:
        for match in _BARE_NUMBER_RE.finditer(working):
            value = _parse_number_token(match.group("num"))
            if value is not None:
                counts.add(value)
    return percents, multipliers, counts


def collect_profile_fact_text(profile: UserProfile) -> str:
    """
    Join the profile fields that may contain a checkable number.

    The fields are the summary, experience descriptions and highlights,
    project descriptions and highlights, and education text. Skill names
    and dates are not included.

    Args:
        profile: Candidate profile.

    Returns:
        The joined fact text. Empty when those fields are empty.
    """
    parts: List[str] = []
    if profile.summary:
        parts.append(profile.summary)
    for experience in profile.experience or []:
        if experience.description:
            parts.append(experience.description)
        parts.extend(item for item in (experience.highlights or []) if item)
    for project in profile.projects or []:
        if project.description:
            parts.append(project.description)
        parts.extend(item for item in (project.highlights or []) if item)
    for education in profile.education or []:
        for part in (education.degree, education.school, education.description):
            if part:
                parts.append(part)
        parts.extend(item for item in (education.honors or []) if item)
        parts.extend(item for item in (education.coursework or []) if item)
    return "\n".join(parts)


def flag_unsupported_number_sentences(
    letter_text: str,
    profile: UserProfile,
) -> List[str]:
    """
    Flag candidate sentences whose percent, multiplier, or count is not in the profile.

    Only sentences that the ungrounded check does not skip are examined.
    A percent must match a percent in the profile, a multiplier must match a
    multiplier, and a count with a noun must match a count. A count is checked
    only when the sentence has a past-tense claim verb, so a plan such as
    "a good early task is one test" is not an achievement figure. Durations
    and calendar years are not checked here.

    Args:
        letter_text: Cover-letter body.
        profile: Candidate profile used as the source of the numbers.

    Returns:
        Sentences that contain at least one unsupported number.
    """
    if not letter_text or not letter_text.strip():
        return []
    profile_percents, profile_multipliers, profile_counts = _collect_checkable_numbers(
        collect_profile_fact_text(profile),
        counts_need_noun=False,
    )
    flagged: List[str] = []
    for sentence in _SENTENCE_SPLIT.split(letter_text.strip()):
        cleaned = sentence.strip()
        if not cleaned:
            continue
        remainder = _strip_leading_greeting(cleaned)
        if _is_skippable_non_claim(remainder):
            continue
        checked = remainder if remainder else cleaned
        percents, multipliers, counts = _collect_checkable_numbers(
            checked,
            counts_need_noun=True,
        )
        # A count with no past-tense claim verb is not an achievement figure.
        # "A good early task is one test" is a plan. Checking it dropped
        # ungrounded F1 on the grounding set.
        if not _has_past_claim_verb(checked):
            counts = set()
        unsupported = (
            any(value not in profile_percents for value in percents)
            or any(value not in profile_multipliers for value in multipliers)
            or any(value not in profile_counts for value in counts)
        )
        if unsupported:
            flagged.append(checked.rstrip("."))
    return flagged


def flag_ungrounded_sentences(
    letter_text: str,
    resume_bullets: Sequence[str],
    min_overlap_ratio: float = 0.3,
    jd_terms: Optional[Iterable[str]] = None,
    closing_min_overlap_ratio: float = 0.3,
) -> List[str]:
    """
    Flag sentences in a generated cover letter with weak grounding in the resume.

    Splits the letter into sentences and checks each one's keyword overlap
    against resume bullets (and optional JD terms). Sentences with low overlap
    are likely model-synthesized flourish rather than restated fact, and are
    surfaced for manual review rather than auto-approved.

    A greeting, sign-off, thanks, call to action, statement of interest or
    values, or plan is skipped when it states no fact. A leading greeting
    clause is removed first so it cannot hide the claim that follows it.
    A number, a duration, a lexicon technology, or a past-tense claim verb
    keeps the sentence in the check.

    The closing paragraph used to require a higher overlap (0.4) than the
    body (0.3). On the 2026-10-22 grounding set those two thresholds flagged
    the same sentences, so the default closing threshold is now the body
    threshold. A caller can still pass a higher ``closing_min_overlap_ratio``.
    Sentences that introduce overclaim verbs (for example ``deployed``,
    ``production``, ``launched``) absent from the grounding corpus are
    always flagged.

    Args:
        letter_text: The generated cover letter body.
        resume_bullets: The candidate's resume bullets, used as the source
            of truth for factual grounding.
        min_overlap_ratio: Minimum fraction of a sentence's significant
            words that must appear somewhere in the grounding corpus for
            body sentences to be considered grounded.
        jd_terms: Optional job-description / requirement phrases that are
            also valid grounding (the letter may address JD needs by name).
        closing_min_overlap_ratio: Overlap threshold for sentences in the
            final paragraph. The default matches ``min_overlap_ratio``. A
            stricter closing value is not the default: on the 2026-10-22
            grounding set it flagged the same sentences as the body threshold.

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
        remainder = _strip_leading_greeting(cleaned)
        if _is_skippable_non_claim(remainder):
            continue
        checked = remainder if remainder else cleaned
        words = significant_words(checked)
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
            flagged.append(checked.rstrip("."))

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
