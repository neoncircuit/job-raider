"""
Validate LinkedIn URLs before Playwright navigation.

Step 2.6: reject ``file://``, bare IPs, and non-LinkedIn hosts so a
crafted URL cannot point the browser at arbitrary targets.

A LinkedIn country host (two letters, such as ``sg.linkedin.com``) is
accepted and changed to ``www.linkedin.com``, so the app stores and opens one
form of each URL. The host must match in full: ``sg.linkedin.com.evil.com``
and ``evil-linkedin.com`` are rejected.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse, urlunparse

_ALLOWED_LINKEDIN_HOSTS = frozenset({"linkedin.com", "www.linkedin.com"})
_COUNTRY_HOST = re.compile(r"[a-z]{2}\.linkedin\.com")
_CANONICAL_HOST = "www.linkedin.com"


def validate_linkedin_navigation_url(url: str) -> str:
    """
    Require an ``https`` LinkedIn URL (any path on linkedin.com).

    A two-letter country host (``sg.linkedin.com``) is changed to
    ``www.linkedin.com``; path, query, and fragment stay.

    Used by ``navigate_to_url`` for search and other LinkedIn pages.

    Args:
        url: Candidate URL.

    Returns:
        The stripped URL when valid, with a country host changed to
        ``www.linkedin.com``.

    Raises:
        ValueError: When the URL is not https LinkedIn.
    """
    raw = (url or "").strip()
    if not raw:
        raise ValueError("LinkedIn URL is required")

    parsed = urlparse(raw)
    if parsed.scheme != "https":
        raise ValueError("LinkedIn URL must use https")

    host = (parsed.hostname or "").lower()
    is_country_host = bool(_COUNTRY_HOST.fullmatch(host))
    if host not in _ALLOWED_LINKEDIN_HOSTS and not is_country_host:
        raise ValueError("URL must use a linkedin.com host")

    if parsed.username or parsed.password:
        raise ValueError("LinkedIn URL must not include credentials")

    if is_country_host:
        return urlunparse(parsed._replace(netloc=_CANONICAL_HOST))
    return raw


def validate_linkedin_profile_url(profile_url: str) -> str:
    """
    Require an ``https`` LinkedIn ``/in/`` profile URL.

    Args:
        profile_url: Candidate URL from the user or API.

    Returns:
        The stripped URL when valid, with a country host changed to
        ``www.linkedin.com``.

    Raises:
        ValueError: When the URL is not an https LinkedIn profile.
    """
    raw = validate_linkedin_navigation_url(profile_url)
    parsed = urlparse(raw)
    path = parsed.path or ""
    if not path.startswith("/in/") or path.rstrip("/") == "/in":
        raise ValueError("Profile URL must be a LinkedIn /in/ profile path")
    return raw
