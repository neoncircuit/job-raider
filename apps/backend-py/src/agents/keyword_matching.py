"""
Fuzzy keyword -> target-job resolution for the Career Coach.

The career-coach UI lets users build a list of free-form keywords
("data sciense", "backend dev") instead of hand-writing JSON job objects.
Keywords are resolved against a role catalog with normalized Levenshtein
similarity, so misspellings still land on the intended role. Anything that
does not resolve to a role is treated as a skill keyword and grouped into a
single custom target job so it still participates in gap analysis.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

# Minimum normalized similarity for a keyword to claim a role/skill match.
MATCH_THRESHOLD = 0.72

# Score assigned to containment matches ("backend dev" in "backend developer").
CONTAINMENT_SCORE = 0.85

# Canonical roles. ``skills`` uses the shape consumed by
# ``CareerCoachAgent._analyze_job_skill_gaps`` (``job["skills"] = [{"name"}]``).
ROLE_CATALOG: Dict[str, Dict[str, Any]] = {
    "software_engineer": {
        "title": "Software Engineer",
        "aliases": ["software developer", "swe", "programmer", "software eng"],
        "skills": [
            "python",
            "java",
            "data structures",
            "algorithms",
            "git",
            "testing",
            "system design",
            "sql",
        ],
    },
    "frontend_developer": {
        "title": "Frontend Developer",
        "aliases": ["front end developer", "frontend engineer", "web developer"],
        "skills": [
            "javascript",
            "typescript",
            "react",
            "html",
            "css",
            "next.js",
            "accessibility",
            "testing",
        ],
    },
    "backend_developer": {
        "title": "Backend Developer",
        "aliases": ["back end developer", "backend engineer", "api developer"],
        "skills": [
            "python",
            "node.js",
            "sql",
            "rest apis",
            "databases",
            "docker",
            "caching",
            "message queues",
        ],
    },
    "fullstack_developer": {
        "title": "Full Stack Developer",
        "aliases": ["fullstack developer", "full stack engineer", "fullstack"],
        "skills": [
            "react",
            "typescript",
            "node.js",
            "sql",
            "rest apis",
            "docker",
            "testing",
        ],
    },
    "data_scientist": {
        "title": "Data Scientist",
        "aliases": ["data science", "applied scientist"],
        "skills": [
            "python",
            "statistics",
            "machine learning",
            "pandas",
            "sql",
            "data visualization",
            "experimentation",
            "communication",
        ],
    },
    "data_engineer": {
        "title": "Data Engineer",
        "aliases": ["data engineering", "etl developer"],
        "skills": [
            "python",
            "sql",
            "spark",
            "airflow",
            "etl",
            "data warehousing",
            "kafka",
            "cloud",
        ],
    },
    "ml_engineer": {
        "title": "Machine Learning Engineer",
        "aliases": ["ml engineer", "ai engineer", "mlops engineer", "llm engineer"],
        "skills": [
            "python",
            "pytorch",
            "tensorflow",
            "mlops",
            "docker",
            "kubernetes",
            "model deployment",
            "data pipelines",
        ],
    },
    "devops_engineer": {
        "title": "DevOps Engineer",
        "aliases": ["devops", "site reliability engineer", "sre", "platform engineer"],
        "skills": [
            "linux",
            "docker",
            "kubernetes",
            "ci/cd",
            "terraform",
            "aws",
            "monitoring",
            "scripting",
        ],
    },
    "mobile_developer": {
        "title": "Mobile Developer",
        "aliases": ["mobile engineer", "ios developer", "android developer"],
        "skills": [
            "swift",
            "kotlin",
            "react native",
            "flutter",
            "mobile ui",
            "app store deployment",
        ],
    },
    "cloud_architect": {
        "title": "Cloud Architect",
        "aliases": ["cloud engineer", "solutions architect"],
        "skills": [
            "aws",
            "azure",
            "gcp",
            "networking",
            "security",
            "infrastructure as code",
            "cost optimization",
        ],
    },
    "security_engineer": {
        "title": "Security Engineer",
        "aliases": ["cybersecurity analyst", "security analyst", "infosec"],
        "skills": [
            "security",
            "penetration testing",
            "siem",
            "incident response",
            "networking",
            "compliance",
        ],
    },
    "qa_engineer": {
        "title": "QA Engineer",
        "aliases": ["quality assurance", "test engineer", "sdet"],
        "skills": [
            "test automation",
            "selenium",
            "playwright",
            "api testing",
            "test planning",
            "ci/cd",
        ],
    },
    "product_manager": {
        "title": "Product Manager",
        "aliases": ["product owner", "pm", "product management"],
        "skills": [
            "roadmapping",
            "stakeholder management",
            "user research",
            "analytics",
            "agile",
            "communication",
        ],
    },
    "ui_ux_designer": {
        "title": "UI/UX Designer",
        "aliases": ["ux designer", "ui designer", "product designer"],
        "skills": [
            "figma",
            "wireframing",
            "prototyping",
            "user research",
            "design systems",
            "usability testing",
        ],
    },
}


def _normalize(text: str) -> str:
    """Lowercase and collapse separators so ``Back-End_Dev`` == ``back end dev``."""
    return re.sub(r"[\s\-_/]+", " ", text.strip().lower())


def levenshtein_distance(a: str, b: str) -> int:
    """Compute edit distance with a two-row dynamic program."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    previous = list(range(len(b) + 1))
    for i, char_a in enumerate(a, start=1):
        current = [i]
        for j, char_b in enumerate(b, start=1):
            current.append(
                min(
                    previous[j] + 1,  # deletion
                    current[j - 1] + 1,  # insertion
                    previous[j - 1] + (char_a != char_b),  # substitution
                )
            )
        previous = current
    return previous[-1]


def similarity(a: str, b: str) -> float:
    """Normalized Levenshtein similarity in ``[0, 1]``."""
    norm_a, norm_b = _normalize(a), _normalize(b)
    if not norm_a or not norm_b:
        return 0.0
    longest = max(len(norm_a), len(norm_b))
    return 1.0 - levenshtein_distance(norm_a, norm_b) / longest


def _keyword_score(keyword: str, candidate: str) -> float:
    """Similarity with a containment bonus for partial phrases."""
    kw, cand = _normalize(keyword), _normalize(candidate)
    score = similarity(kw, cand)
    if len(kw) >= 3 and (kw in cand or cand in kw):
        score = max(score, CONTAINMENT_SCORE)
    return score


def best_role_match(keyword: str) -> Tuple[Optional[str], float, Optional[str]]:
    """
    Find the catalog role most similar to a keyword.

    Args:
        keyword: Free-form user keyword.

    Returns:
        Tuple of (role key or None, best score, alias that matched or None).
    """
    best_key: Optional[str] = None
    best_alias: Optional[str] = None
    best_score = 0.0
    for role_key, role in ROLE_CATALOG.items():
        for alias in [role["title"], *role["aliases"]]:
            score = _keyword_score(keyword, alias)
            if score > best_score:
                best_key, best_score, best_alias = role_key, score, alias
    return best_key, best_score, best_alias


def _best_skill_match(keyword: str) -> Tuple[Optional[str], float]:
    """Find the catalog skill most similar to a keyword."""
    best_skill: Optional[str] = None
    best_score = 0.0
    for role in ROLE_CATALOG.values():
        for skill in role["skills"]:
            score = _keyword_score(keyword, skill)
            if score > best_score:
                best_skill, best_score = skill, score
    return best_skill, best_score


def resolve_keywords(keywords: List[str]) -> Dict[str, Any]:
    """
    Resolve free-form keywords into target-job dicts for the Career Coach.

    Args:
        keywords: Raw user keywords; blanks are ignored.

    Returns:
        Dict with:
            ``target_jobs``: jobs shaped ``{"title", "skills": [{"name"}], ...}``
            ``matches``: per-keyword resolution report
            ``unmatched``: keywords that resolved to neither role nor skill
    """
    role_hits: Dict[str, Dict[str, Any]] = {}
    skill_names: List[str] = []
    matches: List[Dict[str, Any]] = []
    unmatched: List[str] = []

    for raw in keywords:
        keyword = raw.strip()
        if not keyword:
            continue

        role_key, role_score, alias = best_role_match(keyword)
        if role_key and role_score >= MATCH_THRESHOLD:
            hit = role_hits.setdefault(role_key, {"keywords": [], "score": 0.0})
            hit["keywords"].append(keyword)
            hit["score"] = max(hit["score"], role_score)
            matches.append(
                {
                    "keyword": keyword,
                    "matched": ROLE_CATALOG[role_key]["title"],
                    "kind": "role",
                    "score": round(role_score, 3),
                    "via": alias,
                }
            )
            continue

        skill, skill_score = _best_skill_match(keyword)
        if skill and skill_score >= MATCH_THRESHOLD:
            if skill not in skill_names:
                skill_names.append(skill)
            matches.append(
                {
                    "keyword": keyword,
                    "matched": skill,
                    "kind": "skill",
                    "score": round(skill_score, 3),
                    "via": skill,
                }
            )
            continue

        normalized = _normalize(keyword)
        if normalized not in skill_names:
            skill_names.append(normalized)
        unmatched.append(keyword)
        matches.append(
            {
                "keyword": keyword,
                "matched": None,
                "kind": "unmatched",
                "score": round(max(role_score, skill_score), 3),
                "via": None,
            }
        )

    target_jobs: List[Dict[str, Any]] = []
    for role_key, hit in role_hits.items():
        role = ROLE_CATALOG[role_key]
        target_jobs.append(
            {
                "title": role["title"],
                "skills": [{"name": skill} for skill in role["skills"]],
                "source": "keyword_match",
                "matched_keywords": hit["keywords"],
                "match_score": round(hit["score"], 3),
            }
        )
    if skill_names:
        target_jobs.append(
            {
                "title": "Custom skill targets",
                "skills": [{"name": skill} for skill in skill_names],
                "source": "keyword_skills",
                "matched_keywords": [
                    m["keyword"] for m in matches if m["kind"] in ("skill", "unmatched")
                ],
            }
        )

    return {"target_jobs": target_jobs, "matches": matches, "unmatched": unmatched}
