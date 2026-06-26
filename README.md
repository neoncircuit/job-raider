# Job Raider

Automated job application pipeline that aggregates listings from multiple platforms, scores relevance, generates tailored resumes, and automates submissions.

## Features

- **Multi-Platform Job Aggregation**: LinkedIn (Playwright) + JSearch API (50+ boards via Google for Jobs)
- **Smart Filtering**: Keyword matching, scam detection (10 indicators), profile-based filtering
- **Relevance Scoring**: 100-point heuristic scoring with configurable thresholds
- **Semantic Matching**: RAG-powered similarity search using ChromaDB vector store and embeddings
- **Resume Generation**: Two-model approach (small for selection, large for writing)
- **Resume Analysis**: AI-powered general and job-specific gap analysis with scoring
- **LinkedIn Profile Analysis**: Inbound-attraction scoring and recruiter-focused recommendations
- **AI Cover Letter Generation**: Tailored cover letters from profile and job description
- **Multi-Agent Career Coaching**: `/api/agents/*` career analysis, gap analysis, roadmaps, and goals
- **DISC Personality Assessment**: Most/least forced-choice assessment with job matching
- **Technical Assessment Trainer**: Practice engine for coding and technical interviews
- **Job Trust Analysis**: Scam detection and employer-trust scoring
- **LinkedIn Easy Apply Automation**: Browser automation for one-click applications
- **Fresh-Graduate Scoring Mode**: Projects 35%, Skills 30%, Education 20% weighting
- **Light/Dark Theme Toggle**: UI theme switching via the sidebar
- **Frontend Testing Infrastructure**: Vitest unit tests + Playwright E2E tests
- **Auto-Submit Detection**: Identifies "Easy Apply" opportunities
- **Dry Run Mode**: Test everything without actual submissions
- **Cost Optimization**: 80% cost reduction using local Ollama models
- **Application Tracking**: Track applications from submission to offer with custom statuses

## Architecture

```mermaid
graph LR
    A[Scrape Jobs] --> B[Deduplicate]
    B --> C[Filter Scams]
    C --> D[Score & Rank]
    D --> E[Generate Resumes]
    E --> F[Submit Applications]
```

### Two-Model Approach

1. **Small Model (qwen2.5:3b)** - Selects relevant projects and keywords
2. **Large Model (qwen2.5:7b)** - Writes tailored resumes

This reduces API costs by 80% while maintaining quality.

## Quick Start

### Prerequisites

- Python 3.11+
- 8GB VRAM (for local models)
- Ollama installed

### Installation

```bash
# Clone repository
git clone https://github.com/yourusername/job-raider.git
cd job-raider

# Run setup
./setup.sh

# Pull Ollama models
ollama pull qwen2.5:3b
ollama pull qwen2.5:7b
ollama pull nomic-embed-text

# Configure environment
cp backend-py/.env.example backend-py/.env
# Edit backend-py/.env with your API keys
```

### Usage

#### Interactive Mode

```bash
cd backend-py
python main.py --interactive
```

#### CLI Mode

```bash
# Basic search with dry run
cd backend-py
python main.py \
  --resume my_resume.pdf \
  --keywords "python engineer" \
  --locations "remote" \
  --dry-run

# Full pipeline with submission
cd backend-py
python main.py \
  --resume my_resume.pdf \
  --keywords "fintech AI" \
  --locations "remote" \
  --no-dry-run
```

## Pipeline Stages

| Stage | Description | Output |
|-------|-------------|--------|
| 1. Scrape | Aggregate from LinkedIn and JSearch API (50+ boards) | Raw listings |
| 2. Deduplicate | Remove duplicates across sources | Unique listings |
| 3. Filter Scams | Filter out potential scams | Legitimate listings |
| 4. Filter by Profile | Match user preferences | Relevant listings |
| 5. Score & Rank | Heuristic relevance scoring (0-100) | Ranked listings |
| 6. Semantic Re-Rank | RAG-based similarity scoring with ChromaDB embeddings | Re-ranked listings |
| 7. Detect Auto-Submit | Identify "Easy Apply" opportunities | Submission info |
| 8. Present Selection | Show ranked list to user | Selected jobs |
| 9. Generate Resumes | Create tailored resumes (5 templates, ATS mode) | PDF/DOCX files |
| 10. Submit | Auto-submit where possible | Application tracking |

## Scoring Heuristic

| Category | Points | Description |
|----------|--------|-------------|
| Keywords | 30 | Keyword overlap with targets |
| Skills | 40 | Skills match against profile |
| Experience | 20 | Experience level alignment |
| Location | 10 | Location preference match |
| **Total** | **100** | **Threshold: 60 to apply** |

## Scam Detection

10 scam indicators:
- Payment required
- Personal email domains
- Messaging app only contact
- Unrealistic salary
- Fake company names
- Vague descriptions
- Poor grammar
- Immediate hire language
- Suspicious titles
- Phishing links

## Project Structure

```
job-raider/                      # Project root (monorepo)
├── backend-py/                  # Python backend
│   ├── .venv/                   # Python virtual environment
│   ├── config/                  # Configuration files
│   │   ├── agent_config.yaml
│   │   ├── app_config.yaml
│   │   ├── logging_config.yaml
│   │   ├── model_config.yaml
│   │   ├── prompt_templates.yaml
│   │   ├── rag_config.yaml
│   │   ├── scoring_config.yaml
│   │   ├── scrapers_config.yaml
│   │   └── search_config.yaml
│   ├── src/                     # Source code
│   │   ├── agents/              # Multi-agent system (coordinator, communication bus, career coach)
│   │   ├── api/                 # FastAPI REST API (routes, models, websocket)
│   │   ├── assessment/          # Technical assessment trainer + DISC engine
│   │   ├── classifiers/         # LLM-based job classification
│   │   ├── config/              # YAML config loader
│   │   ├── database/            # Database models and connection helpers
│   │   ├── extractors/          # Resume and JD parsing (pypdf)
│   │   ├── experiments/         # A/B testing framework
│   │   ├── generation/          # Resume generation (selector, writer, formatter) + analyzers
│   │   ├── health/              # System health checks (including MLflow)
│   │   ├── linkedin/            # LinkedIn Easy Apply automation
│   │   ├── llm/                 # LLM clients (Claude, Ollama, router)
│   │   ├── metrics/             # Cost tracking, outcome tracking, MLflow integration
│   │   ├── models/              # Pydantic V2 data models
│   │   ├── pipeline/            # Pipeline orchestration and stages
│   │   ├── rag/                 # RAG pipeline (embeddings, vector store, ranker, chunker)
│   │   ├── reports/             # HTML report generation
│   │   ├── scrapers/            # Job scraping (LinkedIn, JSearch API)
│   │   ├── scoring/             # Filtering, matching, scam detection, trust analysis
│   │   ├── submission/          # Application submission and detection
│   │   └── utils/               # Caching, logging, Sentry, utilities
│   ├── tests/                   # Unit and integration tests
│   ├── notebooks/               # Jupyter notebooks
│   ├── main.py                  # CLI entry point
│   └── requirements.txt         # Python dependencies
├── frontend-ts/                 # Next.js + Tailwind dashboard (active frontend)
│   ├── src/
│   │   ├── app/                 # Next.js App Router pages (10 pages)
│   │   ├── components/          # Shared UI components + layout
│   │   └── lib/                 # API client, types, utilities
│   ├── tests/                   # Vitest unit + Playwright E2E tests
│   ├── Dockerfile               # Multi-stage production build (standalone)
│   └── package.json             # Node dependencies
├── frontend-py/                 # Legacy Streamlit dashboard (superseded by frontend-ts; still tested in CI)
├── data/                        # Shared data storage
│   ├── alerts/                  # Alert records
│   ├── applications/            # Tracked applications
│   ├── applied_jobs/            # Jobs already applied to
│   ├── cache/                   # LLM response cache
│   ├── chroma/                  # ChromaDB vector store persistence
│   ├── disc_results/            # DISC assessment results
│   ├── experiments/             # A/B test results
│   ├── linkedin_session/        # LinkedIn browser session data
│   ├── listings/                # Scraped listings
│   ├── logs/                    # Application logs
│   ├── metrics/                 # Cost/outcome metrics
│   ├── outputs/                 # General output files
│   ├── profiles/                # User profile data
│   ├── reports/                 # Generated HTML reports
│   ├── results/                 # Pipeline results
│   │   ├── applications/        # Generated application packages
│   │   └── resumes/             # Generated resumes
│   ├── screenshots/             # Automation screenshots
│   └── settings/                # User settings snapshots
├── docker/                      # Backend Dockerfiles
│   ├── Dockerfile               # Production (CUDA + GPU)
│   └── Dockerfile.dev           # Development (slim)
├── docs/                        # Documentation
│   ├── api.md
│   ├── architecture.md
│   ├── disk-space.md
│   ├── fresh-grad-profile-guide.md
│   ├── index.md
│   ├── manual-verification-checklist.md
│   ├── mlflow-setup.md
│   ├── testing.md
│   ├── troubleshooting.md
│   └── usage.md
├── scripts/                     # Shell/utility scripts
│   ├── cleanup.sh               # Temporary file cleanup
│   └── find-port.sh             # Dynamic port discovery
├── tasks/                       # Project tracking (todo.md, lessons.md)
├── .github/workflows/           # CI/CD pipelines
├── docker-compose.yml           # Multi-service orchestration
├── docker-rebuild.sh            # Docker rebuild helper (WSL2 caching workaround)
├── docker-run.sh                # Docker startup with port detection
├── setup.sh                     # One-command setup script
├── dev.sh                       # Local development with hot reload
├── Makefile                     # Common development commands
└── README.md                    # This file
```

## Documentation

- **[Documentation Index](docs/index.md)** - Documentation hub and quick links
- **[Architecture](docs/architecture.md)** - System architecture and design
- **[Usage Guide](docs/usage.md)** - Installation and usage
- **[API Reference](docs/api.md)** - Complete API documentation
- **[Testing Guide](docs/testing.md)** - Backend and frontend test commands
- **[Troubleshooting](docs/troubleshooting.md)** - Common issues and solutions
- **[Disk Space Management](docs/disk-space.md)** - Data retention policies

## Configuration

Job Raider uses a two-tier configuration system:

### Credentials (.env)

API keys and secrets live in `backend-py/.env` (copy from `backend-py/.env.example`).

```bash
# Required for API fallback
ANTHROPIC_API_KEY=your_key_here

# Required for JSearch API (job aggregation from 50+ boards)
RAPIDAPI_KEY=your_rapidapi_key_here

# Optional: Kaggle API (for scam detector evaluation notebook)
KAGGLE_USERNAME=your_username
KAGGLE_KEY=your_key

# Optional: Scraping credentials (for Easy Apply)
LINKEDIN_EMAIL=your_email
LINKEDIN_PASSWORD=your_password

# Optional: Sentry error tracking
SENTRY_DSN=your_sentry_dsn_here

# Optional: MLflow experiment tracking (shared service)
MLFLOW_TRACKING_URI=http://localhost:5000
```

### Application Settings (config/*.yaml)

All non-sensitive configuration lives in YAML files under `backend-py/config/`:

| Config File | Purpose |
|-------------|---------|
| `agent_config.yaml` | Multi-agent system configuration (coordinator, career coach) |
| `app_config.yaml` | General settings (paths, development flags, monitoring) |
| `model_config.yaml` | LLM model selection, routing, caching, rate limits |
| `rag_config.yaml` | RAG pipeline configuration (embeddings, chunking, vector store) |
| `scoring_config.yaml` | Scoring weights, thresholds, skill categories |
| `scrapers_config.yaml` | Scraper settings, rate limiting, browser automation |
| `search_config.yaml` | Default keywords, locations, filters |
| `logging_config.yaml` | Logging levels and output configuration |
| `prompt_templates.yaml` | LLM prompt templates |

Example: Edit `backend-py/config/search_config.yaml` to change default search keywords:

```yaml
keywords:
  - "python"
  - "software engineer"
  - "backend"
  - "remote"
```

## System Requirements

### Minimum

- Python 3.11+
- 16GB RAM
- 8GB VRAM
- Ollama installed

### Recommended

- NVIDIA GPU (RTX 3070 Ti or better)
- 32GB RAM
- SSD storage

## Development

### Web Dashboard (Next.js)

The web dashboard (`frontend-ts/`) is a Next.js + Tailwind CSS application that provides a visual interface for the full pipeline. It is the active frontend; the legacy Streamlit dashboard in `frontend-py/` is retained but superseded.

```bash
# Start backend API first (http://localhost:8000)
make dev-api

# In another terminal, start the Next.js dashboard (http://localhost:3000)
make dev-frontend

# Or start both together
make dev
```

Or use Docker to start all services at once:

```bash
bash docker-run.sh
```

The dashboard includes ten pages: Dashboard (overview), Pipeline (run/monitor), Jobs (search/browse), Profile (resume upload), Resume Analysis (AI scoring), LinkedIn Analysis (inbound-attraction recommendations), Assessment (technical trainer + DISC), Applications (tracker), Metrics (costs/outcomes), and Settings (configuration).

### Running Tests

```bash
# Backend tests
cd backend-py
.venv/bin/python -m pytest tests/
# Expected: 409 passed, 2 skipped

# Frontend unit tests
cd frontend-ts
npm run test -- --run
# Expected: 28 passed

# Frontend E2E tests
cd frontend-ts
npm run test:e2e
# Expected: 20 passed

# Or use make from project root
make test
```

### Code Style

```bash
# From project root
make format      # Format code
make lint        # Run linting

# Or manually
cd backend-py
black src/
pylint src/
mypy src/
```

## Contributing

Contributions welcome! Please:

1. Read the [architecture documentation](docs/architecture.md)
2. Follow code style guidelines
3. Add tests for new features
4. Update documentation

## License

MIT License - See LICENSE file for details
