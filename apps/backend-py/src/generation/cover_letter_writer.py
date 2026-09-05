"""
Job Raider - Cover Letter Writer

This module implements the large-model cover letter writing stage.
Generates tailored cover letters (200-300 words) that connect the
candidate's relevant experience to the target job requirements.

Reuses the SelectionOutput from ResumeSelector to ensure the cover
letter and resume tell a consistent story.

Author: Job Raider
Date: 2026-05-13
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional

from ..llm.base import Message, MessageType
from ..llm.router import LLMRouter, TaskType
from ..models.job_listing import JobListing
from ..models.user_profile import UserProfile
from ..utils.logger import Components, get_logger
from .cover_letter_grounding import (
    collect_resume_supported_names,
    filter_resume_supported_keywords,
    is_domain_mismatch,
    normalize_tech_name,
    redact_unsupported_technologies,
)
from .selector import SelectionOutput

CoverLetterStyle = Literal["modern", "classic"]

# Shared drafting rules for write + rewrite so grounding constraints stay aligned.
_COVER_LETTER_RULES = (
    "RULES:\n"
    "1. The letter MUST be between 200 and 300 words\n"
    "2. Connect 2-3 specific experiences from the candidate's "
    "background only to job requirements that also appear on the "
    "resume. If a requirement is absent from the resume, omit it. "
    "Do not invent a narrative that the candidate already performs "
    "those duties\n"
    "3. Mention the company and role by name\n"
    "4. Do NOT use generic phrases or templates\n"
    "5. Be direct and confident in tone\n"
    "6. Do NOT include headers, addresses, or date lines\n"
    "7. Open with a specific hook: lead with the candidate's "
    "most relevant concrete achievement or a specific detail "
    "about the company's product, mission, or tech stack. "
    "NEVER open with cliches like 'I am writing to express "
    "my interest' or 'I am excited to apply'\n"
    "8. Include at least one quantified result (numbers, "
    "percentages, scale) from the candidate's background "
    "when one is available\n"
    "9. Avoid stock phrases such as 'team player', 'fast "
    "learner', 'passionate about', and 'proven track record'\n"
    "10. End with a brief, confident call to action. The closing "
    "pitch MUST restate facts already used earlier in the same "
    "letter or explicitly listed in the candidate profile / "
    "selection strategy — do NOT invent new capability claims. "
    "Do not use words like deployed, production, launched, or "
    "shipped unless those exact claims appear in the profile\n"
    "11. Every sentence must be traceable to either a specific "
    "resume bullet/achievement or a specific job requirement "
    "being addressed. Prefer restating concrete profile facts "
    "over persuasive synthesis. Do not inflate scope with verbs "
    "like led, leading, spearheaded, or owned unless the profile "
    "uses that phrasing. Do not attach techniques (retrieval, "
    "RAG, fine-tuning, distributed, real-time, containerized) "
    "to a project unless that project's own bullets list them\n"
    "12. Never name a technology, tool, cloud platform, or database "
    "that is not listed in the candidate's skills / Technical Skills. "
    "Do not copy example stacks from the job description unless those "
    "exact names appear on the resume\n"
    "13. Never claim proficiency, strong knowledge, hands-on experience, "
    "or production experience for a technology absent from Technical "
    "Skills. When the job asks for skills the candidate lacks, connect "
    "with resume-supported evidence only — do not name the missing tools "
    "and do not apologize for gaps mid-letter\n"
    "14. Duration claims (N years, over N years) must not exceed the "
    "candidate's total dated work experience on the profile\n"
    "15. Quantified improvements must restate numbers that appear in the "
    "profile or selection achievements. Do not invent a relative "
    "percentage from absolute endpoints unless that relative figure is "
    "already stated on the resume\n"
    "16. Do not analogize across domains. Do not claim that resume work "
    "is similar to, comparable to, transferable to, or preparation for "
    "job duties that are not on the resume. Restate resume facts "
    "without claiming they satisfy unsupported duties\n"
    "17. Prefer 3-5 short paragraphs: (1) concrete resume hook naming "
    "the company and role, (2-3) one grounded evidence paragraph each, "
    "(final) brief CTA that restates facts already used. Do not pad "
    "with soft-sell filler\n"
    "18. Return ONLY the letter body as plain text, no JSON"
)

_COVER_LETTER_SYSTEM = (
    "You are a professional cover letter writer.\n\n" + _COVER_LETTER_RULES
)

_CLASSIC_COVER_LETTER_RULES = (
    "RULES:\n"
    "1. The letter MUST be between 200 and 350 words including "
    "salutation and signature\n"
    "2. Connect 2-3 specific experiences from the candidate's "
    "background only to job requirements that also appear on the "
    "resume. If a requirement is absent from the resume, omit it. "
    "Do not invent a narrative that the candidate already performs "
    "those duties\n"
    "3. Mention the company and role by name\n"
    "4. Use a traditional letter structure:\n"
    "   - Open with 'Dear Hiring Manager,' (or a named contact "
    "if one is provided in the profile context)\n"
    "   - Brief statement of the role and company you are applying for\n"
    "   - Current-role paragraph with a concrete result tied to the JD\n"
    "   - Prior-role or project paragraph with another grounded result\n"
    "   - Short closing asking for a conversation (e.g. opportunity "
    "to discuss how you can contribute; thank them for consideration)\n"
    "   - Close with 'Sincerely,' then the candidate's full name on "
    "the next line\n"
    "5. Do NOT include date lines, postal addresses, or recipient "
    "street addresses — export formatting adds those separately\n"
    "6. Do NOT include fluffy soft-sell paragraphs about being hard "
    "working, having a great attitude, loving teamwork, or vague "
    "passion without concrete profile evidence\n"
    "7. Include at least one quantified result (numbers, "
    "percentages, scale) from the candidate's background "
    "when one is available\n"
    "8. Avoid stock phrases such as 'team player', 'fast "
    "learner', 'passionate about', and 'proven track record'\n"
    "9. The closing pitch MUST restate facts already used earlier "
    "in the same letter or explicitly listed in the candidate "
    "profile / selection strategy — do NOT invent new capability "
    "claims. Do not use words like deployed, production, launched, "
    "or shipped unless those exact claims appear in the profile\n"
    "10. Every sentence must be traceable to either a specific "
    "resume bullet/achievement or a specific job requirement "
    "being addressed. Prefer restating concrete profile facts "
    "over persuasive synthesis. Do not inflate scope with verbs "
    "like led, leading, spearheaded, or owned unless the profile "
    "uses that phrasing. Do not attach techniques (retrieval, "
    "RAG, fine-tuning, distributed, real-time, containerized) "
    "to a project unless that project's own bullets list them\n"
    "11. Never name a technology, tool, cloud platform, or database "
    "that is not listed in the candidate's skills / Technical Skills. "
    "Do not copy example stacks from the job description unless those "
    "exact names appear on the resume\n"
    "12. Never claim proficiency, strong knowledge, hands-on experience, "
    "or production experience for a technology absent from Technical "
    "Skills. When the job asks for skills the candidate lacks, connect "
    "with resume-supported evidence only — do not name the missing tools "
    "and do not apologize for gaps mid-letter\n"
    "13. Duration claims (N years, over N years) must not exceed the "
    "candidate's total dated work experience on the profile\n"
    "14. Quantified improvements must restate numbers that appear in the "
    "profile or selection achievements. Do not invent a relative "
    "percentage from absolute endpoints unless that relative figure is "
    "already stated on the resume\n"
    "15. Do not analogize across domains. Do not claim that resume work "
    "is similar to, comparable to, transferable to, or preparation for "
    "job duties that are not on the resume. Restate resume facts "
    "without claiming they satisfy unsupported duties\n"
    "16. Keep the traditional structure tight: salutation, role line, "
    "two grounded evidence paragraphs, short closing, Sincerely + name. "
    "Do not pad with soft-sell filler\n"
    "17. Return ONLY the letter body as plain text, no JSON"
)

_CLASSIC_COVER_LETTER_SYSTEM = (
    "You are a professional cover letter writer who drafts "
    "traditional formal letters.\n\n" + _CLASSIC_COVER_LETTER_RULES
)

# Markers shared by modern and classic prompts (asserted in unit tests).
_SHARED_GROUNDING_MARKERS = (
    "do NOT invent new capability claims",
    "Every sentence must be traceable",
    "Never name a technology, tool, cloud platform, or database",
    "Never claim proficiency, strong knowledge, hands-on experience",
    "Duration claims (N years, over N years)",
    "Do not invent a relative percentage",
    "Do not analogize across domains",
    "only to job requirements that also appear on the",
    "Do not pad with soft-sell filler",
)

_DOMAIN_MISMATCH_RULES = (
    "DOMAIN MISMATCH:\n"
    "The job's duties have little overlap with the resume.\n"
    "- Mention the company and role by name\n"
    "- Restate 2-3 concrete resume facts\n"
    "- Do not claim the candidate already performs this job's duties\n"
    "- Do not analogize resume work to unsupported duties "
    "(similar to, prepared me for, transferable to, is like)\n"
    "- Omit job requirements that are not on the resume"
)


_MISSION_PRESENT_RULES = (
    "COMPANY MISSION CONTEXT:\n"
    "- A verified COMPANY MISSION brief is included under TARGET JOB. "
    "You may use it for one specific opening or body detail about the "
    "employer.\n"
    "- Paraphrase the brief; do not quote marketing slogans verbatim.\n"
    "- Do not invent additional mission, product, or initiative claims "
    "beyond that brief and the job description."
)

_MISSION_ABSENT_RULES = (
    "COMPANY MISSION CONTEXT:\n"
    "- No verified company-mission brief is available.\n"
    "- Do NOT invent the company's mission, vision, products, or "
    "initiatives. Open with a resume achievement or a JD-stated fact only."
)


def _system_prompt_for_style(
    style: CoverLetterStyle,
    domain_mismatch: bool = False,
    has_mission_brief: bool = False,
) -> str:
    """
    Return the system prompt for the requested cover-letter style.

    Args:
        style: ``modern`` or ``classic``.
        domain_mismatch: When True, append instructions that forbid
            analogical mapping onto unsupported JD duties.
        has_mission_brief: When True, allow using the verified mission
            brief; when False, forbid inventing company mission claims.

    Returns:
        Full system prompt string.
    """
    if style == "classic":
        prompt = _CLASSIC_COVER_LETTER_SYSTEM
    else:
        prompt = _COVER_LETTER_SYSTEM
    if domain_mismatch:
        prompt = prompt + "\n\n" + _DOMAIN_MISMATCH_RULES
    if has_mission_brief:
        prompt = prompt + "\n\n" + _MISSION_PRESENT_RULES
    else:
        prompt = prompt + "\n\n" + _MISSION_ABSENT_RULES
    return prompt


@dataclass
class GeneratedCoverLetter:
    """Generated cover letter with metadata."""

    content: str
    highlighted_experiences: List[Dict[str, str]]
    word_count: int
    model_used: str
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    tokens_used: Optional[int] = None


def _tokens_from_llm_response(
    response: Any,
) -> tuple[Optional[int], Optional[int], Optional[int]]:
    """
    Extract prompt, completion, and total token counts from an LLM response.

    Args:
        response: ``LLMResponse`` or similar object with token fields.

    Returns:
        Tuple of ``(prompt_tokens, completion_tokens, tokens_used)``.
    """
    prompt_tokens = getattr(response, "prompt_tokens", None)
    completion_tokens = getattr(response, "completion_tokens", None)
    tokens_used = getattr(response, "tokens_used", None)
    if tokens_used is None and prompt_tokens is not None and completion_tokens is not None:
        tokens_used = int(prompt_tokens) + int(completion_tokens)
    return prompt_tokens, completion_tokens, tokens_used


class CoverLetterWriter:
    """
    Generate tailored cover letters using a large model.

    Takes the same SelectionOutput used for resume generation and produces
    a concise cover letter (200-300 words) that connects 2-3 relevant
    experiences to the job requirements.
    """

    def __init__(self, llm_router: LLMRouter):
        """
        Initialize the cover letter writer.

        Args:
            llm_router: LLM router for model selection
        """
        self.llm_router = llm_router
        self.logger = get_logger(Components.GENERATION)

    def write(
        self,
        job: JobListing,
        profile: UserProfile,
        selection: SelectionOutput,
        style: CoverLetterStyle = "modern",
        model: Optional[str] = None,
        mission_brief: Optional[str] = None,
        inclusion_urls: Optional[Dict[str, Optional[str]]] = None,
    ) -> GeneratedCoverLetter:
        """
        Generate a tailored cover letter for a job application.

        Args:
            job: Target job listing
            profile: User profile
            selection: Selection output from selector stage
            style: ``modern`` (achievement-led) or ``classic`` (formal structure)
            model: Optional one-shot writer model override (Settings provider)
            mission_brief: Optional verified company-mission brief
            inclusion_urls: Optional kind→URL map for JD inclusion asks

        Returns:
            GeneratedCoverLetter with the letter content and metadata
        """
        brief = (mission_brief or "").strip() or None
        job_context = self._prepare_job_context(
            job,
            profile,
            mission_brief=brief,
            inclusion_urls=inclusion_urls,
        )
        profile_context = self._prepare_profile_context(profile)
        mismatch = is_domain_mismatch(job, profile)
        selection_context = self._prepare_selection_context(
            selection, profile, domain_mismatch=mismatch
        )
        system_prompt = _system_prompt_for_style(
            style,
            domain_mismatch=mismatch,
            has_mission_brief=bool(brief),
        )
        if style == "classic":
            user_lead = (
                "Write a classic formal cover letter for the following "
                "job application (salutation, grounded body, sincerely + name):\n\n"
            )
        else:
            user_lead = "Write a cover letter for the following job application:\n\n"

        messages = [
            Message(
                role=MessageType.SYSTEM,
                content=system_prompt,
            ),
            Message(
                role=MessageType.USER,
                content=(
                    f"{user_lead}"
                    f"TARGET JOB:\n{job_context}\n\n"
                    f"SELECTION STRATEGY:\n{selection_context}\n\n"
                    f"CANDIDATE PROFILE:\n{profile_context}"
                ),
            ),
        ]

        try:
            response = self.llm_router.generate(
                messages=messages,
                task_type=TaskType.COVER_LETTER_WRITING,
                model=model,
                # Slightly higher than default creative temp: more varied
                # phrasing between letters without sacrificing coherence.
                temperature=0.8,
                max_tokens=1200,
                # Opt-in for this call only: thinking models (e.g. gemma4:e4b)
                # otherwise spend the token budget on reasoning and return a
                # blank letter body. Does not change the shared Ollama client
                # default for other tasks.
                think=False,
            )

            content = response.content.strip()
            if not content:
                raise ValueError("Cover letter model returned empty content")
            word_count = len(content.split())
            model_used = (
                response.model
                or self.llm_router.routes[TaskType.COVER_LETTER_WRITING].primary_model
            )

            highlighted = self._extract_highlighted_experiences(content, selection)
            prompt_tokens, completion_tokens, tokens_used = _tokens_from_llm_response(
                response
            )

            self.logger.info(
                "Cover letter generated: %d words, model=%s style=%s tokens=%s",
                word_count,
                model_used,
                style,
                tokens_used,
            )

            return GeneratedCoverLetter(
                content=content,
                highlighted_experiences=highlighted,
                word_count=word_count,
                model_used=model_used,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                tokens_used=tokens_used,
            )

        except Exception as e:
            self.logger.error("Cover letter writing failed: %s", str(e))
            return self._fallback_cover_letter(job, profile, selection)

    def write_why_interest_block(
        self,
        job: JobListing,
        profile: UserProfile,
        selection: SelectionOutput,
        why_interest: Any,
        *,
        mission_brief: Optional[str] = None,
        inclusion_urls: Optional[Dict[str, Optional[str]]] = None,
        model: Optional[str] = None,
    ) -> GeneratedCoverLetter:
        """
        Generate a short why-interest answer that replaces a full cover letter.

        Used when the JD asks for a length-constrained "why this interests you"
        block (Phase C). Does not use modern/classic letter structure rules.

        Args:
            job: Target job listing.
            profile: Candidate profile.
            selection: Selection output (for grounding context).
            why_interest: ``WhyInterestSpec`` with min/max/unit.
            mission_brief: Optional verified company-mission brief.
            inclusion_urls: Optional kind→URL map for required inclusions.
            model: Optional writer model override.

        Returns:
            ``GeneratedCoverLetter`` containing only the short answer block.
        """
        min_n = int(getattr(why_interest, "min_n", 3))
        raw_max = getattr(why_interest, "max_n", 4)
        max_n: Optional[int] = None if raw_max is None else int(raw_max)
        unit = str(getattr(why_interest, "unit", "lines"))
        brief = (mission_brief or "").strip() or None
        job_context = self._prepare_job_context(
            job,
            profile,
            mission_brief=brief,
            inclusion_urls=inclusion_urls,
        )
        profile_context = self._prepare_profile_context(profile)
        selection_context = self._prepare_selection_context(
            selection, profile, domain_mismatch=is_domain_mismatch(job, profile)
        )

        if max_n is None:
            length_rule = (
                f"Write at least {min_n} {unit} (this is a minimum floor, "
                f"not an exact length — slightly over is fine). "
                f"Do not write a full cover letter. Do not add salutation, "
                f"signature, or call-to-action beyond the requested block."
            )
        else:
            length_rule = (
                f"Write between {min_n} and {max_n} {unit} (inclusive). "
                f"Do not write a full cover letter. Do not add salutation, "
                f"signature, or call-to-action beyond the requested block."
            )
        if unit == "lines":
            length_rule += (
                " Prefer one sentence per line, or clear sentence breaks "
                "so the answer is countable as lines."
            )

        system_prompt = (
            "You are writing a short application answer required by a job "
            "posting — not a full cover letter.\n\n"
            f"LENGTH RULE: {length_rule}\n"
            "GROUNDING RULES:\n"
            "- If COMPANY MISSION (verified) is present, use it as factual "
            "grounding for why the company interests the candidate.\n"
            "- If no verified mission is present, ground only in the job "
            "title, company name, and JD responsibilities already listed.\n"
            "- Do not invent enthusiasm, products, or initiatives that are "
            "not in the provided context.\n"
            "- Do not invent technologies absent from the candidate profile.\n"
            "- If required inclusion URLs are listed, include each exact URL.\n"
            "- Return ONLY the short answer as plain text."
        )

        messages = [
            Message(role=MessageType.SYSTEM, content=system_prompt),
            Message(
                role=MessageType.USER,
                content=(
                    f"Write the short answer for why this role/company "
                    f"interests the candidate.\n\n"
                    f"TARGET JOB:\n{job_context}\n\n"
                    f"SELECTION STRATEGY:\n{selection_context}\n\n"
                    f"CANDIDATE PROFILE:\n{profile_context}"
                ),
            ),
        ]

        try:
            response = self.llm_router.generate(
                messages=messages,
                task_type=TaskType.COVER_LETTER_WRITING,
                model=model,
                temperature=0.5,
                max_tokens=400,
                think=False,
            )
            content = response.content.strip()
            if not content:
                raise ValueError("Why-interest model returned empty content")
            word_count = len(content.split())
            model_used = (
                response.model
                or self.llm_router.routes[TaskType.COVER_LETTER_WRITING].primary_model
            )
            prompt_tokens, completion_tokens, tokens_used = _tokens_from_llm_response(
                response
            )
            self.logger.info(
                "Why-interest block generated: %d words, model=%s unit=%s "
                "range=%s-%s tokens=%s",
                word_count,
                model_used,
                unit,
                min_n,
                max_n if max_n is not None else "open",
                tokens_used,
            )
            return GeneratedCoverLetter(
                content=content,
                highlighted_experiences=[],
                word_count=word_count,
                model_used=model_used,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                tokens_used=tokens_used,
            )
        except Exception as e:
            self.logger.error("Why-interest writing failed: %s", str(e))
            return self._fallback_why_interest(
                job, why_interest, mission_brief=brief, inclusion_urls=inclusion_urls
            )

    def _fallback_why_interest(
        self,
        job: JobListing,
        why_interest: Any,
        *,
        mission_brief: Optional[str] = None,
        inclusion_urls: Optional[Dict[str, Optional[str]]] = None,
    ) -> GeneratedCoverLetter:
        """
        Build a minimal grounded why-interest fallback without an LLM.

        Args:
            job: Target job listing.
            why_interest: Length spec (used for rough line count).
            mission_brief: Optional verified mission brief.
            inclusion_urls: Optional required URLs.

        Returns:
            Short ``GeneratedCoverLetter``.
        """
        min_n = int(getattr(why_interest, "min_n", 3))
        raw_max = getattr(why_interest, "max_n", 4)
        max_n: Optional[int] = None if raw_max is None else int(raw_max)
        lines: List[str] = []
        if mission_brief:
            lines.append(
                f"I am drawn to {job.company} because of its focus on "
                f"{mission_brief[:180].rstrip('.')} — relevant to the "
                f"{job.title} role."
            )
        else:
            lines.append(
                f"The {job.title} role at {job.company} matches responsibilities "
                f"described in the posting."
            )
        lines.append(
            "I am interested in contributing to the work outlined in the job "
            "description using experience already on my resume."
        )
        if len(lines) < min_n:
            lines.append(
                f"I am applying because the {job.company} opportunity is a "
                f"clear fit for the skills listed in my profile."
            )
        # Cap only when the JD gave an explicit upper bound.
        body = "\n".join(lines) if max_n is None else "\n".join(lines[:max_n])
        if inclusion_urls:
            for url in inclusion_urls.values():
                if url and url not in body:
                    body = f"{body}\n{url}"
        return GeneratedCoverLetter(
            content=body,
            highlighted_experiences=[],
            word_count=len(body.split()),
            model_used="fallback",
        )

    def rewrite(
        self,
        job: JobListing,
        profile: UserProfile,
        selection: SelectionOutput,
        draft: GeneratedCoverLetter,
        critique: str,
        style: CoverLetterStyle = "modern",
        model: Optional[str] = None,
        mission_brief: Optional[str] = None,
        inclusion_urls: Optional[Dict[str, Optional[str]]] = None,
    ) -> GeneratedCoverLetter:
        """
        Rewrite a cover letter draft using a reviewer critique.

        Args:
            job: Target job listing.
            profile: Candidate profile.
            selection: Selection output from selector stage.
            draft: The original generated cover letter.
            critique: Actionable feedback from the reviewer.
            style: ``modern`` or ``classic`` (must match the original draft style).
            model: Optional one-shot writer model override (Settings provider).
            mission_brief: Optional verified company-mission brief.
            inclusion_urls: Optional kind→URL map for JD inclusion asks.

        Returns:
            ``GeneratedCoverLetter`` with the rewritten content and metadata.
        """
        brief = (mission_brief or "").strip() or None
        job_context = self._prepare_job_context(
            job,
            profile,
            mission_brief=brief,
            inclusion_urls=inclusion_urls,
        )
        profile_context = self._prepare_profile_context(profile)
        mismatch = is_domain_mismatch(job, profile)
        selection_context = self._prepare_selection_context(
            selection, profile, domain_mismatch=mismatch
        )
        system_prompt = _system_prompt_for_style(
            style,
            domain_mismatch=mismatch,
            has_mission_brief=bool(brief),
        )
        style_note = (
            "Preserve classic formal structure (salutation, sincerely + name). "
            if style == "classic"
            else "Preserve modern achievement-led body style. "
        )

        messages = [
            Message(
                role=MessageType.SYSTEM,
                content=system_prompt,
            ),
            Message(
                role=MessageType.USER,
                content=(
                    f"Rewrite the following cover letter for the job application. "
                    f"{style_note}"
                    "Apply the EDITOR CRITIQUE by deleting unsupported claims "
                    "and restating resume-grounded facts only. Do not invent "
                    "new JD relevance, technologies, metrics, or soft-sell "
                    "filler to 'fix' gaps.\n\n"
                    f"TARGET JOB:\n{job_context}\n\n"
                    f"SELECTION STRATEGY:\n{selection_context}\n\n"
                    f"CANDIDATE PROFILE:\n{profile_context}\n\n"
                    f"ORIGINAL DRAFT:\n{draft.content}\n\n"
                    f"EDITOR CRITIQUE:\n{critique}"
                ),
            ),
        ]

        try:
            response = self.llm_router.generate(
                messages=messages,
                task_type=TaskType.COVER_LETTER_WRITING,
                model=model,
                # Slightly higher than default creative temp: more varied
                # phrasing between letters without sacrificing coherence.
                temperature=0.8,
                max_tokens=1200,
                # Opt-in for this call only: thinking models (e.g. gemma4:e4b)
                # otherwise spend the token budget on reasoning and return a
                # blank letter body. Does not change the shared Ollama client
                # default for other tasks.
                think=False,
            )

            content = response.content.strip()
            if not content:
                raise ValueError("Cover letter rewrite returned empty content")
            word_count = len(content.split())
            model_used = (
                response.model
                or self.llm_router.routes[TaskType.COVER_LETTER_WRITING].primary_model
            )

            highlighted = self._extract_highlighted_experiences(content, selection)
            prompt_tokens, completion_tokens, tokens_used = _tokens_from_llm_response(
                response
            )

            self.logger.info(
                "Cover letter rewritten: %d words, model=%s style=%s tokens=%s",
                word_count,
                model_used,
                style,
                tokens_used,
            )

            return GeneratedCoverLetter(
                content=content,
                highlighted_experiences=highlighted,
                word_count=word_count,
                model_used=model_used,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                tokens_used=tokens_used,
            )

        except Exception as e:
            self.logger.error("Cover letter rewrite failed: %s", str(e))
            return self._fallback_cover_letter(job, profile, selection)

    def _prepare_job_context(
        self,
        job: JobListing,
        profile: UserProfile,
        mission_brief: Optional[str] = None,
        inclusion_urls: Optional[Dict[str, Optional[str]]] = None,
    ) -> str:
        """
        Prepare job context for the prompt.

        JD-only technologies are omitted so the model cannot echo stacks
        that are absent from the resume.

        Args:
            job: Target job listing
            profile: Candidate profile used as the technology allowlist
            mission_brief: Optional verified company-mission brief
            inclusion_urls: Optional kind→URL map for JD inclusion asks

        Returns:
            Formatted job context string
        """
        allowed = collect_resume_supported_names(profile)
        parts = [
            f"Title: {job.title}",
            f"Company: {job.company}",
            f"Location: {job.location or 'Not specified'}",
            "Only mention technologies listed under CANDIDATE PROFILE.",
        ]

        if job.description:
            sanitized = redact_unsupported_technologies(job.description[:2000], profile)
            if sanitized:
                parts.append(f"\nDescription:\n{sanitized}")

        if job.requirements:
            parts.append("\nKey Requirements:")
            for req in job.requirements[:8]:
                sanitized_req = redact_unsupported_technologies(req.text, profile)
                if sanitized_req:
                    parts.append(f"- {sanitized_req}")

        overlap_skills = [
            skill.name
            for skill in (job.skills or [])[:10]
            if skill.name and normalize_tech_name(skill.name) in allowed
        ]
        if overlap_skills:
            parts.append("\nRequired skills that also appear on the resume:")
            for name in overlap_skills:
                parts.append(f"- {name}")

        brief = (mission_brief or "").strip()
        if brief:
            parts.append(
                "\nCOMPANY MISSION (verified; paraphrase only, do not invent "
                f"beyond this):\n{brief}"
            )

        if inclusion_urls:
            required = [
                f"- {kind}: {url}" for kind, url in inclusion_urls.items() if url
            ]
            missing = [
                f"- {kind}: (not on profile — do not invent)"
                for kind, url in inclusion_urls.items()
                if not url
            ]
            if required:
                parts.append(
                    "\nREQUIRED INCLUSIONS (include each exact URL in the output):"
                )
                parts.extend(required)
            if missing:
                parts.append("\nINCLUSIONS REQUESTED BUT UNAVAILABLE ON PROFILE:")
                parts.extend(missing)

        if is_domain_mismatch(job, profile):
            parts.append(
                "\nDOMAIN OVERLAP: low. Do not claim the candidate already "
                "performs this job's duties. Restate resume facts. Do not "
                "analogize (similar to, prepared me for, transferable to, "
                "is like). Omit unsupported requirements."
            )

        return "\n".join(parts)

    def _prepare_profile_context(self, profile: UserProfile) -> str:
        """
        Prepare profile context for the prompt.

        Args:
            profile: User profile

        Returns:
            Formatted profile context string
        """
        parts = []
        parts.append(f"Name: {profile.name}")
        parts.append(f"Email: {profile.contact.email}")
        parts.append(f"Location: {profile.contact.location}")

        if profile.summary:
            parts.append(f"\nProfessional Summary:\n{profile.summary}")

        if profile.skills:
            parts.append(f"\nSkills: {', '.join(s.name for s in profile.skills)}")

        if profile.experience:
            parts.append("\nWork Experience:")
            for exp in profile.experience:
                dates = (
                    f"{exp.start_date.strftime('%b %Y')} - "
                    f"{exp.end_date.strftime('%b %Y') if exp.end_date else 'Present'}"
                )
                parts.append(f"\n{exp.title} at {exp.company}")
                parts.append(f"  {dates}")
                for highlight in exp.highlights[:5]:
                    parts.append(f"  - {highlight}")

        if profile.projects:
            parts.append("\nProjects:")
            for project in profile.projects:
                parts.append(f"\n{project.name}")
                if project.description:
                    parts.append(f"  {project.description}")
                if project.technologies:
                    parts.append(f"  Technologies: {', '.join(project.technologies)}")
                for highlight in project.highlights[:3]:
                    parts.append(f"  - {highlight}")

        if profile.education:
            parts.append("\nEducation:")
            for edu in profile.education:
                year = edu.end_date.year if edu.end_date else ""
                parts.append(
                    f"- {edu.degree} from {edu.school} "
                    f"{'(' + str(year) + ')' if year else ''}"
                )

        return "\n".join(parts)

    def _prepare_selection_context(
        self,
        selection: SelectionOutput,
        profile: UserProfile,
        domain_mismatch: bool = False,
    ) -> str:
        """
        Prepare selection context for the prompt.

        Keywords are filtered to resume-supported terms so JD-only stacks
        are never presented as ``KEYWORDS TO WEAVE IN``. On domain mismatch,
        project alignment reasons are omitted so the selector cannot teach
        invented fit.

        Args:
            selection: Selection output from selector stage
            profile: Candidate profile used as the keyword allowlist source
            domain_mismatch: When True, list project names without reasons

        Returns:
            Formatted selection context string
        """
        parts = []

        if selection.selected_projects:
            parts.append("SELECTED PROJECTS (emphasize these):")
            for proj in selection.selected_projects:
                if domain_mismatch:
                    parts.append(f"- {proj['name']}")
                else:
                    parts.append(f"- {proj['name']}: {proj['reason']}")

        allowed_keywords = filter_resume_supported_keywords(
            selection.keywords_to_emphasize or [],
            profile,
        )
        if allowed_keywords:
            parts.append("\nKEYWORDS TO WEAVE IN:")
            parts.append(", ".join(allowed_keywords))

        if selection.key_achievements:
            parts.append("\nKEY ACHIEVEMENTS:")
            for achievement in selection.key_achievements:
                parts.append(f"- {achievement}")

        return "\n".join(parts)

    def _extract_highlighted_experiences(
        self,
        content: str,
        selection: SelectionOutput,
    ) -> List[Dict[str, str]]:
        """
        Identify which selected projects appear in the cover letter.

        Args:
            content: Generated cover letter text
            selection: Selection output to check against

        Returns:
            List of dicts with project name and reason
        """
        highlighted = []
        content_lower = content.lower()

        for proj in selection.selected_projects:
            if proj["name"].lower() in content_lower:
                highlighted.append(proj)

        return highlighted

    def _fallback_cover_letter(
        self,
        job: JobListing,
        profile: UserProfile,
        selection: SelectionOutput,
    ) -> GeneratedCoverLetter:
        """
        Template-based fallback when LLM generation fails.

        Args:
            job: Target job listing
            profile: User profile
            selection: Selection output

        Returns:
            GeneratedCoverLetter with template-based content
        """
        title = job.title
        company = job.company

        projects_text = ""
        if selection.selected_projects:
            project_parts = []
            mismatch = is_domain_mismatch(job, profile)
            for proj in selection.selected_projects[:2]:
                if mismatch:
                    project_parts.append(
                        f"My work on {proj['name']} is listed on my resume"
                    )
                else:
                    project_parts.append(
                        f"My work on {proj['name']} has given me direct experience "
                        f"that aligns with this role"
                    )
            projects_text = " ".join(project_parts)

        keywords_text = ""
        safe_keywords = filter_resume_supported_keywords(
            selection.keywords_to_emphasize or [],
            profile,
        )
        if safe_keywords:
            keywords_text = (
                f"My expertise in "
                f"{', '.join(safe_keywords[:3])} "
                f"makes me a strong fit for this position."
            )

        content = (
            f"I am writing to express my strong interest in the {title} "
            f"position at {company}. With my background and experience, "
            f"I am confident I can make a meaningful contribution to your team.\n\n"
            f"{projects_text}\n\n"
            f"{keywords_text}\n\n"
            f"I would welcome the opportunity to discuss how my skills "
            f"and experience align with {company}'s goals. "
            f"Thank you for considering my application."
        )

        return GeneratedCoverLetter(
            content=content,
            highlighted_experiences=selection.selected_projects[:2],
            word_count=len(content.split()),
            model_used="template_fallback",
        )
