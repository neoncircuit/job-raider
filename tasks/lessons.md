# Job Raider - Lessons Learned

## Implementation Lessons

### Phase 7: Pipeline Implementation (2026-04-21)

#### Pipeline Stages Design

**Lesson:** Keep stages as pure functions that transform data and return StageResult objects.

**Why:**
- Makes testing easier - each stage can be tested independently
- Enables stage resumption - can start from any stage
- Clear error handling - each stage reports its own success/failure
- Better observability - metadata tracking at each stage

**How to apply:**
- Each stage should accept input data and return a StageResult
- StageResult includes: success boolean, data payload, metadata dict, timestamp, error_message
- Use PipelineContext to share state between stages
- Implement hooks for before/after stage callbacks

#### Two-Model Architecture

**Lesson:** Split expensive LLM operations into two stages: cheap selection model + expensive writing model.

**Why:**
- 80% cost reduction (selection uses local model)
- Better quality control (selection extracts signal before writing)
- Reduced hallucination (focused prompts for each stage)
- Faster iteration (selection is cheap to test)

**How to apply:**
- Use qwen2.5:3b for selection (projects, keywords, achievements)
- Use qwen2.5:7b for writing (resume generation)
- Always validate output deterministically (check projects present, keywords mentioned)

#### Dry Run Mode

**Lesson:** Always default to dry-run mode for submission operations.

**Why:**
- Prevents accidental submissions during development
- Allows testing without side effects
- User must explicitly enable with --no-dry-run flag

**How to apply:**
- AutoSubmitter dry_run=True by default
- CLI --dry-run flag is default
- Clear logging when in dry-run mode
- Save results even in dry-run for review

#### Documentation Needs

**Lesson:** Create documentation as you build, not after.

**Why:**
- Documentation clarifies design decisions
- Catches architectural issues earlier
- Makes onboarding easier
- Prevents "I'll document later" which never happens

**How to apply:**
- docs/architecture.md - System design and data flow
- docs/usage.md - Installation and usage examples
- docs/api.md - Complete API reference
- docs/troubleshooting.md - Common issues and solutions
- docs/index.md - Documentation hub

#### Task Tracking

**Lesson:** Keep tasks.md updated with current status as you progress.

**Why:**
- Clear progress tracking
- Easy to resume after context breaks
- Communication tool for collaborators
- Historical record of decisions

**How to apply:**
- Mark phases as [COMPLETED] when done
- Update summary percentages
- Note remaining work clearly
- Review before starting new session

## General Development Lessons

### Code Organization

**Lesson:** Use clear module boundaries with __init__.py exports.

**Why:**
- Clean public API
- Easier imports for users
- Encapsulates implementation details

**How to apply:**
- Each module has __init__.py with __all__
- Export only public interfaces
- Keep internals private (no leading underscore exports)

### Error Handling

**Lesson:** Use custom exceptions for domain-specific errors.

**Why:**
- Clearer error handling in calling code
- Easier to debug
- Better error messages for users

**How to apply:**
- ScrapingError for scraping failures
- LLMError for LLM client issues
- ValidationError for validation failures
- SubmissionError for submission problems

### Configuration

**Lesson:** Separate credentials (.env) from configuration (config/*.yaml).

**Why:**
- .env files should only contain sensitive data (API keys, secrets)
- Configuration settings belong in version-controlled YAML files
- Clear separation makes security audits easier
- Configuration can be templated and documented in-code
- Prevents accidentally committing secrets to version control

**How to apply:**
- `backend-py/.env.example` - Template for credentials only (API keys, tokens, passwords)
- `backend-py/config/app_config.yaml` - General settings, paths, monitoring, development flags
- `backend-py/config/model_config.yaml` - Model endpoints, routing, caching, rate limits
- `backend-py/config/scrapers_config.yaml` - Scraper settings, rate limits, browser automation
- `backend-py/config/search_config.yaml` - Default keywords, locations, filters
- `backend-py/config/scoring_config.yaml` - Scoring weights and thresholds
- `backend-py/config/logging_config.yaml` - Logging configuration
- `backend-py/config/prompt_templates.yaml` - LLM prompt templates
- Document the two-tier approach in README.md and DOCKER.md

### Logging

**Lesson:** Use structured logging with component-specific loggers.

**Why:**
- Easy to filter by component
- Clear log ownership
- Better debugging

**How to apply:**
- Components enum with logger names
- get_logger(Components.SCRAPERS)
- Consistent log levels (DEBUG, INFO, WARNING, ERROR)
- Include context in log messages

## Lessons to Apply Future

### Testing

**Need:** Add comprehensive tests for each component.

**Plan:**
- Unit tests for each module
- Integration tests for pipeline
- Mock external services (scrapers, LLM)
- Test validation logic thoroughly

### Metrics

**Need:** Add cost tracking and outcome tracking.

**Plan:**
- Track API costs per run
- Track applications -> interviews -> offers
- Calculate success rate
- Optimize based on data

### Deployment

**Need:** Containerize for cloud deployment.

**Plan:**
- Docker image with Ollama + models
- GPU support for local inference
- Scheduled runs via cron
- Health checks and monitoring

### CI/CD

**Need:** Add automated checks.

**Plan:**
- GitHub Actions for linting
- Run tests on PR
- Type checking with mypy
- Documentation build check


## Additional Lessons Learned

### Phase 8-9 Extras (2026-04-21)

#### Health Check Architecture

**Lesson:** Implement comprehensive health checks before deployment.

**Why:**
- Catches configuration issues early
- Monitors GPU VRAM availability for local models
- Ensures data directories are writable
- Validates external service availability (Ollama)

**How to apply:**
- Create modular health check classes (DiskSpaceCheck, GPUMemoryCheck, etc.)
- Use status levels: HEALTHY, DEGRADED, UNHEALTHY, UNKNOWN
- Aggregate results in HealthMonitor
- Provide both programmatic and console output options

#### VRAM Monitoring

**Lesson:** Proactive VRAM monitoring prevents OOM errors.

**Why:**
- GPU memory is limited (8GB on RTX 3070 Ti)
- LLM models can exceed available memory
- OOM errors crash the entire pipeline

**How to apply:**
- Monitor VRAM at regular intervals (background thread)
- Alert when free memory drops below thresholds (500MB critical, 1GB warning)
- Recommend appropriate model sizes based on available VRAM
- Enable CPU fallback when GPU is full

#### Report Generation

**Lesson:** Automated reports provide visibility into pipeline effectiveness.

**Why:**
- Tracks cost per application over time
- Measures conversion funnel (applied → interview → offer)
- Identifies optimization opportunities
- Documents ROI of automated approach

**How to apply:**
- Calculate effectiveness score from multiple metrics
- Generate HTML reports for easy viewing
- Save JSON for programmatic access
- Include actionable recommendations

#### A/B Testing Framework

**Lesson:** A/B testing enables data-driven optimization.

**Why:**
- Different scoring weights may work better for different job types
- Threshold tuning affects quality vs quantity trade-off
- Experiments provide evidence for configuration decisions

**How to apply:**
- Create ExperimentConfig with variant A/B configurations
- Run same jobs through both variants
- Compare pass rates, average scores
- Calculate significance of differences
- Save best configuration for future runs

### Verification Phase (2026-04-21)

#### Cost Optimization Achievement

**Lesson:** Local models achieve zero marginal cost.

**Why:**
- Ollama with qwen2.5 models is completely free after initial download
- $0.00 per 50 applications (far exceeds <$0.50 target)
- Even hybrid approach (10% API) costs only ~$0.05

**How to apply:**
- Default to local models for all operations
- Use API only as fallback for missing capabilities
- Cost enables aggressive application without financial concerns

#### System Readiness

**Lesson:** Verification ensures production readiness.

**Why:**
- Confirms all modules are importable
- Validates project structure is sound
- Verifies external dependencies (Ollama, GPU) are available
- Tests core algorithms independently

**How to apply:**
- Test imports without full dependency installation
- Verify syntax with py_compile
- Check GPU availability with nvidia-smi
- Validate algorithm logic with unit tests

### Docker Containerization (2026-04-22)

#### Sanity Check Findings (2026-04-22)

##### Test Suite Drift

**Lesson:** Tests must be updated when model schemas change, or the entire test suite breaks silently.

**Why:**
- `test_models.py` creates `JobListing` with plain strings for `requirements`, `responsibilities`, `skills` but the models now expect Pydantic sub-objects (`JobRequirement`, `JobResponsibility`, `Skill`)
- `test_models.py` references `JobListingCollection.jobs` which doesn't exist
- `test_metrics.py::test_update_status` fails with `'dict' object has no attribute 'append'`
- `test_pipeline.py` uses `pytest.config.getoption()` which doesn't exist in modern pytest

**How to apply:**
- After any model schema change, grep tests for the old interface and update
- Run the full test suite after model refactors, not just the module's own tests
- Use `pytest.config` via `request.getfixturevalue` or `pytest_configure` instead of the deprecated module-level attribute

##### Pydantic V1 Deprecation

**Lesson:** Migrate from Pydantic V1 to V2 patterns before they break.

**Why:**
- `@validator` is deprecated in Pydantic V2 and will be removed in V3
- `class Config:` pattern is deprecated in favor of `model_config = ConfigDict(...)`
- `json_encoders` is deprecated
- These warnings appear in every test run and mask real issues

**How to apply:**
- Replace `@validator` with `@field_validator` in `job_listing.py` and `user_profile.py`
- Replace `class Config:` with `model_config = ConfigDict(...)` in `JobListing` and `UserProfile`
- Test that all serialization still works after migration

##### CI Workflow Path Issues

**Lesson:** CI workflows must set `working-directory` for monorepo projects.

**Why:**
- All lint/test commands ran from repo root but `src/` and `tests/` are inside `backend-py/`
- `requirements.txt` doesn't exist at root level
- `pip cache` action needs `cache-dependency-path` to point to the correct requirements file

**How to apply:**
- Use `defaults: run: working-directory: backend-py` for each job
- Set `cache-dependency-path` in `setup-python` action
- Add a separate `test-frontend` job for `frontend-py/`

#### Dynamic Port Allocation

**Lesson:** Use environment variable interpolation in docker-compose.yml for flexible port mapping.

**Why:**
- Fixed port bindings (`"8000:8000"`) fail when another service already uses that port on the host
- Docker Compose supports `${VAR:-default}` syntax in extended port definition format
- The `find-port.sh` script discovers available ports at startup

**How to apply:**
- Use extended port syntax in docker-compose.yml: `target: 8000, published: "${BACKEND_PORT:-8000}"`
- Shell-only `"8000"` only exposes inside the Docker network, not to localhost
- Use `docker-run.sh` which calls `find-port.sh` for automatic port discovery

#### Verify COPY Targets Exist

**Lesson:** Dockerfile COPY directives fail the build if the source file doesn't exist. Always verify against the actual filesystem.

**Why:**
- The dockerfile referenced `backend-py/setup.sh`, `backend-py/README.md`, and `backend-py/CLAUDE.md` which didn't exist
- Docker doesn't resolve these lazily -- it fails at build time
- Stale references accumulate as project structure evolves

**How to apply:**
- Before building, verify all COPY source paths: `ls backend-py/setup.sh backend-py/README.md`
- Remove COPY lines for non-essential files (documentation, setup scripts) that aren't needed at runtime
- Only COPY what the container actually needs: requirements.txt, config/, src/, main.py

#### Ollama Install Requires zstd

**Lesson:** The Ollama install script (`curl -fsSL https://ollama.com/install.sh | sh`) requires the `zstd` compression tool, which is not included in minimal Ubuntu base images.

**Why:**
- Ollama's binary distribution is compressed with zstd
- `nvidia/cuda` base images are minimal and don't include zstd by default
- The install script exits with a clear error but only after downloading

**How to apply:**
- Add `zstd` to the system dependencies list in the Dockerfile's first `apt-get install` step
- Place it alongside other system tools (curl, git, wget)

#### Ollama Pull Requires Running Server

**Lesson:** `ollama pull` requires a running Ollama server daemon. It cannot execute during `docker build` because no services are running in the build context.

**Why:**
- `ollama pull` communicates with the Ollama server via its API
- During `docker build`, only the build steps execute -- no background daemons
- Models must be pulled either at container startup or via a separate Ollama container

**How to apply:**
- Remove `RUN ollama pull` commands from the Dockerfile
- Use a separate Ollama container in docker-compose.yml with a persistent volume for model storage
- Models are pulled on first use or via `docker exec job-raider-ollama ollama pull qwen2.5:3b`

#### CUDA Base Image Deprecation

**Lesson:** NVIDIA CUDA base images have a support lifecycle and get deprecated. Using deprecated images produces warnings and may be deleted.

**Why:**
- `nvidia/cuda:12.1.0-runtime-ubuntu22.04` triggered a deprecation notice during build
- Deprecated images may be removed from Docker Hub without notice
- Newer images include security patches and updated libraries

**How to apply:**
- Use current CUDA versions (12.4.0+ as of 2026-04-22)
- Check NVIDIA's support policy: https://gitlab.com/nvidia/container-images/cuda/blob/master/doc/support-policy.md
- Periodically update the base image version

#### Docker Desktop in WSL

**Lesson:** When running Docker via Docker Desktop for Windows in WSL, `systemctl restart docker` does not work because Docker is managed by the Windows application, not systemd.

**Why:**
- Docker Desktop runs as a Windows process that provides the Docker daemon to WSL
- WSL's systemd does not manage Docker Desktop
- The daemon.json config is shared between Windows and WSL

**How to apply:**
- After modifying `/etc/docker/daemon.json`, restart Docker Desktop via the Windows system tray icon
- Close and relaunch the Docker Desktop application
- Verify changes with `docker info | grep Runtimes`

#### GPU Passthrough Verification

**Lesson:** After installing the NVIDIA Container Toolkit, verify GPU passthrough works before deploying application containers.

**Why:**
- The toolkit must be installed, Docker configured, and Docker restarted -- all three steps are required
- A misconfigured toolkit silently falls back to CPU, causing slow inference without errors
- Quick verification catches issues early

**How to apply:**
- Install toolkit: `sudo apt-get install -y nvidia-container-toolkit`
- Configure Docker: `sudo nvidia-ctk runtime configure --runtime=docker`
- Restart Docker Desktop (WSL) or `sudo systemctl restart docker` (native Linux)
- Verify: `docker run --rm --gpus all nvidia/cuda:12.4.0-runtime-ubuntu22.04 nvidia-smi`
- In docker-compose.yml, add GPU reservation under the Ollama service: `deploy.resources.reservations.devices`

### Test Suite Fixes (2026-04-23)

#### Comprehensive Test Repair

**Lesson:** When model schemas change, update the entire test suite, not just the model's own tests.

**Why:**
- Tests in other modules may use the old interface
- Pydantic V2 requires sub-objects (JobRequirement, JobResponsibility, Skill) instead of plain strings
- MatchScore changed from individual attributes to a breakdown dict
- Import shadowing causes issues when two modules have classes with the same name

**How to apply:**
- After any model schema change, grep all tests for the old interface
- Run the full test suite after model refactors: `pytest tests/ -v`
- Use aliased imports to avoid shadowing: `from src.models.job_listing import Skill as JobSkill`
- Update assertion patterns: `score.breakdown["keyword"]` instead of `score.keyword_score`
- Fix type annotations to match runtime behavior: `List[Dict[str, str]]` not `List[str]` with dict factory

#### Environment Variable vs Configuration

**Lesson:** Keep .env for credentials only, move all configuration to YAML files.

**Why:**
- .env files are for secrets that shouldn't be committed
- Configuration values (timeouts, thresholds, defaults) belong in version-controlled config files
- Makes it clear what needs to be secured vs what can be shared
- Aligns with 12-factor app methodology

**How to apply:**
- Create config files for each domain: scrapers_config.yaml, search_config.yaml, app_config.yaml
- Keep only API keys, tokens, and passwords in .env
- Document the two-tier approach in README.md
- Update docker-compose.yml to use the correct env_file path

#### Test Fix Summary

**Tests Fixed (2026-04-23):**
1. `pytest.config` deprecation → Use `request.getfixturevalue` or add `pytest_configure` to conftest.py
2. JobListing plain strings → Create JobRequirement, JobResponsibility, Skill objects
3. MatchScore attributes → Use `score.breakdown["keyword"]` dict access pattern
4. timeline_notes type → Changed from `List[str]` with `dict` factory to `List[Dict[str, str]]` with `list` factory
5. ResumeSelector/ResumeWriter → Pass `llm_router` parameter
6. setup_logging args → Changed `level=` to `log_level=`, `log_file` to `log_dir`
7. Skill import shadowing → Use `Skill as JobSkill` alias
8. QuickFilter return → Updated test to expect JobListingCollection
9. docker-compose env_file → Changed to `backend-py/.env`

**Result:** 55/55 backend tests passing, 55/55 frontend tests passing

### API Development & UX (2026-04-24)

#### Attribute Name Consistency

**Lesson:** Model attribute names must match exactly between definition and usage.

**Why:**
- UserProfile model uses `experience` but profile route used `work_experience`
- UserProfile model uses `targets` but profile route used `target_job`
- Skill model uses `years_of_experience` but profile route used `years_experience`
- Education model uses `school` but profile route used `institution`
- Education model uses `end_date` but profile route used `graduation_date`
- These mismatches caused AttributeError exceptions at runtime

**How to apply:**
- Always reference actual model attributes when writing API response code
- Use type hints and IDE autocomplete to avoid guessing attribute names
- Run the actual code path before marking task complete - "Would a staff engineer approve this?"
- Test with real data, not just mock data
- grep for attribute usage after model changes to find all references

#### Resume Parsing Validation

**Lesson:** Resume extraction patterns must be carefully validated to avoid false matches.

**Why:**
- Location regex `r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?),\s*([A-Z]{2})'` matched "Data Structures" as a location
- The pattern looked for "Word Word, ST" but could match any two capitalized words
- False matches lead to confusing user experience ("Location: Data Structures")

**How to apply:**
- Add validation logic to check match quality (length, structure)
- Use more specific patterns with context cues ("Location:", "City:", etc.)
- Test against real resume data, not synthetic examples
- Add fallback logic when confidence is low (return "Unknown" rather than bad data)
- Consider multiple pattern attempts with decreasing specificity

#### Browser-Based Settings Architecture

**Lesson:** For single-user applications, browser-based settings avoid authentication complexity.

**Why:**
- Full user authentication requires database, sessions, password management, security
- Streamlit session state + file persistence provides sufficient UX for personal use
- Each browser has its own settings, which is actually desirable for shared devices
- Simplifies implementation dramatically (no auth UI, no database migrations)

**How to apply:**
- Store settings in Streamlit session state (`st.session_state._settings`)
- Persist to file on save (`data/settings.json`)
- Load from file on app startup
- Use localStorage for cross-session persistence (optional)
- Consider per-user settings only when multi-tenant requirements exist

#### Settings Implementation Order

**Lesson:** Implement settings from bottom-up: models → storage → API → UI.

**Why:**
- Starting with UI leads to discovering missing backend capabilities mid-stream
- Having models first ensures API contract is clear
- Storage layer provides defaults to build from
- API can be tested independently before UI integration

**How to apply:**
1. Define Pydantic models with validation (UserSettings, ModelRouting, APIConfig, etc.)
2. Create storage layer with defaults and file I/O (SettingsStorage)
3. Build API endpoints with proper error handling
4. Add API client methods for frontend consumption
5. Finally build UI - the API contract is stable and testable

#### Navigation UI Patterns

**Lesson:** Navigation should clearly distinguish active from inactive states.

**Why:**
- Radio buttons provide no visual distinction for current page
- Users need immediate feedback on where they are in the app
- Gradient backgrounds and shadows create professional appearance
- Icons improve visual scanning and navigation

**How to apply:**
- Use different styling for active vs inactive navigation items
- Active: gradient background, white text, shadow
- Inactive: clickable buttons
- Add contextual icons for each page type
- Consider collapsible sections for complex navigation

### Production Readiness (2026-04-25)

#### Ollama Client: Wrong Endpoint and Double Port

**Lesson:** Ollama's `/api/generate` expects a `prompt` string, not a `messages` array. Use `/api/chat` for message-based conversations.

**Why:**
- `/api/generate` with a `messages` payload silently hangs or returns empty responses
- `/api/chat` accepts `messages` array and returns `data.message.content`
- `OLLAMA_HOST=ollama:11434` was treated as hostname, then `:11434` was appended again producing `ollama:11434:11434`

**How to apply:**
- Use `/api/chat` for any message-based LLM interaction
- Parse the response with `data["message"]["content"]`
- When consuming host:port env vars, check if the host already contains a port before appending

#### Python str.format() vs YAML Templates

**Lesson:** Never use `str.format()` with YAML templates containing JSON examples. The `{{ }}` escaping for literal braces also prevents variable substitution.

**Why:**
- `{{profile_context}}` becomes literal string `{profile_context}`, not the variable value
- LLM receives `{profile_context}` instead of actual profile data and responds asking for the resume
- Use `str.replace("{{var}}", value)` instead of `str.format()` for templates with JSON

**How to apply:**
- Use `.replace("{{key}}", value)` for prompt template substitution
- Never mix `str.format()` with templates that contain literal JSON braces

#### Resume Parser Must Handle LLM JSON Variations

**Lesson:** LLMs return structurally correct but semantically varied JSON. Field names differ across runs and models. Never assume exact key names.

**Why:**
- LLM returned `position` instead of `title`, `achievements` instead of `highlights`, `dates` instead of `start_date`/`end_date`
- `technical_skills` instead of `skills`, `profile` instead of `summary`
- `description` field was a list instead of string, crashing Pydantic validation
- The bare `except` in `_parse_with_llm` silently swallowed all errors and fell back to rule-based parsing

**How to apply:**
- Normalize keys at the top of `_create_profile_from_dict`: try multiple common variants
- Coerce types before passing to Pydantic (list to string, etc.)
- Never use bare `except` -- always log the error before falling back
- Add `_split_date_range()` for parsing combined date strings

#### Resume Analysis: Separate Factual Data from LLM Qualitative Output

**Lesson:** Small local models (qwen2.5:7b) hallucinate when asked to reproduce structured data. Build factual data directly from parsed input, only ask LLM for qualitative assessment.

**Why:**
- LLM generated fabricated companies and job titles instead of using the actual profile data
- Profile-derived data (skills, experience, projects) is already structured and truthful
- LLM is better at scoring, summarizing, and recommending than at faithful data reproduction

**How to apply:**
- Build `skills_assessment`, `experience_insights`, `project_insights` directly from parsed UserProfile
- Only ask LLM for: overall_score, summary, key_strengths, key_improvements, recommendations
- This guarantees factual accuracy while still getting AI-powered insights

#### Container Network Connections Go Stale After Recreate

**Lesson:** When a Docker container is recreated (new image), other containers on the same network may hold stale DNS/connection references to it.

**Why:**
- Frontend container created before backend rebuild keeps old IP/connection
- Health check from frontend to backend times out even though both are running
- Docker DNS updates don't always propagate immediately to connected containers

**How to apply:**
- Recreate frontend whenever backend is recreated: `docker compose up -d --force-recreate frontend`
- Run uvicorn with multiple workers so one LLM call doesn't block health checks
- Increase frontend request timeout to accommodate LLM processing time
- Show "Processing..." instead of "Unreachable" when backend was previously healthy

#### Dockerfile Naming Convention

**Lesson:** Use consistent uppercase `Dockerfile` naming and organize in a dedicated directory.

**Why:**
- Root-level lowercase `dockerfile` alongside `docker/Dockerfile` caused ambiguity
- Case-sensitive filesystems (Linux) treat `dockerfile` and `Dockerfile` as different files
- Multiple Dockerfiles without clear naming leads to confusion about which is used
- `docker-compose.yml` and CI must reference the same path

**How to apply:**
- Place all Dockerfiles under `docker/` with descriptive names: `Dockerfile` (production), `Dockerfile.dev` (development)
- Keep frontend Dockerfile in its own context: `frontend-py/docker/Dockerfile`
- Reference consistently in docker-compose.yml and CI workflows

#### Streamlit Form Context Manager

**Lesson:** `st.form()` is a context manager and must use `with`, not `if`.

**Why:**
- `if st.form(...)` evaluates truthiness but does not enter the form context
- `st.form_submit_button()` inside `if` block raises `StreamlitAPIException`
- Form widgets must all be inside the `with` block to be captured on submit
- Buttons that trigger immediate actions (Reset, Validate) cannot live inside forms

**How to apply:**
- Always use `with st.form("name"):` pattern
- Place all input widgets and the submit button inside the form block
- Move action buttons (reset, validate) outside the form context
- Test the settings page after any form restructuring

#### Missing __init__.py Silently Breaks Imports

**Lesson:** A Python package directory without `__init__.py` cannot be imported, but this often goes unnoticed until runtime.

**Why:**
- Python requires `__init__.py` (even empty) to recognize a directory as a package
- The module works when run directly but fails when imported from elsewhere
- IDE autocomplete may not flag the missing file
- Error manifests as `ModuleNotFoundError` in unrelated code paths

**How to apply:**
- Every directory under `src/` must have an `__init__.py`
- Check for missing `__init__.py` files when adding new packages
- Add to pre-commit checks or CI validation

#### CI continue-on-error Masks Failures

**Lesson:** Excessive `continue-on-error: true` in CI pipelines hides real failures, giving false confidence.

**Why:**
- Tests marked `continue-on-error` pass CI even when they fail
- Docker build/push marked `continue-on-error` silently skips deployment
- Only truly optional steps should use it (codecov upload, informational linting)
- Green CI badges become meaningless when failures are suppressed

**How to apply:**
- `continue-on-error: true` only for: codecov upload, pylint informational, mypy, security scan reports
- Remove from: test runs, Docker login, Docker build/push
- CI should fail loudly on anything blocking deployment

### LinkedIn Scraper & Docker Runtime (2026-04-25)

#### LinkedIn URL Format Changes

**Lesson:** Web scrapers must handle URL format evolution. LinkedIn changed from path-based IDs to slug-embedded IDs.

**Why:**
- Old format: `/jobs/view/1234567890/` (ID as path component)
- New format: `/jobs/view/software-engineer-at-notion-4406118990` (ID at end of slug)
- `part.isdigit()` fails on the new format - the entire slug isn't numeric
- Pydantic validation crashes when `job_id` is None

**How to apply:**
- Use regex `re.findall(r'\d+', part)` to extract numbers from any position
- Return the last number found (typically the job ID)
- Test scrapers against actual live URLs regularly
- Add error logging for failed extractions instead of silent None returns

#### API Response Must Handle Nulls

**Lesson:** When constructing API responses from Pydantic models, always check for None/null fields before operations like slicing or substring.

**Why:**
- `listing.description[:500]` crashes with `TypeError: 'NoneType' object is not subscriptable`
- Job listings from scraping often have None for optional fields
- API returns 500 instead of graceful degradation

**How to apply:**
- Use `(listing.description or "")[:500]` pattern for null-safe slicing
- Check optional fields before use: `listing.source_url or None`
- Use `hasattr()` for attributes that may not exist: `hasattr(listing, 'scraped_at') and listing.scraped_at`
- Always test API with scraped data, not just synthetic test data

#### Attribute Name Consistency Across Models

**Lesson:** Pydantic model attributes must match exactly in API serialization code. IDE autocomplete is your friend.

**Why:**
- `JobListing` has `source_url`, not `url`
- `JobListing` has `is_remote`, not `remote`
- `JobListing` enum values need `.value` to serialize as strings
- Typos cause 500 errors that are hard to trace

**How to apply:**
- Always use IDE autocomplete when referencing model attributes
- Check the actual model definition before writing serialization code
- Use type hints to catch mismatches at development time
- Test API endpoints with real scraped data

#### Docker Build vs Runtime Dependencies

**Lesson:** Network-dependent resources should be installed at runtime, not build time. Build environments have unreliable network access.

**Why:**
- `playwright install chromium` fails during `docker build` with DNS errors
- CDN availability varies by region and time
- Build failures waste time and create confusion
- Runtime installation succeeds because container has stable network

**How to apply:**
- Move Playwright browser install to entrypoint script
- Check if browsers exist before installing: `if [ ! -d "/home/jobraider/.cache/ms-playwright/chromium-1208" ]`
- Install on first run, cache persists for container lifetime
- Use `ENTRYPOINT` directive to run setup before main command

#### Dockerfile Permission Order Matters

**Lesson:** `chmod` must happen before `USER` switch. Files copied as root cannot be modified by non-root user after USER directive.

**Why:**
- `chmod +x` after `USER jobraider` fails with "Operation not permitted"
- Files are owned by root when copied before USER directive
- Permission changes require root or file owner privileges

**How to apply:**
- Copy entrypoint script as root
- `RUN chmod +x` immediately after COPY
- Switch to non-root user AFTER all permission changes
- Verify permissions during build: `RUN ls -la /usr/local/bin/docker-entrypoint.sh`

### Job Application Tracker (2026-04-25)

#### Extending Enums vs Creating New Models

**Lesson:** Extend existing enums when adding closely related states rather than creating entirely new models.

**Why:**
- `ApplicationStatus` enum already tracks application lifecycle
- Adding `SAVED_BOOKMARKED`, `APPLIED_ELSEWHERE`, `NOT_INTERESTED` keeps all status logic in one place
- Single `ApplicationOutcome` model can hold all application types with flag fields
- Avoids data fragmentation across multiple similar models

**How to apply:**
- Add new enum values to existing status enums before creating separate tracking models
- Use boolean flags (`is_bookmarked`, `is_hidden`) for quick filtering
- Add optional fields (`custom_status_id`) for extended functionality
- Keep data models flexible with optional fields rather than creating many specialized models

### JSearch API Integration (2026-04-25)

#### Cloudflare Bot Detection Kills Web Scraping

**Lesson:** Major job boards (Indeed, Glassdoor, Jobstreet) employ Cloudflare bot detection that blocks headless Chromium. Playwright-based scrapers are no longer viable for most commercial job boards.

**Why:**
- Cloudflare returns "Just a moment..." challenge pages to headless browsers
- Anti-bot measures include browser fingerprinting, TLS fingerprinting, and JS challenges
- Indeed returns "Blocked - Indeed.com", Glassdoor returns "Humans only"
- Even with custom user agents and delays, detection is reliable
- This is an industry-wide trend, not a temporary issue

**How to apply:**
- Use official APIs or aggregation services (JSearch via RapidAPI) instead of web scraping
- Keep Playwright scrapers for sites that allow it (LinkedIn currently works)
- Design scrapers behind an interface so implementations can be swapped easily
- Have fallback mechanisms when a scraper stops working

#### API-Based Scrapers vs Playwright Scrapers

**Lesson:** When inheriting from `BaseScraper` for API-based scrapers, override `search()` directly and stub the Playwright-specific abstract methods with `NotImplementedError`.

**Why:**
- `BaseScraper.search()` calls `build_search_url()` then `_fetch_page()` (Playwright) then `parse_job_listings()` (HTML)
- API scrapers skip all of this -- they make a single HTTP request and parse JSON
- Forcing API responses through the HTML pipeline is unnecessary complexity
- Stub methods clearly communicate "this scraper works differently"

**How to apply:**
- Override `search()` entirely in API-based scrapers
- Stub `build_search_url()`, `parse_job_listings()` with `NotImplementedError` and clear docstrings
- `get_job_details()` can call a separate API endpoint if available
- The interface (source_name property + search method) is what matters, not the implementation

#### Dynamic Sources Prevent Hard-Coding Drift

**Lesson:** Fetch available sources from the backend dynamically instead of hard-coding them in the frontend. Adding a new scraper should require backend changes only.

**Why:**
- Hard-coded `["linkedin", "indeed", "glassdoor"]` appeared in 3 frontend locations
- Adding JSearch required updating all 3 manually
- Frontend may be deployed separately from backend, causing stale lists
- Backend knows its registered scrapers -- it is the source of truth

**How to apply:**
- Backend endpoint (`GET /api/jobs/sources`) returns registered scraper names
- Frontend caches in session state with fallback to defaults
- New scrapers appear automatically when backend is updated
- Fallback ensures frontend works even when backend is unreachable

#### Graceful Degradation When External APIs Are Unavailable

**Lesson:** When an external API key is missing or the API is unreachable, return empty results rather than crashing. Log the error clearly.

**Why:**
- `RAPIDAPI_KEY` may not be set on first deploy
- Other scrapers (LinkedIn) should still work independently
- Crashing the entire search because one scraper is misconfigured is poor UX
- Users see "0 results" and check logs, not a 500 error

**How to apply:**
- Check for API key in scraper `__init__`, raise `ScraperError` in `search()` with clear message
- `ScraperManager` catches exceptions per-source and logs them, continues with other sources
- Frontend shows total results from all working sources
- Backend logs which source failed and why: `jsearch: scraping failed - RAPIDAPI_KEY environment variable not set`

**Lesson:** LLMs often return URLs without schemes (missing `https://`). Always normalize URLs before Pydantic validation.

**Why:**
- LLM returns `linkedin.com/in/james-tan-2160b8154` instead of `https://linkedin.com/in/james-tan-2160b8154`
- Pydantic `HttpUrl` type requires full URLs with schemes
- Validation crashes with `url_parsing` error on scheme-less URLs
- Users paste partial URLs in resume data which LLM learns from

**How to apply:**
- Create helper method `_normalize_url()` that adds `https://` if missing
- Apply normalization before passing to Pydantic models: `ContactInfo(linkedin=_normalize_url(raw_url))`
- Always handle None values before normalization
- Test with real LLM output, not just synthetic data

#### Logger Attribute Missing in Classes

**Lesson:** When using `self.logger` in a class, always initialize it in `__init__`. Python doesn't provide implicit loggers.

**Why:**
- Code used `self.logger.error()` but logger was never initialized
- Result: `AttributeError: 'ResumeParser' object has no attribute 'logger'`
- Error only surfaced when exception handling path was exercised
- Stack trace pointed to exception handler, not root cause

**How to apply:**
- Initialize logger in `__init__`: `self.logger = get_logger(Components.SCRAPERS)`
- Or use module-level logger: `logger = logging.getLogger(__name__)`
- Test exception handling paths, not just happy paths
- Add logging immediately when catching exceptions

#### Module-Level vs Instance-Level Loggers

**Lesson:** Use module-level loggers for utility classes and instance-level loggers for stateful objects.

**Why:**
- Module-level `logger = logging.getLogger(__name__)` works everywhere
- Instance-level `self.logger` requires initialization in each class
- Module-level is simpler for classes that don't have per-instance logging needs
- Instance-level is better when logger needs instance context

**How to apply:**
- Use module-level logger for stateless utility classes
- Use instance-level logger for stateful classes that track multiple entities
- Be consistent within a module - don't mix both patterns

#### Docker Image Tagging Consistency

**Lesson:** Ensure Docker image tags match what docker-compose.yml expects to avoid "none" image references.

**Why:**
- Building with `-t job-raider:latest` creates tag different from `job-raider-backend:latest`
- Running containers reference old SHA hash instead of tagged name
- Recreated containers still use old image until retagged
- Confusion about which image is actually running

**How to apply:**
- Build with correct tag: `docker build -t job-raider-backend:latest`
- Use `docker tag` to rename if needed: `docker tag old:latest new:latest`
- Remove old tag: `docker rmi old:latest`
- Recreate containers after retagging: `docker-compose up -d --force-recreate`

#### File-Based Storage Design Patterns

**Lesson:** When using file-based JSON storage, create subdirectories for related entity types.

**Why:**
- Custom statuses are different from applications and need separate storage
- `data/applications/*.json` for applications, `data/applications/custom_statuses/*.json` for statuses
- Keeps storage organized and makes cleanup easier
- Prevents filename collisions between different entity types

**How to apply:**
- Create subdirectories for each major entity type
- Use consistent naming: `{entity_id}.json` for files
- Load all entities from subdirectory on startup
- Save immediately after any changes for persistence

### Frontend UI Overhaul - SupCareer-Inspired (2026-04-25)

#### Nested HTML Divs Break in Streamlit Markdown

**Lesson:** Never use nested `<div>` blocks with `st.markdown(unsafe_allow_html=True)`. Streamlit's markdown renderer does not reliably handle block-level HTML -- closing tags like `</div>` appear as visible text.

**Why:**
- A compact job card using `<div>` with nested `<div>` for title and metadata rendered raw `</div>` in the UI
- Even well-formed HTML can break due to Streamlit's internal markdown-to-HTML pipeline
- The issue is inconsistent -- sometimes it works, sometimes it doesn't

**How to apply:**
- Use `st.container(border=True)` for bordered card containers instead of HTML divs
- Use `st.markdown()` only for inline HTML spans (pill badges, styled text)
- Keep HTML in Streamlit to inline elements only (`<span>`, `<strong>`, `<a>`)
- Test all HTML rendering after each Streamlit version upgrade

#### White Text on Light Backgrounds

**Lesson:** Pill badges with `color:white` become invisible on light themes when the background color fails to render. Always add a text shadow or use a darker text color as fallback.

**Why:**
- Badge `<span>` with `background:#4A90E2; color:white` looks fine when background renders
- If CSS is stripped or fails, white text on white background is completely invisible
- Streamlit's light theme (`backgroundColor: #FFFFFF`) makes this worse

**How to apply:**
- Add `text-shadow:0 0 2px rgba(0,0,0,0.3)` to pill badge CSS
- Consider using dark text (`#333`) for pills on light backgrounds
- Test with both light and dark Streamlit themes

#### LinkedIn Descriptions Require Individual Page Fetches

**Lesson:** LinkedIn search result cards only contain basic info (title, company, location, URL). Descriptions require fetching individual job detail pages. Use lightweight `requests` instead of Playwright for these secondary fetches.

**Why:**
- LinkedIn search page HTML has job cards with only title/company/location/posted date
- The base scraper's `search()` calls `get_job_details()` for enrichment, but LinkedIn returned `None`
- Playwright fetches are ~5-10s each; `requests` is ~1-2s for static HTML pages
- Enriching all results with Playwright would take 2+ minutes

**How to apply:**
- Implement `get_job_details()` using `requests` with proper headers
- Override `search()` to cap enrichment at a reasonable number (25 listings)
- Merge description into basic listing rather than replacing the entire listing
- Use `_rate_limit_wait()` between detail page fetches

#### Date Parsing Must Handle Edge Cases

**Lesson:** Relative date strings like "Just posted" or "Recently" must be handled explicitly. Never assume all dates follow "X unit(s) ago" pattern.

**Why:**
- LinkedIn shows "Just posted", "Just now", "Recently", "1 minute ago" in addition to "X days ago"
- Original parser only matched strings containing "ago"
- "Just posted" returned None, causing posted_date to be null in the API response

**How to apply:**
- Check for known literal strings first: "just posted", "just now", "recently" -> `datetime.now()`
- Handle "minute" unit in addition to "hour", "day", "week", "month"
- Add absolute date parsing via `strptime` as a final fallback
- Return None only when no format matches

**Lesson:** Use `st.columns([2, 3])` with `gap="medium"` to create a list+detail split-panel layout. Accept that Streamlit scrolls as one unit -- independent scroll requires fragile CSS hacks.

**Why:**
- Streamlit does not support native split panels or independent scroll regions (pre-1.38)
- `st.container(height=700)` (Streamlit 1.38+) adds scrollable containers but behaves inconsistently
- CSS `overflow-y: auto` on auto-generated div IDs breaks between Streamlit versions
- Single-scroll is acceptable when list items are compact and the detail panel anchors visually

**How to apply:**
- Use `st.columns([2, 3])` for 40/60 split between list and detail
- Keep list items compact (title, company, 3 skills, action row) to fit many in view
- Store selected job ID in session state, render detail in right column based on selection
- Accept single-scroll and optimize item density instead of fighting the framework

#### Pagination via Session State

**Lesson:** Implement pagination using session state page counter with Previous/Next buttons. Reset to page 0 on new search. Use zero-indexed page number with `jobs[page*20 : (page+1)*20]` slicing.

**Why:**
- Streamlit has no native pagination component
- Each button click triggers a full rerun, so state must persist in session_state
- Not resetting page on new search shows stale results at wrong offset
- Zero-indexed simplifies slice arithmetic

**How to apply:**
- Store `jobs_page` in session state, default 0
- `get_page_slice(items, page, per_page)` returns the correct sublist
- Previous/Next buttons update session state and call `st.rerun()`
- Call `reset_jobs_page()` when search form is submitted

#### Status Tabs for Job Filtering

**Lesson:** Use `st.tabs(["All", "Saved", "Applied"])` to separate different views of jobs. "All" shows search results, "Saved" and "Applied" fetch from the application tracker backend API.

**Why:**
- Tabs provide clear visual separation without sidebar clutter
- "Saved" and "Applied" tabs need backend API data, not just filtered search results
- `st.tabs()` is native Streamlit, no CSS hacks needed
- Each tab can have its own layout (split-panel vs simple list)

**How to apply:**
- Tab "All": split-panel with search results
- Tab "Saved": calls `get_application_dashboard(include_bookmarked=True)`
- Tab "Applied": calls `get_application_dashboard()` filtered by applied statuses
- Each tab handles its own empty state messaging

#### Pill Badges via HTML Injection

**Lesson:** Use `st.markdown()` with inline HTML `<span>` elements for pill/chip badges. This is the reliable Streamlit pattern for display-only decorative elements like skill tags and source badges.

**Why:**
- Streamlit has no native pill/chip component
- CSS-styled buttons for pills breaks between Streamlit versions
- HTML spans with inline styles are stable and portable
- `unsafe_allow_html=True` is required but the HTML is controlled (no user input)

**How to apply:**
- `render_pill(text, bg_color, text_color)` returns HTML string
- `st.markdown(html, unsafe_allow_html=True)` renders it
- Escape user-provided text to prevent XSS
- Use consistent color palette for source badges and skill categories

#### Wire Frontend to Existing Backend APIs Early

**Lesson:** When backend APIs exist but have no frontend integration, wire them up immediately. The application tracker backend had 7 endpoints with zero frontend methods -- a major feature gap.

**Why:**
- Backend-only features are invisible to users and rot over time
- Adding API client methods is low-risk (the backend is already tested)
- Frontend pages can then be built incrementally on top of the client methods
- Session state helpers keep the integration clean

**How to apply:**
- Audit backend routes vs frontend API client methods regularly
- Add client methods with proper typing and docstrings
- Add session state helpers for any new UI state (pagination, selection, saved sets)
- Build pages after the client layer is complete

### RAG Vector Store & Test Fixes (2026-04-27)

#### ChromaDB Returns Numpy Arrays, Not Python Lists

**Lesson:** ChromaDB's `collection.get(include=["embeddings"])` returns numpy ndarrays, not `List[List[float]]`. Truthiness checks like `if results["embeddings"]:` raise `ValueError: The truth value of an array with more than one element is ambiguous`.

**Why:**
- `collection.get()` returns embeddings as `numpy.ndarray` of shape `[n_docs, dim]`
- `if ndarray` with more than one element raises ValueError, not TypeError
- The bare `except Exception: pass` at line 291 caught this silently, returning None
- Every downstream call that relied on profile/job embeddings got None and fell back silently
- Tests passed for months because the fallback path masked the real bug

**How to apply:**
- Never use truthiness checks on values from external libraries that might return numpy arrays
- Use explicit checks: `if results["embeddings"] is not None and len(results["embeddings"]) > 0`
- Convert ndarray to Python list on return to match type hints: `[e.tolist() if hasattr(e, "tolist") else e for e in results["embeddings"]]`
- Never use bare `except Exception: pass` -- always log before falling back

#### Fallback Paths Must Maintain Same Sorting Guarantees

**Lesson:** When a method documents returning results "sorted by X descending", every code path (happy path, fallback, degraded mode) must maintain that contract. A test that verifies sorting should not fail only when the fallback path is triggered.

**Why:**
- `re_rank()` docstring says "sorted by combined_score descending"
- Main path sorts at line 287, but `_fallback_to_heuristic()` returned results in input order
- Test `test_re_rank_sorted_by_combined` passed when embeddings were available, failed when fallback triggered
- Heuristic scores [60, 70, 80] produced combined [0.6, 0.7, 0.8] in input order, not descending
- `assert 0.6 >= 0.7` failed because fallback did not sort

**How to apply:**
- Always apply the same sorting/transformation in fallback paths as in the main path
- Add explicit sort to fallback before return: `results.sort(key=lambda x: x.combined_score, reverse=True)`
- Test both happy path and fallback path independently
- If a function promises ordering, every return path must deliver it

#### Bare Exception Handlers Hide Critical Bugs

**Lesson:** `except Exception: pass` is a code smell that silently swallows errors, making debugging nearly impossible. In the ChromaDB case, a ValueError was caught and hidden for the entire lifetime of the RAG feature.

**Why:**
- `get_profile_embeddings` and `get_job_embeddings` both had `except Exception: pass`
- ChromaDB's numpy truthiness ValueError was caught and swallowed
- Method returned None, callers fell back silently, everything "worked" but embeddings were never used
- No error appeared in logs, no test failed until a sorting test exposed the cascade

**How to apply:**
- Replace `except Exception: pass` with `except Exception as e: logger.error("...", e)`
- Only suppress exceptions you genuinely expect and have a valid reason to ignore
- Prefer specific exception types: `except (ValueError, KeyError)` over bare `Exception`
- If you must suppress, log at warning level so the issue is traceable

### Library Migrations & Infrastructure (2026-04-27)

#### Pydantic V2 Cross-Field Validators Require model_validator

**Lesson:** Validators that read or write sibling fields via `values` dict must become `@model_validator(mode="before")` in Pydantic V2. The `values` parameter no longer exists in `@field_validator`.

**Why:**
- `@validator("total_count", always=True)` received `values` dict with already-validated fields
- `@field_validator` in V2 only receives the field value, no sibling access
- `@model_validator(mode="before")` receives the entire raw data dict before field validation
- Two patterns needed: `isinstance(data, dict)` check, then mutate and return `data`

**How to apply:**
- Simple validators (no `values` access): `@field_validator("field")` + `@classmethod`
- Cross-field readers (reads `values["other"]`): `@model_validator(mode="before")`, check `isinstance(data, dict)`
- Cross-field writers (mutates `values["other"]`): Same `@model_validator(mode="before")` pattern
- Always add `@classmethod` decorator -- V2 requires it for all validator types

#### pypdf Is a Drop-In PyPDF2 Replacement

**Lesson:** `pypdf` (the maintained fork) uses the identical API to `PyPDF2`. Migration is literally just changing the import statement.

**Why:**
- PyPDF2 is no longer actively maintained; `pypdf` is the successor project
- `PdfReader`, `.pages`, `.extract_text()` are all identical
- No code changes beyond the import line and requirements.txt entry

**How to apply:**
- `from PyPDF2 import PdfReader` -> `from pypdf import PdfReader`
- `PyPDF2>=3.0.0` -> `pypdf>=4.0.0` in requirements.txt
- Install in venv immediately after changing requirements.txt

#### Template Configs Must Be Wired Into Formatting Logic

**Lesson:** Having template configuration dictionaries (fonts, colors, sizes) that are never used by the actual formatting functions is dead code. Templates must actually drive the output styling.

**Why:**
- `TemplateManager.TEMPLATES` had 3 configs but `_format_pdf()` and `_format_docx()` used hardcoded values
- Users selecting different templates saw identical output
- The `FormatOptions` parameter was missing entirely from `format_resume()`

**How to apply:**
- Pass template config through to every style creation call
- Use `TemplateManager.get_template(options.template)` at the start of each format method
- Apply `template["font"]`, `template["heading_color"]`, etc. to ReportLab styles and python-docx runs
- Test each template produces visually distinct output

### TypeScript/Next.js Frontend Migration (2026-04-28)

#### shadcn/ui Uses base-ui, Not Radix — `asChild` Does Not Exist

**Lesson:** The `shadcn` CLI in this project configured components on top of `@base-ui/react`, not Radix UI. `asChild` is a Radix pattern and does not exist on base-ui primitives.

**Why:**
- `<SheetTrigger asChild>` compiled but failed TypeScript: `Property 'asChild' does not exist`
- base-ui uses a `render` prop for polymorphic rendering instead
- Assuming Radix patterns from shadcn docs will break in this stack

**How to apply:**
- For triggers/buttons: pass the icon/content as children directly — base-ui primitives already render as the correct element
- For custom element swap: use `render={<button />}` or `render={<a />}` prop
- Always read the installed component source (e.g., `src/components/ui/sheet.tsx`) before writing usage code

#### Server-Side Proxy Is the Right Pattern for API Key Injection

**Lesson:** Placing a Next.js Route Handler at `/api/proxy/[...path]` that injects `X-API-Key` from a server-only env var is cleaner and more secure than any client-side approach.

**Why:**
- API key never appears in browser network tab or client JS bundle
- `BACKEND_API_URL` is also server-only — prevents accidental CORS exposure
- A single catch-all route handles all HTTP methods with no per-endpoint boilerplate

**How to apply:**
- Use `process.env.API_KEY` (no `NEXT_PUBLIC_` prefix) in the Route Handler
- Strip `host` header before forwarding to avoid backend rejection
- For multipart uploads: forward the raw blob body without resetting `Content-Type` (the multipart boundary must be preserved)

#### FastAPI `dependencies=` on `include_router` Is the Cleanest Auth Pattern

**Lesson:** Adding auth as `dependencies=[Depends(verify_api_key)]` on `app.include_router(...)` protects every route in a router without modifying any individual endpoint signature.

**Why:**
- Touching 40+ individual endpoint functions to add a dependency is error-prone
- Router-level dependency is enforced uniformly — easy to audit in one place (`main.py`)
- WebSocket routes must be excluded separately (they handle auth differently)

**How to apply:**
- Create `_auth = [Depends(verify_api_key)]` once, pass to all `include_router` calls
- Keep the WebSocket endpoint on `app` directly (not on a router) to exclude it from auth
- Make auth a no-op when `API_KEY` env var is empty so local dev works without config

### Docker & WSL2 Runtime (2026-04-28)

#### WSL2 Windows Filesystem Bind Mounts Drop to root:root 755 Inside Containers

**Lesson:** When Docker bind-mounts a path from the Windows filesystem (via WSL2 DrvFs, e.g. `/mnt/d/...`), the mount appears inside the container as `root:root drwxr-xr-x` (755) — regardless of the host-side permissions showing `777`. Any container user other than root will receive `PermissionError` when writing to the mount.

**Why:**
- DrvFs is a Windows-to-WSL filesystem bridge that does not preserve Linux ownership or permission bits in the way that native ext4 volumes do
- Docker volumes mounted from DrvFs paths land as uid=0 gid=0 with mode 755 inside the container
- The app was running as `jobraider` (uid 1000); the mounted `/app/data` was owned by root — so `mkdir("data/metrics")` raised `PermissionError: [Errno 13]`
- The container reported "healthy" (via a Python no-op health check) even though the app server had crashed on startup, masking the failure

**How to apply:**
- For local dev tools using WSL2 + Docker Desktop: add `user: root` to the service in `docker-compose.yml` to override the Dockerfile `USER` directive
- For production: use a Docker-managed named volume instead of a bind mount (avoids DrvFs ownership issues entirely)
- Always check container logs (`docker compose logs <service>`) when a service appears healthy but returns no HTTP response — the Python health check passes even when uvicorn failed to start
- Prefer the `http://127.0.0.1:<port>` form over `localhost` in curl health checks; `localhost` resolves to `::1` (IPv6) in WSL2 which can cause "Connection reset by peer" even when the server is bound to `0.0.0.0`

#### WSL2 DrvFs Aggressive Caching Causes Stale Code in Containers

**Lesson:** Changes made to files on the WSL2 filesystem are not immediately reflected inside Docker containers due to Windows file system caching with bind mounts. Code that was fixed on the host may still appear broken inside the container.

**Why:**
- WSL2 uses the Windows file system (DrvFs) for bind mounts, which has aggressive caching
- Docker containers read from the cache, not the live filesystem
- `docker compose restart` keeps the same container with cached files — fixes won't appear
- This causes confusing import errors where the host code is correct but container sees old buggy code

**How to apply:**
- Use `docker compose down && docker compose up -d` instead of `restart` after code changes — this recreates containers with fresh file reads
- For persistent fixes, add auto-detection/correction to the entrypoint script (`docker/docker-entrypoint.sh`)
- Example fix: automatically remove invalid pydantic imports like `field_serializer_validator` on container startup
- If files still seem stale after down/up, edit directly inside container with `docker exec -it <container> sed -i ...`
- The helper script `./docker-rebuild.sh` wraps the down + up pattern for convenience

### LinkedIn Easy Apply Automation (2026-05-05)

#### LinkedIn Login Flow Uses Obfuscated DOM

**Lesson:** LinkedIn's login page (`/checkpoint/lg/login`) does not use standard `<input id="username">` fields. The `session_key` input is type="hidden" and the visible email field is rendered via JavaScript or React components that may not match standard CSS selectors.

**Why:**
- `#username` selector times out because LinkedIn no longer uses that ID
- The email field may be rendered as a custom web component, shadow DOM, or React-controlled input
- Dumping all `<input>` elements on the page revealed only hidden inputs and a password field
- The password field (`#password`, `name="session_password"`) does exist as a standard visible input

**How to apply:**
- Use multiple fallback selectors with decreasing specificity for login fields
- Fall back to Playwright's `get_by_role("textbox")` locator which handles shadow DOM
- Fall back to JS injection to set hidden input values directly when no visible input exists
- Always dump page input elements for debugging when selectors fail

#### LinkedIn Easy Apply Button Is an `<a>` Tag, Not `<button>`

**Lesson:** LinkedIn's "Easy Apply" button is an `<a>` element (link), not a `<button>`. Selectors that only check `button` elements will never find it, even though the text "Easy Apply" is clearly visible on the page.

**Why:**
- The Easy Apply element is `<a href="...apply/?openSDUIApplyFlow=true...">Easy Apply</a>`
- Sidebar recommendation cards also contain "easy apply" text, matching broad selectors
- Multiple `a:has-text("Easy Apply")` elements exist — the correct one has `/apply/` in its href

**How to apply:**
- Prioritize `a[href*='/apply/']:has-text('Easy Apply')` selector to match the actual apply link
- Check both `<a>` and `<button>` elements for all interaction points
- Use href-based selectors to distinguish the real apply button from sidebar recommendations

#### LinkedIn Pages Have Overlay Interception (interop-shadowdom)

**Lesson:** LinkedIn renders a `<div id="interop-outlet" data-testid="interop-shadowdom">` overlay that intercepts pointer events, causing Playwright clicks to time out with "element intercepts pointer events" errors.

**Why:**
- The overlay sits on top of the page content and captures all click events
- Normal `element.click()` waits for the element to be "stable" but the overlay never moves
- This appears to be LinkedIn's notification/cookie consent mechanism
- Force clicking the overlay dismiss button resolves the issue

**How to apply:**
- Before any click, attempt to dismiss overlay dialogs with force click
- Use `force=True` on Playwright click when normal click is intercepted
- Maintain a list of overlay dismissal selectors (interop buttons, cookie consent, dismiss buttons)
- Wrap all click operations in try/except with force click fallback

#### Persistent Browser Context Restores LinkedIn Sessions Automatically

**Lesson:** Using Playwright's `launch_persistent_context()` with a user data directory preserves cookies, localStorage, and session state across runs. The LinkedIn session may already be valid when the browser launches, making a fresh login unnecessary.

**Why:**
- `launch_persistent_context` stores browser state (not just cookies) on disk
- Subsequent launches restore the full session including authenticated state
- Navigating to the feed URL redirects immediately when session is valid
- Attempting login when already authenticated fails (login page redirects to feed, no form fields found)

**How to apply:**
- On session start, first check if persistent context already has a valid session by navigating to feed
- Only attempt login if session verification fails
- Save cookies after successful authentication for cross-session backup
- Handle the case where login page redirects to feed (already authenticated)

### Job Trust Scoring Enhancement (2026-05-06)

#### Provide Clear Reasons with All Automated Ratings

**Lesson:** When building automated scoring or rating systems, always provide clear, human-readable reasons explaining WHY a particular rating was given. Binary "good/bad" or numeric scores without explanation create user distrust and confusion.

**Why:**
- Original scam detector only returned a boolean `is_scam` and a score, with reasons only logged
- Users saw "High Risk" badge with zero explanation for WHY that rating was assigned
- Trust requires transparency - users need to understand the reasoning to trust the system
- Per-category breakdowns allow users to see which specific aspects triggered concerns

**How to apply:**
- Structure ratings with multiple levels rather than binary (legitimate, low_risk, moderate_risk, suspicious, likely_scam)
- Return per-category scores so users can see which areas contributed to the overall rating
- Provide human-readable reasons for each concern detected (e.g., "Generic company name", "Personal email instead of corporate")
- For LLM-enhanced analysis, return a summary paragraph explaining the overall assessment
- Display the breakdown visually with color coding and progress bars
- Make the reasons actionable - tell the user what to look out for

#### Tiered Confidence System Improves Decision Making

**Lesson:** Map continuous confidence scores to discrete tiers with clear semantic labels. Users make better decisions with "Moderate Risk" vs "Suspicious" than they do with "confidence: 0.65".

**Why:**
- Numeric confidence scores (0-1 or 0-100) are cognitively demanding to interpret
- Semantic labels like "Legitimate", "Low Risk", "Moderate Risk" are immediately actionable
- Tiers map cleanly to visual color coding (green, blue, amber, orange, red)
- Discrete tiers prevent decision paralysis at borderline values
- Users can quickly filter/sort by tier without remembering thresholds

**How to apply:**
- Define tier boundaries based on confidence percentiles (0.2, 0.4, 0.6, 0.8, 1.0)
- Provide semantic names for each tier that clearly communicate risk level
- Include tier display names alongside internal enum values
- Map colors to tiers for consistent visual communication
- Document the tier boundaries in the API response

#### On-Demand Deep Analysis Reduces Latency and Cost

**Lesson:** Provide both quick rule-based analysis and optional LLM-enhanced deep analysis via a `deep` query parameter. Most users get instant results; those who need more detail can request it.

**Why:**
- Rule-based analysis runs in milliseconds, LLM analysis takes seconds
- LLM calls cost money and add latency; not all users need the extra detail
- A boolean flag enables progressive enhancement pattern
- Frontend can show "Analyze Trust" button for on-demand deep analysis
- Baseline experience remains fast and cheap

**How to apply:**
- Default analysis uses rule-based scoring only (instant, free)
- Add `deep` query parameter to enable LLM-enhanced analysis
- Return additional fields (`llm_summary`, `llm_indicators`) only when deep=True
- Frontend shows "Analyze Trust" button that triggers deep analysis
- Cache deep analysis results per job_id to avoid redundant LLM calls

**Lesson:** Using Playwright's `launch_persistent_context()` with a user data directory preserves cookies, localStorage, and session state across runs. The LinkedIn session may already be valid when the browser launches, making a fresh login unnecessary.

**Why:**
- `launch_persistent_context` stores browser state (not just cookies) on disk
- Subsequent launches restore the full session including authenticated state
- Navigating to the feed URL redirects immediately when session is valid
- Attempting login when already authenticated fails (login page redirects to feed, no form fields found)

**How to apply:**
- On session start, first check if persistent context already has a valid session by navigating to feed
- Only attempt login if session verification fails
- Save cookies after successful authentication for cross-session backup
- Handle the case where login page redirects to feed (already authenticated)

### Phase 32: Already-Applied Flow Fix (2026-05-07)

#### Scraper-Detected State Must Be Persisted to Tracker

**Lesson:** When a scraper detects transient signals (like "Applied" badges on LinkedIn job cards), that state must be persisted to the long-lived tracker immediately. Relying solely on a boolean field on the in-memory model means the knowledge is lost between pipeline runs.

**Why:**
- The LinkedIn scraper sets `already_applied=True` on `JobListing` when it sees an "Applied" badge
- This boolean only exists in memory for the duration of that pipeline run
- If the badge is not visible on a subsequent run (different scroll position, page layout change), the tracker will not know to exclude those jobs
- The `AppliedJobsTracker` is the source of truth for applied status across runs

**How to apply:**
- In the deduplicate stage, before filtering, sync any `already_applied=True` jobs to the tracker via `tracker.mark_applied()`
- Guard against double-sync by checking `tracker.is_applied()` first
- Then filter using both the model boolean AND the tracker: `not job.already_applied and not tracker.is_applied(job.job_id)`
- This ensures badge-detected and tracker-known jobs are both excluded

#### API Response Must Include All Frontend-Needed Fields

**Lesson:** Every model field that the frontend needs to render must be explicitly included in the API response model and the route handler's response dict. Missing fields silently produce `undefined` on the frontend.

**Why:**
- `already_applied` was set on the `JobListing` model but not included in `JobListingResponse`
- The `/jobs/search` route handler manually constructed the response dict and omitted it
- Frontend received `undefined` for `already_applied`, so the badge never rendered
- No error was raised anywhere — the field was simply absent from the JSON payload

**How to apply:**
- When adding a field to a model, trace the full path: model -> response schema -> route handler -> frontend type -> UI component
- Add the field to the Pydantic response model
- Add it to the route handler's response dict construction
- Add it to the TypeScript interface
- Add the UI rendering for it

#### Pydantic V2 use_enum_values Makes Enums Transparent

**Lesson:** When `model_config = ConfigDict(use_enum_values=True)` is set on a Pydantic model, enum fields return their value (a string) rather than the enum instance. Code that calls `.value` on such fields will throw `AttributeError: 'str' object has no attribute 'value'`.

**Why:**
- `JobListing` uses `use_enum_values=True`, so `job.source` is a string like `"linkedin"`, not a `JobSource` enum
- Test code called `job.source.value` expecting an enum, but got a string
- The `stages.py` code was correct because it used `hasattr(job.source, "value")` as a guard

**How to apply:**
- For models with `use_enum_values=True`, always guard enum access with `hasattr(obj.field, "value")` or `isinstance(obj.field, str)`
- In tests, use `job.source if isinstance(job.source, str) else str(job.source.value)` for robustness
- Be aware that Pydantic V2 config can change the type of fields at the Python level even though the schema looks the same

#### PYTHONPATH Must Match Import Structure

**Lesson:** When tests import using `from src.models.job_listing import ...`, the `PYTHONPATH` must be set to the directory containing `src/` as a package — not to `src/` itself.

**Why:**
- Setting `PYTHONPATH=backend-py/src` caused `ModuleNotFoundError: No module named 'src'`
- The correct value is `PYTHONPATH=backend-py` because `src/` is a package inside `backend-py/`
- Python resolves `from src.models...` by looking for `src/` as a package directory in `sys.path`

**How to apply:**
- Always use `PYTHONPATH=backend-py` for backend Python commands
- Full test invocation: `PYTHONPATH=backend-py backend-py/.venv/bin/python -m pytest backend-py/tests/unit/...`
- Never `cd` into `backend-py/` and use bare paths — stay at project root

### Phase 33: Shared MLflow Migration (2026-05-17)

#### Shared Services Must Use Allowed-Hosts for Cross-Network Access

**Lesson:** MLflow 2.x includes a security middleware that validates the `Host` header. By default it only allows `localhost`. When containers on a different Docker network connect using the service name (e.g., `mlflow:5000`), requests are rejected with 403 Forbidden.

**Why:**
- The `Host` header from the backend container is `mlflow:5000`, not `localhost:5000`
- MLflow logs: `Rejected request with invalid Host header: mlflow:5000`
- The fix is to pass `--allowed-hosts mlflow:5000,localhost:5000,127.0.0.1:5000` in the MLflow server command

**How to apply:**
- When running MLflow as a shared service accessed by other containers, always set `--allowed-hosts` with both the Docker service name and localhost variants
- Test cross-network connectivity explicitly with `docker exec <container> curl http://mlflow:5000`

#### Docker Compose Port Long Syntax vs Short Syntax

**Lesson:** The Docker Compose long-form port syntax with `mode: host` can silently fail to publish ports in some Docker Compose versions. The short syntax (`"5000:5000"`) is more reliable.

**Why:**
- Using `target: 5000, published: "5000", protocol: tcp, mode: host` resulted in no port mapping (`docker port mlflow` returned empty)
- Switching to `"${MLFLOW_PORT:-5000}:5000"` immediately fixed the mapping

**How to apply:**
- Prefer the short port syntax in docker-compose.yml unless you specifically need the long-form features
- Always verify port mapping with `docker port <container>` after starting a service

#### Setup Scripts Must Not Reach Outside the Project Directory

**Lesson:** Project setup scripts (setup.sh, dev.sh) should never create files or directories outside the project root. For external dependencies like shared Docker services, provide documentation instead of automation.

**Why:**
- A `setup_shared_services()` function that created `~/docker-services/` would leak host filesystem paths into the project's setup script
- Confidentiality concern: setup scripts committed to Git should not reference or create paths outside the project
- Other users may have different directory structures

**How to apply:**
- Keep setup.sh scoped to the project directory only
- For shared external services, create a documentation page (e.g., `docs/mlflow-setup.md`) with manual setup instructions
- The docs approach is reproducible, reviewable, and does not expose host-specific paths

#### Force-Recreate When Adding Networks to Existing Services

**Lesson:** When adding a new Docker network to an existing service in docker-compose.yml, the container must be force-recreated. A plain `docker compose up -d` will not recreate containers whose image hasn't changed.

**Why:**
- After adding `shared-services` to the backend's network list, `docker compose up -d` reported "Running" without changes
- The container's network configuration only updates on recreation
- `docker compose up -d --force-recreate backend` was required

**How to apply:**
- After modifying network, volume, or environment settings in docker-compose.yml, use `--force-recreate` for affected services
- Verify with `docker inspect <container> --format '{{range .NetworkSettings.Networks}}{{.NetworkID}}{{end}}'`
