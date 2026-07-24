# Job Raider - Documentation Index

## Overview

Job Raider is an automated job application pipeline that scrapes job listings from multiple platforms, scores relevance, generates tailored resumes, and automates submissions.

## Tech Stack

Job Raider combines an async Python backend, a local-first LLM strategy, and a modern React dashboard. For a detailed breakdown of why each technology is used, see the canonical [Tech Stack](architecture.md#tech-stack) section in the architecture guide.

| Layer | Purpose | Key Technologies |
|-------|---------|------------------|
| Backend API | Async web framework and validation | Python 3.11+, FastAPI 0.115+, Uvicorn 0.30+, Pydantic 2.5+ |
| Data | ORM, migrations, vector store, and storage | SQLAlchemy 2.0+, Alembic 1.13+, asyncpg 0.29+, Supabase 2.4+, pgvector 0.2+, ChromaDB 1.0+ |
| LLMs | Local and cloud model providers | Ollama, Anthropic API, Google GenAI |
| Scraping & Documents | Browser automation and file parsing | Playwright 1.40+, BeautifulSoup4 4.12+, pypdf 4.0+, python-docx 1.1+, reportlab 4.0+ |
| Frontend | Dashboard framework and styling | Next.js 16.2.4, React 19.2.4, TypeScript 5, Tailwind CSS 4, shadcn/ui 4.5.0 |
| Frontend Libraries | State, forms, validation, and charts | TanStack Query 5.100.5, React Hook Form 7.74.0, Zod 4.3.6, Recharts 3.8.1 |
| Operations | Containers, experiment tracking, and monitoring | Docker, Docker Compose, MLflow 2.0+, Sentry SDK 1.40+ |
| Testing | Backend, frontend unit, and E2E tests | pytest 8.0+, Vitest 1.0+, Playwright 1.40+ |

## Documentation

### Getting Started

- **[Architecture](architecture.md)** - System architecture, component design, and data flow
- **[Usage Guide](usage.md)** - Installation, CLI usage, and examples
- **[Tech Stack](architecture.md#tech-stack)** - Languages, frameworks, and key dependencies
- **[API Reference](api.md)** - Complete API documentation
- **[Troubleshooting](troubleshooting.md)** - Common issues and solutions

## Quick Links

### For Users

- [Installation Guide](usage.md#installation)
- [Quick Start](usage.md#quick-start)
- [CLI Options](usage.md#command-line-options)
- [Usage Examples](usage.md#usage-examples)

### For Developers

- [Architecture Overview](architecture.md#overview)
- [Component Architecture](architecture.md#component-architecture)
- [API Documentation](api.md#core-modules)
- [Type Definitions](api.md#type-definitions)

### For Operators

- [Deployment](architecture.md#deployment-architecture)
- [Monitoring](troubleshooting.md#logging-and-debugging)
- [Performance Tuning](troubleshooting.md#performance-issues)
- [Docker Storage Guide](docker-storage.md)
- [Shared MLflow Setup](mlflow-setup.md)

## Key Concepts

### Two-Model Architecture

Job Raider uses a cost-optimized two-model approach:

1. **Small Model (recommended: qwen2.5:3b)** - Selection and scoring
2. **Large Model (recommended: qwen2.5:7b)** - Resume writing, analysis, and parsing

This reduces API costs by 80% while maintaining quality. Settings can assign any installed Ollama models to these tiers (including models on a shared desktop Ollama service); documented recommendations remain 3b / 7b.

### Resume Analysis

The dashboard includes an AI-powered resume analysis feature that:
- Parses resumes in any format using LLM-based extraction
- Builds structured skills, experience, and project data from parsed content
- Provides qualitative scoring, summaries, and improvement recommendations
- Supports both general analysis and job-specific gap analysis

### Recent Updates (2026-07-23)

**UI/UX polish:** Shared page chrome (`PageHeader`, empty/error banners), honest Simulate Apply / Request Cancel labels, metrics outcomes aligned to API rates, Assessment limited to skill-based + DISC.

**Job preference targeting:** Editable Profile Job Targets (`experience_levels`, `exclude_internships`) with opt-in Use profile targets on Pipeline and Jobs (default off).

**Ollama model freedom of choice:** Settings small/large pickers from live Ollama tags; `POST /api/settings/ollama-defaults`; `create_router()` applies saved routing. Shared Ollama host supported via Settings.

### Recent Updates (Phase 44 - 2026-06-27)

This release rolls up the LinkedIn Profile Analyzer feature plus the frontend and code-review follow-ups that landed in Phases 42-44.

**LinkedIn Profile Analyzer (Phase 42):**
- New `POST /api/profile/analyze-linkedin` endpoint backed by `LinkedInAnalyzer`.
- Pydantic models: `LinkedInProfileInput`, `LinkedInProfileAnalysis`, `ProfileSectionScore`, `InboundAttractionInsight`.
- Frontend page at `/linkedin-analysis` with raw-text paste and structured-form input tabs.
- 24 unit tests in `apps/backend-py/tests/unit/test_linkedin_analyzer.py`.

**Frontend ESLint Cleanup (Phase 43):**
- Eliminated all remaining ESLint warnings across dashboard pages.
- Migrated from `watch` to `useWatch` in React Hook Form forms to avoid unnecessary re-renders.
- Type-check and lint gates are now stable.

**Code-Review Follow-up Fixes (Phase 44):**
- Robust LLM JSON extraction: markdown-fence stripping + brace balancing with string-literal awareness.
- Converted LinkedIn analyzer route to use an async module-level singleton via `_get_linkedin_analyzer()`.
- Restored missing `ExperienceSelector` filter wiring on the Jobs page.
- Refreshed documentation, `tasks/todo.md`, `tasks/lessons.md`, and `setup.sh`.

**Verification:**
- Backend: 409 passed, 2 skipped.
- Frontend: 28 Vitest unit tests + 20 Playwright E2E tests.

### Recent Updates (Phase 41 - 2026-06-16)

**Multi-Agent System (now wired and live):**
- The multi-agent system (`src/agents/`) was built in a prior session but had never been registered with the FastAPI app. This phase wires it in, fixes four latent bugs that had hidden because the module never imported, and documents it.
- **Architecture:** `AgentCoordinator` orchestrates specialized agents over an `AgentCommunicationBus`; `BaseAgent` defines the contract (Task, TaskResult, TaskType, AgentCapability). The first concrete agent is `CareerCoachAgent`.
- **9 REST endpoints** under `/api/agents/*` (status, performance, health, shutdown, career-analysis, gap-analysis, upskilling-roadmap, career-goals, recommendations), rate-limited via `src/api/rate_limiter.py`.
- **Startup:** initialized non-fatally in the app lifespan (`initialize_agent_system(LLMRouter())`); agent endpoints return 503 until the coordinator is ready, so the API always boots.
- **Config:** `apps/backend-py/config/agent_config.yaml` (coordinator, career-coach, communication settings).
- **Verification:** `GET /api/agents/status` returns 200 (coordinator running, communication healthy, 1 registered agent). Backend suite: 376 passed, 2 skipped.
- See [Architecture - Multi-Agent Layer](architecture.md#multi-agent-layer) and [Usage - Multi-Agent API](usage.md#multi-agent-api).

### Recent Updates (Phase 36 - 2026-06-07)

**UI/UX Overhaul + Fresh Graduate Features:**
- **Odysseus Design Theme** - Complete UI overhaul inspired by modern design patterns
  - Fira Code monospaced font for technical aesthetic
  - Red accent color (#e63946) for CTAs and highlights
  - Sharp card borders (4px radius) instead of rounded
  - Space-themed dark mode with neon effects (cyan, magenta, blue, gold glows)
  - Starfield background and gradient mesh overlays
  - Geometric corner accents with animated pulses
- **Theme Toggle System** - Light/dark mode switching
  - Toggle button in sidebar with Sun/Moon icons
  - System theme detection with manual override
  - Theme persistence across sessions
  - Fixed contrast issues in both themes (visible tab icons and text)
- **Fresh Graduate Scoring Mode** - Optimized for entry-level candidates
  - Projects (35%), Skills (30%), Education (20%), Experience (10%), Location (5%)
  - Lower threshold (50 vs 60) to increase opportunities
  - Dedicated weight configuration in `scoring_config.yaml`
  - `fresh_grad_mode` parameter in job search API
- **DISC Personality Assessment** - Industry-standard assessment format
  - Most/Least forced-choice format (24 questions across 4 categories)
  - Categories: Leadership, Communication, Work Style, Problem Solving
  - Backend engine with session generation, scoring, and job matching
  - Job profile matching (Software Engineer, Sales, PM, Data Analyst, Team Lead)
  - Question bank: `apps/backend-py/config/disc_questions.json`
  - Frontend component with two-column selection UI
- **Jobs Location Filtering** - Post-filter to ensure API results match requested location
  - Fixes issue where Singapore searches returned USA listings
  - Case-insensitive matching with location variation support
  - Logs filtering results for debugging
- **Jobs State Management Fix** - Fixed issue where search results disappeared after appearing
  - Fixed useEffect dependency array causing race conditions
  - Stable state management for search results persistence

### Recent Updates (Phase 35 - 2026-05-30)

**Shared Ollama Migration:**
- Migrated Ollama from project-specific to shared services container pattern
- Created `~/docker-services/docker-compose.yml` with Ollama and MLflow services
- Removed Ollama service from job-raider docker-compose.yml
- All projects now share one Ollama instance for GPU resource efficiency
- Model cache shared across all projects
- Consistent endpoints via `shared-services` Docker network
- Cleanup: Pruned 1.5GB of stale Docker images
- All services verified healthy and connected

### Recent Updates (Phase 34 - 2026-05-22)

**Cover Letter Generation + Technical Assessment Trainer:**
- Cover letter generation wired into job detail panel with copy-to-clipboard
- `POST /jobs/{job_id}/cover-letter` API endpoint using ResumeSelector + CoverLetterWriter
- Full assessment trainer feature for technical interview preparation
  - Dynamic LLM-generated questions (never from a fixed bank) with random nonce and shuffled topics
  - Both job-targeted and skill-based practice modes
  - Freeform (LLM-evaluated) and multiple-choice question formats
  - Adaptive difficulty: adjusts after every 3 answers based on average score
  - Session lifecycle: create, answer, get feedback with strengths/improvements/model answer, complete
  - Progress tracking: aggregate stats, score trend, strongest/weakest topics
- Backend: `src/assessment/` package (engine, storage) + `src/models/assessment.py` (6 enums, 5 models)
- 10 REST endpoints at `/api/assessment/*`
- Frontend: assessment page with SetupView, SessionView, ResultsView
- 57 backend tests (29 engine + 15 storage + 13 API), 0 failures
- TypeScript compiles clean

### Recent Updates (Phase 31 - 2026-05-06)

**Job Trust Scoring with Reasons:**
- Enhanced scam detector with tiered ratings and per-category breakdowns
- `TrustTier` enum with 5 levels: Legitimate, Low Risk, Moderate Risk, Suspicious, Likely Scam
- `TrustAnalysis` dataclass with category scores (title, description, company, salary, contact)
- Each listing now carries a clear trust rating with specific reasons explaining WHY
- LLM-enhanced trust analysis for subtle signals (pressure tactics, pyramid/MLM indicators)
- `POST /jobs/{job_id}/trust-analysis` API endpoint with optional `deep` param for LLM analysis
- Frontend trust display component with color-coded badges and category breakdown
- Visual confidence meter and collapsible AI summary section
- All 142 backend tests passing (0 regressions)
- TypeScript compiles cleanly

### Recent Updates (Phase 30 - 2026-05-05)

**LinkedIn Easy Apply Automation:**
- Created `src/linkedin/` package with 7 modules for end-to-end LinkedIn application automation
- `session.py` - Playwright persistent browser context with cookie persistence and 2FA/CAPTCHA detection
- `form_parser.py` - Parses multi-step Easy Apply modal forms into structured question data
- `answer_engine.py` - 3-tier answer strategy: rule-based (from user profile) -> answer bank (YAML) -> LLM fallback
- `form_filler.py` - Playwright automation for filling and submitting application forms
- `safety.py` - Rate limiting (20/day, 5/hour) with human-like delays and breaks
- `applied_scraper.py` - Scrapes LinkedIn "My Jobs > Applied" page for canonical tracking
- Already-applied detection: "Applied" badge captured during scraping, filtered in pipeline
- `AppliedJobsTracker` for local JSON-based tracking of submitted applications
- `QUESTION_ANSWERING` task type added to LLM router (qwen2.5:3b primary, haiku fallback)
- `LINKEDIN_AUTH` pipeline stage (non-fatal, validates credentials availability)
- Replaced `_submit_linkedin()` placeholder with full implementation
- Example `config/answer_bank.example.yaml` for pre-configured answers to custom questions
- Tested end-to-end: authentication, form parsing (3 steps, 8 questions), answer generation
- See [Troubleshooting Guide](troubleshooting.md#backend-unreachable--permissionerror-on-data-directory) for Docker setup notes

### Recent Updates (Phase 29 - 2026-04-30)

**LLM-Based Job Classification & WSL2 DrvFs Caching Fix:**
- Added `src/classifiers/job_classifier.py` - LLM-based job categorization service
- Rich classification metadata: industry, role_category, company_size, work_pace, team_structure
- Skills breakdown by category (technical, soft, domain) with proficiency levels
- Experience validation with confidence scores
- Management level and impact scope analysis
- Red flags and warnings detection
- `POST /jobs/{job_id}/classify` API endpoint
- "Analyze with AI" button in job detail panel with beautiful visual display
- Fixed WSL2 DrvFs aggressive caching issue with auto-fix entrypoint script
- Created `docker-rebuild.sh` helper script for proper container rebuilds (down + up vs restart)
- See [Troubleshooting Guide](troubleshooting.md#backend-unreachable--permissionerror-on-data-directory) for Docker caching solutions

### Recent Updates (Phase 28 - 2026-04-28)

**Backend Docker Volume Permissions Fix:**
- Backend was unreachable at startup due to a `PermissionError` when writing to `data/metrics`
- Root cause: WSL2 DrvFs bind mounts appear as `root:root 755` inside Docker containers regardless of host permissions, causing the `jobraider` user (uid 1000) to be denied write access
- Fix: added `user: root` to the backend service in `docker-compose.yml` to override the Dockerfile `USER jobraider` directive
- All 5 health checks now pass: disk, ollama, data directories, configuration, MLflow
- See [Troubleshooting Guide](troubleshooting.md#backend-unreachable--permissionerror-on-data-directory) for details

### Recent Updates (Phase 27 - 2026-04-28)

**TypeScript/Next.js Frontend Migration:**
- Replaced Streamlit with a Next.js 16 + Tailwind CSS + shadcn/ui dashboard
- 8 fully implemented pages: Dashboard, Pipeline, Jobs, Applications, Profile, Resume Analysis, Metrics, Settings
- API key auth (`X-API-Key`) added to all FastAPI routes; Next.js proxy injects it server-side
- Mobile responsive: desktop sidebar + mobile hamburger Sheet drawer
- Error boundary and Suspense skeleton on every page
- Docker service updated from Streamlit (:8501) to Next.js (:3000)
- Makefile rewritten with `make dev`, `make dev-frontend`, `make type-check`
- `setup.sh` now installs Node dependencies via `npm ci`
- TypeScript: 0 errors. Next.js production build clean.
- `.python-version` file added to `apps/backend-py/` (pins Python 3.11)

### Recent Updates (Phase 26 - 2026-04-27)

**Library Migrations and Infrastructure:**
- Migrated Pydantic V1 patterns to V2: `@validator` to `@field_validator`, `.dict()` to `.model_dump()`, `class Config` to `ConfigDict`
- Migrated PyPDF2 to pypdf (maintained successor, identical API)
- Added MLflow experiment tracking server with Docker service and health check
- Added Sentry error tracking integration (disabled by default, env-configured)
- Enhanced resume formatter with 5 templates (professional, modern, minimal, technical, executive)
- Added ATS-friendly resume mode with plain text formatting
- Added section customization (reorder, hide, rename resume sections)
- Zero Pydantic deprecation warnings in test output

### Recent Updates (Phase 25 - 2026-04-27)

**RAG Test Suite Fixes:**
- Fixed ChromaDB numpy ndarray truthiness bug: `if results["embeddings"]:` raised ValueError on ndarray, silently caught by bare `except`
- Fixed RAG ranker fallback path: `_fallback_to_heuristic()` now sorts by combined_score descending, matching main path contract
- Converted ChromaDB ndarray returns to Python lists for consistent type handling
- All 199 tests passing (144 backend + 55 frontend)

### RAG / Semantic Matching

The pipeline includes a RAG (Retrieval-Augmented Generation) stage that enhances heuristic scoring with semantic similarity:

1. **Text Chunking** - Job descriptions and resumes are split into embedding-ready chunks
2. **Embedding Generation** - Chunks are embedded using `nomic-embed-text` via Ollama
3. **Vector Storage** - Embeddings stored in ChromaDB with metadata filtering
4. **Semantic Re-Ranking** - Combined heuristic (40%) + semantic (60%) scoring for final ranking
5. **Fallback** - Gracefully degrades to heuristic-only when embeddings are unavailable

Components:
- `src/rag/chunker.py` - Text chunking for jobs and profiles
- `src/rag/embedding_client.py` - Ollama embedding client with batch support
- `src/rag/vector_store.py` - ChromaDB persistent vector store
- `src/rag/ranker.py` - Semantic re-ranking with heuristic fallback
- `src/rag/config.py` - RAG configuration models

### Recent Updates (Phase 23 - 2026-04-26)

**LinkedIn Description Fetching & UI Fixes:**
- LinkedIn jobs now include full descriptions fetched from individual job detail pages
- Posted date parsing handles additional formats: "Just posted", "Recently", "1 minute ago", absolute dates
- Fixed raw `</div>` HTML tags appearing in job cards (replaced nested HTML with `st.container`)
- Fixed white-on-white text in pill badges (added text-shadow for visibility)
- Description display limit increased from 500 to 5000 characters

### Recent Updates (Phase 22 - 2026-04-26)

**Frontend UI Overhaul (SupCareer-Inspired):**
- Jobs page restructured with split-panel layout: compact list (left) + detail view (right)
- Added pagination with Previous/Next buttons and "Showing X-Y of Z" info
- Added status tabs: All, Saved, Applied
- Created pill badge components for skills, sources, and score indicators
- Created Applications tracker page wired to backend `/api/applications/*` endpoints
- Added Streamlit theme configuration (`.streamlit/theme.toml`)

### Recent Updates (Phase 21 - 2026-04-25)

**JSearch API Integration:**
- Replaced broken Indeed/Glassdoor Playwright scrapers with JSearch API (RapidAPI)
- JSearch aggregates from Google for Jobs covering Indeed, Glassdoor, Jobstreet, and 50+ boards
- Dynamic job sources fetched from backend (no more hard-coded source lists)
- Frontend source checkboxes update automatically when new scrapers are registered
- Requires `RAPIDAPI_KEY` in `apps/backend-py/.env`

**Why the change:**
- Indeed, Glassdoor, and Jobstreet block headless Chromium via Cloudflare bot detection
- LinkedIn is the only working Playwright scraper (60 results)
- JSearch provides wider coverage through a single API integration

### Job Application Tracker (Phase 19 - 2026-04-25)

**New Feature:** Job Application Tracking

The system now includes comprehensive job application tracking capabilities:

**Key Features:**
- **Save/Bookmark Jobs** - Save interesting jobs for later review
- **Track External Applications** - Log applications made outside the system (company website, referrals)
- **Hide Jobs** - Mark jobs as "not interested" to hide from future results
- **Custom Statuses** - Create personalized application statuses (e.g., "Waiting for Feedback", "Phone Screen Scheduled")
- **Dashboard** - View all tracked applications with filtering and summary statistics

**API Endpoints:**
- `POST /api/applications/actions` - Quick actions (save, hide, unsave, unhide)
- `POST /api/applications/external` - Track external applications
- `POST /api/applications/statuses/custom` - Create custom statuses
- `GET /api/applications/statuses/custom` - List all custom statuses
- `GET /api/applications/dashboard` - Application dashboard with filtering
- `GET /api/applications/{job_id}` - Get detailed application information

**Storage:**
- Applications stored in `data/applications/*.json`
- Custom statuses stored in `data/applications/custom_statuses/*.json`
- File-based persistence with automatic loading

See [API Documentation](api.md#applications-api) for detailed usage.

### Docker Storage Documentation (Phase 20 - 2026-04-25)

**New Documentation:** Docker Storage Guide

A comprehensive guide was added to address the critical Docker storage issue on Windows/WSL2:

**Key Points:**
- Docker Desktop stores ALL data on C: drive by default, even if project is on D: or E:
- Storage location: `C:\Program Files\Docker\Docker\resources`
- Space requirements: 200GB+ on C: drive, 100GB+ on project drive
- Breakdown of what consumes space (images 15-20GB, project data 10-20GB, overhead 30-50GB)

**Solutions Documented:**
- Move Docker data directory to D: drive
- Use WSL2 directly instead of Docker Desktop
- Cleanup commands for unused resources
- Ollama model storage management
- WSL2 VHDX compaction

**Setup Script Updates:**
- Added `check_disk_space()` function to warn users before installation
- Checks both C: drive and current drive availability
- References `docs/docker-storage.md` for solutions

**See Also:**
- [Docker Storage Guide](docker-storage.md) - Complete documentation

### Pipeline Stages

1. **Scrape** - Aggregates listings from LinkedIn and JSearch API (50+ boards)
2. **Deduplicate** - Removes duplicates across sources
3. **Filter Scams** - Filters out potential scams (10 indicators)
4. **Filter by Profile** - Matches user preferences
5. **Score & Rank** - Heuristic relevance scoring (0-100)
6. **Semantic Re-Rank** - RAG-based similarity scoring with ChromaDB embeddings
7. **Detect Auto-Submit** - Identifies "Easy Apply" opportunities
8. **Present Selection** - Shows ranked list to user
9. **Generate Resumes** - Creates tailored resumes (5 templates, ATS mode available)
10. **Submit** - Auto-submits where possible

### Scoring Heuristic

| Category | Points | Description |
|----------|--------|-------------|
| Keywords | 30 | Keyword overlap with targets |
| Skills | 40 | Skills match against profile |
| Experience | 20 | Experience level alignment |
| Location | 10 | Location preference match |
| **Total** | **100** | Threshold: 60 to apply |

## System Requirements

### Minimum

- Python 3.11+
- Node.js 20+ (for Next.js frontend)
- 16GB RAM
- 8GB VRAM (for local models)
- Ollama installed
- Playwright browsers

### Recommended

- NVIDIA GPU (RTX 3070 Ti or better)
- 32GB RAM
- SSD storage
- Stable internet connection

## Configuration

### Environment Variables

```bash
# apps/backend-py/.env
ANTHROPIC_API_KEY=your_key_here          # Optional — Ollama is used by default
RAPIDAPI_KEY=your_rapidapi_key_here      # Required for JSearch (50+ job boards)
OLLAMA_HOST=http://localhost:11434       # Local Ollama; use http://ollama:11434 in Docker
SENTRY_DSN=your_sentry_dsn_here         # Optional error tracking
MLFLOW_TRACKING_URI=http://localhost:5000 # Optional experiment tracking

# apps/frontend-ts/.env.local
BACKEND_API_URL=http://localhost:8000   # FastAPI backend URL
API_KEY=your_shared_secret_here         # Must match apps/backend-py/.env API_KEY
NEXT_PUBLIC_WS_URL=ws://localhost:8000  # WebSocket for live pipeline progress
```

### Configuration Files

- `apps/backend-py/config/model_config.yaml` - Model endpoints and settings
- `apps/backend-py/config/prompt_templates.yaml` - LLM prompts
- `apps/backend-py/config/scoring_config.yaml` - Scoring weights and thresholds
- `apps/backend-py/config/logging_config.yaml` - Logging configuration

## Support

### Getting Help

1. Check [Troubleshooting Guide](troubleshooting.md)
2. Review [Architecture Documentation](architecture.md)
3. Search existing GitHub issues
4. Create new issue with details

### Project Structure

```
job-raider/                      # Project root (monorepo)
├── apps/backend-py/                  # Python backend
│   ├── .venv/                   # Python virtual environment
│   ├── .python-version          # Pins Python 3.11 for pyenv / CI
│   ├── config/                  # Configuration files (YAML)
│   ├── src/                     # Source code
│   │   ├── agents/             # Multi-agent system (coordinator, communication bus, career coach)
│   │   ├── api/                # FastAPI REST API + auth
│   │   ├── config/             # Config loader
│   │   ├── llm/                # LLM clients (Claude, Ollama)
│   │   ├── models/             # Pydantic data models
│   │   ├── scrapers/           # Job scraping (LinkedIn, JSearch)
│   │   ├── extractors/         # Resume and JD parsing
│   │   ├── scoring/            # Filtering and matching
│   │   ├── rag/                # RAG pipeline (embeddings, vector store, ranker)
│   │   ├── linkedin/           # LinkedIn Easy Apply automation
│   │   ├── assessment/         # Technical assessment trainer (engine, storage)
│   │   ├── generation/         # Resume generation + analysis
│   │   ├── submission/         # Application submission
│   │   ├── pipeline/           # Pipeline orchestration
│   │   ├── health/             # System health checks
│   │   ├── metrics/            # Cost and outcome tracking
│   │   ├── reports/            # Report generation
│   │   └── utils/              # Shared utilities
│   ├── tests/                   # Python test suite (376 passing)
│   ├── notebooks/               # Jupyter notebooks
│   ├── main.py                  # CLI entry point
│   └── requirements.txt         # Python dependencies
├── apps/frontend-ts/                 # Next.js 16 + Tailwind CSS dashboard
│   ├── src/
│   │   ├── app/                # Next.js App Router pages (10 pages)
│   │   ├── components/         # Shared UI components + layout
│   │   └── lib/                # API client, types, utilities
│   ├── Dockerfile               # Multi-stage production build (standalone)
│   ├── next.config.ts           # Next.js config (standalone output)
│   └── package.json             # Node dependencies
├── docker/                      # Backend Dockerfiles
│   ├── Dockerfile               # Production (CUDA + GPU)
│   └── Dockerfile.dev           # Development (slim)
├── data/                        # Shared data
├── docs/                        # Documentation
├── scripts/                     # Shell/utility scripts
└── tasks/                       # Project tasks and lessons
```

### Contributing

Contributions welcome! Please:

1. Read the architecture documentation
2. Follow code style guidelines
3. Add tests in `apps/backend-py/tests/`
4. Update documentation

## License

MIT License - See LICENSE file for details
