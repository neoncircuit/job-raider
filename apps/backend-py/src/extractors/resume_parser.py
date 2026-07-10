"""
Job Raider - Resume Parser

This module provides functionality to parse resumes from PDF and DOCX files
and extract structured user profile information.

Author: Job Raider
Date: 2026-04-20
"""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from docx import Document
from pypdf import PdfReader

from ..llm.base import Message, MessageType
from ..llm.router import LLMRouter, TaskType
from ..models.job_listing import ExperienceLevel
from ..models.user_profile import (
    ApprenticeshipContract,
    Certification,
    ContactInfo,
    Education,
    Project,
    Skill,
    SkillCategory,
    TargetJob,
    UserProfile,
    WorkExperience,
)

logger = logging.getLogger(__name__)


class ResumeParser:
    """
    Parse resumes from PDF and DOCX files.

    Extracts structured user profile information including
    skills, experience, projects, and education.
    """

    def __init__(self, llm_router: Optional[LLMRouter] = None):
        """
        Initialize the resume parser.

        Args:
            llm_router: Optional LLM router for AI-based parsing
        """
        self.llm_router = llm_router

    def parse_file(self, file_path: str) -> UserProfile:
        """
        Parse a resume file (PDF or DOCX).

        Args:
            file_path: Path to resume file

        Returns:
            UserProfile with extracted information

        Raises:
            ValueError: If file format is not supported
            FileNotFoundError: If file doesn't exist
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"Resume file not found: {file_path}")

        # Determine file type and extract text
        if path.suffix.lower() == ".pdf":
            text = self._extract_text_from_pdf(path)
        elif path.suffix.lower() in [".docx", ".doc"]:
            text = self._extract_text_from_docx(path)
        else:
            raise ValueError(f"Unsupported file format: {path.suffix}")

        # Parse text into profile
        return self.parse_text(text)

    def parse_text(self, text: str) -> UserProfile:
        """
        Parse resume text into a UserProfile.

        Args:
            text: Resume text content

        Returns:
            UserProfile with extracted information
        """
        if self.llm_router:
            return self._parse_with_llm(text)
        else:
            return self._parse_rule_based(text)

    def _extract_text_from_pdf(self, path: Path) -> str:
        """Extract text from PDF file."""
        try:
            reader = PdfReader(str(path))
            text = ""

            for page in reader.pages:
                text += page.extract_text() + "\n"

            return text

        except Exception as e:
            raise ValueError(f"Failed to extract text from PDF: {str(e)}")

    def _extract_text_from_docx(self, path: Path) -> str:
        """Extract text from DOCX file."""
        try:
            doc = Document(str(path))
            text = ""

            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"

            # Also extract from tables
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        text += cell.text + " "
                    text += "\n"

            return text

        except Exception as e:
            raise ValueError(f"Failed to extract text from DOCX: {str(e)}")

    def _parse_with_llm(self, text: str) -> UserProfile:
        """
        Parse resume using LLM.

        Args:
            text: Resume text content

        Returns:
            UserProfile with extracted information
        """
        # Truncate text if too long
        max_length = 8000  # For models with 32K context
        if len(text) > max_length:
            text = text[:max_length]

        # Prepare prompt
        system_prompt = """You are a resume parser. Extract structured information from resume documents.
Be thorough and capture all relevant details. Return information in valid JSON format."""

        user_prompt = f"""Parse this resume and extract structured information:

RESUME TEXT:
{text}

Return a JSON object with these exact fields:
{{
  "basics": {{
    "name": "Full Name",
    "email": "email@example.com",
    "phone": "phone number",
    "location": "City, State/Country - this must be a physical geographic location (e.g. 'Singapore, Singapore', 'New York, NY', 'London, UK', 'Tokyo, Japan'), NOT a job title, role, or department name",
    "linkedin": "LinkedIn URL if present",
    "github": "GitHub URL if present"
  }},
  "summary": "Professional summary",
  "skills": {{
    "programming_languages": ["Python", "JavaScript", ...],
    "frameworks": ["React", "Django", ...],
    "tools": ["Git", "Docker", ...],
    "domains": ["Machine Learning", "Web Development", ...]
  }},
  "experience": [
    {{
      "title": "Job Title",
      "company": "Company Name",
      "location": "Location",
      "start_date": "YYYY-MM",
      "end_date": "YYYY-MM or 'present'",
      "highlights": ["bullet1", "bullet2", ...]
    }}
  ],
  "projects": [
    {{
      "name": "Project Name",
      "description": "Description",
      "technologies": ["tech1", "tech2"],
      "url": "URL if present",
      "highlights": ["achievement1", "achievement2"]
    }}
  ],
  "education": [
    {{
      "degree": "Degree Name",
      "school": "School Name",
      "location": "Location",
      "graduation_year": "YYYY",
      "gpa": "GPA if present"
    }}
  ],
  "certifications": [
    {{"name": "Certification", "issuer": "Issuer", "date": "YYYY-MM"}}
  ],
  "target_job": {{
    "keywords": ["target job titles or roles inferred from the candidate's profile. For experienced candidates, use work history. For recent graduates or students, infer from degree major, coursework, projects, and skills instead. e.g. Software Engineer, Data Analyst, Research Assistant"],
    "locations": ["preferred work locations inferred from current location or stated preferences"],
    "experience_levels": ["inferred career stage: one or more of Entry Level, Mid Level, Senior, Lead, Principal, Executive, Internship. Use Entry Level or Internship for recent graduates with little or no work experience."],
    "remote_preference": true or false based on any stated remote work preference,
    "industries": ["target industries inferred from the candidate's background. For experienced candidates, use work history. For recent graduates, infer from degree field, projects, and skills instead. e.g. Technology, Finance, Healthcare"]
  }},
  "apprenticeship": {{
    "field": "required field of work if the candidate has an apprenticeship/traineeship contract obligation, e.g. 'AI/ML', 'Healthcare'. Leave as null if no such contract exists.",
    "duration_months": "remaining contract duration in months as integer, or null",
    "employer": "sponsoring employer or organization name, or null",
    "start_date": "YYYY-MM or null",
    "end_date": "YYYY-MM or null",
    "is_active": true or false
  }}
}}

IMPORTANT: Return ONLY valid JSON. No markdown, no explanations, just the JSON object.
IMPORTANT: The "location" in "basics" must be a real city and state/country (e.g. "Singapore, Singapore" or "New York, NY" or "London, UK"), never a job title or role. City-states like Singapore are valid locations.
IMPORTANT: If the candidate has no work experience (recent graduate or student), still populate target_job keywords and industries based on their education, projects, and skills. Default experience_levels to ["Entry Level"] or ["Internship"] as appropriate.
IMPORTANT: If the resume mentions an apprenticeship, traineeship, or sponsored training program with a work obligation, populate the "apprenticeship" object. If no such program is mentioned, set all apprenticeship fields to null."""

        messages = [
            Message(role=MessageType.SYSTEM, content=system_prompt),
            Message(role=MessageType.USER, content=user_prompt),
        ]

        try:
            # Get LLM response
            response = self.llm_router.generate(
                messages=messages,
                task_type=TaskType.RESUME_PARSING,
                temperature=0.3,
            )

            # Extract JSON from response
            json_match = re.search(r"\{.*\}", response.content, re.DOTALL)
            if not json_match:
                raise ValueError("Failed to extract JSON from LLM response")

            import json

            data = json.loads(json_match.group(0))

            # Create UserProfile from dict
            return self._create_profile_from_dict(data)

        except Exception as e:
            # Fall back to rule-based parsing
            logger.error(f"LLM resume parsing failed, falling back to rule-based: {e}")
            return self._parse_rule_based(text)

    def _create_profile_from_dict(self, data: Dict[str, Any]) -> UserProfile:
        """Create UserProfile from extracted dictionary data."""
        # Normalize top-level keys: LLM may return different field names
        basics = data.get("basics") or data.get("basic_info") or {}
        summary = (
            data.get("summary")
            or data.get("profile")
            or data.get("professional_summary")
            or ""
        )
        skills_dict = data.get("skills") or data.get("technical_skills") or {}
        # If skills is a flat list instead of categorized dict, convert it
        if isinstance(skills_dict, list):
            skills_dict = {"programming_languages": skills_dict}

        # Parse contact info with normalized URLs
        contact = ContactInfo(
            email=basics.get("email", "user@example.com"),
            phone=basics.get("phone"),
            location=basics.get("location", "Unknown"),
            linkedin=self._normalize_url(basics.get("linkedin")),
            github=self._normalize_url(basics.get("github")),
        )

        # Parse skills (using normalized skills_dict from above)
        skills = []

        skill_category_map = {
            "programming_languages": SkillCategory.PROGRAMMING_LANGUAGE,
            "frameworks": SkillCategory.FRAMEWORK,
            "tools": SkillCategory.TOOL,
            "cloud": SkillCategory.CLOUD,
            "database": SkillCategory.DATABASE,
            "languages": SkillCategory.LANGUAGE,
        }

        for category_str, skill_list in skills_dict.items():
            category = skill_category_map.get(category_str, SkillCategory.OTHER)
            for skill_name in skill_list:
                skills.append(Skill(name=skill_name, category=category))

        # Parse experience
        experience = []
        for exp_data in data.get("experience", []):
            title = exp_data.get("title") or exp_data.get("position") or "Unknown"
            company = (
                exp_data.get("company") or exp_data.get("organization") or "Unknown"
            )
            highlights = (
                exp_data.get("highlights")
                or exp_data.get("achievements")
                or exp_data.get("responsibilities")
                or []
            )

            # Handle dates: prefer explicit start_date/end_date, fall back to parsing "dates" string
            start_date = self._parse_date(exp_data.get("start_date"))
            end_date_str = exp_data.get("end_date")
            if not start_date and not end_date_str:
                dates_raw = exp_data.get("dates") or exp_data.get("date_range") or ""
                start_date, end_date_str = self._split_date_range(dates_raw)
            end_date = (
                None
                if (end_date_str or "").lower() in ("present", "current", "")
                else self._parse_date(end_date_str)
            )

            description = exp_data.get("description") or ""
            if isinstance(description, list):
                description = " ".join(str(h) for h in description)
            if not description and highlights:
                first = (
                    highlights[0]
                    if isinstance(highlights, list) and highlights
                    else highlights
                )
                description = (
                    str(first)
                    if not isinstance(first, list)
                    else " ".join(str(h) for h in first)
                )

            experience.append(
                WorkExperience(
                    title=title,
                    company=company,
                    location=exp_data.get("location"),
                    start_date=start_date or datetime.now(),
                    end_date=end_date,
                    description=description[:500] if description else None,
                    highlights=highlights if isinstance(highlights, list) else [],
                    technologies=exp_data.get("technologies", []),
                )
            )

        # Parse projects
        projects = []
        for proj_data in data.get("projects", []):
            description = proj_data.get("description") or ""
            highlights = (
                proj_data.get("highlights") or proj_data.get("achievements") or []
            )
            if not description and highlights:
                description = (
                    highlights[0] if isinstance(highlights, list) else str(highlights)
                )

            projects.append(
                Project(
                    name=proj_data.get("name") or proj_data.get("title") or "Unknown",
                    description=description[:500] if description else "",
                    technologies=proj_data.get("technologies")
                    or proj_data.get("tech_stack")
                    or [],
                    url=proj_data.get("url"),
                    highlights=highlights if isinstance(highlights, list) else [],
                )
            )

        # Parse education
        education = []
        for edu_data in data.get("education", []):
            grad_year = edu_data.get("graduation_year") or edu_data.get("year")
            end_date = None
            if grad_year:
                try:
                    end_date = datetime(int(str(grad_year)[:4]), 6, 1)
                except (ValueError, TypeError):
                    pass

            education.append(
                Education(
                    degree=edu_data.get("degree")
                    or edu_data.get("qualification")
                    or "Unknown",
                    school=edu_data.get("school")
                    or edu_data.get("university")
                    or edu_data.get("institution")
                    or "Unknown",
                    location=edu_data.get("location"),
                    end_date=end_date,
                    gpa=edu_data.get("gpa"),
                )
            )

        # Parse certifications
        certifications = []
        for cert_data in data.get("certifications", []):
            issue_date = self._parse_date(cert_data.get("date"))

            certifications.append(
                Certification(
                    name=cert_data.get("name", "Unknown"),
                    issuer=cert_data.get("issuer", "Unknown"),
                    issue_date=issue_date,
                )
            )

        # Parse target job preferences
        target_job_data = data.get("target_job", {})
        target_job = self._build_target_job(target_job_data)

        # Parse apprenticeship contract (optional)
        apprenticeship = self._build_apprenticeship(data.get("apprenticeship", {}))

        # Create profile
        return UserProfile(
            name=basics.get("name", "User"),
            contact=contact,
            summary=summary or None,
            skills=skills,
            experience=experience,
            projects=projects,
            education=education,
            certifications=certifications,
            targets=target_job,
            apprenticeship=apprenticeship,
        )

    def _build_target_job(self, data: Dict[str, Any]) -> TargetJob:
        """Build a TargetJob from extracted dictionary data.

        Maps experience level strings to the ExperienceLevel enum,
        falling back to NOT_SPECIFIED for unrecognized values.

        Args:
            data: Dictionary with target job preference fields.

        Returns:
            TargetJob with extracted preferences.
        """
        level_map = {
            "entry level": ExperienceLevel.ENTRY,
            "entry": ExperienceLevel.ENTRY,
            "mid level": ExperienceLevel.MID,
            "mid": ExperienceLevel.MID,
            "senior": ExperienceLevel.SENIOR,
            "lead": ExperienceLevel.LEAD,
            "principal": ExperienceLevel.PRINCIPAL,
            "executive": ExperienceLevel.EXECUTIVE,
            "internship": ExperienceLevel.INTERNSHIP,
        }

        experience_levels: List[ExperienceLevel] = []
        for level_str in data.get("experience_levels", []):
            normalized = level_str.strip().lower()
            matched = level_map.get(normalized, ExperienceLevel.NOT_SPECIFIED)
            if matched not in experience_levels:
                experience_levels.append(matched)

        return TargetJob(
            keywords=data.get("keywords", []),
            locations=data.get("locations", []),
            experience_levels=experience_levels,
            remote_preference=data.get("remote_preference", False),
            industries=data.get("industries", []),
        )

    def _build_apprenticeship(
        self, data: Dict[str, Any]
    ) -> Optional[ApprenticeshipContract]:
        """Build an ApprenticeshipContract from extracted dictionary data.

        Returns None if no apprenticeship data is present or the field
        is empty/null.

        Args:
            data: Dictionary with apprenticeship contract fields.

        Returns:
            ApprenticeshipContract if data is valid, None otherwise.
        """
        field = data.get("field")
        if not field:
            return None

        return ApprenticeshipContract(
            field=field,
            duration_months=data.get("duration_months"),
            employer=data.get("employer"),
            start_date=self._parse_date(data.get("start_date")),
            end_date=self._parse_date(data.get("end_date")),
            is_active=data.get("is_active", True),
        )

    def _parse_rule_based(self, text: str) -> UserProfile:
        """
        Parse resume using rule-based extraction.

        This is a simplified version. In production, you'd want
        more sophisticated patterns or use a dedicated resume parsing library.

        Args:
            text: Resume text content

        Returns:
            UserProfile with extracted information
        """
        # Extract name (first line typically)
        lines = text.split("\n")
        name = lines[0].strip() if lines else "User"

        # Extract email
        email_match = re.search(r"\b[\w\.-]+@[\w\.-]+\.\w+\b", text)
        email = email_match.group(0) if email_match else "user@example.com"

        # Extract phone - more flexible patterns for international formats
        phone_patterns = [
            r"\+\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}",  # International
            r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",  # US format
            r"\d{3}[-.\s]?\d{3}[-.\s]?\d{4}",  # Simple format
            r"\b\d{10}\b",  # 10 digits
        ]
        phone = None
        for pattern in phone_patterns:
            phone_match = re.search(pattern, text)
            if phone_match:
                phone = phone_match.group(0)
                break

        # Extract location - improved pattern to avoid false matches
        # Look for common location indicators
        location = None

        # Blocklist of words that indicate a job title, not a location
        location_blocklist = {
            "assistant",
            "manager",
            "engineer",
            "developer",
            "analyst",
            "director",
            "coordinator",
            "specialist",
            "consultant",
            "intern",
            "associate",
            "designer",
            "administrator",
            "lead",
            "architect",
            "scientist",
            "officer",
            "executive",
            "supervisor",
            "technician",
        }

        # Try specific patterns first
        location_patterns = [
            r"(?:Location|City|Address|Based in?):\s*([A-Z][a-zA-Z\s]+?(?:,\s*[A-Z]{2}|,\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)?(?:\n|$))",
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?),\s*([A-Z]{2}|[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",  # City, State/Country (e.g. "Singapore, Singapore")
        ]

        for pattern in location_patterns:
            location_match = re.search(pattern, text, re.IGNORECASE)
            if location_match:
                loc_text = location_match.group(1).strip()
                loc_words = loc_text.lower().split()
                # Validate: reasonable length and not a job title
                is_blocked = any(word in location_blocklist for word in loc_words)
                if 3 < len(loc_text) < 100 and not is_blocked:
                    location = loc_text
                    break

        # Fallback to unknown if no location found
        if not location:
            location = "Unknown"

        # Create basic profile
        return UserProfile(
            name=name,
            contact=ContactInfo(
                email=email,
                phone=phone,
                location=location,
            ),
            skills=self._extract_skills_rule_based(text),
            experience=[],
            projects=[],
            education=[],
        )

    def _extract_skills_rule_based(self, text: str) -> List[Skill]:
        """Extract skills using rule-based patterns."""
        skills = []
        found_skills = set()

        # Common programming languages and frameworks
        skill_patterns = [
            r"\b(Python|JavaScript|TypeScript|Java|C\+\+|C#|Go|Rust|Ruby|PHP|Swift|Kotlin|Scala|R|MATLAB)\b",
            r"\b(React|Angular|Vue|Next\.js|Nuxt|Django|Flask|FastAPI|Spring|Express\.js|Node\.js|\.NET)\b",
            r"\b(AWS|Azure|GCP|Docker|Kubernetes|Terraform|Ansible|Jenkins|Git|GitHub|GitLab|CI/CD)\b",
            r"\b(SQL|NoSQL|MongoDB|PostgreSQL|MySQL|Redis|Elasticsearch|GraphQL|REST|GraphQL)\b",
            r"\b(Machine Learning|Deep Learning|AI|Data Science|NLP|Computer Vision)\b",
        ]

        for pattern in skill_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                found_skills.add(match.group(1))

        for skill_name in found_skills:
            skills.append(Skill(name=skill_name))

        return skills

    def _split_date_range(self, date_range: str) -> tuple:
        """
        Split a date range string like 'Oct 2025 - Mar 2026' into start and end.

        Args:
            date_range: Date range string

        Returns:
            Tuple of (parsed_start_date_or_None, end_date_string_or_None)
        """
        if not date_range:
            return None, None

        # Common separators: dash, en-dash, em-dash, to
        for sep in [" – ", " - ", " — ", " to "]:
            if sep in date_range:
                parts = date_range.split(sep, 1)
                return self._parse_date(parts[0].strip()), parts[1].strip()

        # Single date (treat as start)
        return self._parse_date(date_range.strip()), None

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """
        Parse date string into datetime object.

        Args:
            date_str: Date string in various formats

        Returns:
            Datetime object or None
        """
        if not date_str:
            return None

        # Common date formats
        formats = [
            "%Y-%m",
            "%Y-%m-%d",
            "%m/%Y",
            "%m/%Y",
            "%b %Y",
            "%B %Y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue

        return None

    def _normalize_url(self, url: Optional[str]) -> Optional[str]:
        """
        Normalize URL by adding https:// scheme if missing.

        LLMs often return URLs without the scheme (e.g., 'linkedin.com/in/...')
        which causes pydantic HttpUrl validation to fail.

        Args:
            url: URL string that may or may not have a scheme

        Returns:
            Normalized URL with scheme, or None if input is None/empty
        """
        if not url or not isinstance(url, str):
            return None

        url = url.strip()

        # Already has a scheme
        if url.startswith(("http://", "https://")):
            return url

        # Add https:// scheme for common domains
        return f"https://{url}"
