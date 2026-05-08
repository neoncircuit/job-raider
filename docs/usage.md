# Job Raider - User Guide

## Quick Start

### Prerequisites

- Python 3.10+
- WSL 2 (Windows) or Linux/macOS
- NVIDIA GPU with 8GB+ VRAM (recommended)
- Ollama installed (for local models)
- Anthropic API key (optional, for fallback)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/job-raider.git
cd job-raider

# Run setup (creates backend-py/.venv, installs Python + Node deps)
./setup.sh

# Pull Ollama models
ollama pull qwen2.5:3b
ollama pull qwen2.5:7b

# Configure backend credentials
cp backend-py/.env.example backend-py/.env
# Edit backend-py/.env — add ANTHROPIC_API_KEY, RAPIDAPI_KEY, API_KEY

# Configure frontend
cp frontend-ts/.env.example frontend-ts/.env.local
# Edit frontend-ts/.env.local — set BACKEND_API_URL and API_KEY (must match backend)
```

### Running Locally

```bash
# Start both services together
make dev

# Or start them individually
make dev-api          # FastAPI backend on :8000
make dev-frontend     # Next.js dashboard on :3000
```

Open http://localhost:3000 in your browser.

### Basic Usage

#### Interactive Mode

```bash
cd backend-py
python main.py --interactive
```

This will guide you through:
1. Providing your resume path
2. Entering job keywords
3. Specifying locations
4. Choosing sources
5. Confirming options

#### CLI Mode

```bash
# Basic search with dry run
cd backend-py
python main.py \
  --resume my_resume.pdf \
  --keywords "python engineer" \
  --locations "new york remote" \
  --dry-run

# Full pipeline with submission
cd backend-py
python main.py \
  --resume my_resume.pdf \
  --keywords "fintech AI" \
  --locations "remote" \
  --sources linkedin jsearch \
  --no-dry-run

# Resume from specific stage
cd backend-py
python main.py \
  --resume my_resume.pdf \
  --keywords "SWE" \
  --start-from score_and_rank
```

## Command-Line Options

### Required Arguments

| Option | Description |
|--------|-------------|
| `--resume PATH` | Path to your resume (PDF or DOCX) |
| `--keywords WORDS` | Job keywords to search (space-separated) |
| `--locations LOCS` | Job locations (space-separated) |

### Optional Arguments

#### Search Options

| Option | Description | Default |
|--------|-------------|---------|
| `--sources` | Sources to search | all |
| `--target-keywords` | Additional profile keywords | - |
| `--target-locations` | Additional profile locations | - |
| `--target-experience` | Experience levels | - |

#### Pipeline Options

| Option | Description | Default |
|--------|-------------|---------|
| `--dry-run` | Simulate submissions | true |
| `--no-dry-run` | Enable actual submissions | - |
| `--skip-submission` | Skip submission entirely | false |
| `--start-from STAGE` | Resume from stage | - |
| `--stop-at STAGE` | Stop at stage | - |

#### Scoring Options

| Option | Description | Default |
|--------|-------------|---------|
| `--min-score` | Minimum relevance (0-100) | 60 |
| `--scam-threshold` | Scam confidence (0-1) | 0.7 |
| `--max-jobs` | Jobs to present | 20 |

#### Submission Options

| Option | Description | Default |
|--------|-------------|---------|
| `--submission-delay` | Delay between submissions (sec) | 2.0 |
| `--max-submissions` | Max submissions per hour | 30 |

#### Storage Options

| Option | Description | Default |
|--------|-------------|---------|
| `--data-dir` | Data storage directory | data |
| `--results-dir` | Results directory | data/results |

#### Logging Options

| Option | Description | Default |
|--------|-------------|---------|
| `--log-level` | Logging level | INFO |
| `--log-file` | Log file path | stdout only |

## Usage Examples

### Example 1: First-Time User

```bash
# Interactive mode for first-time setup
cd backend-py
python main.py --interactive
```

### Example 2: Remote Job Search

```bash
cd backend-py
python main.py \
  --resume ~/Documents/my_resume.pdf \
  --keywords "remote python engineer" \
  --locations "remote united states" \
  --dry-run
```

### Example 3: Target Specific Companies

```bash
cd backend-py
python main.py \
  --resume ~/resume.pdf \
  --keywords "fintech blockchain" \
  --locations "new york san francisco" \
  --sources linkedin \
  --min-score 70
```

### Example 4: High-Volume Application

```bash
cd backend-py
python main.py \
  --resume ~/resume.pdf \
  --keywords "software engineer" \
  --locations "remote" \
  --max-jobs 50 \
  --no-dry-run
```

### Example 5: Resume from Specific Stage

```bash
# Resume from resume generation (skip scraping)
cd backend-py
python main.py \
  --resume ~/resume.pdf \
  --keywords "python" \
  --start-from generate_resumes
```

## Pipeline Stages

### Stage 1: Scrape

Scrapes job listings from configured sources.

```bash
# Specific sources only
cd backend-py
python main.py \
  --resume resume.pdf \
  --keywords "python" \
  --locations "remote" \
  --sources linkedin jsearch
```

### Stage 2: Deduplicate

Removes duplicate listings across sources.

### Stage 3: Filter Scams

Filters out potential scam listings using 10 indicators.

### Stage 4: Filter by Profile

Filters listings matching your profile preferences.

### Stage 5: Score and Rank

Scores listings by relevance (0-100 scale).

```bash
# Adjust minimum score
cd backend-py
python main.py \
  --resume resume.pdf \
  --keywords "python" \
  --locations "remote" \
  --min-score 70
```

### Stage 6: Detect Auto-Submit

Identifies "Easy Apply" opportunities.

### Stage 7: Present Selection

Shows ranked list for selection.

```bash
# Adjust number of jobs presented
cd backend-py
python main.py \
  --resume resume.pdf \
  --keywords "python" \
  --locations "remote" \
  --max-jobs 30
```

### Stage 8: Generate Resumes

Creates tailored resumes for selected jobs.

### Stage 9: Submit Applications

Submits applications (auto-submit where possible).

```bash
# Dry run (default)
cd backend-py
python main.py --resume resume.pdf --keywords "python" --locations "remote"

# Actual submissions
cd backend-py
python main.py --resume resume.pdf --keywords "python" --locations "remote" --no-dry-run

# Skip submission entirely
cd backend-py
python main.py --resume resume.pdf --keywords "python" --locations "remote" --skip-submission
```

## Working with Results

### Generated Resumes

Resumes are saved to `data/results/resumes/`:

```
data/results/resumes/
├── {job_id}.pdf
└── {job_id}.docx
```

### Application Tracking

Applications are tracked in `data/results/applications/`:

```bash
# View application status
cat data/results/applications/{app_id}.json
```

### Pipeline Results

Each run saves results to `data/results/pipeline_run_*.json`:

```bash
# View latest run
ls -lt data/results/pipeline_run_*.json | head -1
cat data/results/pipeline_run_TIMESTAMP.json
```

## Docker Usage

### Starting Services with Docker

The recommended way to run Job Raider is via the Docker startup script:

```bash
# Start all services (auto-detects available ports)
bash docker-run.sh
```

This script:
1. Finds available ports starting from 8000 (API), 11434 (Ollama), and 3000 (frontend)
2. Stops any existing containers
3. Builds images if needed
4. Starts all services in detached mode
5. Displays the assigned ports and access URLs

### Manual Docker Commands

```bash
# Start all services
docker-compose up -d

# View running containers
docker-compose ps

# View logs
docker-compose logs -f

# View logs for a specific service
docker-compose logs -f backend

# Stop all services
docker-compose down

# Rebuild and restart
docker-compose up -d --build
```

### Accessing the API

Once containers are running, the FastAPI interactive documentation is available at:

```bash
# If port 8000 is available
http://localhost:8000/docs

# If port 8000 is taken, the script assigns the next available port
http://localhost:8001/docs
```

Check assigned ports with:

```bash
docker ps --filter "name=job-raider" --format "table {{.Names}}\t{{.Ports}}"
```

### Accessing the Web Dashboard

The Next.js dashboard runs on port 3000:

```bash
http://localhost:3000
```

### Pulling Ollama Models

Models are stored in a persistent Docker volume and pulled on first use. To pre-pull models:

```bash
# Pull models into the Ollama container
docker exec job-raider-ollama ollama pull qwen2.5:3b
docker exec job-raider-ollama ollama pull qwen2.5:7b

# List available models
docker exec job-raider-ollama ollama list
```

### GPU Support

GPU acceleration is automatically available when:
1. An NVIDIA GPU is present on the host
2. The NVIDIA Container Toolkit is installed
3. Docker is configured with the NVIDIA runtime

Verify GPU passthrough:

```bash
docker exec job-raider-ollama nvidia-smi
```

### Docker Troubleshooting

#### Port Already Allocated

If you see `Bind for 0.0.0.0:8000 failed: port is already allocated`:

```bash
# Use docker-run.sh which auto-detects available ports
bash docker-run.sh

# Or manually find what's using the port
lsof -i :8000
docker ps --format "table {{.Names}}\t{{.Ports}}"
```

#### GPU Not Detected in Container

If Ollama logs show CPU-only inference:

```bash
# Check host GPU
nvidia-smi

# Check NVIDIA runtime is registered
docker info | grep -A 3 Runtimes

# Restart Docker Desktop (WSL) to pick up toolkit changes
```

## Best Practices

### 1. Start with Dry Run

Always start with dry-run mode:

```bash
cd backend-py
python main.py --resume resume.pdf --keywords "python" --locations "remote" --dry-run
```

### 2. Adjust Score Threshold

Find the right threshold for your goals:

```bash
# Higher quality, fewer matches
--min-score 80

# Balanced (recommended)
--min-score 60

# More matches, lower quality
--min-score 50
```

### 3. Use Specific Keywords

Better keywords = better matches:

```bash
# Too broad
--keywords "software engineer"

# Better
--keywords "python backend engineer"

# Best
--keywords "python django backend engineer fintech"
```

### 4. Check Scam Detection

Review scam filtering in logs:

```bash
# Run with debug logging
python main.py --resume resume.pdf --keywords "python" --log-level DEBUG
```

### 5. Monitor Submissions

Track submission history:

```bash
# Check application status
ls ../data/results/applications/
```

## Troubleshooting

### Issue: No jobs found

**Solutions:**
- Try broader keywords
- Add more locations
- Check if sources are accessible
- Lower `--min-score`

### Issue: Too many false positives

**Solutions:**
- Increase `--min-score` (try 70-80)
- Use more specific keywords
- Check scam detection logs

### Issue: Submissions failing

**Solutions:**
- Ensure `--dry-run` is disabled
- Check rate limiting settings
- Verify platform credentials
- Review error logs

### Issue: Ollama models not working

**Solutions:**
```bash
# Check Ollama is running
ollama list

# Pull missing models
ollama pull qwen2.5:3b
ollama pull qwen2.5:7b

# Check GPU support
nvidia-smi

# Check models from backend-py
cd backend-py
python scripts/check_ollama_models.py
```

## Advanced Usage

### Custom Configuration

Edit `backend-py/config/scoring_config.yaml` to customize:

```yaml
# Adjust scoring weights
weights:
  keywords: 30
  skills: 40
  experience: 20
  location: 10

# Set default keywords
default_keywords:
  - python
  - software engineer
  - remote
```

### Programmatic Usage

```python
import sys
sys.path.insert(0, 'backend-py')

from src.pipeline.orchestrator import PipelineOrchestrator, PipelineConfig
from src.models.user_profile import UserProfile
from src.extractors.resume_parser import ResumeParser

# Load profile
parser = ResumeParser()
profile = parser.parse("my_resume.pdf")

# Configure pipeline
config = PipelineConfig(
    keywords=["python", "engineer"],
    locations=["remote"],
    dry_run=True,
)

# Run pipeline
orchestrator = PipelineOrchestrator(config=config, user_profile=profile)
result = orchestrator.run()

print(f"Jobs scraped: {result.jobs_scraped}")
print(f"Jobs applied: {result.jobs_applied}")
```
