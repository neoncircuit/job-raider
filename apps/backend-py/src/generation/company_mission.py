"""
Job Raider - Company Mission Grounding (verify helpers)

Search-independent helpers for verify-against-JD-facts gating of
company-mission candidates. Network I/O lives in
``company_mission_search``; cover-letter generate calls
``resolve_company_mission`` when Settings ``enable_company_mission`` is on.

Author: Job Raider
Date: 2026-08-20
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set
from urllib.parse import urlparse

# Max numbered citations shown next to a generated cover letter.
MAX_MISSION_CITATION_SOURCES = 3

# Shared stopwords — keep mission scoring focused on entity/industry tokens.
_STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "of",
        "to",
        "in",
        "on",
        "for",
        "with",
        "from",
        "by",
        "as",
        "at",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "that",
        "this",
        "these",
        "those",
        "it",
        "its",
        "their",
        "our",
        "your",
        "you",
        "we",
        "they",
        "he",
        "she",
        "his",
        "her",
        "them",
        "than",
        "then",
        "also",
        "only",
        "into",
        "over",
        "under",
        "about",
        "across",
        "through",
        "between",
        "during",
        "before",
        "after",
        "above",
        "below",
        "such",
        "other",
        "some",
        "any",
        "all",
        "each",
        "more",
        "most",
        "very",
        "just",
        "like",
        "using",
        "use",
        "used",
        "role",
        "hiring",
        "company",
        "job",
        "position",
        "team",
        "work",
        "working",
        "experience",
        "years",
        "including",
        "include",
        "includes",
        "related",
        "support",
        "supporting",
        "building",
        "products",
        "product",
        "public",
        "documented",
        "major",
        "group",
        "entity",
        "not",
        "must",
        "will",
        "can",
        "may",
        "should",
    }
)

# Phrases that often indicate a wrong "Akro" (storage / industrial) match.
_COLLISION_NEGATIVE_PHRASES: frozenset[str] = frozenset(
    {
        "akro-mils",
        "akro mils",
        "storage bin",
        "storage bins",
        "shelving",
        "plastic bin",
        "plastic bins",
        "material handling",
        "industrial storage",
    }
)

# Minimum fraction of JD fact tokens that must appear in page text.
DEFAULT_FACT_MATCH_RATIO = 0.35
# Absolute minimum matched fact tokens (after ratio) for a pass.
DEFAULT_MIN_MATCHED_FACTS = 2
# Company-name token overlap required on the candidate page.
DEFAULT_NAME_MATCH_RATIO = 0.5


@dataclass
class MissionCandidate:
    """
    One fetched web page considered as a company-mission source.

    Attributes:
        url: Page URL.
        title: Search or page title.
        text: Extracted visible text (may be truncated).
        snippet: Optional search snippet.
    """

    url: str
    title: str = ""
    text: str = ""
    snippet: str = ""


@dataclass
class MissionVerifyResult:
    """
    Outcome of verify-against-JD-facts for a company.

    Attributes:
        status: ``pass`` or ``skip``.
        company: Company name from the request.
        skip_reason: Human-readable reason when status is ``skip`` (never blank on skip).
        source_url: Winning page URL when status is ``pass``.
        source_title: Winning page title when status is ``pass``.
        matched_facts: JD fact tokens found on the winning page.
        missing_facts: JD fact tokens not found on the winning page.
        fact_match_ratio: Matched facts / total facts.
        collision_hits: Negative collision phrases found (wrong-entity signal).
        excerpt: Short source excerpt used for paraphrase (pass only).
        score_details: Per-candidate scores for debugging / spike reports.
        sources: User-facing citation list (winner + same-domain secondaries).
    """

    status: str
    company: str
    skip_reason: str = ""
    source_url: Optional[str] = None
    source_title: Optional[str] = None
    matched_facts: List[str] = field(default_factory=list)
    missing_facts: List[str] = field(default_factory=list)
    fact_match_ratio: float = 0.0
    collision_hits: List[str] = field(default_factory=list)
    excerpt: str = ""
    score_details: List[Dict[str, Any]] = field(default_factory=list)
    sources: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize the result for JSON reports.

        Returns:
            Plain dict suitable for ``json.dumps``.
        """
        return asdict(self)


def normalize_text(value: str) -> str:
    """
    Lowercase and collapse whitespace for matching.

    Args:
        value: Raw text.

    Returns:
        Normalized lowercase string.
    """
    return re.sub(r"\s+", " ", (value or "").lower()).strip()


def tokenize(value: str) -> List[str]:
    """
    Split text into alphanumeric tokens of length >= 2.

    Args:
        value: Raw or normalized text.

    Returns:
        List of lowercase tokens.
    """
    return re.findall(r"[a-z0-9][a-z0-9\-]{1,}", normalize_text(value))


def company_name_tokens(company: str) -> List[str]:
    """
    Extract meaningful tokens from a company name.

    Args:
        company: Company display name.

    Returns:
        Tokens excluding stopwords and very short legal suffixes.
    """
    skip_suffixes = {"pte", "ltd", "llc", "inc", "co", "corp", "plc", "sa", "bv"}
    tokens: List[str] = []
    for tok in tokenize(company):
        if tok in _STOPWORDS or tok in skip_suffixes:
            continue
        tokens.append(tok)
    return tokens


def extract_jd_facts(
    jd_text: str = "",
    jd_facts: Optional[Sequence[str]] = None,
) -> List[str]:
    """
    Build a deduplicated list of JD fact phrases/tokens for verification.

    Explicit ``jd_facts`` entries are preferred as whole phrases. Tokens from
    ``jd_text`` fill gaps after stopword filtering.

    Args:
        jd_text: Full or partial job description text.
        jd_facts: Optional curated fact phrases from the spike fixture.

    Returns:
        Ordered unique fact strings (lowercase phrases or tokens).
    """
    facts: List[str] = []
    seen: Set[str] = set()

    curated = list(jd_facts or [])
    for raw in curated:
        phrase = normalize_text(str(raw))
        if not phrase or phrase in seen:
            continue
        seen.add(phrase)
        facts.append(phrase)

    # When curated facts are present, do not mine narrative JD prose for
    # extra tokens (avoids scoring noise like "unrelated" / "brands").
    if curated:
        return facts

    for tok in tokenize(jd_text):
        if tok in _STOPWORDS or tok in seen or len(tok) < 3:
            continue
        if tok in {"pte", "ltd", "llc", "inc", "corp"}:
            continue
        seen.add(tok)
        facts.append(tok)

    return facts


def build_search_query(
    company: str,
    jd_text: str = "",
    jd_facts: Optional[Sequence[str]] = None,
    max_extra_terms: int = 4,
) -> str:
    """
    Build a DuckDuckGo-style query from company + JD disambiguators.

    Args:
        company: Company name.
        jd_text: Job description text.
        jd_facts: Optional curated facts.
        max_extra_terms: Cap on extra disambiguator terms after the company.

    Returns:
        Search query string.
    """
    facts = extract_jd_facts(jd_text=jd_text, jd_facts=jd_facts)
    extras: List[str] = []
    for fact in facts:
        if fact in normalize_text(company):
            continue
        extras.append(fact)
        if len(extras) >= max_extra_terms:
            break
    if extras:
        return f"{company.strip()} {' '.join(extras)} mission about"
    return f"{company.strip()} company mission about"


def _fact_present(fact: str, haystack: str) -> bool:
    """
    Return True if a fact phrase or all of its tokens appear in haystack.

    Args:
        fact: Fact phrase (already normalized preferred).
        haystack: Normalized page text.

    Returns:
        Whether the fact is considered present.
    """
    fact_n = normalize_text(fact)
    if not fact_n:
        return False
    if fact_n in haystack:
        return True
    tokens = [t for t in tokenize(fact_n) if t not in _STOPWORDS]
    if not tokens:
        return False
    return all(t in haystack for t in tokens)


def detect_collision_phrases(page_text: str) -> List[str]:
    """
    Detect known wrong-entity phrases (e.g. Akro-Mils storage signals).

    Args:
        page_text: Page or snippet text.

    Returns:
        List of matched negative phrases.
    """
    hay = normalize_text(page_text)
    return [p for p in sorted(_COLLISION_NEGATIVE_PHRASES) if p in hay]


def name_match_ratio(company: str, page_text: str) -> float:
    """
    Fraction of company-name tokens present in page text.

    Args:
        company: Company name.
        page_text: Page text.

    Returns:
        Ratio in [0.0, 1.0]. Empty company tokens yield 0.0.
    """
    tokens = company_name_tokens(company)
    if not tokens:
        return 0.0
    hay = normalize_text(page_text)
    hits = sum(1 for t in tokens if t in hay)
    return hits / len(tokens)


def score_candidate(
    company: str,
    facts: Sequence[str],
    candidate: MissionCandidate,
    *,
    fact_match_ratio_threshold: float = DEFAULT_FACT_MATCH_RATIO,
    min_matched_facts: int = DEFAULT_MIN_MATCHED_FACTS,
    name_match_ratio_threshold: float = DEFAULT_NAME_MATCH_RATIO,
) -> Dict[str, Any]:
    """
    Score one candidate page against company name and JD facts.

    Args:
        company: Company name.
        facts: JD fact list from ``extract_jd_facts``.
        candidate: Fetched page.
        fact_match_ratio_threshold: Minimum matched-fact ratio to clear.
        min_matched_facts: Minimum absolute matched facts.
        name_match_ratio_threshold: Minimum company-name token ratio.

    Returns:
        Score dict with pass flag, ratios, matched/missing facts, collisions.
    """
    blob = " ".join(
        [
            candidate.title or "",
            candidate.snippet or "",
            candidate.text or "",
        ]
    )
    hay = normalize_text(blob)
    matched = [f for f in facts if _fact_present(f, hay)]
    missing = [f for f in facts if f not in matched]
    ratio = (len(matched) / len(facts)) if facts else 0.0
    name_ratio = name_match_ratio(company, hay)
    collisions = detect_collision_phrases(blob)

    clears_name = name_ratio >= name_match_ratio_threshold
    clears_facts = (
        len(matched) >= min_matched_facts and ratio >= fact_match_ratio_threshold
    )
    collision_block = bool(collisions) and not clears_facts
    passed = clears_name and clears_facts and not collision_block

    return {
        "url": candidate.url,
        "title": candidate.title,
        "name_match_ratio": round(name_ratio, 3),
        "fact_match_ratio": round(ratio, 3),
        "matched_facts": matched,
        "missing_facts": missing,
        "collision_hits": collisions,
        "clears_name": clears_name,
        "clears_facts": clears_facts,
        "collision_block": collision_block,
        "passed": passed,
        "excerpt": _pick_excerpt(blob, matched or list(facts)[:3]),
    }


def _pick_excerpt(text: str, anchor_facts: Sequence[str], max_chars: int = 600) -> str:
    """
    Pick a short excerpt near the first matched fact for paraphrase input.

    Skips obvious cookie/consent boilerplate when a better sentence exists.

    Args:
        text: Full page text.
        anchor_facts: Facts to locate in the text.
        max_chars: Maximum excerpt length.

    Returns:
        Excerpt string (may be empty).
    """
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if not cleaned:
        return ""
    lower = cleaned.lower()
    boilerplate = (
        "manage consent",
        "we use cookies",
        "accept cookies",
        "privacy policy",
        "terms & conditions",
        "terms and conditions",
        "all rights reserved",
        "copyright",
        "follow us",
        "subscribe to our newsletter",
        "pasir panjang road",
        "phone:",
        "fax:",
    )

    # Prefer a sentence that contains an anchor fact and is not boilerplate.
    sentences = re.split(r"(?<=[.!?])\s+", cleaned)
    scored: List[tuple[int, str]] = []
    for fact in anchor_facts:
        fact_n = normalize_text(fact)
        if not fact_n:
            continue
        for sentence in sentences:
            s_lower = sentence.lower()
            if fact_n not in s_lower and not all(
                t in s_lower for t in tokenize(fact_n) if t not in _STOPWORDS
            ):
                continue
            if any(b in s_lower for b in boilerplate):
                continue
            if len(sentence.strip()) < 40:
                continue
            # Prefer longer substantive sentences over short nav crumbs.
            scored.append((len(sentence.strip()), sentence.strip()))
    if scored:
        scored.sort(key=lambda item: item[0], reverse=True)
        return scored[0][1][:max_chars]

    # Fall back: first non-boilerplate window that contains a fact.
    for fact in anchor_facts:
        fact_n = normalize_text(fact)
        if not fact_n:
            continue
        pos = lower.find(fact_n)
        if pos < 0:
            continue
        start = max(0, pos - 80)
        end = min(len(cleaned), start + max_chars)
        window = cleaned[start:end].strip()
        if any(b in window.lower() for b in boilerplate):
            continue
        return window

    # Last resort: first sentence that is not boilerplate.
    for sentence in sentences:
        s = sentence.strip()
        if len(s) < 50:
            continue
        if any(b in s.lower() for b in boilerplate):
            continue
        return s[:max_chars]

    return cleaned[:max_chars]


def registrable_domain(url: str) -> str:
    """
    Return a normalized registrable-domain key for same-site citation filtering.

    Strips scheme, credentials, port, and a leading ``www.``. Uses a lightweight
    public-suffix heuristic (last two labels, or three for known multi-part
    TLDs such as ``com.sg`` / ``co.uk``) so ``careers.example.com`` and
    ``www.example.com`` share a key while ``akro.ai`` and ``akro-mils.com``
    do not.

    Args:
        url: Absolute or host-bearing URL string.

    Returns:
        Lowercase domain key, or empty string when unparseable.
    """
    raw = (url or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    host = (parsed.hostname or "").lower().strip(".")
    if host.startswith("www."):
        host = host[4:]
    if not host or "." not in host:
        return host
    parts = host.split(".")
    multi = {
        "com.sg",
        "com.au",
        "co.uk",
        "org.uk",
        "co.jp",
        "com.br",
        "co.nz",
        "com.hk",
        "com.my",
    }
    if len(parts) >= 3 and ".".join(parts[-2:]) in multi:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def _normalize_citation_url(url: str) -> str:
    """
    Normalize a URL for citation deduplication.

    Args:
        url: Source URL.

    Returns:
        Lowercase URL without trailing slash (except bare origin).
    """
    cleaned = (url or "").strip()
    if not cleaned:
        return ""
    parsed = urlparse(cleaned if "://" in cleaned else f"https://{cleaned}")
    scheme = (parsed.scheme or "https").lower()
    host = registrable_domain(cleaned)
    path = (parsed.path or "").rstrip("/") or ""
    query = f"?{parsed.query}" if parsed.query else ""
    if not host:
        return cleaned.lower().rstrip("/")
    return f"{scheme}://{host}{path}{query}"


def build_mission_citation_sources(
    winner: Dict[str, Any],
    score_details: Sequence[Dict[str, Any]],
    *,
    max_sources: int = MAX_MISSION_CITATION_SOURCES,
) -> List[Dict[str, Any]]:
    """
    Build user-facing citation cards from verify scores.

    ``[1]`` is always the paraphrase winner. Further entries must also clear
    verify and share the winner's registrable domain (stricter bar). Total
    length is hard-capped (default 3).

    Args:
        winner: Winning score dict (must include ``url``).
        score_details: All candidate scores from verify.
        max_sources: Inclusive maximum citation count.

    Returns:
        Numbered source dicts for ``mission_context.sources``.
    """
    if max_sources < 1 or not winner.get("url"):
        return []

    winner_url = str(winner["url"])
    winner_domain = registrable_domain(winner_url)
    seen: Set[str] = {_normalize_citation_url(winner_url)}

    def _card(index: int, score: Dict[str, Any]) -> Dict[str, Any]:
        url = str(score.get("url") or "")
        title = str(score.get("title") or "").strip()
        excerpt = str(score.get("excerpt") or "").strip()
        snippet = excerpt[:180] + ("…" if len(excerpt) > 180 else "") if excerpt else ""
        return {
            "index": index,
            "url": url,
            "title": title,
            "domain": registrable_domain(url),
            "snippet": snippet or None,
            "kind": "company_mission",
        }

    sources: List[Dict[str, Any]] = [_card(1, winner)]
    if max_sources == 1 or not winner_domain:
        return sources

    secondaries = [
        score
        for score in score_details
        if score.get("passed")
        and str(score.get("url") or "")
        and _normalize_citation_url(str(score["url"])) not in seen
        and registrable_domain(str(score["url"])) == winner_domain
    ]
    secondaries.sort(
        key=lambda item: float(item.get("fact_match_ratio") or 0.0),
        reverse=True,
    )
    for score in secondaries:
        if len(sources) >= max_sources:
            break
        norm = _normalize_citation_url(str(score["url"]))
        if norm in seen:
            continue
        seen.add(norm)
        sources.append(_card(len(sources) + 1, score))
    return sources


def verify_mission_candidates(
    company: str,
    candidates: Sequence[MissionCandidate],
    *,
    jd_text: str = "",
    jd_facts: Optional[Sequence[str]] = None,
    fact_match_ratio_threshold: float = DEFAULT_FACT_MATCH_RATIO,
    min_matched_facts: int = DEFAULT_MIN_MATCHED_FACTS,
    name_match_ratio_threshold: float = DEFAULT_NAME_MATCH_RATIO,
) -> MissionVerifyResult:
    """
    Verify fetched candidates against JD facts; return pass or skip.

    Score every candidate, then pick the first that clears name + fact
    thresholds without collision as the paraphrase winner. On pass, also
    build a capped citation list (winner + same-domain secondaries).
    On failure, always return a legible ``skip_reason``.

    Args:
        company: Company name.
        candidates: Ordered search/fetch results.
        jd_text: Job description text.
        jd_facts: Optional curated facts.
        fact_match_ratio_threshold: Minimum matched-fact ratio.
        min_matched_facts: Minimum absolute matched facts.
        name_match_ratio_threshold: Minimum company-name token ratio.

    Returns:
        ``MissionVerifyResult`` with status ``pass`` or ``skip``.
    """
    facts = extract_jd_facts(jd_text=jd_text, jd_facts=jd_facts)
    if not company.strip():
        return MissionVerifyResult(
            status="skip",
            company=company,
            skip_reason="company name empty; cannot verify mission candidates",
        )
    if not facts:
        return MissionVerifyResult(
            status="skip",
            company=company,
            skip_reason="no JD facts available to verify company mission candidates",
        )
    if not candidates:
        return MissionVerifyResult(
            status="skip",
            company=company,
            skip_reason="no search results returned for company mission query",
        )

    score_details: List[Dict[str, Any]] = []
    best_near_miss: Optional[Dict[str, Any]] = None
    collision_any: List[str] = []
    winner: Optional[Dict[str, Any]] = None

    for candidate in candidates:
        score = score_candidate(
            company,
            facts,
            candidate,
            fact_match_ratio_threshold=fact_match_ratio_threshold,
            min_matched_facts=min_matched_facts,
            name_match_ratio_threshold=name_match_ratio_threshold,
        )
        score_details.append(score)
        if score["collision_hits"]:
            collision_any.extend(score["collision_hits"])
        if score["passed"] and winner is None:
            winner = score
        if best_near_miss is None or float(score["fact_match_ratio"]) > float(
            best_near_miss["fact_match_ratio"]
        ):
            best_near_miss = score

    if winner is not None:
        return MissionVerifyResult(
            status="pass",
            company=company,
            source_url=str(winner["url"]),
            source_title=(str(winner["title"]).strip() or None),
            matched_facts=list(winner["matched_facts"]),
            missing_facts=list(winner["missing_facts"]),
            fact_match_ratio=float(winner["fact_match_ratio"]),
            collision_hits=list(winner["collision_hits"]),
            excerpt=str(winner["excerpt"] or ""),
            score_details=score_details,
            sources=build_mission_citation_sources(winner, score_details),
        )

    unique_collisions = sorted(set(collision_any))
    if unique_collisions and (
        best_near_miss is None or not best_near_miss.get("clears_facts")
    ):
        return MissionVerifyResult(
            status="skip",
            company=company,
            skip_reason=(
                "company name ambiguous; collision signals "
                f"({', '.join(unique_collisions[:4])}) without JD-fact match "
                "cleared threshold"
            ),
            matched_facts=(
                list(best_near_miss["matched_facts"]) if best_near_miss else []
            ),
            missing_facts=(
                list(best_near_miss["missing_facts"]) if best_near_miss else list(facts)
            ),
            fact_match_ratio=(
                float(best_near_miss["fact_match_ratio"]) if best_near_miss else 0.0
            ),
            collision_hits=unique_collisions,
            score_details=score_details,
        )

    if best_near_miss and best_near_miss.get("clears_name"):
        return MissionVerifyResult(
            status="skip",
            company=company,
            skip_reason=(
                "company name matched search results, but no JD-fact match "
                f"cleared threshold (best fact_match_ratio="
                f"{best_near_miss['fact_match_ratio']:.2f}; "
                f"matched={best_near_miss['matched_facts'][:5]})"
            ),
            matched_facts=list(best_near_miss["matched_facts"]),
            missing_facts=list(best_near_miss["missing_facts"]),
            fact_match_ratio=float(best_near_miss["fact_match_ratio"]),
            collision_hits=unique_collisions,
            score_details=score_details,
        )

    return MissionVerifyResult(
        status="skip",
        company=company,
        skip_reason=(
            "company name ambiguous, no JD-fact match cleared threshold "
            "(no candidate cleared company-name and JD-fact gates)"
        ),
        matched_facts=list(best_near_miss["matched_facts"]) if best_near_miss else [],
        missing_facts=(
            list(best_near_miss["missing_facts"]) if best_near_miss else list(facts)
        ),
        fact_match_ratio=(
            float(best_near_miss["fact_match_ratio"]) if best_near_miss else 0.0
        ),
        collision_hits=unique_collisions,
        score_details=score_details,
    )


def extractive_paraphrase(excerpt: str, company: str, max_sentences: int = 2) -> str:
    """
    Build a short non-verbatim mission brief without an LLM.

    Takes the first sentences of the excerpt, strips common marketing openers,
    and prefixes a neutral attribution. Used when Ollama is unavailable.

    Args:
        excerpt: Source excerpt from a verified page.
        company: Company name for attribution.
        max_sentences: Maximum sentences to keep.

    Returns:
        Paraphrased brief, or empty string if excerpt is empty.
    """
    text = re.sub(r"\s+", " ", excerpt or "").strip()
    if not text:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", text)
    kept: List[str] = []
    for part in parts:
        cleaned = part.strip()
        if len(cleaned) < 20:
            continue
        cleaned = re.sub(
            r"^(we are|we're|our mission is to|our vision is to)\s+",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        kept.append(cleaned)
        if len(kept) >= max_sentences:
            break
    if not kept:
        kept = [text[:280]]
    body = " ".join(kept)
    first_token = company.strip().split()[0] if company.strip() else "The company"
    if not body.lower().startswith(first_token.lower()):
        body = f"{company} is described as focusing on: {body}"
    if len(body) > 420:
        body = body[:417].rstrip() + "..."
    return body
