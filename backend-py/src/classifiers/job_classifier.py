"""
Job Raider - Job Classifier

Uses LLM to classify and enrich job listings with detailed metadata.

Author: Job Raider
Date: 2026-04-29
"""

import json
from enum import Enum
from typing import List, Optional, Dict, Any, Tuple
from pydantic import BaseModel, Field
from dataclasses import dataclass

from ..llm.base import Message, MessageType
from ..llm.router import LLMRouter, TaskType
from ..models.job_listing import JobListing


class Industry(str, Enum):
    """Industry classifications."""
    TECHNOLOGY = "Technology"
    FINANCE = "Finance"
    HEALTHCARE = "Healthcare"
    EDUCATION = "Education"
    RETAIL = "Retail"
    MANUFACTURING = "Manufacturing"
    CONSULTING = "Consulting"
    MEDIA = "Media & Entertainment"
    TELECOMMUNICATIONS = "Telecommunications"
    AUTOMOTIVE = "Automotive"
    ENERGY = "Energy"
    GOVERNMENT = "Government"
    NON_PROFIT = "Non-Profit"
    REAL_ESTATE = "Real Estate"
    TRANSPORTATION = "Transportation"
    OTHER = "Other"


class RoleCategory(str, Enum):
    """Job role categories."""
    ENGINEERING = "Engineering"
    PRODUCT = "Product"
    DESIGN = "Design"
    DATA_SCIENCE = "Data Science"
    MARKETING = "Marketing"
    SALES = "Sales"
    OPERATIONS = "Operations"
    FINANCE = "Finance"
    HR = "Human Resources"
    LEGAL = "Legal"
    CUSTOMER_SUCCESS = "Customer Success"
    MANAGEMENT = "Management"
    RESEARCH = "Research"
    WRITING = "Writing & Content"
    OTHER = "Other"


class CompanySize(str, Enum):
    """Company size classifications."""
    STARTUP = "Startup (1-10)"
    SMALL = "Small (11-50)"
    MEDIUM_SMALL = "Medium-Small (51-200)"
    MEDIUM = "Medium (201-500)"
    MEDIUM_LARGE = "Medium-Large (501-1000)"
    LARGE = "Large (1001-5000)"
    ENTERPRISE = "Enterprise (5000+)"
    UNKNOWN = "Unknown"


class WorkPace(str, Enum):
    """Expected work pace/environment."""
    RELAXED = "Relaxed"
    STEADY = "Steady"
    FAST_PACED = "Fast-Paced"
    HIGH_PRESSURE = "High Pressure"
    UNKNOWN = "Unknown"


class TeamStructure(str, Enum):
    """Team structure type."""
    SOLO_CONTRIBUTOR = "Solo Contributor"
    SMALL_TEAM = "Small Team (2-5)"
    MEDIUM_TEAM = "Medium Team (6-15)"
    LARGE_TEAM = "Large Team (16+)"
    CROSS_FUNCTIONAL = "Cross-Functional"
    UNKNOWN = "Unknown"


class SkillRequirement(BaseModel):
    """Detailed skill requirement."""
    name: str = Field(description="Skill name")
    category: str = Field(description="Skill category (technical, soft, domain, tool)")
    proficiency: str = Field(description="Required proficiency level")
    is_required: bool = Field(description="True if must-have, False if nice-to-have")
    confidence: float = Field(description="Confidence score 0-1")


class JobClassification(BaseModel):
    """Rich classification data for a job listing."""

    # Primary classifications
    industry: Industry = Field(default=Industry.OTHER, description="Industry sector")
    role_category: RoleCategory = Field(default=RoleCategory.OTHER, description="Role category")

    # Company insights
    company_size: CompanySize = Field(default=CompanySize.UNKNOWN, description="Estimated company size")
    company_stage: Optional[str] = Field(default=None, description="Company stage (e.g., 'Series B', 'IPO')")

    # Work environment
    work_pace: WorkPace = Field(default=WorkPace.UNKNOWN, description="Expected work pace")
    team_structure: TeamStructure = Field(default=TeamStructure.UNKNOWN, description="Team structure type")

    # Skill analysis
    technical_skills: List[SkillRequirement] = Field(default_factory=list, description="Technical skills")
    soft_skills: List[SkillRequirement] = Field(default_factory=list, description="Soft skills")
    domain_skills: List[SkillRequirement] = Field(default_factory=list, description="Domain knowledge")

    # Experience validation
    experience_level_confidence: float = Field(default=0.0, description="Confidence in experience level (0-1)")
    actual_experience_years: Optional[Tuple[float, float]] = Field(default=None, description="Min, max years range")

    # Role specifics
    management_level: Optional[str] = Field(default=None, description="Management level (individual, lead, manager, director)")
    impact_scope: Optional[str] = Field(default=None, description="Scope of impact (team, department, company, industry)")

    # Metadata
    classification_confidence: float = Field(default=0.0, description="Overall confidence (0-1)")
    tags: List[str] = Field(default_factory=list, description="Additional searchable tags")
    red_flags: List[str] = Field(default_factory=list, description="Potential concerns in the listing")


@dataclass
class JobClassificationResult:
    """Result of job classification."""
    success: bool
    classification: Optional[JobClassification]
    errors: List[str]
    warnings: List[str]


class JobClassifier:
    """
    LLM-based job classifier for enriching job listings.

    Analyzes job descriptions to extract rich metadata for better
    filtering, matching, and recommendations.
    """

    # Classification prompt template
    SYSTEM_PROMPT = """You are an expert job analyst. Analyze job descriptions to extract
rich, structured metadata. Be precise and realistic in your assessments.

Guidelines:
- Industry: Choose the most relevant sector based on company business and role
- Role Category: Match to primary function (Engineering, Product, Design, etc.)
- Company Size: Estimate from company description, benefits structure, and role scope
- Work Pace: Infer from language like "fast-paced", "startup environment", "established"
- Team Structure: Look for mentions of team size, cross-functional work, reporting lines
- Skills: Classify as technical (hard skills), soft (interpersonal), or domain (industry knowledge)
- Experience: Extract specific years ranges and validate against stated level
- Management: Identify if role manages people, projects, or is individual contributor
- Impact: Determine scope (team-level vs company-wide vs industry)
- Red Flags: Note concerning patterns (vague requirements, unrealistic expectations, etc.)"""

    USER_PROMPT_TEMPLATE = """Analyze this job listing and provide structured classification:

Job Title: {title}
Company: {company}
Location: {location}
Description:
{description}

Requirements:
{requirements_text}

Responsibilities:
{responsibilities_text}

Return a JSON object with this exact structure:
{{
  "industry": "Technology|Finance|Healthcare|...",
  "role_category": "Engineering|Product|Design|Data Science|...",
  "company_size": "Startup (1-10)|Small (11-50)|Medium-Small (51-200)|Medium (201-500)|Medium-Large (501-1000)|Large (1001-5000)|Enterprise (5000+)|Unknown",
  "company_stage": "e.g., 'Seed', 'Series A', 'IPO', or null",
  "work_pace": "Relaxed|Steady|Fast-Paced|High Pressure|Unknown",
  "team_structure": "Solo Contributor|Small Team (2-5)|Medium Team (6-15)|Large Team (16+)|Cross-Functional|Unknown",
  "technical_skills": [
    {{"name": "Python", "proficiency": "Expert", "is_required": true, "category": "programming_language"}},
    {{"name": "React", "proficiency": "Advanced", "is_required": false, "category": "framework"}}
  ],
  "soft_skills": [
    {{"name": "Communication", "proficiency": "Strong", "is_required": true, "category": "communication"}},
    {{"name": "Leadership", "proficiency": "Moderate", "is_required": false, "category": "management"}}
  ],
  "domain_skills": [
    {{"name": "FinTech", "proficiency": "Familiar", "is_required": true, "category": "industry"}}
  ],
  "experience_level_confidence": 0.85,
  "actual_experience_years": [3.0, 5.0],
  "management_level": "individual_contributor|lead|manager|director|vp",
  "impact_scope": "team|department|company|industry",
  "classification_confidence": 0.8,
  "tags": ["ai/ml", "backend", "apis"],
  "red_flags": ["Unrealistic requirements for stated level"]
}}

Be thorough but realistic. If information is not available, use Unknown/null or empty lists."""

    def __init__(self, llm_router: Optional[LLMRouter] = None):
        """
        Initialize the job classifier.

        Args:
            llm_router: LLM router for classification
        """
        self.llm_router = llm_router

    def classify(
        self,
        job_listing: JobListing,
        use_llm: bool = True,
    ) -> JobClassificationResult:
        """
        Classify a job listing with rich metadata.

        Args:
            job_listing: Job listing to classify
            use_llm: Whether to use LLM (fallback to rule-based if False)

        Returns:
            JobClassificationResult with classification data
        """
        errors = []
        warnings = []

        try:
            if use_llm and self.llm_router:
                return self._classify_with_llm(job_listing)
            else:
                return self._classify_rule_based(job_listing, errors, warnings)

        except Exception as e:
            errors.append(f"Classification failed: {str(e)}")
            return JobClassificationResult(
                success=False,
                classification=None,
                errors=errors,
                warnings=warnings,
            )

    def _classify_with_llm(
        self,
        job_listing: JobListing,
    ) -> JobClassificationResult:
        """
        Classify job listing using LLM.

        Args:
            job_listing: Job listing to classify

        Returns:
            JobClassificationResult with classification data
        """
        errors = []
        warnings = []

        # Prepare text sections
        requirements_text = "\n".join([req.text for req in job_listing.requirements[:5]])
        responsibilities_text = "\n".join([resp.text for resp in job_listing.responsibilities[:5]])

        # Truncate description if too long
        description = job_listing.description or ""
        if len(description) > 3000:
            description = description[:3000]
            warnings.append("Description truncated for LLM processing")

        # Build prompt
        user_prompt = self.USER_PROMPT_TEMPLATE.format(
            title=job_listing.title,
            company=job_listing.company,
            location=job_listing.location or "Not specified",
            description=description,
            requirements_text=requirements_text or "Not specified",
            responsibilities_text=responsibilities_text or "Not specified",
        )

        messages = [
            Message(role=MessageType.SYSTEM, content=self.SYSTEM_PROMPT),
            Message(role=MessageType.USER, content=user_prompt),
        ]

        try:
            # Get LLM response
            response = self.llm_router.generate(
                messages=messages,
                task_type=TaskType.CLASSIFICATION,
                temperature=0.2,  # Low temperature for consistent classification
            )

            # Parse JSON response
            import re

            json_match = re.search(r'\{.*\}', response.content, re.DOTALL)
            if not json_match:
                errors.append("Failed to extract JSON from LLM response")
                return JobClassificationResult(
                    success=False,
                    classification=None,
                    errors=errors,
                    warnings=warnings,
                )

            data = json.loads(json_match.group(0))

            # Create classification
            classification = self._create_classification_from_dict(data)

            return JobClassificationResult(
                success=True,
                classification=classification,
                errors=errors,
                warnings=warnings,
            )

        except Exception as e:
            errors.append(f"LLM classification failed: {str(e)}")
            # Fall back to rule-based
            return self._classify_rule_based(job_listing, errors, warnings)

    def _create_classification_from_dict(self, data: Dict[str, Any]) -> JobClassification:
        """Create JobClassification from dictionary data."""
        # Parse skill requirements
        def parse_skills(skills_data: List[Dict]) -> List[SkillRequirement]:
            skills = []
            for skill_data in skills_data:
                try:
                    skills.append(SkillRequirement(
                        name=skill_data.get("name", ""),
                        category=skill_data.get("category", "other"),
                        proficiency=skill_data.get("proficiency", "Intermediate"),
                        is_required=skill_data.get("is_required", True),
                        confidence=0.8,  # Default confidence
                    ))
                except Exception:
                    continue
            return skills

        # Parse enum values
        try:
            industry = Industry(data.get("industry", Industry.OTHER))
        except ValueError:
            industry = Industry.OTHER

        try:
            role_category = RoleCategory(data.get("role_category", RoleCategory.OTHER))
        except ValueError:
            role_category = RoleCategory.OTHER

        try:
            company_size = CompanySize(data.get("company_size", CompanySize.UNKNOWN))
        except ValueError:
            company_size = CompanySize.UNKNOWN

        try:
            work_pace = WorkPace(data.get("work_pace", WorkPace.UNKNOWN))
        except ValueError:
            work_pace = WorkPace.UNKNOWN

        try:
            team_structure = TeamStructure(data.get("team_structure", TeamStructure.UNKNOWN))
        except ValueError:
            team_structure = TeamStructure.UNKNOWN

        # Parse experience range
        experience_range = None
        if "actual_experience_years" in data:
            try:
                years = data["actual_experience_years"]
                if isinstance(years, list) and len(years) == 2:
                    experience_range = (float(years[0]), float(years[1]))
            except (ValueError, TypeError, IndexError):
                pass

        return JobClassification(
            industry=industry,
            role_category=role_category,
            company_size=company_size,
            company_stage=data.get("company_stage"),
            work_pace=work_pace,
            team_structure=team_structure,
            technical_skills=parse_skills(data.get("technical_skills", [])),
            soft_skills=parse_skills(data.get("soft_skills", [])),
            domain_skills=parse_skills(data.get("domain_skills", [])),
            experience_level_confidence=float(data.get("experience_level_confidence", 0.5)),
            actual_experience_years=experience_range,
            management_level=data.get("management_level"),
            impact_scope=data.get("impact_scope"),
            classification_confidence=float(data.get("classification_confidence", 0.5)),
            tags=data.get("tags", []),
            red_flags=data.get("red_flags", []),
        )

    def _classify_rule_based(
        self,
        job_listing: JobListing,
        errors: List[str],
        warnings: List[str],
    ) -> JobClassificationResult:
        """
        Classify job listing using rule-based heuristics.

        Args:
            job_listing: Job listing to classify
            errors: List to append errors to
            warnings: List to append warnings to

        Returns:
            JobClassificationResult with classification data
        """
        warnings.append("Using rule-based classification (less accurate than LLM)")

        # Analyze title and description for keywords
        title_lower = job_listing.title.lower()
        desc_lower = (job_listing.description or "").lower()

        # Determine role category from title
        role_category = self._infer_role_category(title_lower, desc_lower)

        # Determine industry from company/description
        industry = self._infer_industry(job_listing.company, desc_lower)

        # Estimate work pace from language
        work_pace = self._infer_work_pace(desc_lower)

        # Create basic classification
        classification = JobClassification(
            industry=industry,
            role_category=role_category,
            work_pace=work_pace,
            company_size=CompanySize.UNKNOWN,
            team_structure=TeamStructure.UNKNOWN,
            classification_confidence=0.5,
        )

        return JobClassificationResult(
            success=True,
            classification=classification,
            errors=errors,
            warnings=warnings,
        )

    def _infer_role_category(self, title: str, description: str) -> RoleCategory:
        """Infer role category from title and description."""
        text = f"{title} {description}"

        role_keywords = {
            RoleCategory.ENGINEERING: ["engineer", "developer", "programmer", "software", "frontend", "backend", "full-stack"],
            RoleCategory.PRODUCT: ["product manager", "product owner", "pm", "roadmap"],
            RoleCategory.DESIGN: ["designer", "ux", "ui", "visual", "graphic"],
            RoleCategory.DATA_SCIENCE: ["data scientist", "analyst", "machine learning", "ai", "ml engineer"],
            RoleCategory.MARKETING: ["marketing", "growth", "seo", "content", "brand"],
            RoleCategory.SALES: ["sales", "account executive", "business development", "bd"],
            RoleCategory.OPERATIONS: ["operations", "ops", "logistics", "supply chain"],
            RoleCategory.FINANCE: ["finance", "accounting", "financial analyst"],
            RoleCategory.HR: ["human resources", "recruiter", "talent", "hr", "people"],
            RoleCategory.CUSTOMER_SUCCESS: ["customer success", "support", "customer service"],
        }

        for role, keywords in role_keywords.items():
            if any(keyword in text for keyword in keywords):
                return role

        return RoleCategory.OTHER

    def _infer_industry(self, company: str, description: str) -> Industry:
        """Infer industry from company and description."""
        text = f"{company} {description}".lower()

        industry_keywords = {
            Industry.FINANCE: ["bank", "fintech", "financial", "investment", "trading", "crypto"],
            Industry.HEALTHCARE: ["health", "medical", "hospital", "clinic", "pharma", "biotech"],
            Industry.EDUCATION: ["education", "school", "university", "learning", "edtech"],
            Industry.RETAIL: ["retail", "e-commerce", "shop", "store"],
            Industry.MEDIA: ["media", "news", "publishing", "entertainment", "streaming"],
            Industry.TECHNOLOGY: ["software", "tech", "saas", "cloud", "platform"],
        }

        for industry, keywords in industry_keywords.items():
            if any(keyword in text for keyword in keywords):
                return industry

        return Industry.OTHER

    def _infer_work_pace(self, description: str) -> WorkPace:
        """Infer work pace from description language."""
        desc_lower = description.lower()

        if any(word in desc_lower for word in ["fast-paced", "fast paced", "startup environment", "rapidly"]):
            return WorkPace.FAST-paced
        elif any(word in desc_lower for word in ["high pressure", "demanding", "deadline-driven"]):
            return WorkPace.HIGH_PRESSURE
        elif any(word in desc_lower for word in ["relaxed", "balance", "flexible", " laid back"]):
            return WorkPace.RELAXED
        else:
            return WorkPace.STEADY

    def batch_classify(
        self,
        job_listings: List[JobListing],
        use_llm: bool = True,
    ) -> List[JobClassificationResult]:
        """
        Classify multiple job listings.

        Args:
            job_listings: List of job listings to classify
            use_llm: Whether to use LLM classification

        Returns:
            List of classification results
        """
        results = []
        for job_listing in job_listings:
            result = self.classify(job_listing, use_llm=use_llm)
            results.append(result)
        return results
