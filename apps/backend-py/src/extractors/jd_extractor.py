"""
Job Raider - Job Description Extractor

This module provides functionality to extract structured information
from job description text or HTML.

Author: Job Raider
Date: 2026-04-20
"""

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup

from ..llm.base import Message, MessageType
from ..llm.router import LLMRouter, TaskType
from ..models.job_listing import (
    ExperienceLevel,
    JobListing,
    JobRequirement,
    JobResponsibility,
    JobSource,
    JobType,
    SalaryRange,
    Skill,
    WorkMode,
)


@dataclass
class ExtractionResult:
    """Result of job description extraction."""

    success: bool
    job_listing: Optional[JobListing]
    errors: List[str]
    warnings: List[str]


class JDExtractor:
    """
    Extract structured information from job descriptions.

    Uses a combination of rule-based parsing and LLM-based extraction
    to get structured data from job postings.
    """

    # Section patterns for rule-based extraction
    SECTION_PATTERNS = {
        "requirements": [
            r"requirements?",
            r"qualifications?",
            r"what you'll need",
            r"what we're looking for",
            r"must have",
        ],
        "responsibilities": [
            r"responsibilities?",
            r"what you'll do",
            r"you will",
            r"role overview",
            r"about the role",
        ],
        "skills": [
            r"skills?",
            r"technologies?",
            r"tech stack",
        ],
        "benefits": [
            r"benefits?",
            r"perks",
            r"compensation",
            r"what we offer",
        ],
    }

    # Experience level patterns
    EXPERIENCE_PATTERNS = {
        ExperienceLevel.ENTRY: [
            r"entry level",
            r"junior",
            r"0-2 years?",
            r"0-\s*2 years?",
            r"recent graduate",
        ],
        ExperienceLevel.MID: [
            r"mid level",
            r"mid-level",
            r"intermediate",
            r"2-5 years?",
            r"3-5 years?",
            r"2-\s*5 years?",
        ],
        ExperienceLevel.SENIOR: [
            r"senior",
            r"5\+ years?",
            r"5-10 years?",
            r"experienced",
        ],
        ExperienceLevel.LEAD: [
            r"lead",
            r"staff",
            r"principal",
            r"10\+ years?",
        ],
    }

    # Salary patterns
    SALARY_PATTERNS = [
        r"\$?(\d{1,3}(?:,\d{3})*(?:\.\d+)?[kK]?)\s*[-–to]\s*\$?(\d{1,3}(?:,\d{3})*(?:\.\d+)?[kK]?)",
        r"\$?(\d{1,3}(?:,\d{3})*(?:\.\d+)?[kK]?)\s*\+\s*",
        r"(\d{1,3}(?:,\d{3})*)(?:\.\d{2})?",
    ]

    def __init__(self, llm_router: Optional[LLMRouter] = None):
        """
        Initialize the JD extractor.

        Args:
            llm_router: Optional LLM router for AI-based extraction
        """
        self.llm_router = llm_router

    def extract_from_html(
        self,
        html: str,
        url: Optional[str] = None,
        source: JobSource = JobSource.OTHER,
    ) -> ExtractionResult:
        """
        Extract job listing from HTML content.

        Args:
            html: Raw HTML content
            url: URL of the job posting
            source: Source of the listing

        Returns:
            ExtractionResult with extracted data
        """
        errors = []
        warnings = []
        job_listing = None

        try:
            # Parse HTML
            soup = BeautifulSoup(html, "html.parser")

            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()

            # Get text content
            text = soup.get_text(separator="\n", strip=True)

            # Extract from text
            result = self.extract_from_text(text, url, source)
            result.warnings.extend(warnings)

            return result

        except Exception as e:
            errors.append(f"HTML parsing failed: {str(e)}")
            return ExtractionResult(
                success=False, job_listing=None, errors=errors, warnings=warnings
            )

    def extract_from_text(
        self,
        text: str,
        url: Optional[str] = None,
        source: JobSource = JobSource.OTHER,
    ) -> ExtractionResult:
        """
        Extract job listing from text content.

        Args:
            text: Job description text
            url: URL of the job posting
            source: Source of the listing

        Returns:
            ExtractionResult with extracted data
        """
        errors = []
        warnings = []

        try:
            # Use LLM for extraction if available
            if self.llm_router:
                return self._extract_with_llm(text, url, source)

            # Fall back to rule-based extraction
            return self._extract_rule_based(text, url, source, errors, warnings)

        except Exception as e:
            errors.append(f"Extraction failed: {str(e)}")
            return ExtractionResult(
                success=False, job_listing=None, errors=errors, warnings=warnings
            )

    def _extract_with_llm(
        self,
        text: str,
        url: Optional[str],
        source: JobSource,
    ) -> ExtractionResult:
        """
        Extract job listing using LLM.

        Args:
            text: Job description text
            url: URL of the job posting
            source: Source of the listing

        Returns:
            ExtractionResult with extracted data
        """
        errors = []
        warnings = []

        # Truncate text if too long
        max_length = 50000  # Adjust based on model context
        if len(text) > max_length:
            warnings.append(
                f"Text truncated from {len(text)} to {max_length} characters"
            )
            text = text[:max_length]

        # Prepare prompt
        system_prompt = """You are a job description parser. Extract structured information from job postings.
Focus on high-signal sections: Requirements, Responsibilities, Qualifications, Skills.
Ignore fluff like company culture paragraphs, equal opportunity statements, etc."""

        user_prompt = f"""Extract the following information from this job description:
{text}

Return a JSON object with these exact fields:
{{
  "title": "Job title",
  "company": "Company name",
  "location": "Location (or 'Remote')",
  "requirements": ["List of key requirements"],
  "responsibilities": ["List of key responsibilities"],
  "skills": ["List of mentioned skills (technical and soft)"],
  "experience_level": "Entry/Mid/Senior/Executive",
  "salary_range": "Salary if mentioned, else null"
}}"""

        messages = [
            Message(role=MessageType.SYSTEM, content=system_prompt),
            Message(role=MessageType.USER, content=user_prompt),
        ]

        try:
            # Get LLM response
            response = self.llm_router.generate(
                messages=messages,
                task_type=TaskType.JD_EXTRACTION,
                temperature=0.3,  # Lower temperature for extraction
            )

            # Parse JSON response
            import json

            # Extract JSON from response
            json_match = re.search(r"\{.*\}", response.content, re.DOTALL)
            if not json_match:
                errors.append("Failed to extract JSON from LLM response")
                return ExtractionResult(
                    success=False, job_listing=None, errors=errors, warnings=warnings
                )

            data = json.loads(json_match.group(0))

            # Create JobListing
            job_listing = self._create_job_listing_from_dict(data, url, source)

            return ExtractionResult(
                success=True,
                job_listing=job_listing,
                errors=errors,
                warnings=warnings,
            )

        except Exception as e:
            errors.append(f"LLM extraction failed: {str(e)}")
            # Fall back to rule-based
            return self._extract_rule_based(text, url, source, errors, warnings)

    def _extract_rule_based(
        self,
        text: str,
        url: Optional[str],
        source: JobSource,
        errors: List[str],
        warnings: List[str],
    ) -> ExtractionResult:
        """
        Extract job listing using rule-based parsing.

        Args:
            text: Job description text
            url: URL of the job posting
            source: Source of the listing
            errors: List to append errors to
            warnings: List to append warnings to

        Returns:
            ExtractionResult with extracted data
        """
        # Split into sections
        sections = self._split_into_sections(text)

        # Extract basic info
        title = self._extract_title(text, sections)
        company = self._extract_company(text, sections)
        location = self._extract_location(text, sections)

        # Extract detailed info
        requirements = self._extract_requirements(sections)
        responsibilities = self._extract_responsibilities(sections)
        skills = self._extract_skills(sections)
        experience_level = self._extract_experience_level(text)
        salary = self._extract_salary(text)

        # Create job listing
        try:
            job_listing = JobListing(
                title=title or "Unknown",
                company=company or "Unknown",
                job_id=self._generate_job_id(title, company, url),
                source=source,
                source_url=url,
                location=location,
                description=text[:1000],  # Truncate description
                requirements=requirements,
                responsibilities=responsibilities,
                skills=skills,
                experience_level=experience_level,
                salary_range=salary,
                work_mode=self._detect_work_mode(text),
                job_type=self._detect_job_type(text),
            )

            return ExtractionResult(
                success=True,
                job_listing=job_listing,
                errors=errors,
                warnings=warnings,
            )

        except Exception as e:
            errors.append(f"Failed to create JobListing: {str(e)}")
            return ExtractionResult(
                success=False, job_listing=None, errors=errors, warnings=warnings
            )

    def _create_job_listing_from_dict(
        self,
        data: Dict[str, Any],
        url: Optional[str],
        source: JobSource,
    ) -> JobListing:
        """Create JobListing from extracted dictionary data."""
        # Parse skills
        skills = []
        for skill_name in data.get("skills", []):
            skills.append(Skill(name=skill_name))

        # Parse requirements
        requirements = []
        for req_text in data.get("requirements", []):
            requirements.append(JobRequirement(text=req_text))

        # Parse responsibilities
        responsibilities = []
        for resp_text in data.get("responsibilities", []):
            responsibilities.append(JobResponsibility(text=resp_text))

        # Parse experience level
        exp_level_str = data.get("experience_level", "Not Specified")
        try:
            experience_level = ExperienceLevel(exp_level_str.title())
        except ValueError:
            experience_level = ExperienceLevel.NOT_SPECIFIED

        return JobListing(
            title=data.get("title", "Unknown"),
            company=data.get("company", "Unknown"),
            job_id=self._generate_job_id(data.get("title"), data.get("company"), url),
            source=source,
            source_url=url,
            location=data.get("location"),
            description=data.get("description", ""),
            requirements=requirements,
            responsibilities=responsibilities,
            skills=skills,
            experience_level=experience_level,
            salary_range=None,  # Parse salary if present
        )

    def _split_into_sections(self, text: str) -> Dict[str, str]:
        """Split text into sections based on headings."""
        sections = {"full": text}
        current_section = "full"
        current_content = []

        lines = text.split("\n")

        for line in lines:
            line_stripped = line.strip()

            # Check if this line looks like a section header
            is_header = False
            for section_name, patterns in self.SECTION_PATTERNS.items():
                for pattern in patterns:
                    if re.search(pattern, line_stripped, re.IGNORECASE):
                        # Save previous section
                        if current_content:
                            sections[current_section] = "\n".join(current_content)

                        # Start new section
                        current_section = section_name
                        current_content = []
                        is_header = True
                        break

                if is_header:
                    break

            if not is_header:
                current_content.append(line)

        # Save last section
        if current_content:
            sections[current_section] = "\n".join(current_content)

        return sections

    def _extract_title(self, text: str, sections: Dict[str, str]) -> Optional[str]:
        """Extract job title from text or sections."""
        # Look for common title patterns
        patterns = [
            r"(?:Job Title|Position|Role):\s*([^\n]+)",
            r"^([A-Z][A-Za-z\s]+)\s+(?:Engineer|Developer|Manager|Director|Analyst)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return None

    def _extract_company(self, text: str, sections: Dict[str, str]) -> Optional[str]:
        """Extract company name from text or sections."""
        patterns = [
            r"(?:Company|Employer|Organization):\s*([^\n]+)",
            r"(?:at|@)\s+([A-Z][A-Za-z\s]+?)(?:\s|$|\n)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return None

    def _extract_location(self, text: str, sections: Dict[str, str]) -> Optional[str]:
        """Extract location from text or sections."""
        patterns = [
            r"(?:Location|City|State):\s*([^\n]+)",
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?),\s*([A-Z]{2})",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()

        return None

    def _extract_requirements(self, sections: Dict[str, str]) -> List[JobRequirement]:
        """Extract requirements from sections."""
        requirements = []
        section_text = sections.get("requirements", "")

        # Split by bullet points or numbered lists
        items = re.split(r"[\n•\-\*]\s*", section_text)

        for item in items:
            item = item.strip()
            if item and len(item) > 10:  # Filter out short items
                requirements.append(JobRequirement(text=item))

        return requirements

    def _extract_responsibilities(
        self, sections: Dict[str, str]
    ) -> List[JobResponsibility]:
        """Extract responsibilities from sections."""
        responsibilities = []
        section_text = sections.get("responsibilities", "")

        # Split by bullet points or numbered lists
        items = re.split(r"[\n•\-\*]\s*", section_text)

        for item in items:
            item = item.strip()
            if item and len(item) > 10:
                responsibilities.append(JobResponsibility(text=item))

        return responsibilities

    def _extract_skills(self, sections: Dict[str, str]) -> List[Skill]:
        """Extract skills from sections."""
        skills = []
        section_text = sections.get("skills", "")

        # Look for common programming languages, frameworks, tools
        # This is a simplified version - in production, use a more comprehensive list
        skill_patterns = [
            r"\b(Python|JavaScript|Java|C\+\+|Go|Rust|TypeScript|SQL|HTML|CSS|React|Angular|Vue|Django|Flask|Node\.js|Docker|AWS|Azure|GCP|Kubernetes|Git|Linux)\b",
        ]

        all_text = sections.get("full", "")
        found_skills = set()

        for pattern in skill_patterns:
            matches = re.finditer(pattern, all_text, re.IGNORECASE)
            for match in matches:
                found_skills.add(match.group(1))

        for skill_name in found_skills:
            skills.append(Skill(name=skill_name))

        return skills

    def _extract_experience_level(self, text: str) -> ExperienceLevel:
        """Extract experience level from text."""
        text_lower = text.lower()

        for level, patterns in self.EXPERIENCE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return level

        return ExperienceLevel.NOT_SPECIFIED

    def _extract_salary(self, text: str) -> Optional[SalaryRange]:
        """Extract salary range from text."""
        # Look for salary patterns
        for pattern in self.SALARY_PATTERNS:
            matches = re.finditer(pattern, text)
            for match in matches:
                # Parse salary range
                try:
                    min_str = (
                        match.group(1)
                        .replace(",", "")
                        .replace("k", "000")
                        .replace("K", "000")
                    )
                    min_amount = float(min_str)

                    if match.lastindex >= 2:
                        max_str = (
                            match.group(2)
                            .replace(",", "")
                            .replace("k", "000")
                            .replace("K", "000")
                        )
                        max_amount = float(max_str)
                    else:
                        max_amount = None

                    return SalaryRange(
                        min_amount=min_amount,
                        max_amount=max_amount,
                        currency="USD",
                        period="annual",
                    )
                except (ValueError, IndexError):
                    continue

        return None

    def _detect_work_mode(self, text: str) -> WorkMode:
        """Detect work mode from text."""
        text_lower = text.lower()

        if "remote" in text_lower and (
            "office" in text_lower or "hybrid" in text_lower
        ):
            return WorkMode.HYBRID
        elif "remote" in text_lower:
            return WorkMode.REMOTE
        else:
            return WorkMode.ON_SITE

    def _detect_job_type(self, text: str) -> JobType:
        """Detect job type from text."""
        text_lower = text.lower()

        if "contract" in text_lower or "contractor" in text_lower:
            return JobType.CONTRACT
        elif "part-time" in text_lower or "part time" in text_lower:
            return JobType.PART_TIME
        elif "internship" in text_lower or "intern" in text_lower:
            return JobType.INTERNSHIP
        else:
            return JobType.FULL_TIME

    def _generate_job_id(
        self,
        title: Optional[str],
        company: Optional[str],
        url: Optional[str],
    ) -> str:
        """Generate a unique job ID."""
        import hashlib

        parts = [title or "", company or "", url or ""]
        combined = "|".join(parts)

        return hashlib.md5(combined.encode()).hexdigest()[:12]
