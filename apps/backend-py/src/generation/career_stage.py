"""
Job Raider - Career-stage inference for LinkedIn analysis.

Infers whether a candidate is early-career (fresh graduate / first-role)
or experienced, and whether an early-career candidate is intern-seeking
or targeting a full-time first role. Uses the stored Job Raider profile
and LinkedIn payload signals. Analysis prompts and fallback scoring use
this framing so the model does not invent mid-career tenure or keep
pushing internships after a traineeship.

Author: Job Raider
Date: 2026-08-15
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from ..models.job_listing import ExperienceLevel
from ..models.linkedin_analysis import LinkedInProfileInput
from ..models.user_profile import UserProfile

CareerStage = Literal["early_career", "experienced"]
JobSearchIntent = Literal["internship", "full_time"]

# Non-internship professional years at or above this value count as experienced.
_EXPERIENCED_YEARS = 2.0
# Graduation within this many calendar years is a fresh-graduate signal.
_RECENT_GRAD_YEARS = 2
_YEAR_RE = re.compile(r"(?:19|20)\d{2}")
_INTERNSHIP_RE = re.compile(
    r"\b(intern(?:ship)?s?|trainee(?:ship)?s?|apprentices?|co-?ops?|"
    r"industrial attachment|student assistant|graduate assistant|"
    r"teaching assistant|research assistant|national service|"
    r"nsmen|nsman|nsf)\b",
    re.IGNORECASE,
)
_GRADUATE_RE = re.compile(
    r"\b((?:fresh|recent)\s+graduates?|university students?|"
    r"final[- ]year students?|seeking (?:a )?first (?:full[- ]time )?role|"
    r"open to internships?)\b",
    re.IGNORECASE,
)
_INTERN_SEEKING_RE = re.compile(
    r"\b(open to internships?|seeking (?:an? )?intern(?:ship)?s?|"
    r"looking for (?:an? )?intern(?:ship)?s?|apply(?:ing)? to internships?)\b",
    re.IGNORECASE,
)
_FULL_TIME_SEEKING_RE = re.compile(
    r"\b(first full[- ]time|full[- ]time (?:role|position|job)|"
    r"junior (?:role|position)|entry[- ]level|"
    r"graduate (?:programme|program|scheme))\b",
    re.IGNORECASE,
)
_SENIOR_TITLE_RE = re.compile(
    r"\b(senior|staff|principal|lead|head of|director|vp|vice president|"
    r"manager|head)\b",
    re.IGNORECASE,
)
_PROFESSIONAL_TARGET_LEVELS = {
    ExperienceLevel.ENTRY,
    ExperienceLevel.MID,
    ExperienceLevel.SENIOR,
    ExperienceLevel.LEAD,
    ExperienceLevel.PRINCIPAL,
    ExperienceLevel.EXECUTIVE,
}

EARLY_CAREER_INTERN_GUIDANCE = """\
CAREER STAGE: early_career (intern-seeking)

Frame this analysis for someone still targeting internships or intern-level
roles. Finding that first role is the hard part. Do not treat a sparse or
internship-heavy profile as a failed mid-career profile.

SCORING WEIGHTS (early-career intern-seeking):
- Headline (weight 0.25): Clear intern or first-role targeting (degree or
  domain plus intern/junior/graduate keywords). Do not demand senior
  keyword stuffing.
- Projects, internships, and coursework (weight 0.25): Core evidence. Credit
  detailed project bullets, internships, and relevant coursework. Do not
  penalize the absence of multi-year full-time leadership.
- Skills for intern/graduate roles (weight 0.20): Skills that match intern,
  graduate, or junior postings. Do not demand large endorsement counts.
- About / summary (weight 0.20): Honest positioning. A short, specific About
  is acceptable. Never invent tenure.
- Education (weight 0.10): Degree, dates, coursework, and activities.

FORBIDDEN:
- Do not invent years of experience, titles, or employers that are not in
  the source LinkedIn profile.
- Do not write tenure phrases such as "with over N years of experience".
- Do not recommend senior quantified leadership, large endorsement drives,
  or mid-career product-manager playbooks.
- Headline and summary rewrites must stay consistent with internships,
  projects, coursework, and stated target roles only.

RECOMMEND: a headline aimed at intern and first-role discovery; showcase
projects, internships, and coursework; skills aligned to intern/grad roles;
an honest summary without invented tenure.
"""

EARLY_CAREER_FULL_TIME_GUIDANCE = """\
CAREER STAGE: early_career (full-time first role)

Frame this analysis for someone seeking a first full-time junior or entry
role. They may have finished an internship, traineeship, apprenticeship, or
national service and are now obligated or ready to work full-time. Finding
that first full-time role is the hard part. Do not treat a sparse profile
as a failed mid-career profile.

SCORING WEIGHTS (early-career full-time):
- Headline (weight 0.25): Clear full-time junior/entry targeting (degree or
  domain plus junior, graduate, or entry keywords). Do not use intern
  titles. Do not demand senior keyword stuffing.
- Completed training, projects, and coursework (weight 0.25): Core evidence.
  Frame internships and traineeships as completed training. Do not penalize
  the absence of multi-year full-time leadership.
- Skills for junior/entry roles (weight 0.20): Skills that match junior,
  graduate, or entry postings. Do not demand large endorsement counts.
- About / summary (weight 0.20): Honest positioning toward a full-time first
  role. A short, specific About is acceptable. Never invent tenure.
- Education (weight 0.10): Degree, dates, coursework, and activities.

FORBIDDEN:
- Do not invent years of experience, titles, or employers that are not in
  the source LinkedIn profile.
- Do not write tenure phrases such as "with over N years of experience".
- Do not recommend internships, intern titles, or "get more internships"
  as the next step.
- Do not recommend senior quantified leadership, large endorsement drives,
  or mid-career product-manager playbooks.
- Do not score the profile down for lacking endorsements or ten years of
  experience.
- Headline and summary rewrites must stay consistent with completed
  training, projects, coursework, and stated full-time target roles only.

RECOMMEND: a headline aimed at full-time junior/entry discovery; showcase
completed internships or traineeships as training already done; skills
aligned to junior/entry roles; an honest summary without invented tenure.
"""

# Backward-compatible alias used by older tests and imports.
EARLY_CAREER_GUIDANCE = EARLY_CAREER_INTERN_GUIDANCE

EXPERIENCED_GUIDANCE = """\
CAREER STAGE: experienced

This profile shows substantial professional work history. Use
experienced-hire inbound-attraction standards.

SCORING WEIGHTS (experienced):
- Headline (weight 0.25): Keyword-rich, includes target role, 80-120
  characters.
- Summary/About (weight 0.25): Value proposition, keywords, and a call to
  action. Depth should match tenure that is actually listed.
- Experience (weight 0.25): Quantified achievements and keyword-rich
  descriptions of the real roles. Achievement-depth guidance applies here.
- Skills (weight 0.15): Relevant skills. Endorsements are optional, not a
  reason to invent social proof.
- Education (weight 0.10): Degrees and certifications.

FORBIDDEN:
- Do not invent years of experience, titles, or employers that are not in
  the source LinkedIn profile.
- Do not inflate tenure. Mention years only when listed dates support them.

RECOMMEND: recruiter-searchable headline; achievement depth on actual roles;
keyword-rich experience bullets grounded in the source profile.
"""


@dataclass
class CareerStageContext:
    """Resolved career-stage framing for LinkedIn analysis.

    Attributes:
        stage: ``early_career`` or ``experienced``.
        label: Short UI-facing label.
        professional_years: Estimated non-internship professional years.
        signals: Human-readable evidence used for the decision.
        guidance: Prompt block with stage-specific scoring rules.
        intern_seeking: True when early-career advice should target internships.
        job_search_intent: ``internship`` or ``full_time``.
    """

    stage: CareerStage
    label: str
    professional_years: float
    signals: List[str] = field(default_factory=list)
    guidance: str = ""
    intern_seeking: bool = False
    job_search_intent: JobSearchIntent = "full_time"

    def as_metadata(self) -> Dict[str, Any]:
        """Return JSON-serializable metadata for the analysis payload.

        Returns:
            Dict with stage, intern-seeking flag, label, years, and signals.
        """
        return {
            "career_stage": self.stage,
            "career_stage_label": self.label,
            "intern_seeking": self.intern_seeking,
            "job_search_intent": self.job_search_intent,
            "professional_years": self.professional_years,
            "career_stage_signals": list(self.signals),
        }


def is_internship_like(title: str, extra: str = "") -> bool:
    """Return True when a role looks like an internship or similar.

    Args:
        title: Job title.
        extra: Optional description or company text.

    Returns:
        True if internship-like language is present.
    """
    blob = f"{title} {extra}".strip()
    if not blob:
        return False
    return bool(_INTERNSHIP_RE.search(blob))


def _years_from_date_text(dates: str, now: datetime) -> float:
    """Estimate years covered by a free-text date range.

    Args:
        dates: Date string such as ``2024-2026`` or ``May 2025 - Present``.
        now: Current time used for "present".

    Returns:
        Estimated years, or 0.0 when no year can be parsed.
    """
    if not dates:
        return 0.0
    years = [int(y) for y in _YEAR_RE.findall(dates)]
    if not years:
        return 0.0
    start = years[0]
    present = bool(re.search(r"\b(present|current|now)\b", dates, re.IGNORECASE))
    end = years[-1] if len(years) >= 2 else (now.year if present else start)
    if end < start:
        return 0.0
    span = float(end - start)
    if present and end == now.year and span == 0:
        return 0.5
    if span == 0:
        return 0.5
    return min(span, 40.0)


def _latest_year(dates: str) -> Optional[int]:
    """Return the last four-digit year in a date string.

    Args:
        dates: Free-text dates.

    Returns:
        Year integer, or None.
    """
    years = _YEAR_RE.findall(dates or "")
    if not years:
        return None
    return int(years[-1])


def _entry_text(entry: Dict[str, Any], *keys: str) -> str:
    """Join selected string fields from a mapping.

    Args:
        entry: Experience or education dict.
        keys: Field names to include.

    Returns:
        Space-joined string values.
    """
    parts: List[str] = []
    for key in keys:
        value = entry.get(key)
        if value:
            parts.append(str(value))
    return " ".join(parts)


def _linkedin_professional_years(
    input_data: LinkedInProfileInput, now: datetime
) -> tuple[float, int, int]:
    """Estimate professional years from LinkedIn experience entries.

    Args:
        input_data: LinkedIn payload being analyzed.
        now: Current time.

    Returns:
        Tuple of (years, professional_role_count, intern_count).
    """
    years = 0.0
    professional = 0
    interns = 0
    for entry in input_data.experience_entries:
        title = str(entry.get("title") or "")
        extra = _entry_text(entry, "company", "description")
        if is_internship_like(title, extra):
            interns += 1
            continue
        if not title and not extra:
            continue
        professional += 1
        years += _years_from_date_text(str(entry.get("dates") or ""), now)
    return round(years, 1), professional, interns


def _profile_professional_years(profile: UserProfile) -> tuple[float, int, int]:
    """Estimate professional years from a stored Job Raider profile.

    Args:
        profile: Stored user profile.

    Returns:
        Tuple of (years, professional_role_count, intern_count).
    """
    months = 0
    professional = 0
    interns = 0
    for exp in profile.experience:
        extra = " ".join(filter(None, [exp.company, exp.description or ""]))
        if is_internship_like(exp.title, extra):
            interns += 1
            continue
        professional += 1
        months += exp.duration_months
    return round(months / 12, 1), professional, interns


def _education_end_year(
    input_data: LinkedInProfileInput,
    profile: Optional[UserProfile],
) -> Optional[int]:
    """Return the latest education end year from either source.

    Args:
        input_data: LinkedIn payload.
        profile: Stored user profile, if any.

    Returns:
        Latest end year, or None.
    """
    years: List[int] = []
    for entry in input_data.education_entries:
        parsed = _latest_year(_entry_text(entry, "dates", "end_date", "end_year"))
        if parsed:
            years.append(parsed)
    if profile:
        for edu in profile.education:
            if edu.end_date:
                years.append(edu.end_date.year)
            elif edu.start_date and not edu.end_date:
                # Ongoing study: treat as current year for recency.
                years.append(datetime.now().year)
    return max(years) if years else None


def _stored_profile_signals(profile: UserProfile, now: datetime) -> List[str]:
    """Build human-readable signals from the stored profile.

    Args:
        profile: Stored user profile.
        now: Current time.

    Returns:
        List of short signal strings.
    """
    signals: List[str] = []
    years, professional, interns = _profile_professional_years(profile)
    signals.append(
        f"stored profile: {years} professional years, "
        f"{professional} full-time roles, {interns} internships, "
        f"{len(profile.projects)} projects"
    )
    end_years = [e.end_date.year for e in profile.education if e.end_date]
    if end_years:
        latest = max(end_years)
        signals.append(f"stored education end year {latest}")
        if latest >= now.year - _RECENT_GRAD_YEARS:
            signals.append("recent or upcoming graduation on stored profile")
    levels = {level for level in profile.targets.experience_levels}
    if ExperienceLevel.INTERNSHIP in levels:
        signals.append("target experience levels include internship")
    elif ExperienceLevel.ENTRY in levels:
        signals.append("target experience levels include entry")
    if getattr(profile.targets, "exclude_internships", False):
        signals.append("exclude_internships is set")
    if profile.apprenticeship and profile.apprenticeship.is_active:
        signals.append("active traineeship/apprenticeship obligation")
    visa = getattr(profile.visa_status, "value", None) or str(profile.visa_status or "")
    if "student" in visa.lower():
        signals.append("student visa on stored profile")
    return signals


def _linkedin_intent_blob(input_data: Optional[LinkedInProfileInput]) -> str:
    """Join LinkedIn text used to detect intern vs full-time intent.

    Args:
        input_data: LinkedIn payload, if any.

    Returns:
        Combined lowercase-ready text blob.
    """
    if input_data is None:
        return ""
    parts = [
        input_data.raw_text or "",
        input_data.headline or "",
        input_data.summary or "",
        input_data.career_goals or "",
        " ".join(input_data.target_roles),
    ]
    return " ".join(parts)


def infer_intern_seeking(
    user_profile: Optional[UserProfile] = None,
    input_data: Optional[LinkedInProfileInput] = None,
    intern_roles: int = 0,
) -> tuple[bool, List[str]]:
    """Infer whether an early-career candidate is still intern-seeking.

    Explicit internship targets win. Otherwise full-time/entry targets, an
    active traineeship obligation, or a completed internship/traineeship
    without an intern target select full-time first-role intent.

    Args:
        user_profile: Stored Job Raider profile, if any.
        input_data: LinkedIn payload, if any.
        intern_roles: Count of internship/traineeship-like roles already seen.

    Returns:
        Tuple of (intern_seeking, evidence strings).
    """
    signals: List[str] = []
    levels = set()
    exclude_flag = False
    apprenticeship_active = False
    student_visa = False
    if user_profile is not None:
        levels = set(user_profile.targets.experience_levels or [])
        exclude_flag = bool(getattr(user_profile.targets, "exclude_internships", False))
        if user_profile.apprenticeship and user_profile.apprenticeship.is_active:
            apprenticeship_active = True
        visa = getattr(user_profile.visa_status, "value", None) or str(
            user_profile.visa_status or ""
        )
        student_visa = "student" in visa.lower()

    intern_target = ExperienceLevel.INTERNSHIP in levels
    has_full_time_level = bool(levels & _PROFESSIONAL_TARGET_LEVELS)

    blob = _linkedin_intent_blob(input_data)
    target_roles = list(input_data.target_roles) if input_data else []
    intern_in_roles = any("intern" in role.lower() for role in target_roles)
    intern_language = bool(_INTERN_SEEKING_RE.search(blob) or intern_in_roles)
    full_time_language = bool(_FULL_TIME_SEEKING_RE.search(blob))

    if intern_target:
        signals.append("target experience levels include internship")
        return True, signals
    if exclude_flag:
        signals.append("exclude_internships prefers full-time roles")
        return False, signals
    if apprenticeship_active:
        signals.append("active traineeship/apprenticeship obligation")
        return False, signals
    if has_full_time_level:
        signals.append("target experience levels are full-time/entry, not intern")
        return False, signals
    if intern_roles > 0 and not intern_language:
        signals.append("completed internship/traineeship without intern-seeking target")
        return False, signals
    if intern_language and not full_time_language:
        signals.append("intern-seeking language in profile or LinkedIn text")
        return True, signals
    if intern_language and full_time_language:
        signals.append("mixed intern and full-time language; intern target present")
        return True, signals
    if student_visa:
        signals.append("student visa without full-time target")
        return True, signals
    signals.append("default intern-seeking for early-career without full-time target")
    return True, signals


def should_exclude_intern_listings(profile: UserProfile) -> bool:
    """Return True when intern-only listings should be dropped for this profile.

    Uses the explicit ``exclude_internships`` flag, or infers full-time
    first-role intent for early-career candidates. Experienced profiles are
    unchanged unless the flag is set. Intern-seeking graduates keep intern
    listings.

    Args:
        profile: Stored user profile.

    Returns:
        True when internship listings should be filtered out.
    """
    if bool(getattr(profile.targets, "exclude_internships", False)):
        return True
    years, _, intern_count = _profile_professional_years(profile)
    intern_seeking, _ = infer_intern_seeking(
        user_profile=profile, intern_roles=intern_count
    )
    if intern_seeking:
        return False
    if years >= _EXPERIENCED_YEARS:
        return False
    return True


def format_stored_profile_context(profile: Optional[UserProfile]) -> str:
    """Format stored profile facts for the analysis prompt.

    This block is career-stage context only. The model must not copy
    employers, titles, or years onto LinkedIn rewrite suggestions unless
    those facts already appear on the LinkedIn payload.

    Args:
        profile: Stored user profile, or None.

    Returns:
        Prompt section, or an empty string when no profile is stored.
    """
    if profile is None:
        return ""

    lines = [
        "JOB RAIDER STORED PROFILE (career-stage context only; do not add "
        "employers, titles, or years that are not on the LinkedIn profile):",
    ]
    if profile.education:
        lines.append("Education:")
        for edu in profile.education[:5]:
            start = edu.start_date.year if edu.start_date else "?"
            end = edu.end_date.year if edu.end_date else "present"
            lines.append(f"- {edu.degree} from {edu.school} ({start}-{end})")
            if edu.coursework:
                lines.append(f"  Coursework: {', '.join(edu.coursework[:8])}")
    if profile.experience:
        lines.append("Experience:")
        for exp in profile.experience[:8]:
            kind = "internship" if is_internship_like(exp.title) else "role"
            end = (
                "present"
                if exp.current or exp.end_date is None
                else (exp.end_date.year if exp.end_date else "?")
            )
            start = exp.start_date.year if exp.start_date else "?"
            lines.append(f"- [{kind}] {exp.title} at {exp.company} ({start}-{end})")
    else:
        lines.append("Experience: none listed (education/projects may be primary).")
    if profile.projects:
        names = ", ".join(p.name for p in profile.projects[:8])
        lines.append(f"Projects: {names}")
    years, _, intern_count = _profile_professional_years(profile)
    lines.append(f"Non-internship professional years: {years}")
    if profile.targets.keywords:
        lines.append(f"Target keywords: {', '.join(profile.targets.keywords[:8])}")
    intern_seeking, _ = infer_intern_seeking(
        user_profile=profile, intern_roles=intern_count
    )
    if intern_seeking:
        lines.append("Job-search intent: internships / intern-level roles")
    else:
        lines.append(
            "Job-search intent: full-time junior/entry (do not recommend internships)"
        )
    return "\n".join(lines)


def infer_career_stage(
    input_data: LinkedInProfileInput,
    user_profile: Optional[UserProfile] = None,
    now: Optional[datetime] = None,
) -> CareerStageContext:
    """Infer early-career vs experienced framing.

    Uses stored Job Raider profile data when present, plus LinkedIn
    payload signals (education end years, internships, empty or short
    experience, graduate language). Substantial non-internship work
    history selects experienced framing. Early-career profiles are split
    into intern-seeking vs full-time first-role using target levels,
    exclude_internships, traineeship obligations, and completed training.
    Ambiguous or education-only profiles default to intern-seeking
    early-career so the model does not invent tenure.

    Args:
        input_data: LinkedIn profile being analyzed.
        user_profile: Optional stored Job Raider profile.
        now: Clock override for tests.

    Returns:
        CareerStageContext with stage, signals, and prompt guidance.
    """
    clock = now or datetime.now()
    signals: List[str] = []

    li_years, li_professional, li_interns = _linkedin_professional_years(
        input_data, clock
    )
    signals.append(
        f"LinkedIn payload: {li_years} estimated professional years, "
        f"{li_professional} non-intern roles, {li_interns} internships"
    )

    stored_years = 0.0
    stored_professional = 0
    stored_interns = 0
    if user_profile is not None:
        stored_years, stored_professional, stored_interns = _profile_professional_years(
            user_profile
        )
        signals.extend(_stored_profile_signals(user_profile, clock))

    professional_years = max(li_years, stored_years)
    professional_roles = max(li_professional, stored_professional)
    intern_roles = li_interns + stored_interns

    edu_end = _education_end_year(input_data, user_profile)
    recent_grad = False
    if edu_end is not None:
        signals.append(f"latest education end year {edu_end}")
        if edu_end >= clock.year - _RECENT_GRAD_YEARS:
            recent_grad = True
            signals.append("recent or upcoming graduation")

    blob_parts = [
        input_data.raw_text or "",
        input_data.headline or "",
        input_data.summary or "",
        input_data.career_goals or "",
        " ".join(input_data.target_roles),
    ]
    blob = " ".join(blob_parts)
    if _GRADUATE_RE.search(blob):
        signals.append("graduate/first-role language in LinkedIn text")
        recent_grad = True

    project_count = len(user_profile.projects) if user_profile else 0
    if project_count:
        signals.append(f"{project_count} stored projects")

    senior_titles = 0
    for entry in input_data.experience_entries:
        title = str(entry.get("title") or "")
        if title and not is_internship_like(title) and _SENIOR_TITLE_RE.search(title):
            senior_titles += 1
    if user_profile:
        for exp in user_profile.experience:
            if not is_internship_like(exp.title) and _SENIOR_TITLE_RE.search(exp.title):
                senior_titles += 1

    experienced = False
    if professional_years >= _EXPERIENCED_YEARS:
        experienced = True
        signals.append(
            f"professional years {professional_years} meet experienced threshold"
        )
    elif (
        professional_roles >= 3
        and intern_roles == 0
        and not recent_grad
        and senior_titles >= 1
    ):
        experienced = True
        signals.append("multiple non-intern roles with senior titles")

    if experienced:
        stage: CareerStage = "experienced"
        label = "experienced hire"
        guidance = EXPERIENCED_GUIDANCE
        intern_seeking = False
        intent: JobSearchIntent = "full_time"
    else:
        intern_seeking, intent_signals = infer_intern_seeking(
            user_profile=user_profile,
            input_data=input_data,
            intern_roles=intern_roles,
        )
        signals.extend(intent_signals)
        stage = "early_career"
        if intern_seeking:
            label = "early career, intern-seeking"
            guidance = EARLY_CAREER_INTERN_GUIDANCE
            intent = "internship"
        else:
            label = "early career, full-time first role"
            guidance = EARLY_CAREER_FULL_TIME_GUIDANCE
            intent = "full_time"
        signals.append(
            "defaulted to early-career framing (no substantial work history)"
        )

    return CareerStageContext(
        stage=stage,
        label=label,
        professional_years=professional_years,
        signals=signals,
        guidance=guidance.strip(),
        intern_seeking=intern_seeking,
        job_search_intent=intent,
    )
