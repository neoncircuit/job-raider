"""
Job Raider - Company Site Finder

Finds a job's posting or careers page on the company's own site or on a
known applicant tracking system (ATS). Search and fetch are injected, so
tests need no network. A link is returned only when the fetched page names
the company, and an exact posting also matches the job title. A wrong link
is worse than no link, so the finder returns level ``none`` when unsure.

Author: Job Raider
Date: 2026-11-20
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple
from urllib.parse import urlparse

import requests

from ..generation.company_mission import registrable_domain
from ..generation.company_mission_search import fetch_page, search_duckduckgo_html

MAX_RESULTS = 8
MAX_FETCH = 5
TITLE_MATCH_RATIO = 0.8

LEVEL_EXACT = "exact"
LEVEL_CAREERS = "careers"
LEVEL_NONE = "none"

_LEGAL_SUFFIXES: Set[str] = {
    "pte",
    "ltd",
    "limited",
    "llp",
    "llc",
    "inc",
    "co",
    "corp",
    "corporation",
    "plc",
    "pvt",
    "private",
}
_TITLE_STOPWORDS: Set[str] = {"a", "an", "and", "at", "for", "in", "of", "the", "to"}
_PORTAL_LABELS: Set[str] = {
    "mycareersfuture",
    "linkedin",
    "indeed",
    "jobstreet",
    "glassdoor",
    "jobsdb",
    "monster",
    "ziprecruiter",
    "seek",
    "adzuna",
    "jora",
    "careerjet",
}
_ATS_SUFFIXES: Tuple[str, ...] = (
    "greenhouse.io",
    "lever.co",
    "myworkdayjobs.com",
    "smartrecruiters.com",
    "ashbyhq.com",
    "workable.com",
    "successfactors.com",
    "successfactors.eu",
    "taleo.net",
    "icims.com",
    "bamboohr.com",
    "recruitee.com",
    "personio.com",
    "personio.de",
    "jobvite.com",
    "breezy.hr",
    "teamtailor.com",
)
_CAREERS_MARKER = re.compile(r"career|jobs|join|vacanc|opening|hiring")
_SENIORITY_WORDS: Set[str] = {
    "senior",
    "sr",
    "lead",
    "principal",
    "staff",
    "manager",
    "director",
    "head",
}

SearchFn = Callable[[str], List[Dict[str, str]]]
FetchFn = Callable[[str], Tuple[str, str]]


@dataclass
class CompanySiteResult:
    """
    Outcome of looking for a job on the company's own site.

    Attributes:
        level: ``exact`` (posting), ``careers`` (careers page), or ``none``.
        url: Verified page URL, or None when level is ``none``.
        page_title: Title of the verified page.
        evidence: Human-readable checks that the page passed.
        checked_at: UTC time of the check, ISO 8601.
        query: Search query that was used.
        search_failed: True when the search itself failed (for example a
            network error), so the outcome is not a real answer and is not cached.
        pages_attempted: Number of candidate pages that were fetched.
        pages_loaded: Number of those pages that loaded (returned content).
    """

    level: str
    url: Optional[str] = None
    page_title: Optional[str] = None
    evidence: List[str] = field(default_factory=list)
    checked_at: str = ""
    query: str = ""
    search_failed: bool = False
    pages_attempted: int = 0
    pages_loaded: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize the result for the API and the cache.

        Returns:
            Plain dict with JSON-ready values.
        """
        return asdict(self)


def _words(text: str) -> List[str]:
    """
    Split text into lowercase alphanumeric words.

    Args:
        text: Any text.

    Returns:
        The words in order.
    """
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def clean_company_name(name: str) -> str:
    """
    Normalize a company name and drop trailing legal suffixes.

    Args:
        name: Company name as listed on the job, e.g. "Acme Pte. Ltd.".

    Returns:
        Lowercase words joined by one space; empty when nothing is left.
    """
    words = _words(name)
    while words and words[-1] in _LEGAL_SUFFIXES:
        words.pop()
    return " ".join(words)


def _host(url: str) -> str:
    """
    Return the lowercase host of a URL.

    Args:
        url: Absolute URL.

    Returns:
        The host, or an empty string when there is none.
    """
    return (urlparse(url).hostname or "").lower()


def is_portal_url(url: str) -> bool:
    """
    Tell whether a URL belongs to a job portal or aggregator.

    Args:
        url: Absolute URL.

    Returns:
        True for known job portals, False otherwise.
    """
    host = _host(url)
    if host == "careers.gov.sg" or host.endswith(".careers.gov.sg"):
        return True
    return any(label in _PORTAL_LABELS for label in host.split("."))


def is_ats_url(url: str) -> bool:
    """
    Tell whether a URL is on a known applicant tracking system.

    Args:
        url: Absolute URL.

    Returns:
        True when the host is an ATS host or one of its subdomains.
    """
    host = _host(url)
    return any(host == s or host.endswith("." + s) for s in _ATS_SUFFIXES)


def _is_company_domain(url: str, slug: str) -> bool:
    """
    Tell whether the URL's registrable domain is named after the company.

    Args:
        url: Absolute URL.
        slug: Company name without spaces or punctuation, e.g. "marigoldhealth".

    Returns:
        True when the domain label equals the slug.
    """
    label = registrable_domain(url).split(".")[0]
    return re.sub(r"[^a-z0-9]", "", label) == slug


def _title_matches(job_title: str, page_title: str) -> bool:
    """
    Tell whether a page title names the job, in any word order.

    At least 80 % of the job title words must appear, and at least two
    words when the job title has two or more. A page title that adds a
    seniority word (senior, lead, manager, and so on) that the job title does
    not have is rejected.

    Args:
        job_title: Job title as listed.
        page_title: Title of the fetched page.

    Returns:
        True when the page title matches the job title.
    """
    job_words = [w for w in _words(job_title) if w not in _TITLE_STOPWORDS]
    if not job_words:
        return False
    page_words = set(_words(page_title))
    extra_seniority = (page_words - set(_words(job_title))) & _SENIORITY_WORDS
    if extra_seniority:
        return False
    matched = sum(1 for w in job_words if w in page_words)
    needed = min(2, len(job_words))
    return matched >= needed and matched / len(job_words) >= TITLE_MATCH_RATIO


def _names_company_in_title_or_url(name: str, url: str, page_title: str) -> bool:
    """
    Tell whether an ATS page names the company in its title or its URL.

    The page text is not enough: a posting of another company can mention our
    company as a client. All words of the company name must be in the page
    title, or the first k words of the company name, joined, must equal a
    whole word of the URL, for some k (for example ``harbourline`` in
    ``harbourline.wd3.myworkdayjobs.com``, or ``lumenanalytics`` in
    ``boards.greenhouse.io/lumenanalytics``). A single first word must have at
    least four letters.

    Args:
        name: Cleaned company name (lowercase words).
        url: Page URL.
        page_title: Title of the fetched page.

    Returns:
        True when the company is named in the title or the URL.
    """
    name_words = _words(name)
    if not name_words:
        return False
    if set(name_words) <= set(_words(page_title)):
        return True
    url_words = set(_words(url))
    for k in range(1, len(name_words) + 1):
        joined = "".join(name_words[:k])
        if len(joined) >= 4 and joined in url_words:
            return True
    return False


def _careers_marker(url: str, page_title: str) -> bool:
    """
    Tell whether a URL path or page title says it is a careers page.

    Args:
        url: Page URL.
        page_title: Title of the fetched page.

    Returns:
        True when "career", "jobs", or a similar word appears.
    """
    path = urlparse(url).path.lower()
    return bool(
        _CAREERS_MARKER.search(path) or _CAREERS_MARKER.search(page_title.lower())
    )


def find_company_site(
    company: str,
    job_title: str,
    *,
    search: SearchFn = search_duckduckgo_html,
    fetch: FetchFn = fetch_page,
    max_results: int = MAX_RESULTS,
    max_fetch: int = MAX_FETCH,
) -> CompanySiteResult:
    """
    Find the job's posting or careers page on the company's own site or ATS.

    Portal URLs are skipped before any fetch. A URL is fetched only when its
    host is an ATS host or its domain is named after the company. A fetched
    page must name every word of the company. An exact posting also needs a
    matching page title. A careers page needs a company domain and a careers
    word in the URL or title. An exact posting always beats a careers page.

    Args:
        company: Company name from the job listing.
        job_title: Job title from the job listing.
        search: Function that takes a query and returns result dicts with a
            ``url`` key.
        fetch: Function that takes a URL and returns ``(title, text)``; both
            empty means the fetch failed.
        max_results: Maximum search results to consider.
        max_fetch: Maximum pages to fetch.

    Returns:
        ``CompanySiteResult`` with level, URL, evidence, and time checked.
    """
    checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    name = clean_company_name(company)
    query = f"{name} {job_title} careers".strip()
    attempted = 0
    loaded = 0

    def _none(evidence: List[str], search_failed: bool = False) -> CompanySiteResult:
        return CompanySiteResult(
            level=LEVEL_NONE,
            evidence=evidence,
            checked_at=checked_at,
            query=query,
            search_failed=search_failed,
            pages_attempted=attempted,
            pages_loaded=loaded,
        )

    if not name:
        return _none(["company name is empty"])

    try:
        hits: Sequence[Dict[str, str]] = search(query)[:max_results]
    except requests.RequestException as exc:
        return _none([f"search failed: {exc}"], search_failed=True)

    name_words = set(_words(name))
    slug = "".join(_words(name))
    careers: Optional[CompanySiteResult] = None

    for hit in hits:
        url = hit.get("url", "")
        if not url or is_portal_url(url):
            continue
        ats = is_ats_url(url)
        own_domain = _is_company_domain(url, slug)
        if not ats and not own_domain:
            continue
        if attempted >= max_fetch:
            break
        attempted += 1
        page_title, text = fetch(url)
        if not page_title and not text:
            continue
        loaded += 1
        if not name_words <= set(_words(f"{page_title} {text}")):
            continue
        if ats and not _names_company_in_title_or_url(name, url, page_title):
            continue

        host_note = f"host {_host(url)} is an ATS" if ats else "company domain"
        if _title_matches(job_title, page_title):
            return CompanySiteResult(
                level=LEVEL_EXACT,
                url=url,
                page_title=page_title,
                evidence=[
                    host_note,
                    "page names the company",
                    "page title matches the job title",
                ],
                checked_at=checked_at,
                query=query,
                pages_attempted=attempted,
                pages_loaded=loaded,
            )
        if own_domain and careers is None and _careers_marker(url, page_title):
            careers = CompanySiteResult(
                level=LEVEL_CAREERS,
                url=url,
                page_title=page_title,
                evidence=[host_note, "page names the company", "careers page"],
                checked_at=checked_at,
                query=query,
                pages_attempted=attempted,
                pages_loaded=loaded,
            )

    if careers is not None:
        careers.pages_attempted = attempted
        careers.pages_loaded = loaded
        return careers
    return _none([f"no verified page among {len(hits)} search results"])
