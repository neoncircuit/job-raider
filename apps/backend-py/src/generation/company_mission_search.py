"""
Job Raider - Company Mission Search / Resolve

Network I/O for company-mission grounding: DuckDuckGo HTML search, page
fetch, verify-against-JD-facts, and paraphrased brief. Used by cover-letter
generate when ``enable_company_mission`` is on, and by the Phase B spike.

Author: Job Raider
Date: 2026-08-21
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import parse_qs, unquote, urlparse

import requests
from bs4 import BeautifulSoup

from .company_mission import (
    MissionCandidate,
    MissionVerifyResult,
    build_search_query,
    extractive_paraphrase,
    verify_mission_candidates,
)

USER_AGENT = "Mozilla/5.0 (compatible; JobRaiderMission/0.1; +https://github.com/local)"
SEARCH_TIMEOUT_S = 12
FETCH_TIMEOUT_S = 10
PARAPHRASE_TIMEOUT_S = 20
MAX_PAGE_BYTES = 800_000
MAX_TEXT_CHARS = 12_000
MAX_SEARCH_RESULTS = 8
MAX_FETCH = 5
# Hard wall-clock budget so cover-letter Generate cannot hang on search.
RESOLVE_DEADLINE_S = 28.0

_BOILERPLATE_MARKERS = (
    "manage consent",
    "we use cookies",
    "accept cookies",
    "privacy policy",
    "terms & conditions",
    "terms and conditions",
    "all rights reserved",
    "copyright ©",
    "follow us",
    "subscribe to our newsletter",
)


@dataclass
class MissionResolveResult:
    """
    Outcome of resolving a company mission brief for cover-letter use.

    Attributes:
        status: ``pass``, ``skip``, ``disabled``, or ``error``.
        brief: Paraphrased mission text when status is ``pass``.
        skip_reason: Legible reason when status is ``skip`` or ``error``.
        source_url: Winning page URL when status is ``pass``.
        source_title: Winning page title when status is ``pass``.
        paraphrase_method: ``ollama``, ``extractive``, or empty.
        query: Search query used (when search ran).
        elapsed_ms: Wall time for the resolve attempt.
        verify: Optional raw verify payload for logging / responses.
    """

    status: str
    brief: str = ""
    skip_reason: str = ""
    source_url: Optional[str] = None
    source_title: Optional[str] = None
    paraphrase_method: str = ""
    query: str = ""
    elapsed_ms: float = 0.0
    verify: Dict[str, Any] = field(default_factory=dict)

    def to_mission_context(self) -> Dict[str, Any]:
        """
        Build the API ``mission_context`` payload.

        Returns:
            Dict with status and optional source / skip / brief fields.
        """
        payload: Dict[str, Any] = {
            "status": self.status,
            "elapsed_ms": self.elapsed_ms,
        }
        if self.brief:
            payload["brief"] = self.brief
        if self.source_url:
            payload["source_url"] = self.source_url
        if self.source_title:
            payload["source_title"] = self.source_title
        if self.skip_reason:
            payload["skip_reason"] = self.skip_reason
        if self.paraphrase_method:
            payload["paraphrase_method"] = self.paraphrase_method
        if self.query:
            payload["query"] = self.query
        return payload

    def to_dict(self) -> Dict[str, Any]:
        """
        Full dict for spike / debug artifacts.

        Returns:
            Plain dict including nested verify details.
        """
        return asdict(self)


def _unwrap_ddg_redirect(href: str) -> str:
    """
    Unwrap DuckDuckGo redirect URLs to the destination.

    Args:
        href: Raw href from DDG HTML.

    Returns:
        Destination URL when present, else the input href.
    """
    if not href:
        return ""
    if href.startswith("//"):
        href = "https:" + href
    parsed = urlparse(href)
    if "duckduckgo.com" in (parsed.netloc or "") and parsed.path.startswith("/l/"):
        qs = parse_qs(parsed.query)
        uddg = qs.get("uddg") or qs.get("u")
        if uddg:
            return unquote(uddg[0])
    return href


def search_duckduckgo_html(
    query: str,
    max_results: int = MAX_SEARCH_RESULTS,
    timeout_s: float = SEARCH_TIMEOUT_S,
) -> List[Dict[str, str]]:
    """
    Search DuckDuckGo HTML endpoint with requests + BeautifulSoup.

    Args:
        query: Search query.
        max_results: Maximum result rows to return.
        timeout_s: HTTP timeout in seconds.

    Returns:
        List of dicts with ``url``, ``title``, ``snippet``.
    """
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    resp = session.post(
        "https://html.duckduckgo.com/html/",
        data={"q": query},
        timeout=timeout_s,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    results: List[Dict[str, str]] = []
    for result in soup.select("div.result"):
        link = result.select_one("a.result__a")
        if not link or not link.get("href"):
            continue
        url = _unwrap_ddg_redirect(link["href"])
        if not url.startswith("http"):
            continue
        if "duckduckgo.com" in urlparse(url).netloc:
            continue
        snippet_el = result.select_one("a.result__snippet") or result.select_one(
            "div.result__snippet"
        )
        title = link.get_text(" ", strip=True)
        snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""
        results.append({"url": url, "title": title, "snippet": snippet})
        if len(results) >= max_results:
            break
    return results


def extract_main_content_text(html: str, max_chars: int = MAX_TEXT_CHARS) -> str:
    """
    Extract substantive page text, preferring main/article over chrome.

    Removes script/style/nav/footer/aside and cookie/consent nodes, then
    prefers ``main`` / ``article`` / ``[role=main]`` when present.

    Args:
        html: Raw HTML.
        max_chars: Truncation limit.

    Returns:
        Visible main-content text string.
    """
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(
        [
            "script",
            "style",
            "noscript",
            "svg",
            "iframe",
            "nav",
            "footer",
            "header",
            "aside",
            "form",
        ]
    ):
        tag.decompose()

    for node in list(soup.find_all(True)):
        attrs = " ".join(
            [
                " ".join(node.get("class") or []),
                str(node.get("id") or ""),
                str(node.get("role") or ""),
            ]
        ).lower()
        if any(
            hint in attrs
            for hint in (
                "cookie",
                "consent",
                "newsletter",
                "subscribe",
                "cookie-banner",
                "gdpr",
            )
        ):
            node.decompose()

    root = (
        soup.find("main")
        or soup.find("article")
        or soup.find(attrs={"role": "main"})
        or soup.body
        or soup
    )
    text = root.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    for marker in _BOILERPLATE_MARKERS:
        idx = text.lower().find(marker)
        if idx > 200:
            text = text[:idx].rstrip()
            break
    return text[:max_chars]


def fetch_page(url: str, timeout_s: float = FETCH_TIMEOUT_S) -> Tuple[str, str]:
    """
    Fetch a page and return title + main-content text.

    Args:
        url: Absolute HTTP(S) URL.
        timeout_s: HTTP timeout in seconds.

    Returns:
        Tuple of (title, text). Empty strings on soft failure.
    """
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=timeout_s,
            allow_redirects=True,
        )
        if resp.status_code >= 400:
            return "", ""
        content = resp.content[:MAX_PAGE_BYTES]
        encoding = resp.encoding or "utf-8"
        try:
            html = content.decode(encoding, errors="replace")
        except LookupError:
            html = content.decode("utf-8", errors="replace")
        soup = BeautifulSoup(html, "lxml")
        title = (soup.title.get_text(" ", strip=True) if soup.title else "") or ""
        text = extract_main_content_text(html)
        return title, text
    except requests.RequestException:
        return "", ""


def resolve_ollama_host() -> str:
    """
    Resolve Ollama host for optional paraphrase.

    Returns:
        Host string without scheme (e.g. ``localhost:11434``).
    """
    env = (os.getenv("OLLAMA_HOST") or "").strip()
    if env:
        return env.replace("http://", "").replace("https://", "").rstrip("/")
    return "localhost:11434"


def paraphrase_with_ollama(
    excerpt: str,
    company: str,
    model: str = "qwen2.5:7b",
    timeout_s: float = PARAPHRASE_TIMEOUT_S,
) -> Optional[str]:
    """
    Ask Ollama to paraphrase a mission excerpt; return None on failure.

    Args:
        excerpt: Verified page excerpt.
        company: Company name.
        model: Ollama model tag.
        timeout_s: HTTP timeout in seconds.

    Returns:
        Paraphrased brief, or None if Ollama is unavailable / errors.
    """
    if not excerpt.strip():
        return None
    host = resolve_ollama_host()
    url = f"http://{host}/api/generate"
    prompt = (
        "Rewrite the following company website excerpt into 1-2 neutral sentences "
        f"about what {company} does (mission / focus). Do not copy marketing slogans "
        "verbatim. Do not invent facts. Output plain text only.\n\n"
        f"EXCERPT:\n{excerpt[:900]}"
    )
    try:
        resp = requests.post(
            url,
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.2, "num_predict": 180},
            },
            timeout=timeout_s,
        )
        if resp.status_code >= 400:
            return None
        data = resp.json()
        text = (data.get("response") or "").strip()
        return text or None
    except (requests.RequestException, ValueError, json.JSONDecodeError):
        return None


def paraphrase_mission(excerpt: str, company: str) -> Dict[str, str]:
    """
    Produce a mission brief via Ollama or extractive fallback.

    Args:
        excerpt: Source excerpt.
        company: Company name.

    Returns:
        Dict with ``method`` and ``brief``.
    """
    llm = paraphrase_with_ollama(excerpt, company)
    if llm:
        return {"method": "ollama", "brief": llm}
    return {
        "method": "extractive",
        "brief": extractive_paraphrase(excerpt, company),
    }


def resolve_company_mission(
    company: str,
    *,
    jd_text: str = "",
    jd_facts: Optional[Sequence[str]] = None,
    enabled: bool = True,
    deadline_s: float = RESOLVE_DEADLINE_S,
) -> MissionResolveResult:
    """
    Search, verify, and paraphrase a company mission brief under a deadline.

    Args:
        company: Company name from the job listing.
        jd_text: Job description text for disambiguation.
        jd_facts: Optional curated fact phrases.
        enabled: When False, return status ``disabled`` immediately.
        deadline_s: Wall-clock budget for the full resolve path.

    Returns:
        ``MissionResolveResult`` with pass/skip/disabled/error status.
    """
    started = time.perf_counter()

    def _elapsed() -> float:
        return round((time.perf_counter() - started) * 1000, 1)

    def _remaining() -> float:
        return max(0.5, deadline_s - (time.perf_counter() - started))

    if not enabled:
        return MissionResolveResult(status="disabled", elapsed_ms=_elapsed())

    company = (company or "").strip()
    if not company:
        return MissionResolveResult(
            status="skip",
            skip_reason="company name empty; cannot resolve company mission",
            elapsed_ms=_elapsed(),
        )

    query = build_search_query(company, jd_text=jd_text, jd_facts=jd_facts)
    search_hits: List[Dict[str, str]] = []
    try:
        search_hits = search_duckduckgo_html(
            query,
            timeout_s=min(SEARCH_TIMEOUT_S, _remaining()),
        )
    except requests.RequestException as exc:
        return MissionResolveResult(
            status="error",
            skip_reason=f"company mission search failed: {exc}",
            query=query,
            elapsed_ms=_elapsed(),
        )

    if _remaining() < 1.0:
        return MissionResolveResult(
            status="skip",
            skip_reason="company mission resolve timed out before page fetch",
            query=query,
            elapsed_ms=_elapsed(),
        )

    candidates: List[MissionCandidate] = []
    for hit in search_hits[:MAX_FETCH]:
        if _remaining() < 1.5:
            break
        title, text = fetch_page(
            hit["url"],
            timeout_s=min(FETCH_TIMEOUT_S, _remaining()),
        )
        candidates.append(
            MissionCandidate(
                url=hit["url"],
                title=title or hit.get("title") or "",
                text=text,
                snippet=hit.get("snippet") or "",
            )
        )

    if not any(c.text for c in candidates) and search_hits:
        candidates = [
            MissionCandidate(
                url=h["url"],
                title=h.get("title") or "",
                text="",
                snippet=h.get("snippet") or "",
            )
            for h in search_hits
        ]

    verify: MissionVerifyResult = verify_mission_candidates(
        company,
        candidates,
        jd_text=jd_text,
        jd_facts=jd_facts,
    )

    if verify.status != "pass":
        return MissionResolveResult(
            status="skip",
            skip_reason=verify.skip_reason
            or "company name ambiguous, no JD-fact match cleared threshold",
            query=query,
            elapsed_ms=_elapsed(),
            verify=verify.to_dict(),
        )

    paraphrase = paraphrase_mission(verify.excerpt, company)
    brief = (paraphrase.get("brief") or "").strip()
    if not brief:
        return MissionResolveResult(
            status="skip",
            skip_reason="verified source found but mission paraphrase was empty",
            source_url=verify.source_url,
            source_title=verify.source_title,
            query=query,
            elapsed_ms=_elapsed(),
            verify=verify.to_dict(),
        )

    return MissionResolveResult(
        status="pass",
        brief=brief,
        source_url=verify.source_url,
        source_title=verify.source_title,
        paraphrase_method=str(paraphrase.get("method") or ""),
        query=query,
        elapsed_ms=_elapsed(),
        verify=verify.to_dict(),
    )
