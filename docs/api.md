# Job Raider - API Documentation

## Core Modules

### Pipeline Module

#### PipelineOrchestrator

Main orchestrator for the job application pipeline.

```python
import sys
sys.path.insert(0, 'backend-py')

from src.pipeline.orchestrator import (
    PipelineOrchestrator,
    PipelineConfig,
    PipelineResult,
    PipelineStage,
)

# Create configuration
config = PipelineConfig(
    keywords=["python", "engineer"],
    locations=["remote"],
    sources=["linkedin", "jsearch"],
    dry_run=True,
    min_score=60,
)

# Create orchestrator
orchestrator = PipelineOrchestrator(
    config=config,
    user_profile=user_profile,
)

# Run pipeline
result = orchestrator.run()
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `keywords` | `List[str]` | required | Job keywords to search |
| `locations` | `List[str]` | required | Job locations |
| `sources` | `Optional[List[str]]` | `None` | Job sources (linkedin, jsearch) |
| `dry_run` | `bool` | `True` | Simulate submissions |
| `skip_submission` | `bool` | `False` | Skip submission stage |
| `min_score` | `int` | `60` | Minimum relevance score (0-100) |
| `scam_threshold` | `float` | `0.7` | Scam detection threshold (0-1) |
| `max_jobs_to_present` | `int` | `20` | Max jobs to present for selection |

**Methods:**

- `run(start_from, stop_at)` - Run the pipeline
- `register_before_hook(stage, hook)` - Register pre-stage callback
- `register_after_hook(stage, hook)` - Register post-stage callback

#### PipelineResult

Result of pipeline execution.

```python
result = orchestrator.run()

# Access properties
result.success           # bool: Overall success
result.stages_completed  # List[str]: Completed stage names
result.duration_seconds  # float: Pipeline duration
result.jobs_scraped      # int: Number of jobs scraped
result.jobs_applied      # int: Number of jobs applied
```

## Profile API

Base URL: `http://localhost:8000/api/profile`

Endpoints for resume upload, active profile management, resume analysis, and LinkedIn profile analysis.

### Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/profile/upload` | Upload and parse a PDF/DOCX resume |
| GET | `/api/profile/` | Get the current active profile |
| PUT | `/api/profile/` | Update the active profile |
| GET | `/api/profile/export` | Export the active profile as JSON |
| POST | `/api/profile/analyze` | Analyze a resume (general or job-specific) |
| POST | `/api/profile/analyze-linkedin` | Analyze a LinkedIn profile for inbound attraction |
| POST | `/api/profile/search-linkedin` | Search LinkedIn people by keywords, name, title, company, or location |

#### POST /api/profile/upload

Upload a resume file. Returns a profile ID and resume path.

```bash
curl -s -X POST http://localhost:8000/api/profile/upload \
  -F "file=@/path/to/resume.pdf"
```

**Response:**
```json
{
  "profile_id": "profile_abc123",
  "resume_path": "apps/backend-py/data/profiles/profile_abc123.pdf",
  "message": "Resume uploaded and parsed successfully"
}
```

#### GET /api/profile/

Returns the active profile with contact info, skills, experience, education, etc.

```bash
curl -s http://localhost:8000/api/profile/ | jq .
```

#### PUT /api/profile/

Update fields of the active profile.

```bash
curl -s -X PUT http://localhost:8000/api/profile/ \
  -H "Content-Type: application/json" \
  -d '{"name": "Jane Doe", "target_keywords": ["python", "fastapi"]}'
```

**Response:**
```json
{
  "message": "Profile updated successfully"
}
```

#### GET /api/profile/export

Export the active profile as JSON.

```bash
curl -s http://localhost:8000/api/profile/export | jq .
```

#### POST /api/profile/analyze

Analyze a resume. Provide an optional `job_description` form field for job-specific analysis.

```bash
curl -s -X POST http://localhost:8000/api/profile/analyze \
  -F "file=@/path/to/resume.pdf" \
  -F "job_description=Senior Python Engineer with FastAPI experience"
```

**Response:** Resume analysis with `overall_score`, `key_strengths`, `key_improvements`, `skills_assessment`, `experience_insights`, etc.

#### POST /api/profile/analyze-linkedin

Analyze a LinkedIn profile for inbound attraction. Accepts a LinkedIn profile URL, raw text, structured fields, or any combination of the three. At least one of `profile_url`, `raw_text`, or a structured field must be provided.

When `profile_url` is supplied and the backend has LinkedIn credentials (`LINKEDIN_EMAIL` and `LINKEDIN_PASSWORD`), the profile content is fetched automatically and merged into the raw text sent to the analyzer.

```bash
curl -s -X POST http://localhost:8000/api/profile/analyze-linkedin \
  -H "Content-Type: application/json" \
  -d '{
    "profile_url": "https://www.linkedin.com/in/janedoe",
    "raw_text": "Senior Software Engineer at Acme...",
    "headline": "Senior Software Engineer | Python | FastAPI",
    "summary": "I build scalable backend systems...",
    "experience_entries": [
      {"title": "Senior Software Engineer", "company": "Acme", "description": "Built APIs..."}
    ],
    "education_entries": [
      {"school": "State University", "degree": "BS", "field": "Computer Science"}
    ],
    "skills": ["Python", "FastAPI", "PostgreSQL"],
    "industry": "Software Engineering",
    "career_goals": "Staff engineer role in fintech",
    "target_roles": ["Staff Software Engineer", "Senior Backend Engineer"]
  }'
```

**Response:**
```json
{
  "overall_score": 72,
  "summary": "The profile has solid technical signals...",
  "section_scores": [
    {
      "section_name": "Headline",
      "score": 80,
      "weight": 0.15,
      "feedback": "Add a concrete specialty or outcome."
    }
  ],
  "insights": [
    {
      "category": "keywords",
      "observation": "Top skills are listed but not repeated in the summary.",
      "recommendation": "Weave target keywords naturally into the About section.",
      "priority": "high"
    }
  ],
  "keyword_recommendations": ["fintech", "distributed systems", "system design"],
  "action_plan": ["Rewrite headline to include target role", "Expand About section"],
  "generated_headline_options": ["Senior Backend Engineer | Fintech | Python"],
  "summary_rewrite_suggestions": ["..."],
  "competitive_edge": "Strong open-source presence...",
  "is_strong_profile": true,
  "high_priority_insights": [],
  "weighted_overall_score": 74.2,
  "metadata": {},
  "analyzed_at": "2026-06-27T12:00:00"
}
```

#### POST /api/profile/search-linkedin

Search LinkedIn people by keywords, name, title, company, or location. Requires `LINKEDIN_EMAIL` and `LINKEDIN_PASSWORD` to be configured. Returns an empty result set with HTTP 503 if LinkedIn credentials or the authenticated session are unavailable.

```bash
curl -s -X POST http://localhost:8000/api/profile/search-linkedin \
  -H "Content-Type: application/json" \
  -d '{
    "keywords": "software engineer",
    "name": "Jane",
    "title": "Senior Engineer",
    "company": "Acme",
    "location": "San Francisco",
    "limit": 10
  }' | jq .
```

**Response:**
```json
{
  "query": {
    "keywords": "software engineer",
    "name": "Jane",
    "title": "Senior Engineer",
    "company": "Acme",
    "location": "San Francisco"
  },
  "total": 2,
  "results": [
    {
      "name": "Jane Doe",
      "headline": "Senior Software Engineer at Acme",
      "profile_url": "https://www.linkedin.com/in/janedoe",
      "location": "San Francisco, CA"
    },
    {
      "name": "Jane Smith",
      "headline": "Engineering Manager",
      "profile_url": "https://www.linkedin.com/in/janesmith",
      "location": null
    }
  ]
}
```

### Type Definitions

See the [Type Definitions](#type-definitions) section below for `LinkedInProfileInput`, `LinkedInProfileAnalysis`, `ProfileSectionScore`, `InboundAttractionInsight`, `LinkedInPeopleSearchInput`, `LinkedInPeopleSearchResult`, and `LinkedInPeopleSearchResponse`.

### Data Models

#### JobListing

Represents a job listing.

```python
import sys
sys.path.insert(0, 'backend-py')

from src.models.job_listing import JobListing, JobSource, ExperienceLevel

job = JobListing(
    title="Senior Python Engineer",
    company="Tech Corp",
    location="San Francisco, CA",
    description="Job description...",
    requirements=["Python", "Django"],
    responsibilities=["Build APIs"],
    skills=["python", "django", "postgresql"],
    source=JobSource.LINKEDIN,
    source_url="https://linkedin.com/jobs/...",
)
```

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `title` | `str` | Job title |
| `company` | `str` | Company name |
| `location` | `str` | Job location |
| `description` | `Optional[str]` | Full job description |
| `requirements` | `List[str]` | Job requirements |
| `responsibilities` | `List[str]` | Job responsibilities |
| `skills` | `List[str]` | Required skills |
| `salary_range` | `Optional[SalaryRange]` | Salary information |
| `source` | `JobSource` | Job source |
| `source_url` | `Optional[HttpUrl]` | Source URL |

#### UserProfile

Represents user profile and qualifications.

```python
from src.models.user_profile import (
    UserProfile,
    ContactInfo,
    TargetJob,
    Skill,
    SkillCategory,
    ProficiencyLevel,
)

profile = UserProfile(
    contact_info=ContactInfo(
        name="John Doe",
        email="john@example.com",
        phone="555-1234",
    ),
    skills={
        SkillCategory.PROGRAMMING: [
            Skill(name="Python", proficiency=ProficiencyLevel.EXPERT),
        ],
    },
    target_job=TargetJob(
        keywords=["python", "engineer"],
        locations=["remote", "san francisco"],
        experience_levels=[ExperienceLevel.MID, ExperienceLevel.SENIOR],
    ),
)
```

#### MatchScore

Relevance score for a job listing.

```python
from src.scoring.matcher import MatchScore

score = MatchScore(
    total_score=75,
    keyword_score=25,
    skills_score=30,
    experience_score=15,
    location_score=5,
    details={
        "matched_keywords": ["python", "engineer"],
        "matched_skills": ["python", "django"],
    },
)
```

### Scrapers

#### ScraperManager

Manages parallel job scraping.

```python
from src.scrapers.manager import ScraperManager

manager = ScraperManager()
listings = manager.search_all(
    keywords=["python", "engineer"],
    locations=["remote"],
    sources=["linkedin", "jsearch"],
)
```

**Methods:**

- `search_all(keywords, locations, sources)` - Search all sources
- `search_source(source, keywords, locations)` - Search single source

### Scoring

#### JobMatcher

Scores job relevance against user profile.

```python
from src.scoring.matcher import JobMatcher

matcher = JobMatcher()
score = matcher.match_and_score(
    job=job_listing,
    user_profile=user_profile,
)
```

**Scoring Breakdown:**

| Category | Points | Max |
|----------|--------|-----|
| Keywords | Variable | 30 |
| Skills | Variable | 40 |
| Experience | Fixed | 20 |
| Location | Fixed | 10 |
| **Total** | | **100** |

#### JobScamDetector

Detects potential job scams.

```python
from src.scoring.scam_detector import JobScamDetector, ScamReport

detector = JobScamDetector(threshold=0.7)
report = detector.detect(job_listing)

# Check result
report.is_scam        # bool: Is this a scam?
report.confidence     # float: Confidence (0-1)
report.indicators     # List[ScamIndicator]: Detected indicators
report.reasons        # List[str]: Human-readable reasons
report.risk_score     # int: Risk score (0-100)
```

**Scam Indicators:**

| Indicator | Weight | Description |
|-----------|--------|-------------|
| `PAYMENT_REQUIRED` | 50 | Requests payment to work |
| `PERSONAL_EMAIL` | 20 | Uses personal email domain |
| `MESSAGING_APP_ONLY` | 40 | Contact only via messaging apps |
| `UNREALISTIC_SALARY` | 40 | Unrealistic compensation |
| `FAKE_COMPANY` | 30 | Suspicious company name |

### Generation

#### ResumeSelector

Selects relevant content for resume (small model).

```python
from src.generation.selector import ResumeSelector

selector = ResumeSelector()
output = selector.select(
    job_description=job.description,
    user_profile=user_profile,
)

# Access results
output.selected_projects    # List[Project]: 3 most relevant projects
output.target_keywords     # List[str]: 5 keywords to emphasize
output.achievements        # List[str]: Suggested achievements
```

#### ResumeWriter

Generates tailored resume (large model).

```python
from src.generation.resume_writer import ResumeWriter

writer = ResumeWriter()
resume = writer.write(
    job=job_listing,
    user_profile=user_profile,
    selection_output=selection_output,
)

# Access sections
resume.summary         # str: Professional summary
resume.experience      # List[WorkExperience]: Tailored experience
resume.projects        # List[Project]: Tailored projects
resume.skills          # List[str]: Relevant skills
```

#### ResumeValidator

Validates generated resumes.

```python
from src.generation.validator import ResumeValidator

validator = ResumeValidator()
result = validator.validate(
    generated_resume=resume,
    selection_output=selection_output,
    user_profile=user_profile,
)

# Check result
result.is_valid           # bool: Is resume valid?
result.score             # int: Validation score (0-100)
result.issues            # List[ValidationIssue]: Validation issues
result.recommendation     # str: Recommendation
```

**Validation Checks:**

1. All selected projects present
2. All keywords mentioned
3. No fabricated skills
4. Date consistency
5. No hallucinated experience

### Submission

#### AutoSubmitDetector

Detects auto-submit opportunities.

```python
from src.submission.detector import AutoSubmitDetector, SubmissionInfo

detector = AutoSubmitDetector()
info = detector.detect_submission_method(
    job=job_listing,
    html=html_content,  # Optional
)

# Check result
info.can_auto_submit     # bool: Can auto-submit?
info.apply_method        # ApplyMethod: Application method
info.apply_url           # Optional[str]: Application URL
info.requirements        # List[str]: Requirements
info.estimated_time_minutes  # int: Estimated time
```

**Apply Methods:**

| Method | Description | Auto-Submit |
|--------|-------------|-------------|
| `EASY_APPLY` | Platform quick apply | Yes |
| `EXTERNAL_SITE` | External ATS | No |
| `EMAIL` | Email application | No |
| `MANUAL` | Manual process | No |

#### AutoSubmitter

Handles automated submissions.

```python
from src.submission.submitter import AutoSubmitter, SubmissionStatus

submitter = AutoSubmitter(
    dry_run=True,
    delay_between_submissions=2.0,
    max_submissions_per_hour=30,
)

# Submit single job
result = submitter.submit(
    info=submission_info,
    user_profile=user_profile,
)

# Check result
result.status          # SubmissionStatus: PENDING/IN_PROGRESS/SUBMITTED/FAILED/SKIPPED
result.success         # bool: Was submission successful?
result.submission_id   # Optional[str]: Submission ID
result.error_message   # Optional[str]: Error message

# Batch submit
results = submitter.submit_batch(
    submission_info=[info1, info2, ...],
)

# Get statistics
stats = submitter.get_submission_stats()
```

#### ApplicationTracker

Tracks application outcomes.

```python
from src.submission.submitter import ApplicationTracker

tracker = ApplicationTracker(storage_dir="data/applications")

# Track new application
app_id = tracker.track_application(
    job=job_listing,
    submission_id="sub_123",
    generated_resume_path="/path/to/resume.pdf",
)

# Update status
tracker.update_status(
    app_id=app_id,
    status="applied",
    interview_status="screening_scheduled",
    note="Phone screen next Tuesday",
)

# Get application
app = tracker.get_application(app_id)

# Get statistics
stats = tracker.get_stats()
```

### Utilities

#### Cache Manager

Caches LLM responses to avoid redundant calls.

```python
from src.utils.cache import ResponseCache

cache = ResponseCache(
    backend="file",  # or "memory"
    ttl_seconds=3600,
)

# Generate with caching
response = cache.get_or_generate(
    key="unique_key",
    generator=lambda: llm_client.generate(messages),
)
```

#### Logger

Structured logging with component-specific loggers.

```python
from src.utils.logger import get_logger, Components

logger = get_logger(Components.SCRAPERS)

logger.info("Scraping jobs...")
logger.warning("Rate limit reached")
logger.error("Scraping failed", exc_info=True)
```

**Components:**

- `SCRAPERS` - Job scraping activities
- `SCORING` - Job matching and scoring
- `GENERATION` - Resume generation
- `SUBMISSION` - Application submission
- `LLM` - LLM client operations

## Type Definitions

### Enums

```python
# Job Source
class JobSource(str, Enum):
    LINKEDIN = "linkedin"
    INDEED = "indeed"
    GLASSDOOR = "glassdoor"
    JSEARCH = "jsearch"
    MANUAL = "manual"

# Experience Level
class ExperienceLevel(str, Enum):
    ENTRY = "entry"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"
    EXECUTIVE = "executive"

# Job Type
class JobType(str, Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"

# Work Mode
class WorkMode(str, Enum):
    ONSITE = "onsite"
    REMOTE = "remote"
    HYBRID = "hybrid"

# Submission Status
class SubmissionStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    FAILED = "failed"
    SKIPPED = "skipped"
```

#### LinkedInProfileInput

Input data for LinkedIn profile analysis. Accepts a LinkedIn profile URL, raw pasted text, structured fields, or any combination of the three. At least one of `profile_url`, `raw_text`, or a structured field must be provided.

```python
from src.models.linkedin_analysis import LinkedInProfileInput

input_data = LinkedInProfileInput(
    profile_url="https://www.linkedin.com/in/janedoe",
    raw_text="Senior Software Engineer at Acme...",
    headline="Senior Software Engineer | Python | FastAPI",
    summary="I build scalable backend systems...",
    experience_entries=[...],
    education_entries=[...],
    skills=["Python", "FastAPI", "PostgreSQL"],
    industry="Software Engineering",
    career_goals="Staff engineer role in fintech",
    target_roles=["Staff Software Engineer", "Senior Backend Engineer"],
)
```

| Field | Type | Description |
|-------|------|-------------|
| `profile_url` | `Optional[str]` | LinkedIn profile URL to fetch and analyze |
| `raw_text` | `Optional[str]` | Raw pasted LinkedIn profile text |
| `headline` | `Optional[str]` | Current LinkedIn headline |
| `summary` | `Optional[str]` | LinkedIn About / summary section |
| `experience_entries` | `List[Dict[str, Any]]` | Experience entries (title, company, description, dates) |
| `education_entries` | `List[Dict[str, Any]]` | Education entries (school, degree, field, dates) |
| `skills` | `List[str]` | Skills listed on the profile |
| `industry` | `Optional[str]` | Industry or field of work |
| `career_goals` | `Optional[str]` | Stated career goals or aspirations |
| `target_roles` | `List[str]` | Target job titles or roles |

#### ProfileSectionScore

Score and feedback for a specific LinkedIn profile section.

```python
from src.models.linkedin_analysis import ProfileSectionScore

section = ProfileSectionScore(
    section_name="Headline",
    score=80,
    weight=0.15,
    feedback="Add a concrete specialty or outcome.",
)
```

| Field | Type | Description |
|-------|------|-------------|
| `section_name` | `str` | Name of the profile section |
| `score` | `float` | Section score (0-100) |
| `weight` | `float` | Section weight in overall score (0-1) |
| `feedback` | `str` | Actionable improvement feedback |

#### InboundAttractionInsight

Prioritized insight for improving inbound recruiter attraction.

```python
from src.models.linkedin_analysis import InboundAttractionInsight

insight = InboundAttractionInsight(
    category="keywords",
    observation="Top skills are listed but not repeated in the summary.",
    recommendation="Weave target keywords naturally into the About section.",
    priority="high",
)
```

| Field | Type | Description |
|-------|------|-------------|
| `category` | `str` | Insight category (e.g., headline, keywords, content) |
| `observation` | `str` | Observed profile weakness or strength |
| `recommendation` | `str` | Specific recommendation |
| `priority` | `Literal["critical", "high", "medium", "low"]` | Priority level |

#### LinkedInProfileAnalysis

Complete LinkedIn profile analysis result.

```python
from src.models.linkedin_analysis import LinkedInProfileAnalysis

analysis = LinkedInProfileAnalysis(
    overall_score=72,
    summary="The profile has solid technical signals...",
    section_scores=[...],
    insights=[...],
    keyword_recommendations=[...],
    action_plan=[...],
    generated_headline_options=[...],
    summary_rewrite_suggestions=[...],
    competitive_edge="Strong open-source presence...",
)
```

| Field | Type | Description |
|-------|------|-------------|
| `analyzed_at` | `datetime` | When the analysis was performed |
| `overall_score` | `float` | Overall profile strength (0-100) |
| `summary` | `str` | Executive summary |
| `section_scores` | `List[ProfileSectionScore]` | Per-section scores and feedback |
| `insights` | `List[InboundAttractionInsight]` | Prioritized insights |
| `keyword_recommendations` | `List[str]` | Keywords to add or emphasize |
| `action_plan` | `List[str]` | Step-by-step improvement plan |
| `generated_headline_options` | `List[str]` | Suggested headline options |
| `summary_rewrite_suggestions` | `List[str]` | Suggested About-section rewrites |
| `competitive_edge` | `str` | Competitive positioning assessment |
| `metadata` | `Dict[str, Any]` | Additional metadata |

**Properties:**
- `is_strong_profile` — `True` when `overall_score >= 70`
- `high_priority_insights` — Insights with `priority == "high"`
- `weighted_overall_score` — Weighted average of `section_scores`

#### LinkedInPeopleSearchInput

Input data for LinkedIn people search. Any combination of the optional fields may be provided; the backend builds a single keywords query from the non-empty values.

```python
from src.models.linkedin_analysis import LinkedInPeopleSearchInput

input_data = LinkedInPeopleSearchInput(
    keywords="software engineer",
    name="Jane",
    title="Senior Software Engineer",
    company="Acme",
    location="San Francisco",
    limit=10,
)
```

| Field | Type | Description |
|-------|------|-------------|
| `keywords` | `Optional[str]` | General keywords to include in the search |
| `name` | `Optional[str]` | Person's name (first, last, or full) |
| `title` | `Optional[str]` | Job title to search for |
| `company` | `Optional[str]` | Current or past company name |
| `location` | `Optional[str]` | Geographic location |
| `limit` | `int` | Maximum number of results to return (1–50, default 10) |

#### LinkedInPeopleSearchResult

A single result returned by LinkedIn people search.

```python
from src.models.linkedin_analysis import LinkedInPeopleSearchResult

result = LinkedInPeopleSearchResult(
    name="Jane Doe",
    headline="Senior Software Engineer at Acme",
    profile_url="https://www.linkedin.com/in/janedoe",
    location="San Francisco, CA",
)
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Full name of the person |
| `headline` | `str` | LinkedIn headline / current title |
| `profile_url` | `str` | Direct URL to the LinkedIn profile |
| `location` | `Optional[str]` | Location if visible on the result card |

#### LinkedInPeopleSearchResponse

Wrapper for a LinkedIn people search response.

```python
from src.models.linkedin_analysis import LinkedInPeopleSearchResponse

response = LinkedInPeopleSearchResponse(
    query={"keywords": "software engineer"},
    total=1,
    results=[result],
)
```

| Field | Type | Description |
|-------|------|-------------|
| `query` | `Dict[str, Any]` | Query parameters used for the search |
| `total` | `int` | Number of results returned |
| `results` | `List[LinkedInPeopleSearchResult]` | List of matching people |

### Data Classes

```python
@dataclass
class SalaryRange:
    min_amount: Optional[float]
    max_amount: Optional[float]
    currency: str = "USD"
    period: str = "annual"  # hourly, monthly, annual

@dataclass
class ContactInfo:
    name: str
    email: str
    phone: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None

@dataclass
class Skill:
    name: str
    proficiency: ProficiencyLevel
    years_experience: Optional[float] = None
```

## Error Handling

### Exceptions

```python
# Scraping errors
class ScrapingError(Exception):
    """Raised when scraping fails."""

# LLM errors
class LLMError(Exception):
    """Raised when LLM call fails."""

class LLMRateLimitError(LLMError):
    """Raised when rate limit is hit."""

# Validation errors
class ValidationError(Exception):
    """Raised when validation fails."""

# Submission errors
class SubmissionError(Exception):
    """Raised when submission fails."""
```

### Example Error Handling

```python
from src.pipeline.orchestrator import PipelineOrchestrator

try:
    orchestrator = PipelineOrchestrator(config, profile)
    result = orchestrator.run()

    if not result.success:
        # Handle partial failure
        for stage_name, stage_result in result.stage_results.items():
            if not stage_result.success:
                print(f"{stage_name} failed: {stage_result.error_message}")

except ScrapingError as e:
    print(f"Scraping failed: {e}")
except LLMError as e:
    print(f"LLM error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## Settings Management API

### Overview

The Settings API provides endpoints for configuring model routing, API credentials, and application parameters through a RESTful interface.

### Base URL

```
http://localhost:8000/api/settings/
```

### Endpoints

#### GET /api/settings/

Get current user settings including model routing, API configuration, and parameters.

**Response:**
```json
{
  "routing": {
    "selection": {
      "task_type": "selection",
      "primary_provider": "ollama",
      "primary_model": "qwen2.5:3b",
      "fallback_provider": "anthropic",
      "fallback_model": "claude-haiku-4-5-20251001"
    }
  },
  "api_config": {
    "anthropic_api_key": null,
    "ollama_host": "localhost:11434"
  },
  "model_params": {
    "temperature": 0.7,
    "max_tokens": 4096,
    "top_p": 0.9,
    "top_k": 40
  },
  "cost_limits": {
    "max_api_cost_per_run": 5.0,
    "enable_cache": true,
    "cache_ttl": 3600,
    "max_concurrent_requests": 2
  },
  "updated_at": "2026-04-24T12:00:00",
  "version": "1.0"
}
```

#### PUT /api/settings/

Update user settings. Settings are persisted to `data/settings.json` and apply to new pipeline runs.

**Request Body:**
```json
{
  "routing": {
    "selection": {
      "task_type": "selection",
      "primary_provider": "ollama",
      "primary_model": "qwen2.5:3b",
      "fallback_provider": "anthropic",
      "fallback_model": "claude-haiku-4-5-20251001"
    }
  },
  "api_config": {
    "anthropic_api_key": "sk-ant-xxx",
    "ollama_host": "localhost:11434"
  },
  "model_params": {
    "temperature": 0.8,
    "max_tokens": 8192
  }
}
```

**Response:** Updated UserSettings object

#### POST /api/settings/reset

Reset all settings to default values.

**Response:** Default UserSettings object

#### GET /api/settings/models

Get list of available models by provider.

**Response:**
```json
{
  "anthropic": [
    "claude-sonnet-4-6",
    "claude-opus-4-7",
    "claude-haiku-4-5-20251001"
  ],
  "ollama": [
    "qwen2.5:3b",
    "qwen2.5:7b",
    "gemma3:4b",
    "gemma3:12b"
  ]
}
```

#### POST /api/settings/validate

Validate settings without saving them.

**Request Body:** UserSettings object

**Response:**
```json
{
  "valid": true,
  "errors": [],
  "warnings": []
}
```

#### GET /api/settings/config/merged

Get merged configuration (YAML defaults + user settings).

**Response:** Merged configuration dictionary used by the application

### Settings Model Reference

#### UserSettings

Main settings container.

| Field | Type | Description |
|-------|------|-------------|
| `routing` | Dict[str, ModelRouting] | Model routing per task type |
| `api_config` | APIConfig | API and service configuration |
| `model_params` | ModelParameters | Default generation parameters |
| `cost_limits` | CostLimits | Cost and usage limits |
| `updated_at` | datetime | Last update timestamp |
| `version` | str | Settings schema version |

#### ModelRouting

Configuration for a single task type.

| Field | Type | Description |
|-------|------|-------------|
| `task_type` | str | Task identifier (selection, scoring, etc.) |
| `primary_provider` | Provider | Primary provider to use |
| `primary_model` | str | Model name for primary |
| `fallback_provider` | Provider | Fallback provider |
| `fallback_model` | str | Model name for fallback |

#### APIConfig

API and service configuration.

| Field | Type | Description |
|-------|------|-------------|
| `anthropic_api_key` | str \| null | Anthropic API key |
| `ollama_host` | str | Ollama service host:port |

#### ModelParameters

Generation parameters.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `temperature` | float | 0.7 | Generation temperature (0.0-2.0) |
| `max_tokens` | int | 4096 | Maximum tokens to generate |
| `top_p` | float | 0.9 | Nucleus sampling (0.0-1.0) |
| `top_k` | int | 40 | Top-k sampling (1-100) |

#### CostLimits

Cost and usage limits.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_api_cost_per_run` | float | 5.0 | Maximum API cost per run (USD) |
| `enable_cache` | bool | true | Enable response caching |
| `cache_ttl` | int | 3600 | Cache TTL in seconds |
| `max_concurrent_requests` | int | 2 | Max concurrent LLM requests |

### Example Usage

```python
from src.api.client import APIClient

client = APIClient()

# Get current settings
settings = client.get_settings()

# Update Anthropic API key
settings["api_config"]["anthropic_api_key"] = "sk-ant-xxx"
updated = client.update_settings(settings)

# Validate before saving
result = client.validate_settings(settings)
if result["valid"]:
    print("Settings are valid!")
else:
    for error in result["errors"]:
        print(f"Error: {error}")

# Reset to defaults
defaults = client.reset_settings()

# Get available models
models = client.get_available_models()
print(f"Available Anthropic models: {models['anthropic']}")
```

### Applications API

Base URL: `http://localhost:8001/api/applications`

#### Job Actions

Perform quick actions on jobs (save, hide, etc.).

**Endpoint:** `POST /api/applications/actions`

**Request Body:**

```json
{
  "job_id": "string",
  "action": "save | unsave | hide | unhide",
  "note": "string (optional)",
  "metadata": {
    "title": "string",
    "company": "string",
    "source_url": "string"
  }
}
```

**Response:**

```json
{
  "success": true,
  "job_id": "string",
  "action": "string",
  "new_status": "string",
  "message": "string"
}
```

**Actions:**
- `save` - Save/bookmark a job for later
- `unsave` - Remove bookmark from job
- `hide` - Mark job as not interested (hides from results)
- `unhide` - Unhide a previously hidden job

#### Track External Application

Track an application made outside the system (e.g., via company website or referral).

**Endpoint:** `POST /api/applications/external`

**Request Body:**

```json
{
  "job_id": "string",
  "job_title": "string",
  "company": "string",
  "application_date": "string (ISO format, optional)",
  "application_method": "manual | referral | recruiter",
  "metadata": {}
}
```

**Response:**

```json
{
  "success": true,
  "application_id": "string",
  "status": "applied_elsewhere",
  "message": "External application tracked successfully"
}
```

#### Custom Statuses

Create and manage custom application statuses.

**Create Custom Status:** `POST /api/applications/statuses/custom`

**Request Body:**

```json
{
  "name": "Waiting for Feedback",
  "description": "Applied and waiting for response",
  "color": "#FFA500",
  "icon": "clock"
}
```

**Response:**

```json
{
  "status_id": "string",
  "name": "string",
  "description": "string",
  "color": "string",
  "icon": "string | null",
  "is_active": true,
  "created_at": "datetime",
  "usage_count": 0
}
```

**List Custom Statuses:** `GET /api/applications/statuses/custom?active_only=true`

Returns array of `CustomStatusResponse` objects.

**Set Custom Status on Application:** `POST /api/applications/statuses/set`

**Request Body:**

```json
{
  "job_id": "string",
  "custom_status_id": "string",
  "note": "string (optional)"
}
```

#### Update Application Status

Update the status of any tracked application.

**Endpoint:** `PUT /api/applications/status`

**Request Body:**

```json
{
  "job_id": "string",
  "status": "applied | under_review | screening_scheduled | ...",
  "note": "string (optional)"
}
```

**Available Statuses:**
- `applied` - Application submitted
- `under_review` - Being reviewed by employer
- `screening_scheduled`, `screening_completed` - Screening interviews
- `technical_scheduled`, `technical_completed` - Technical interviews
- `onsite_scheduled`, `onsite_completed` - Onsite interviews
- `offer_received`, `offer_accepted`, `offer_declined` - Offer stages
- `rejected`, `withdrawn` - Application ended
- `saved_bookmarked` - Saved for later
- `applied_elsewhere` - Applied outside system
- `not_interested` - Hidden from results
- `custom` - User-defined status

#### Dashboard

Get application dashboard with filtering and summary statistics.

**Endpoint:** `GET /api/applications/dashboard`

**Query Parameters:**
- `status` (optional) - Filter by status
- `company` (optional) - Filter by company
- `days` (optional) - Filter by days since application
- `include_hidden` (default: false) - Include hidden jobs
- `include_bookmarked` (default: true) - Include bookmarked jobs
- `include_external` (default: true) - Include external applications

**Response:**

```json
{
  "applications": [
    {
      "application_id": "string",
      "job_title": "string",
      "company": "string",
      "applied_date": "datetime",
      "current_status": "string",
      "custom_status": {
        "status_id": "string",
        "name": "string",
        "description": "string",
        "color": "string"
      } | null,
      "is_bookmarked": true,
      "is_hidden": false,
      "final_outcome": "string | null",
      "interview_count": 0,
      "days_since_application": 5
    }
  ],
  "summary": {
    "total_applications": 10,
    "bookmarked": 3,
    "hidden": 2,
    "external": 1,
    "by_status": {
      "applied": 5,
      "under_review": 2,
      "saved_bookmarked": 3
    }
  },
  "custom_statuses": [
    {
      "status_id": "string",
      "name": "string",
      "description": "string",
      "color": "string",
      "icon": "string | null",
      "is_active": true,
      "created_at": "datetime"
    }
  ],
  "filters_applied": {
    "status": "applied",
    "company": "Tech Corp",
    "days": 30
  }
}
```

#### Application Details

Get detailed information for a specific application.

**Endpoint:** `GET /api/applications/{job_id}`

**Response:**

```json
{
  "application_id": "string",
  "job_title": "string",
  "company": "string",
  "applied_date": "datetime",
  "current_status": "string",
  "custom_status": {
    "status_id": "string",
    "name": "string",
    "description": "string",
    "color": "string",
    "icon": "string | null",
    "is_active": true,
    "created_at": "datetime"
  } | null,
  "is_bookmarked": true,
  "is_hidden": false,
  "external_application_details": {
    "application_method": "referral",
    "tracked_at": "datetime"
  } | null,
  "final_outcome": "offer | null",
  "interviews": [
    {
      "stage": "screening | technical | onsite",
      "scheduled_date": "datetime | null",
      "completed_date": "datetime | null",
      "feedback": "string | null",
      "outcome": "string | null"
    }
  ],
  "offer": {
    "salary_min": "number | null",
    "salary_max": "number | null",
    "salary_period": "annual",
    "bonus": "number | null",
    "benefits": ["string"],
    "notes": "string"
  } | null,
  "timeline_notes": [
    {
      "timestamp": "datetime",
      "note": "string"
    }
  ],
  "metadata": {}
}
```

### Example Usage

```python
from src.api.client import APIClient

client = APIClient()

# Save a job
response = client.perform_job_action(
    job_id="linkedin_12345",
    action="save",
    metadata={
        "title": "Software Engineer",
        "company": "Tech Corp",
        "source_url": "https://linkedin.com/jobs/view/12345"
    }
)
print(f"Job saved: {response['message']}")

# Track external application
response = client.track_external_application(
    job_id="ext_app_001",
    job_title="Senior Developer",
    company="Startup Inc",
    application_method="referral",
    application_date="2026-04-25"
)
print(f"Application tracked: {response['application_id']}")

# Create custom status
status = client.create_custom_status(
    name="Phone Screen Scheduled",
    description="HR screening call scheduled",
    color="#3B82F6"
)
print(f"Custom status created: {status['status_id']}")

# Get dashboard
dashboard = client.get_application_dashboard(
    include_hidden=False,
    include_bookmarked=True
)
print(f"Total applications: {dashboard['summary']['total_applications']}")
print(f"Bookmarked jobs: {dashboard['summary']['bookmarked']}")
```
