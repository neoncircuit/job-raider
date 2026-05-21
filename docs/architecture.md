# Job Raider - Architecture Documentation

## Overview

Job Raider is an automated job application pipeline that aggregates job listings from multiple platforms, scores relevance, generates tailored resumes, and automates submissions where possible.

## System Architecture

```mermaid
graph TB
    subgraph "Input Layer"
        Resume[User Resume]
        Config[Configuration]
    end

    subgraph "Pipeline Layer"
        Scrape[Scrape Jobs]
        Dedupe[Deduplicate]
        FilterScam[Filter Scams]
        FilterProfile[Filter by Profile]
        Score[Score & Rank]
        DetectAuto[Detect Auto-Submit]
        Select[Present & Select]
        Generate[Generate Resumes]
        Submit[Submit Applications]
    end

    subgraph "Output Layer"
        Resumes[Generated Resumes]
        Tracking[Application Tracking]
        Reports[Pipeline Reports]
    end

    subgraph "External Services"
        LinkedIn[LinkedIn]
        JSearch[JSearch API]
        Ollama[Ollama API]
        Anthropic[Anthropic API]
    end

    Resume --> Parse[Resume Parser]
    Config --> Orchestrator[Pipeline Orchestrator]
    Parse --> UserProfile[User Profile]

    Orchestrator --> Scrape
    Scrape --> LinkedIn & JSearch
    Scrape --> EnrichDetails[Enrich with Details]
    EnrichDetails -->|LinkedIn only| DetailPages[Job Detail Pages]
    Scrape --> Dedupe
    Dedupe --> FilterScam
    FilterScam --> FilterProfile
    FilterProfile --> Score
    Score --> DetectAuto
    DetectAuto --> Select
    Select --> Generate
    Generate --> Ollama & Anthropic
    Generate --> Resumes
    Resumes --> Submit
    Submit --> Tracking & Reports
```

## Component Architecture

### 1. LLM Layer

```mermaid
classDiagram
    class BaseLLMClient {
        <<abstract>>
        +generate(messages) LLMResponse
        +generate_async(messages) Coroutine~LLMResponse~
        +count_tokens(text) int
        +estimate_cost(messages) CostEstimate
    }

    class ClaudeClient {
        +api_key: str
        +model: str
        +generate(messages) LLMResponse
        +retry_logic: tenacity
    }

    class OllamaClient {
        +base_url: str
        +model: str
        +generate(messages) LLMResponse
        +check_vram() GPUInfo
        +pull_model() None
    }

    class LLMRouter {
        +routes: Dict[TaskType, RouteConfig]
        +generate(task, messages) LLMResponse
        +get_client(task) BaseLLMClient
    }

    BaseLLMClient <|-- ClaudeClient
    BaseLLMClient <|-- OllamaClient
    LLMRouter --> BaseLLMClient
```

### 2. Data Models

```mermaid
classDiagram
    class JobListing {
        +title: str
        +company: str
        +location: str
        +description: str
        +requirements: List[str]
        +responsibilities: List[str]
        +skills: List[str]
        +salary_range: Optional[SalaryRange]
        +source: JobSource
        +source_url: Optional[HttpUrl]
    }

    class UserProfile {
        +contact_info: ContactInfo
        +skills: Dict[SkillCategory, List[Skill]]
        +experience: List[WorkExperience]
        +projects: List[Project]
        +education: List[Education]
        +target_job: TargetJob
    }

    class MatchScore {
        +total_score: int
        +keyword_score: int
        +skills_score: int
        +experience_score: int
        +location_score: int
        +details: Dict[str, Any]
    }

    JobListing --> MatchScore
    UserProfile --> MatchScore
```

### 3. Pipeline Stages

```mermaid
stateDiagram-v2
    [*] --> Scrape
    Scrape --> Deduplicate
    Deduplicate --> FilterScams
    FilterScams --> FilterProfile
    FilterProfile --> ScoreRank
    ScoreRank --> DetectAutoSubmit
    DetectAutoSubmit --> PresentSelect
    PresentSelect --> GenerateResumes
    GenerateResumes --> SubmitApplications
    SubmitApplications --> [*]

    note right of Scrape
        Parallel scraping from
        LinkedIn + JSearch API.
        LinkedIn results enriched
        with descriptions from
        individual job pages.
    end note

    note right of ScoreRank
        Heuristic scoring:
        - Keywords: 30pts
        - Skills: 40pts
        - Experience: 20pts
        - Location: 10pts
    end note

    note right of GenerateResumes
        Two-model approach:
        1. Selector (qwen2.5:3b)
        2. Writer (qwen2.5:7b)
    end note
```

## Two-Model Architecture

### Resume Generation Strategy

Job Raider uses a two-model approach to optimize cost and quality:

```mermaid
sequenceDiagram
    participant JD as Job Description
    participant User as User Profile
    participant Small as Small Model (qwen2.5:3b)
    participant Large as Large Model (qwen2.5:7b)
    participant Validator as Validator

    JD->>Small: Requirements + User Skills
    Small->>Small: Select 3 best projects
    Small->>Small: Extract 5 keywords
    Small-->>User: SelectionOutput

    User->>Large: Selection + Base Resume
    Large->>Large: Rewrite & Tailor
    Large-->>User: GeneratedResume

    User->>Validator: Generated + Selection
    Validator->>Validator: Deterministic checks
    Validator-->>User: ValidationResult
```

**Benefits:**
- **Cost Reduction:** 80% of calls use free local model
- **Quality:** Large model ensures high-quality writing
- **Context Control:** Small model extracts signal, reduces hallucination
- **Validation:** Deterministic checks prevent fabrication

### Model Selection for 8GB VRAM

| Model | Parameters | VRAM Usage | Use Case | Cost |
|-------|-----------|------------|----------|------|
| qwen2.5:3b | 3B | ~2 GB | Selection, Scoring | Free (local) |
| qwen2.5:7b | 7B | ~4 GB | Resume Writing | Free (local) |
| gemma3:4b | 4B | ~2.5 GB | Alt. Selection | Free (local) |
| gemma3:12b | 12B | ~7 GB | Alt. Writing | Free (local) |
| claude-sonnet-4-6 | N/A | N/A | Fallback/API | ~$3/50 apps |

## Data Flow

### Pipeline Execution Flow

```mermaid
flowchart TD
    Start([Start]) --> Config[Load Config]
    Config --> LoadProfile[Load User Profile]
    LoadProfile --> InitOrch[Initialize Orchestrator]

    InitOrch --> Stage1[Stage 1: Scrape]
    Stage1 --> Stage2[Stage 2: Deduplicate]
    Stage2 --> Stage3[Stage 3: Filter Scams]
    Stage3 --> Stage4[Stage 4: Filter by Profile]
    Stage4 --> Stage5[Stage 5: Score & Rank]

    Stage5 --> CheckScore{Score >= 60?}
    CheckScore -->|No| End([End - No Matches])
    CheckScore -->|Yes| Stage6[Stage 6: Detect Auto-Submit]

    Stage6 --> Stage7[Stage 7: Present Selection]
    Stage7 --> UserSelect{User Selects Jobs}
    UserSelect --> Stage8[Stage 8: Generate Resumes]

    Stage8 --> Validate{Validation Pass?}
    Validate -->|No| LogFail[Log Failure]
    Validate -->|Yes| Stage9[Stage 9: Submit]

    Stage9 --> DryRun{Dry Run Mode?}
    DryRun -->|Yes| SaveResults[Save Results]
    DryRun -->|No| SubmitReal[Submit Applications]
    SubmitReal --> SaveResults
    LogFail --> SaveResults
    SaveResults --> End
```

### Storage Architecture

```
data/
├── listings/              # Scraped job listings
│   ├── 20260421_120000.json
│   └── 20260421_130000.json
├── applications/          # Application tracking
│   ├── {app_id}.json
│   └── ...
├── cache/                # LLM response cache
│   └── responses.json
└── results/              # Pipeline results
    ├── resumes/          # Generated resumes
    │   ├── {job_id}.pdf
    │   └── {job_id}.docx
    ├── applications/     # Application data
    │   └── {app_id}.json
    └── pipeline_run_*.json
```

## Scoring Heuristic

The relevance scoring algorithm uses a 100-point scale:

| Category | Points | Calculation |
|----------|--------|-------------|
| Keyword Match | 30 | (matched_keywords / target_keywords) × 30 |
| Skills Match | 40 | (matched_skills / total_skills) × 40 |
| Experience Level | 20 | Exact match: 20, Adjacent: 10, Mismatch: 0 |
| Location Preference | 10 | Exact match: 10, Same region: 5, Remote: 3 |

**Threshold:** 60+ points = worth applying

## Scam Detection

Job Raider includes 10 scam indicators:

1. **Payment Required** - Requests payment to work
2. **Personal Email** - Uses Gmail/Yahoo instead of company domain
3. **Messaging App Only** - Contact only via Telegram/WhatsApp
4. **Unrealistic Salary** - Hourly rates > $100 or too high for role
5. **Fake Company** - Suspicious company names (Confidential, Hidden)
6. **Vague Description** - Missing or too short description
7. **Poor Grammar** - Multiple grammar issues
8. **Immediate Hire** - "Start today", "no interview"
9. **Suspicious Title** - Unrealistic earnings claims
10. **Phishing Links** - Suspicious external URLs

**Scoring:** Each indicator adds 10-50 points. Threshold 70 = scam.

## Auto-Submit Detection

The system detects three types of application methods:

| Method | Description | Action |
|--------|-------------|--------|
| Easy Apply | Platform native quick apply | Auto-submit (dry-run first) |
| External Site | Redirects to company ATS | Flag for manual application |
| Manual | Requires custom process | Flag for manual application |

## Frontend Architecture

The web dashboard is built with Next.js 16 (App Router) + Tailwind CSS + shadcn/ui.

```mermaid
graph LR
    subgraph "Browser"
        Pages[8 App Router Pages]
        Components[Layout + UI Components]
    end

    subgraph "Next.js Server"
        Proxy[/api/proxy/path Route Handler]
    end

    subgraph "FastAPI Backend"
        Routes[API Routes]
        Auth[verify_api_key Dependency]
    end

    Pages -->|fetch /api/proxy/*| Proxy
    Proxy -->|X-API-Key header + forward| Auth
    Auth --> Routes
```

### Key Design Decisions

- **Server-side proxy:** All backend calls go through `/api/proxy/[...path]` — a Next.js Route Handler that injects `X-API-Key` from a server-only env var. The API key is never exposed to the browser.
- **TanStack Query:** All data fetching uses `useQuery` / `useMutation` with automatic caching and refetch.
- **App state context:** Cross-page state (selected job, active pipeline run, saved jobs) lives in a React context populated at the root layout.
- **Error boundary + Suspense:** Every page is wrapped in an `ErrorBoundary` and `<Suspense fallback={<PageSkeleton />}>` in the AppShell.
- **Mobile nav:** Sidebar hidden below `md` breakpoint; a Sheet drawer with hamburger toggle shown instead.

### Pages

| Route | Purpose |
|-------|---------|
| `/dashboard` | Health checks, quick stats, recent pipeline runs |
| `/pipeline` | Start form, WebSocket live monitor, history |
| `/jobs` | Search, split-panel list + detail, pagination, save/apply |
| `/applications` | Tracker: All / Saved / Hidden tabs, track external |
| `/profile` | Resume upload (dropzone), parsed profile display |
| `/resume-analysis` | Upload + optional JD → AI score, gaps, recommendations |
| `/metrics` | Recharts funnel + pie, cost tiles, LLM call log |
| `/settings` | Model params, API config, cost limits, validate/reset |

## Security Considerations

1. **API Keys:** Backend key in `backend-py/.env`, frontend key in `frontend-ts/.env.local` — neither committed
2. **X-API-Key auth:** All FastAPI routes protected by `verify_api_key` dependency; bypassed only when `API_KEY` env var is unset (local dev)
3. **Server-only proxy:** `BACKEND_API_URL` and `API_KEY` are server env vars — never bundled into client JS
4. **Dry Run Mode:** Default for all submissions
5. **Rate Limiting:** 2 sec delay, 30 per hour max
6. **Data Privacy:** Local processing, resume data never leaves system
7. **Scam Protection:** Multi-layer scam detection before processing

## Deployment Architecture

### Docker Service Topology

```mermaid
graph TB
    subgraph "Docker Compose - job-raider-network"
        Backend[Backend API<br/>FastAPI on :8000]
        Ollama[Ollama<br/>Model Inference on :11434]
        Frontend[Next.js Dashboard<br/>on :3000]
    end

    subgraph "Shared Services - shared-services network"
        MLflow[MLflow Tracking<br/>on :5000]
    end

    subgraph "Host System"
        DockerDesktop[Docker Desktop]
        NVIDIAToolkit[NVIDIA Container Toolkit]
        GPU[RTX 3070 Ti - 8GB VRAM]
    end

    Frontend -->|/api/proxy/* with X-API-Key| Backend
    Backend -->|HTTP API| Ollama
    Backend -->|Experiment logging| MLflow
    Ollama -->|GPU Passthrough| GPU
    NVIDIAToolkit -->|Enables GPU| Ollama
    DockerDesktop -->|Manages| Backend
    DockerDesktop -->|Manages| Ollama
    DockerDesktop -->|Manages| Frontend
    DockerDesktop -->|Manages| MLflow
```

### Container Configuration

| Service | Image | Port | GPU | Purpose |
|---------|-------|------|-----|---------|
| backend | Custom (CUDA 12.4.0) | Dynamic (default 8000) | No | FastAPI REST API, pipeline orchestration |
| ollama | ollama/ollama:latest | Dynamic (default 11434) | Yes (NVIDIA) | Local LLM inference (qwen2.5:3b, qwen2.5:7b) |
| frontend | Custom (Node 20 Alpine) | Dynamic (default 3000) | No | Next.js web dashboard |
| mlflow | ghcr.io/mlflow/mlflow:latest | 5000 | No | Shared experiment tracking (see docs/mlflow-setup.md) |

### GPU Passthrough

GPU acceleration is configured via the NVIDIA Container Toolkit:

- The Ollama container receives GPU access through Docker's `deploy.resources.reservations.devices` configuration
- CUDA 12.4.0 runtime is used in the backend container for compatibility with the host driver (595.79, CUDA 13.2)
- Ollama automatically detects and uses CUDA for model inference when GPU is available
- Models (qwen2.5:3b, qwen2.5:7b) are stored in a persistent Docker volume (`ollama-data`) and pulled on first use

### Dynamic Port Allocation

Ports are allocated dynamically to avoid conflicts with other services:

- `docker-run.sh` calls `scripts/find-port.sh` to discover available ports starting from the default
- Port assignments are passed to docker-compose via environment variables (`BACKEND_PORT`, `OLLAMA_PORT`, `FRONTEND_PORT`)
- The docker-compose.yml uses the extended port definition format with `${VAR:-default}` interpolation

### Inter-Service Communication

- Frontend to Backend: Next.js proxy at `/api/proxy/*` forwards to `http://backend:8000` (Docker) or `http://localhost:8000` (local)
- Backend to Ollama: HTTP API calls via Docker internal DNS (`http://ollama:11434`)
- All services share the `job-raider-network` bridge network
