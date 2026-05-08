# Auto-Apply Feature Implementation Plan

## Phase 1: Foundation & User Profile Enrichment

### 1.1 User Profile Enhancement
**File:** `backend-py/src/models/user_profile.py`

Add new fields to support application questions:
```python
class UserProfile(BaseModel):
    # ... existing fields ...

    # Application-specific fields
    visa_status: Optional[str] = None  # "citizen", "h1b", "need_sponsorship"
    visa_expiration_date: Optional[datetime] = None
    salary_expectation_min: Optional[float] = None
    salary_expectation_max: Optional[float] = None
    salary_currency: str = "USD"
    notice_period_weeks: Optional[int] = None
    willing_to_relocate: bool = False
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    linkedin_url: Optional[str] = None
```

**Frontend:** Update profile page to collect this information

### 1.2 Question Answering Module
**New file:** `backend-py/src/submission/question_answerer.py`

```python
class QuestionType(str, Enum):
    VISA_SPONSORSHIP = "visa_sponsorship"
    SALARY_EXPECTATION = "salary_expectation"
    YEARS_EXPERIENCE = "years_experience"
    SKILL_CONFIRMATION = "skill_confirmation"
    NOTICE_PERIOD = "notice_period"
    RELOCATION = "relocation"
    WORK_AUTHORIZATION = "work_authorization"
    YES_NO = "yes_no"
    TEXT = "text"
    MULTIPLE_CHOICE = "multiple_choice"

@dataclass
class ApplicationQuestion:
    question_id: str
    question_text: str
    question_type: QuestionType
    options: Optional[List[str]] = None
    is_required: bool = True
    context: Optional[str] = None  # e.g., "for Python position"

class QuestionAnswerer:
    def answer_question(
        self,
        question: ApplicationQuestion,
        user_profile: UserProfile,
        job: JobListing
    ) -> str:
        """Generate appropriate answer based on profile and job"""
```

### 1.3 Application State Machine
**New file:** `backend-py/src/submission/state_machine.py`

```python
class ApplicationState(str, Enum):
    DETECTING = "detecting"
    PARSING_QUESTIONS = "parsing_questions"
    ANSWERING_QUESTIONS = "answering_questions"
    SUBMITTING = "submitting"
    SUBMITTED = "submitted"
    FAILED_NEEDS_REVIEW = "failed_needs_review"
    BLOCKED = "blocked"  # CAPTCHA, rate limit
    EXTERNAL_REDIRECT = "external_redirect"

@dataclass
class ApplicationProgress:
    job_id: str
    state: ApplicationState
    questions_answered: int
    total_questions: int
    current_step: str
    error_message: Optional[str] = None
    retry_count: int = 0
```

---

## Phase 2: Browser Automation Infrastructure

### 2.1 Playwright Integration
**New file:** `backend-py/src/submission/browser.py`

```python
class BrowserManager:
    """Manage Playwright browser instances for automation"""

    async def create_browser_context(
        self,
        user_data_dir: Optional[str] = None,
        cookies: Optional[Dict] = None
    ) -> BrowserContext:
        """Create authenticated browser context"""

    async def close_all(self):
        """Clean up browser resources"""

class FormAutomator:
    """Automate form filling on various platforms"""

    async def fill_linkedin_easy_apply(
        self,
        page: Page,
        job_url: str,
        answers: Dict[str, str]
    ) -> SubmissionResult:
        """Fill and submit LinkedIn Easy Apply form"""

    async def detect_questions(
        self,
        page: Page
    ) -> List[ApplicationQuestion]:
        """Parse application form questions"""
```

### 2.2 ATS Platform Detection
**New file:** `backend-py/src/submission/ats_detector.py`

```python
class ATSPlatform(str, Enum):
    GREENHOUSE = "greenhouse"        # greenhouse.io
    LEVER = "lever"                  # lever.co
    WORKDAY = "workday"              # myworkdayjobs.com
    ASHBY = "ashby"                  # ashbyhq.com
    BAMBOO_HR = "bamboo_hr"          # bamboohr.com
    SMARTRECRUITERS = "smartrecruiters"
    JOBVITE = "jobvite"
    ICIMS = "icims"
    CUSTOM = "custom"

class ATSDetector:
    def detect_platform(self, url: str, html: str) -> ATSPlatform:
        """Detect which ATS platform is being used"""

    def get_form_selector_map(
        self,
        platform: ATSPlatform
    ) -> Dict[str, str]:
        """Return CSS selectors for common form fields"""
```

### 2.3 LinkedIn Easy Apply Automation
**New file:** `backend-py/src/submission/linkedin_apply.py`

```python
class LinkedInEasyApply:
    """Automate LinkedIn Easy Apply submissions"""

    async def apply_to_job(
        self,
        job_url: str,
        profile: UserProfile,
        context: BrowserContext
    ) -> SubmissionResult:
        """Complete LinkedIn Easy Apply flow"""

    async def _parse_application_questions(
        self,
        page: Page
    ) -> List[ApplicationQuestion]:
        """Extract questions from Easy Apply modal"""

    async def _answer_questions(
        self,
        page: Page,
        questions: List[ApplicationQuestion],
        profile: UserProfile
    ) -> None:
        """Fill in question answers"""

    async def _submit_application(
        self,
        page: Page
    ) -> bool:
        """Click submit and verify success"""
```

---

## Phase 3: AI-Powered Question Answering

### 3.1 LLM Integration for Complex Questions
**New file:** `backend-py/src/submission/llm_answerer.py`

```python
class LLMQuestionAnswerer:
    """Use LLM to answer complex application questions"""

    async def answer_text_question(
        self,
        question: str,
        profile: UserProfile,
        job: JobListing,
        llm_client: BaseLLMClient
    ) -> str:
        """Generate answer for open-ended text questions"""

    def _build_answer_prompt(
        self,
        question: str,
        profile: UserProfile,
        job: JobListing
    ) -> str:
        """Build prompt for LLM to generate appropriate answer"""
```

### 3.2 Answer Templates and Rules
**New file:** `backend-py/src/submission/answer_rules.py`

```python
class AnswerRule:
    """Rule-based answer generation for common questions"""

    @staticmethod
    def answer_visa_question(profile: UserProfile) -> str:
        """Answer visa/sponsorship questions"""
        if profile.visa_status == "citizen":
            return "I am authorized to work in the US without sponsorship"
        elif profile.visa_status == "h1b":
            return "I have an H1B visa and do not require sponsorship"
        # etc.

    @staticmethod
    def answer_salary_question(
        profile: UserProfile,
        job: JobListing
    ) -> str:
        """Answer salary expectation questions"""
        # Use profile salary range or job salary range

    @staticmethod
    def answer_experience_question(
        question: str,
        profile: UserProfile
    ) -> str:
        """Answer years of experience questions"""
        # Parse question for skill name, find in profile
```

---

## Phase 4: External ATS Automation

### 4.1 Greenhouse Automation
**New file:** `backend-py/src/submission/ats_automation.py`

```python
class ATSFormFiller:
    """Automate form filling on various ATS platforms"""

    async def fill_greenhouse_form(
        self,
        url: str,
        profile: UserProfile,
        resume_path: str,
        context: BrowserContext
    ) -> SubmissionResult:
        """Fill and submit Greenhouse application"""

    async def fill_lever_form(
        self,
        url: str,
        profile: UserProfile,
        resume_path: str,
        context: BrowserContext
    ) -> SubmissionResult:
        """Fill and submit Lever application"""

    async def fill_workday_form(
        self,
        url: str,
        profile: UserProfile,
        resume_path: str,
        context: BrowserContext
    ) -> SubmissionResult:
        """Fill and submit Workday application"""
```

### 4.2 Resume Generation for ATS
**Enhancement:** `backend-py/src/generation/resume_generator.py`

```python
class TailoredResumeGenerator:
    """Generate ATS-optimized resumes for specific jobs"""

    def generate_for_ats(
        self,
        profile: UserProfile,
        job: JobListing,
        output_format: str = "pdf"
    ) -> str:
        """Generate resume tailored for job and ATS compatibility"""

    def _optimize_for_ats(
        self,
        resume_content: str,
        job_keywords: List[str]
    ) -> str:
        """Ensure resume is ATS-friendly (keywords, format, etc.)"""
```

---

## Phase 5: API Implementation

### 5.1 Apply Endpoint
**Update:** `backend-py/src/api/routes/jobs.py`

```python
@router.post("/{job_id}/apply")
async def apply_to_job(
    job_id: str,
    dry_run: bool = True,
    background_tasks: BackgroundTasks = None
):
    """
    Apply to a specific job.

    Handles both Easy Apply and external ATS applications.

    Args:
        job_id: Job ID
        dry_run: Simulate without actually submitting
        background_tasks: FastAPI background tasks for async processing

    Returns:
        Application result with status and next steps
    """
    # Implementation
```

### 5.2 Application Status Endpoint
**New endpoint:** `backend-py/src/api/routes/jobs.py`

```python
@router.get("/{job_id}/application/status")
async def get_application_status(job_id: str):
    """Get real-time status of in-progress application"""

@router.post("/{job_id}/application/retry")
async def retry_application(job_id: str):
    """Retry a failed application"""
```

---

## Phase 6: Frontend Integration

### 6.1 Application Modal
**New file:** `frontend-ts/src/components/application-modal.tsx`

```tsx
interface ApplicationModalProps {
  job: JobListing;
  profile: UserProfile;
  onApply: (result: ApplicationResult) => void;
  onCancel: () => void;
}

// Shows:
// - Detection progress
// - Questions found
// - Answers generated (editable)
// - Submit button
// - Real-time status updates
```

### 6.2 Application Status Indicator
**Update:** `frontend-ts/src/app/jobs/page.tsx`

```tsx
// Add visual indicator for application status:
// - Not applied
// - Applying (in progress)
// - Applied successfully
// - Needs review
// - Failed
```

---

## Priority Order

1. **Phase 1** - User profile enrichment ( foundational)
2. **Phase 2** - Browser automation infrastructure (foundational)
3. **Phase 3** - Question answering (core feature)
4. **Phase 5** - API endpoints (integration)
6. **Phase 6** - Frontend UI (user-facing)
7. **Phase 4** - External ATS automation (advanced feature)

---

## Technical Considerations

### Rate Limiting
- LinkedIn: ~15-30 applications/day max
- Delay between applications: 2-5 minutes
- Randomize timing to avoid detection

### Authentication
- Store LinkedIn cookies securely
- Implement session management
- Handle re-authentication flow

### CAPTCHA Handling
- Detect CAPTCHAs during automation
- Pause and notify user for manual intervention
- Implement retry after CAPTCHA solved

### Error Recovery
- Question parsing failures → mark for manual review
- Network errors → retry with exponential backoff
- Form validation errors → capture and report

### Data Privacy
- Encrypt stored credentials
- Secure cookie storage
- Clear sensitive data after use

---

## Dependencies to Add

```bash
# Backend
pip install playwright
playwright install chromium
pip install beautifulsoup4  # For HTML parsing
pip install pyppeteer  # Alternative to playwright

# Frontend (none needed - existing)
```
