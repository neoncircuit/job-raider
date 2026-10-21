# Job Raider Tasks

This file lists active work only. Completed work is in [archive/todo-done.md](archive/todo-done.md).

## How to use this file

```mermaid
flowchart LR
    B[Backlog] -->|Planned| N[Next]
    N -->|Started| W[Now]
    W -->|All steps done| A[archive/todo-done.md]
    B -->|Dropped| A
```

1. Put each work item under one of three sections: **Now**, **Next**, or **Backlog**.
2. Give each work item a level-3 heading with a name and a date. Example: `### Pipeline elapsed timer (2026-10-18)`.
3. Do not give work items numbers. Do not use the word "Phase" for new work.
4. Number the steps inside a work item: "Step 1", "Step 2", and so on. If a step needs its own sub-steps, number them "Step 1.1", "Step 1.2", and so on.
5. When all steps are done, add a "Review" subsection. Then move the work item to the end of [archive/todo-done.md](archive/todo-done.md).
6. "Phase 1" to "Phase 54" are old labels. They are in the archive only. Do not reuse them.

## Now

### Review follow-up (2026-10-18)

Source: [review-2026-10-18.md](review-2026-10-18.md), section 6. Each step has its own checklist in that file.

- [x] Step 0: Push and stabilize.
  - [x] Add LF rules for `*.ts`, `*.tsx`, `*.js`, `*.jsx`, `*.mjs`, `*.cjs`, and `*.css` to `.gitattributes`. Restore LF in the 16 files that had CRLF on disk.
  - [x] Run all local checks (2026-10-18). Backend: ruff and Black clean; pytest 983 passed. Frontend (`node:20` container, same as CI): `npm ci`, ESLint (0 warnings), tsc, Prettier, Vitest 202 passed in 38 files, `next build`, and Playwright 41 passed with 1 flaky (Mobile Chrome Dashboard link timed out on a cold dev-server start, then passed on retry). Gitleaks: no leaks in the unpushed commits. mypy is still non-blocking (195 errors); Step 1.4 makes it a gate.
  - Note: `npm ci` fails with npm 11 (Node 24) because `package-lock.json` lacks the optional `@tailwindcss/oxide-*` platform packages. npm 10 (Node 20, as in CI) accepts it. Regenerate the lock file when CI moves to Node 24.
  - [x] Push to `origin/main` (approved 2026-10-18). Pushed `dbac242..63e5e0a` from WSL (Git Bash on Windows has no GitHub SSH key). CI run 39094293658 passed all 11 jobs; Docker build skipped by design. Note: the mypy "Type Check" and "Security Scan" jobs cannot fail yet.
- [ ] Step 1: Make the core flow run. The plan is below. Approved on 2026-10-18. Steps 1.1 to 1.7 are done and pushed (last: `5a8232f`). Only the manual check in "Verification for Step 1" is open.
- [x] Step 2: Make local-first true. Done on 2026-10-21. Steps 2.1 to 2.6 and review items R1 to R11a are pushed (last: `629eb69`; CI run 39630302033 passed all 11 jobs, Playwright 42 passed with 0 flaky). Open question, not blocking: allow LinkedIn country hosts such as `sg.linkedin.com`.
- [ ] Step 3: Make claims measurable. The plan is below. Decisions recorded on 2026-10-22.
- [ ] Step 4: Make it demo-able.
- [ ] Step 5: Focus and prune.

#### Step 1 plan: Make the core flow run

**Goal:** A full-mode pipeline run goes from scrape to the submit stage in dry run. The CLI starts. CI catches new type errors. The UI shows real progress and does not send POST requests two times.

**Constraints:**

- Do not make auto-submit reachable. Detection and submission stay as they are until the Easy Apply decision in Step 5.
- Keep dry run as the default in every layer.
- Each sub-step is one pull request with its own tests. Run all local checks before each push.

```mermaid
flowchart LR
    S1[1.1 CLI repair] --> S2[1.2 Stage registry and submit-stage fixes]
    S2 --> S5[1.5 Pipeline off the event loop]
    S5 --> S6[1.6 Batch cover letters use the repair loop]
    S3[1.3 Six runtime bugs] --> S4[1.4 Real mypy gate]
    S7[1.7 Frontend input and retry fixes]
```

Steps 1.1, 1.3, and 1.7 do not depend on other sub-steps. Step 1.4 needs 1.3, so that the baseline does not contain the six bugs. Step 1.6 needs 1.5, because the cover-letter service is async and needs a thread without a running event loop.

##### Step 1.1: CLI repair (effort: S)

- [x] Remove the second `argparse` block in `apps/backend-py/main.py` (the block after the first `parse_args()` at line 701). Move parser construction into `build_parser()`. Define `-i/--interactive` on the top-level parser, and share `--log-level` and `--log-file` with both commands through a parent parser.
- [x] Change `profile.target_job` to the fields of `profile.targets` in `run_pipeline` (`main.py:272-281`).
- [x] Read the allowed `--sources` values from the scraper registry, not from a hard-coded list (`main.py:600`). New `available_sources()` in `src/scrapers/manager.py`; `ScraperManager` uses it too.
- [x] Add `tests/unit/test_cli.py` (36 tests): help for each command, README forms, sources, experience choices, target fields, routing, and the full `analyze` path.
- [x] Update the README CLI examples to match the real commands. No edit needed: `pipeline` is the default command again, so `main.py --resume ...` in the README and `docs/usage.md` works as written.
- [x] Found during the work and fixed:
  - `ResumeParser.parse()` does not exist. `load_user_profile` and `analyze` now call `parse_file()`. `profile.contact_info.name` is now `profile.name`.
  - `--target-experience` choices (`entry`, `mid`) did not match `ExperienceLevel` values ("Entry Level"). The choices now map to enum member names.
  - `analyze` always failed: a local `from pathlib import Path` made `Path` unbound at the resume check (ruff F823). Removed the local import; a test now fails if it comes back.
  - The second `ensure_dependencies()` call inside `main()` is removed. The call before the imports stays. `main()` can now run in tests without `os.execv`.
  - `main.py` was not linted in CI. It is now ruff- and Black-clean, and CI and `make lint` check it.
  - Pinned `Makefile` and `Dockerfile*` to LF in `.gitattributes`, because `make` and Docker fail on CRLF.

##### Step 1.2: One stage registry and an honest submit stage (effort: S to M)

Steps 1.2 parts A and B must land together. When the run reaches the submit stage, the bugs in part B start to write wrong data.

Part A: stage registry

- [x] Define one ordered stage list with one handler per stage. New `src/models/pipeline_stage.py` holds `PipelineStage` and `STAGE_ORDER` (the enum order). Both runners in `src/pipeline/orchestrator.py` use `_stages_to_run()`. `PIPELINE_STAGE_ORDER` and `DISCOVER_LAST_STAGE` in `src/api/models/requests.py` derive from it.
- [x] Replace the `if`/`elif` dispatch in `_execute_stage` with a lookup (`_stage_handlers()`). Add the missing `LINKEDIN_AUTH` handler (`stages.stage_linkedin_auth`).
- [x] Make `stage_linkedin_auth` check only that credentials exist. No code change was needed: it already reads only `LINKEDIN_EMAIL` and `LINKEDIN_PASSWORD`. A test now fails if it starts Playwright.
- [x] Tests (`tests/unit/test_pipeline_orchestrator.py`): every `PipelineStage` has a handler; the request stage order equals `STAGE_ORDER`; a full-mode dry run runs all 11 stages in order and passes each stage's output to the next. `tests/integration/test_pipeline.py` now asserts `success` and the completed stages. A mutation check (handler removed) makes the tests fail.

Part B: submit stage

- [x] Match submission results to generated resumes by `job_id`, not by list index.
- [x] Do not save dry-run results as applied records. They are counted as `simulated`.
- [x] Count `jobs_applied` (`total_applications`) from real submissions only. Before, it equaled the number of generated resumes, so the Dashboard and Pipeline history showed every generated resume as "applied".
- [x] Tests for each of the three items above (`tests/unit/test_pipeline_stages.py`).
- [x] Found during the work and fixed: `stage_generate_resumes` failed when no job was selected ("0/0 successful", no error message), so a full run with an empty shortlist ended as failed. An empty selection is now a success. When every selected job fails, the stage fails with a message.

##### Step 1.3: Fix six runtime bugs that mypy found (effort: S)

- [x] `src/classifiers/job_classifier.py:606`: `WorkPace.FAST` to `WorkPace.FAST_PACED`. Rule-based classification of any JD with "fast-paced", "rapidly", or "startup environment" returned `success=False`. Tests: `tests/unit/test_job_classifier.py`.
- [x] `src/generation/formatter.py:535-563`: set `run.bold` and `run.italic` on the returned run, not as `add_run` arguments. DOCX resumes were silently missing; PDF still worked. Test: `tests/unit/test_resume_formatter_docx.py`.
- [x] `src/metrics/outcome_tracker.py:992`: `Path.remove()` to `Path.unlink()`. The status left the cache but its file stayed, so it came back after a restart. Tests: `tests/unit/test_outcome_tracker_custom_status.py`.
- [x] `src/metrics/mlflow_tracker.py:480`: `experiment.experiment_name` to `experiment.experiment_id` in `get_run_history`; run history was always empty. (`get_best_run` was already correct.) Test: `tests/unit/test_mlflow_run_history.py`.
- [x] `src/experiments/ab_testing.py`: deleted the `src/experiments/` package (decision 1). Nothing imported it. Removed its line from the README source tree.
- [x] `src/generation/resume_writer.py:285`: the template fallback, which runs when the LLM fails, now joins the names of the first five skills. Test: `tests/unit/test_resume_writer_fallback.py`.
- [x] Mutation check: with the five source fixes stashed, the bug tests fail with the original errors.

##### Step 1.4: Make mypy a real gate (effort: S)

- [x] Add a `[tool.mypy]` section to `apps/backend-py/pyproject.toml` (`ignore_missing_imports = true`). `python_version` is not set: the local `.venv` is Python 3.12 with a numpy whose stubs only parse on 3.12, so forcing 3.11 stops mypy.
- [x] Add `apps/backend-py/scripts/mypy_gate.py`. It compares errors by file, error code, and message (line numbers and "line N" in messages are ignored), counts duplicates, fails on new errors, and fails when mypy crashes. `--update` writes a new baseline. Tests: `tests/unit/test_mypy_gate.py` (12).
- [x] Remove `|| true` and `continue-on-error` from the CI `type-check` job and from `make lint`. Both run the gate. CI pins `mypy==2.4.0`, `types-requests==2.33.0.20261006`, and `types-PyYAML==6.0.12.20260906` (the versions CI used on 2026-10-18). The local `.venv` uses the same pins.
- [x] Done: the baseline (`apps/backend-py/mypy-baseline.txt`) was built from the CI Type Check log of run 39143155828 and has 183 errors. It does not contain the nine Step 1.3 errors. A deliberate new error makes the gate exit 1; clean code exits 0.
- [x] Found during the work and fixed: local and CI differed only in `src/metrics/mlflow_tracker.py`, because `mlflow` is not pinned and newer releases type `search_runs()` as `list[Run] | DataFrame`. Pass `output_format="pandas"` and cast to `DataFrame`; annotate the compare report as `Dict[str, Any]`. Local and CI now give the same 183 errors.
- [x] Lint `scripts/mypy_gate.py` in CI and `make lint`. Docs: "mypy Baseline Gate" in `docs/testing.md`; README code-style commands; `COMPREHENSIVE_TESTING_STRATEGY.md`.

##### Step 1.5: Run the pipeline off the event loop (effort: M)

- [x] In `src/api/routes/pipeline.py`, `_execute_pipeline()` runs in a worker thread (`asyncio.to_thread`). It builds the orchestrator, runs the stages, and backfills shortlist descriptions; all of these block.
- [x] Use the orchestrator stage hooks to send `stage_started`, `stage_completed`, and `stage_progress` (0 to 100) events with `asyncio.run_coroutine_threadsafe`. The hooks also set `current_stage`, `stage_progress`, `stages_planned`, and `stages_completed`, which `GET /status` now returns, so the monitor is correct even when the WebSocket connects late.
- [x] `PipelineOrchestrator.run(should_stop=...)` checks the cancel status before each stage, so cancel stops the run at the next stage boundary. A running stage is not interrupted.
- [x] Set the default `UVICORN_WORKERS` to 1 in `docker/Dockerfile`, because run state is in memory (decision 2).
- [x] Frontend: progress uses the backend 0 to 100 value (no extra `* 100`). The badge shows Running, Complete, Failed, or Cancelled, and a failed run shows its error. Logic is in `src/lib/pipeline-run-state.ts`. Added the missing `linkedin_auth` and `present_selection` stages to `PIPELINE_STAGES`.
- [x] Tests: `tests/unit/test_pipeline_run_async.py` (worker thread, the loop keeps running during a blocking stage, event order, failed status, cancel), a cancel test in `test_pipeline_orchestrator.py`, `/status` and `/results` tests in `test_pipeline_routes.py`, `src/lib/pipeline-run-state.test.ts`, and `tests/app/pipeline/live-monitor.test.tsx`. A mutation check (pipeline called on the event loop again) fails 3 of the 4 async tests.
- [x] Found during the work and fixed:
  - A run with `success=False` was reported as "completed". It is now "failed", with the failing stage's error.
  - `GET /api/pipeline/results/{run_id}` raised for every completed run: it called `.value` on stage names that are already strings.

##### Step 1.6: Batch cover letters use the repair loop (effort: M)

- [x] `stage_generate_resumes` now gets each cover letter from the shared service (`_generate_cover_letter` in `src/pipeline/stages.py`). The service writes, validates, and rewrites one time on hard-fail grounding issues, like the Cover Letter page. The service body moved to `generate_cover_letter_sync()`; `generate_cover_letter_for_profile()` is a thin async wrapper for the routes. A new `selection` argument lets the stage reuse its resume selection, so there is no second selector call per job.
- [x] A letter that still hard-fails after the rewrite is not saved. It is kept as `cover_letter_status="needs_review"` with `cover_letter_issues`. Stage metadata counts `cover_letters_saved`, `cover_letters_needs_review`, and `cover_letters_failed`. A letter error no longer drops the job's resume.
- [x] Tests (`tests/unit/test_pipeline_stages.py`, `TestBatchCoverLetters`): the service gets the resume selection; a clean letter is saved; a hard-fail letter is not saved; soft issues alone do not block saving; a letter error keeps the resume. A mutation check (hard-fail rule disabled) fails the hard-fail test.
- [x] Removed the unused `cover_letter_writer` and `cover_letter_validator` from `PipelineStages`.
- Follow-up (not in Step 1): the API routes still call the synchronous service from async handlers, so a cover-letter request blocks the event loop while the LLM runs. Use `asyncio.to_thread` in `generate_cover_letter_for_profile`.

##### Step 1.7: Frontend input and retry fixes (effort: S)

- [x] `src/lib/api/client.ts`: retry only `GET` and `HEAD` (`canRetry`). Honor `Retry-After` on 429, capped at 30 s (`retryDelayMs`). TanStack query retries are off in `src/app/providers.tsx`, so the client is the only retry layer (mutations already defaulted to 0). A caller abort (`AbortError`) is rethrown unchanged and not retried.
- [x] The proxy sets `X-Proxy-Error: backend-unreachable` on its 503 for a down backend. The client maps exactly that case to `ConnectionError`, so the "Is the backend running?" message appears. A 503 from the backend itself stays an `ApiError`.
- [x] `splitList` (comma-only) is now `src/lib/utils/split-list.ts`. The Pipeline form, the Jobs search bar, and the profile job targets use it (decision 3). The placeholders already show comma-separated examples, so they did not change.
- [x] The UI `max_jobs` limit is 100, the same as the backend.
- [x] Tests: `canRetry`, `retryDelayMs`, and `request` retry behavior in `src/lib/api/client.test.ts` (POST sent once on 503; GET retried; proxy 503 is `ConnectionError`; backend 503 is `ApiError`; abort rethrown); `src/lib/utils/split-list.test.ts`; a Pipeline form test that "New York, Remote" gives two locations.

##### Verification for Step 1

- [x] Backend: pytest, ruff, Black, and the mypy gate. CI run 39188312697 on `5a8232f`: 1,067 passed; gate 182 known errors, 0 new.
- [x] Frontend (Node 20): ESLint, tsc, Prettier, Vitest, `next build`, and Playwright. CI run 39188312697: 41 Vitest files passed; Playwright 40 passed, 2 flaky (see the Backlog item "Flaky Mobile Chrome navigation smoke test").
- [ ] Manual: start a full-mode dry run from the Pipeline page with Ollama running. Confirm that the stage list moves during the run, and that the run reaches `submit_applications` with zero real submissions.

##### Out of scope for Step 1

- Silent cloud fallback, API binding, and auth (Step 2).
- Scoring, dedupe, scam regex, and RAG fusion fixes (Step 3, after there is an eval set).
- Auto-submit reachability and the Easy Apply decision (Step 5).

##### Decisions (2026-10-18)

1. `ab_testing.py`: delete it. Nothing imports it, and it calls a method that does not exist.
2. Uvicorn workers: change the default to 1. One local user does not need more, and run state is in memory.
3. Keywords: split on commas only. "python engineer" is one search phrase.

#### Step 2 plan: Make local-first true

**Goal:** Resume text and API keys stay on the machine by default. Cloud LLM use is opt-in, logged, and visible in the UI. Auth is on unless the user sets an explicit bypass. The API is not reachable from other devices on the network by default.

**Constraints:**

- Do not make auto-submit reachable (Step 5).
- Keep dry run as the default in every layer.
- Each sub-step is one commit (or PR) with its own tests. Run all local checks before each push.
- Do not change eval scoring, scam rules, or RAG fusion (Step 3).
- Line numbers below were re-checked on 2026-10-19 after Steps 1.1 to 1.7.

```mermaid
flowchart LR
    S21[2.1 Cloud none default] --> S22[2.2 One LLM factory]
    S22 --> S25[2.5 Cover letter off the loop]
    S23[2.3 Bind and auth] --> S24[2.4 Keys and client logging]
    S24 --> S26[2.6 Host Origin and URL guards]
```

Steps 2.1 and 2.3 can start in parallel. Step 2.2 needs 2.1 so that factory-built routers inherit `CloudProvider.NONE`. Step 2.5 is independent of 2.3 and 2.4. Step 2.6 can follow 2.4.

##### Step 2.1: No silent cloud fallback (effort: S) — S1

- [x] Add `CloudProvider.NONE` in `src/api/settings.py`. Make it the default for `APIConfig.cloud_fallback_provider` (today the default is `CloudProvider.ANTHROPIC` at about line 71) (decision 1).
- [x] In `src/llm/router.py`, stop treating Anthropic as the default fallback on the built-in routes (about lines 81 to 201). When the primary provider fails and fallback is `none` or unset, log the failure and raise (or return a clear error). Do not call a cloud client.
- [x] On every successful `generate` call, log and return which provider and model ran (primary or fallback). Extend the response / metadata the API already exposes so the UI can show a small "Cloud" badge on results when the provider was not Ollama (decision 6).
- [x] Settings UI: cloud fallback control includes "None (local only)". Document that a cloud key alone does not send data until the user picks a cloud fallback.
- [x] Tests: with `CloudProvider.NONE`, a forced Ollama failure does not call Anthropic or Gemini. With Anthropic selected, a forced Ollama failure does call Anthropic and the response marks `provider=anthropic`. Mutation: put Anthropic back as the default; the NONE test must fail.
- [x] Done when: a run with no cloud fallback never leaves the machine, and the Cover Letter / Pipeline UIs can show when a cloud model was used.

**Review (2026-10-19):** `LLMResponse.provider` stamped by the router; Cover Letter shows a Cloud badge when `provider_used` is not ollama. Tests: `test_cloud_fallback_none.py`. Backend 1,073 passed; mypy gate 182/0 new.

##### Step 2.2: One LLM factory everywhere (effort: S) — S2

Bare `LLMRouter()` call sites re-checked on 2026-10-19:

| Location | Notes |
|----------|-------|
| `src/pipeline/stages.py` (~114) | Pipeline stages |
| `src/pipeline/orchestrator.py` (~182) | `llm_router or LLMRouter()` |
| `src/api/routes/profile.py` (~141, ~345, ~778) | Three sites |
| `src/api/main.py` (~78) | Agent system init |
| `src/evaluation/cover_letter_compare.py` (~325) | Compare writer |

Already correct: `cover_letter_service.py`, `cover_letter.py` routes, and `jobs.py` use `create_router(prefer_local=True)`.

- [x] Replace every bare `LLMRouter()` above with `create_router(...)` (or inject a router from the caller). Keep one public factory in `src/llm/router.py`.
- [x] Test that fails if a production module constructs `LLMRouter(` directly (AST or import-graph scan of `src/`, excluding tests and the factory itself).
- [x] Done when: Settings (host, models, fallback) apply to pipeline, profile, agents, and compare the same way they apply to Cover Letter.

**Review (2026-10-19):** AST scan in `test_no_bare_llm_router.py`. Backend 1,074 passed.

##### Step 2.3: Bind to localhost and require auth (effort: S) — S3, S4

Current state (2026-10-19):

- `scripts/dev.sh` (~84): `uvicorn ... --host 0.0.0.0`.
- `docker/Dockerfile` CMD: `--host 0.0.0.0`.
- `docker-compose.yml`: publishes backend `8000` and frontend `3000` on all host interfaces.
- `scripts/dev.sh` (~90): `npm run dev -- --port 3000`; `next dev` listens on all interfaces.
- `src/api/auth.py` (~51-58): skips auth when `ENVIRONMENT=development` and `API_KEY` is empty.

- [x] Bind the local API to `127.0.0.1` in `scripts/dev.sh`.
- [x] Docker: keep `--host 0.0.0.0` inside the backend container, so the frontend container reaches `backend:8000` on the Compose network. Stop publishing `8000` on the host (decision 3). Update `docker-run.sh` and `scripts/find-port.sh` if they still look for a free backend port.
  - Consequence: in Docker, the browser WebSocket (`ws://localhost:8000`) no longer connects. The Live Monitor still works from status polling (Step 1.5). If live events are needed in Docker later, publish `127.0.0.1:8000` only.
- [x] Bind the frontend to `127.0.0.1` (decision 4): run `next dev` with `-H 127.0.0.1` in `scripts/dev.sh`, and publish the frontend as `host_ip: 127.0.0.1` in `docker-compose.yml`. Reason: the Next.js proxy adds `X-API-Key` to every request it forwards, so any device that reaches port 3000 can use the API (for example `GET /api/proxy/profile/export`).
- [x] `setup.sh`: generate a random `API_KEY` and write it to both backend `.env` and frontend `.env.local` (never commit those files). Stop writing the public placeholder `your_api_key_here`.
- [x] Auth bypass only when `AUTH_DISABLED=1` is set explicitly. Remove the "empty API_KEY in development" bypass from `src/api/auth.py` (decision 2).
- [x] Tests: empty `API_KEY` without `AUTH_DISABLED` returns 401. `AUTH_DISABLED=1` allows requests. A test reads `docker-compose.yml` and fails if a port is published without `host_ip: 127.0.0.1`, or if backend port `8000` is published. Document the flag in `.env.example` and `docs/usage.md`.
- [x] Done when: a fresh setup has a real key, and another device on the LAN can reach neither the API nor the frontend proxy.

**Review (2026-10-19):** TestClient overrides auth except in `test_auth.py`. Compose test: `test_docker_compose_local_first.py`.

##### Step 2.4: Do not return or log secrets (effort: S) — S5

- [x] `GET /api/settings/` returns `has_anthropic_key` / `has_gemini_key` (booleans), not the key strings (`src/api/routes/settings.py`). PUT still accepts keys to save them.
- [x] Frontend Settings form uses the flags to show "Key saved" vs empty, and only sends a key field when the user edits it.
- [x] `src/lib/api/client.ts` (~149-153): do not log request or response bodies outside development (or never log bodies that may contain keys). Keep method and path.
- [x] Tests: settings GET fixture has no `sk-` / key material; client log spy does not receive the PUT body.
- [x] Done when: DevTools Network still needs HTTPS locally for transport safety, but the JSON settings payload and the console no longer print secrets.

**Review (2026-10-19):** `for_client` / `merge_preserving_api_keys`; client never logs bodies. Mutation: remove `for_client` from GET → test fails on secret leak.

##### Step 2.5: Cover letter routes off the event loop (effort: S) — follow-up from Step 1.6

- [x] `generate_cover_letter_for_profile` in `src/generation/cover_letter_service.py` awaits `asyncio.to_thread(generate_cover_letter_sync, ...)` (today it calls the sync body on the event loop at ~561).
- [x] Same pattern for any other async route that still awaits the sync service directly (`cover_letter.py`, `jobs.py` cover-letter path) if they bypass the helper.
- [x] Tests: while a generate is in flight, a health or status request still completes (same style as `test_pipeline_run_async.py`).
- [x] Done when: a long cover-letter generate does not stall WebSockets or other API requests on the single worker.

**Review (2026-10-19):** Routes already use the helper. Mutation: sync-on-loop → tick count fails.

##### Step 2.6: Host, Origin, ollama_host, and profile_url guards (effort: S to M) — S6, S7, S8

- [x] Validate `ollama_host` on Settings save (`src/api/settings.py` / routes): `http` or `https`, host and port only, and the host must be `localhost`, `127.0.0.1`, `host.docker.internal`, or `ollama` (decision 5).
- [x] Add `TrustedHostMiddleware` in `src/api/main.py` with hosts for local and Compose use.
- [x] Next.js proxy (`apps/frontend-ts/src/app/api/proxy/[...path]/route.ts`): reject a request when `Sec-Fetch-Site` is `cross-site`, or when `Origin` is present and is not the app origin (cross-site requests from a page the user visits). Also reject a `Host` that is not `localhost` or `127.0.0.1` with the app port (DNS rebinding). Allow requests with no `Origin`; after decision 4 only this machine can reach the proxy.
- [x] Validate `profile_url` before Playwright `page.goto` in `src/linkedin/session.py` (`fetch_profile_text` ~376, `navigate_to_url` ~372): allow only `https://` LinkedIn profile URLs; reject `file://`, bare IPs, and non-LinkedIn hosts.
- [x] Tests for each guard (reject bad host, bad Origin, bad profile URL).
- [x] Done when: a changed Settings host, a cross-site POST, and a `file://` profile URL are all refused with clear errors.

**Review (2026-10-19):** `navigate_to_url` allows any https LinkedIn path (search); `fetch_profile_text` requires `/in/`. ``ALLOWED_HOSTS`` includes ``testserver``.

##### Step 2 review (2026-10-20)

Cursor implemented Steps 2.1 to 2.6 in `8e97841`..`0560b48` (pushed with the R1 and R2 fixes on 2026-10-20). All CI checks passed: Black, ruff, mypy gate 182/0 new, pytest 1,085 passed, ESLint, tsc, Prettier, Vitest 241 passed in 43 files, and `next build`. Probes against running servers found two blockers that the tests did not cover.

Blockers (fix before push):

- [x] **R1. `make dev` returns 401 on every API call.** No code path loads `apps/backend-py/.env` for native runs: `scripts/dev.sh` does not source it, uvicorn has no `--env-file`, and `src/` never calls `load_dotenv`. Before Step 2.3, an empty `API_KEY` skipped auth in development, so the gap did not show. Probe: uvicorn started as `dev.sh` does logged `Authentication MISCONFIGURED`, and `GET /api/settings/` returned 401. `AUTH_DISABLED=1` in `.env` is ignored in the same way. Compose is not affected (it uses `env_file`). Fix: pass `--env-file "$BACKEND_DIR/.env"` to uvicorn in `scripts/dev.sh`; every `make dev*` target uses that script.
  - **Done (2026-10-20):** `scripts/dev.sh` passes `--env-file`. `tests/unit/test_dev_launcher.py` runs the real script in a temporary repository layout with a stub `python3` and checks the uvicorn arguments; it failed before the fix (`--env-file` missing). Runtime proof with `--reload`: no key 401, wrong key 401, right key 200. The real `dev.sh api` logged `Loading environment from '.../apps/backend-py/.env'` and no auth error.
- [x] **R2. The proxy rejects the app's own POST requests.** `guard.ts` compares `Origin` with `req.nextUrl.origin`. Next.js builds that URL from the server bind settings, not from the browser `Host`. Probes: the Docker standalone server (`HOSTNAME=0.0.0.0`) returned 403 for every same-origin POST; `next dev --hostname 127.0.0.1` returned 403 for `Origin: http://127.0.0.1:3001` and allowed only `localhost`. Same-origin GET requests send no `Origin`, so pages loaded, but saves, pipeline runs, and cover letter generation failed. The unit test built each request with a URL equal to its `Host`, so it could not see this. Fix: check the `Host` first, then require `Origin` to have the same host and port as the `Host` header.
  - **Done (2026-10-20):** `guard.ts` compares `new URL(origin).host` with the `Host` header. Four new tests in `guard.test.ts`; the two "allows" cases (server URL `0.0.0.0:3000` with `Host: 127.0.0.1:3005`, and server URL `localhost` with `Host: 127.0.0.1`) failed before the fix. Mutation: compare hostnames only, without the port; "rejects an Origin on another local port" failed. Real-server probes after the fix: same-origin POST passed the guard in the Docker standalone server and in `next dev --hostname 127.0.0.1`, on `127.0.0.1`, `localhost`, and published port 3005; `evil.example`, another local port, and a foreign `Host` returned 403.

Should fix (Step 2 gaps):

- [x] **R3.** The `ollama_host` allowlist runs as a model validator, so it also runs on load. `SettingsStorage.load_settings` turns any validation error into defaults, so a stored host outside the allowlist silently drops all saved settings, and the next save writes defaults without the stored API keys. Validate on save and validate only, or replace only the bad host on load and log a warning.
  - **Done (2026-10-21):** `load_settings` replaces a bad host with `host.docker.internal:11434`, logs a warning, keeps keys/routing. PUT/validate still reject bad hosts. Prove: `test_load_replaces_bad_ollama_host_and_keeps_other_fields` (before: key was `None`). Mutation: old `load_settings` → fails. Note: other load errors still `print` + defaults (left for a later cleanup).
- [x] **R4.** A bad LinkedIn `profile_url` is not refused with a clear error. `_fetch_linkedin_profile_text_sync` catches the `ValueError`, logs a warning, and continues with empty text after it opened a LinkedIn session. Validate `profile_url` on the request model (422) before a session starts.
  - **Done (2026-10-21):** `LinkedInProfileInput.profile_url` field_validator calls `validate_linkedin_profile_url`. Prove: `test_rejects_file_http_and_non_linkedin_urls` (before: 500, session reached). Mutation: remove validator → fails. `LinkedInPeopleSearchResult.profile_url` left (output only). Country hosts still refused (ask if that should change).
- [x] **R5.** The "Cloud" badge is on the Cover Letter page only. The Step 2.1 "Done when" also names the Pipeline UI.
  - **Done (2026-10-21):** `provider_used` on `GeneratedResume`; generate stage `cloud_documents`; status response + shared `CloudBadge`. Prove: `test_cloud_documents_counts_non_ollama_providers`, Vitest pipeline Cloud badge. Mutation: ignore resume provider in count → fails.

Smaller items:

- [x] **R6.** `tests/unit/test_settings_api.py` calls `PUT /api/settings/`, `POST /reset`, and `POST /ollama-defaults` on the real `data/settings/user_settings.json` (since 2026-07-09). Each pytest run resets the developer's settings, and after Step 2.4 that includes saved cloud API keys. Point the settings storage at `tmp_path` for these tests.
  - **Done (2026-10-21):** Autouse `_isolate_settings_storage` in `tests/conftest.py`. Prove: `test_get_storage_uses_pytest_temporary_directory` (failed before: pointed at `data/settings/user_settings.json`). Mutation: remove fixture → fails. Runtime: `stat -c %y` on real settings file unchanged across settings API tests and a full pytest run (`2026-10-20 22:27:07.458114300 +0800`). Note: `test_records_expire_after_ttl` flaked once in the full suite (passes alone); unrelated to R6.
- [x] **R7.** The Settings page cannot remove a saved cloud API key (a blank field keeps the stored key).
  - **Done (2026-10-21):** `DELETE /api/settings/api-keys/{provider}` (`anthropic`|`gemini`); Settings UI "Remove saved key" + env-key note. Prove: `test_delete_anthropic_keeps_gemini`, `test_delete_unknown_provider_returns_422` (before: 404); Vitest `remove-api-key.test.tsx`. Mutation: skip `save_settings` → backend test fails. No real-server DELETE (would wipe the user's settings file).
- [x] **R8.** `ALLOWED_HOSTS` defaults include `testserver`. Set it in test setup instead. The comment above `TrustedHostMiddleware` says it is outermost, but CORS (added later) wraps it.
  - **Done (2026-10-21):** Defaults are `localhost,127.0.0.1,backend`; `tests/conftest.py` sets `ALLOWED_HOSTS` with `testserver` before app import; TrustedHost is added after CORS so it runs first. Prove: `test_default_allowed_hosts_exclude_testserver`, `test_cors_preflight_rejects_unknown_host` (before: assert failed / 200). Mutation: old middleware order → preflight test fails. Runtime: uvicorn on 8766, OPTIONS with `Host: evil.example` → 400; GET health with `Host: 127.0.0.1:8766` → 200.
- [x] **R9.** The WebSocket `/api/pipeline/{run_id}/progress` has no auth and no `Origin` check. A page in the browser that knows a `run_id` can read progress events. Check `Origin` on connect.
  - **Done (2026-10-21):** Before `accept()`, refuse an `Origin` not on the CORS allow list with close code 1008; missing `Origin` is allowed. Prove: `test_refuses_evil_origin` / `test_allows_localhost_origin` / `test_allows_missing_origin` (before: evil did not raise). Mutation: remove Origin check → refusal test fails. Runtime: websockets client to uvicorn 8766; evil origin refused, `http://localhost:3000` received `connected`.
- [x] **R10.** Delete the Cursor scratch files `tasks/_*.sh` and `tasks/_commit_msg.txt` (untracked).
  - **Done (2026-10-21):** Removed the 13 untracked `tasks/_*.sh` / `tasks/_commit_msg.txt` files. No commit of its own (untracked). Tick recorded with the R8 commit.

**Review of R3 to R6 and F1 (2026-10-21):** The changes are correct. Full gate in WSL: Black, ruff, mypy gate 182 known and 0 new, pytest 1,092 passed (the real settings file's modification time did not change), ESLint, tsc, Prettier, Vitest 249 passed in 45 files, `next build`, Playwright 42 passed, and the Mobile Chrome smoke spec 10 times with no retries: 140 passed. Prettier first failed only on 8 files that had CRLF on disk and no content change (Cursor rewrites them); after the CR bytes were removed, it passed. Gaps:

- [x] **R5a.** No test covers `cloud_documents` in `GET /api/pipeline/status/{run_id}`. The route reads it with `getattr(..., None) or {}`, so a wrong name would show 0 and no test would fail.
  - **Done (2026-10-21):** `TestRunEndpoints` in `test_pipeline_routes.py` stores a real `PipelineResult` whose generate stage (key from `PipelineStage.GENERATE_RESUMES`) has `cloud_documents=2`, and checks that status returns 2; a run without that stage returns 0. Mutation: the route reads `"generate_resume"`; the test fails.
- [x] **R5b.** The stage test has a cloud resume with a local cover letter, but no case with a local resume and a cloud cover letter. If the cover letter provider is dropped, the test still passes.
  - **Done (2026-10-21):** `test_cloud_documents_counts_a_cloud_cover_letter` (local resume, `gemini` cover letter, count 1). Mutation: count the cover letter provider as `None`; the new test fails and the old test still passes, which confirms the gap.
- F1 also raised E2E timeouts (60 s navigation, 90 s for the navigation tests) for slow local Docker bind mounts. CI passed with 15 s before. See the Backlog item "Test and E2E hardening".

**Review of R7 to R10 (2026-10-21):** The changes are correct. Full gate in WSL: Black, ruff, mypy gate 182 known and 0 new, pytest 1,102 passed (the real settings file's modification time did not change), ESLint, Prettier, Vitest 250 passed in 46 files, `next build`, and Playwright passed. tsc failed once with a stale `.next` left by an earlier dev-server run (`tsconfig.json` includes `.next/types` and `.next/dev/types`); a rerun without `.next` passed. Runtime probes on uvicorn with a temporary env file: a CORS preflight with `Host: evil.example` returned 400 (200 with the real host); `Host: testserver` returned 400; a WebSocket with `Origin: http://evil.example` was refused with HTTP 403 and a warning, and `http://localhost:3000` and a missing `Origin` connected. New items:

- [x] **R11.** Saved Settings do not reach long-lived routers. `src/api/main.py` builds the agent system router one time at startup (`initialize_agent_system(create_router(...))`), and `src/api/routes/profile.py` caches `_llm_router` in `_get_linkedin_analyzer`. Nothing reloads them when settings change. So a removed API key, new routing, or a switch of the cloud fallback to "None (local only)" does not apply to agents or LinkedIn analysis until the backend restarts. Fix: build these routers per request (as the pipeline and cover letter paths do), or reload them after each settings write.
  - **Done (2026-10-21):** Successful saves increment a process-local Settings revision. Routers from `create_router()` check that revision under a lock before each sync/async generation, reload changed routing, and restore constructor keys when saved keys are removed. Direct `LLMRouter(...)` instances do not follow Settings. Prove: four `TestCreateRouterReloadsChangedSettings` tests, including API DELETE reaching a long-lived router (before: Anthropic fallback still ran). Mutation: remove the sync revision check → first test fails; restored file → 7 router Settings tests pass.
- [x] **R7a.** "Remove saved key" saves the settings, which changes `updated_at`. `SettingsPage` keys `SettingsForm` on `updated_at`, so the form remounts and discards unsaved edits in other fields. Update the query cache from the DELETE response without a remount, or warn when the form has unsaved changes.
  - **Done (2026-10-21):** `SettingsForm` is keyed on a local version that changes only after Save or Reset. Key removal and background refetches update server flags without remounting or losing drafts; Save/Reset cache their returned settings before replacing form values. Prove: `keeps unsaved edits when key removal refetches newer settings` and `shows values returned by a successful save` (before: maximum cost reset from 17 to 5). Mutation: restore the `updated_at` key → draft-preservation test fails; restored file → 3 tests pass.

**Review of R11 and R7a (2026-10-21):** The changes are correct. Full gate in WSL: Black, ruff, mypy gate 182 known and 0 new, pytest 1,106 passed (the real settings file's modification time did not change), ESLint, tsc (with `.next` deleted first), Prettier, Vitest 252 passed in 46 files, `next build`, and Playwright 42 passed with 0 retries. Both mutations repeated: with the two `generate` reload calls removed, `test_generate_reloads_removed_key_and_none_fallback` fails (the router takes the Anthropic fallback); with the `updated_at` key restored, the draft test fails. No other code writes the saved Settings from the UI (Ollama tier changes stay in the form until Save), so the local form version is safe. Small items:

- [x] **R11a.** `apply_user_settings` reads the Settings revision after `load_settings()`. If a save lands between the two, the router records the new revision with the old settings and misses that save until the next one. Read the revision before loading.
  - **Done (2026-10-21):** `apply_user_settings` reads the revision before `load_settings()` and records that value. `test_save_during_reload_is_applied_on_next_refresh` wraps `load_settings` so a save with a new key lands after the load; the next refresh must apply the new key (failed before: `'sk-ant-old' == 'sk-ant-new'`). Mutation: record `get_settings_revision()` after the load again (checksum changed, fixed-string count 1); the test fails.
- The API-level R11 test uses a new `create_router()` router and calls `_refresh_user_settings_if_changed()` directly, not the cached LinkedIn or agent router. The cached routers are covered indirectly: the Step 2.2 AST test requires `create_router()` everywhere, and the first R11 test proves that such a router reloads on `generate`.

##### Out of scope for Step 2

- LinkedIn automation / User Agreement / cookie storage hardening (review S9; Step 5).
- Scoring, dedupe, scam regex, RAG fusion (Step 3).
- Demo polish (Step 4).
- Easy Apply / auto-submit reachability (Step 5).

##### Decisions (2026-10-19)

1. **Default cloud fallback:** `CloudProvider.NONE`. A cloud model runs only when the user picks a cloud fallback in Settings.
2. **Auth bypass:** only `AUTH_DISABLED=1`. Remove the `ENVIRONMENT=development` + empty `API_KEY` bypass.
3. **Backend in Docker:** `0.0.0.0` inside the container; do not publish `8000` on the host. The frontend container uses `backend:8000`.
4. **Frontend:** bind to `127.0.0.1` in `next dev` and in Compose. This changes the plan's first recommendation (keep publishing `3000` on all interfaces), because the proxy adds the API key to every request it forwards.
5. **`ollama_host`:** allow only `localhost`, `127.0.0.1`, `host.docker.internal`, and `ollama`.
6. **Cloud badge:** show a small "Cloud" badge on results when the provider was not Ollama.

#### Step 3 plan: Make claims measurable

**Goal:** Every number in the README and in the resume framing (review section 7) comes from a command in this repository that anyone can run again. Each fix in this step is measured on a labeled set before and after the change.

**Constraints:**

- Measure first. For each fix (R2, R3, R4, R5, M7), record the baseline numbers before the change and the numbers after it.
- No personal data in committed fixtures. Use a synthetic profile and public job postings (the source fixtures under `tests/fixtures/`). Runs with the real profile stay local; their outputs stay in `apps/backend-py/data/` (gitignored).
- Deterministic suites (grounding, scam rules, dedupe, heuristic ranking, BM25) run in CI without Ollama. Suites that need Ollama or embeddings (dense and hybrid ranking, LLM output, model comparison) run locally and log to MLflow.
- Keep dry run as the default. Do not make auto-submit reachable (Step 5).
- Each sub-step is one commit (or PR) with its own tests. Run all local checks before each push.
- Line numbers below were checked on 2026-10-22.

```mermaid
flowchart LR
    S31[3.1 Eval harness and run metadata] --> S32[3.2 Grounding set, then M7 fixes]
    S31 --> S33[3.3 Scam set, then R3 fixes]
    S31 --> S34[3.4 Ranking set, then R4 and R5 fixes]
    S31 --> S35[3.5 Dedupe set, then R2 fix]
    S36[3.6 Real cost and usage tracking]
    S37[3.7 Schema output and num_ctx] --> S38[3.8 Model comparison on the grounding set]
    S32 --> S38
    S32 --> S39[3.9 README and resume numbers]
    S33 --> S39
    S34 --> S39
    S35 --> S39
    S36 --> S39
    S38 --> S39
```

##### Step 3.1: Eval harness and run metadata (effort: S to M) — M2

- [ ] Shared pieces in `src/evaluation/`: a JSONL case loader with a Pydantic schema per suite; metric functions (precision, recall, and F1 per label; NDCG@k; recall@k); run metadata (git SHA and dirty flag, SHA-256 of the dataset, hash of the prompt template, model, temperature, seed).
- [ ] One command: `python main.py eval <suite>` (suites: `grounding`, `scam`, `dedupe`, `ranking`, `compare`). It writes a JSON report to `data/eval/<suite>/<timestamp>.json` and, when MLflow is reachable, one MLflow run with the metadata as params and tags and the metrics as metrics.
- [ ] MLflow store: `MLFLOW_TRACKING_URI` when set; otherwise SQLite at an absolute path, `apps/backend-py/data/mlflow.db`, with artifacts in `apps/backend-py/data/mlartifacts` (decision 5), not `./mlruns` relative to the working directory (review R9). Today only 5 of the 16 public `MLflowTracker` methods have a caller (Question 5).
- [ ] Tests: metric functions against hand-computed values (NDCG with ties and with no relevant item); the metadata has a 40-character SHA; the dataset hash changes when one case changes; a report is written when MLflow is not reachable.
- [ ] Done when: `python main.py eval grounding` on a tiny set writes a report and an MLflow run with the git SHA and dataset hash.

##### Step 3.2: Grounding golden set, then the M7 fixes (effort: M) — M4, M7

- [ ] `tests/fixtures/eval/grounding/cases.jsonl` with at least 60 cases. Each case has a synthetic profile, a job, a letter, and the expected set of issues:
  - clean letters that match the profile (expected: no issues);
  - one injected error per case: a number that the profile does not support ("90%", "3x"), an employer, a degree, inflated years of experience, or a tech that the profile does not have;
  - normal English with tech homonyms ("express my interest", "spring semester", "a swift reply", "spark curiosity"; expected: no issue);
  - short tokens that matter ("AWS", "GCP", "C#", "Go", "90%");
  - job descriptions with prompt-injection text, where the letter states JD claims as the candidate's own.
  - About 15 real generated letters labeled by hand (Question 1).
- [ ] Baseline with the deterministic validator only (`cover_letter_validator.py`, `cover_letter_grounding.py`; no LLM): precision, recall, and F1 per issue type, and the false-positive rate on clean letters.
- [ ] Fix M7 after the baseline: keep numbers and known short tech names that `cover_letter_grounding.py:414` drops today (`len(word) > 3`); flag the homonyms `swift`, `express`, `spring`, and `spark` (allowlist at `cover_letter_grounding.py:163-209`) only in a tech context. Record the numbers after the fix.
- [ ] CI gate: a pytest runs the suite and fails if a metric is below `tests/fixtures/eval/grounding/thresholds.json`. Raise a threshold only in a commit that shows the new numbers (Question 4).
- [ ] Done when: the README can say "grounding validator: precision P and recall R per check on N labeled letters", with the command that reproduces it.

##### Step 3.3: Scam set, then the R3 fixes (effort: M) — R3, M4

- [ ] `tests/fixtures/eval/scam/cases.jsonl` with at least 40 postings: legitimate postings from the source fixtures; written scam texts for each indicator group (Payment, Contact, Urgency, Compensation, Listing quality); and legitimate texts that the current rules flag ("signal processing", "competitive pay and the chance to work", a WhatsApp Business API integration role, an engineering role at a bitcoin exchange).
- [ ] Baseline on that set, and locally on the Kaggle EMSCAD set (`fake_job_postings.csv`, used by `notebooks/scam_detector_evaluation.ipynb`; `data/kaggle/` is empty today). Split EMSCAD into a tuning part and a held-out part with a fixed seed (Question 3).
- [ ] Fix R3 after the baseline: word boundaries and phrase context for the patterns at `scam_detector.py:118-140` (`pay.*to.*work`, `signal`, `kik`, `telegram`, `whatsapp`) and the keyword list at `:591-594` (a plain `bitcoin` match). Tune the threshold on the tuning part. Report the held-out numbers only.
- [ ] CI gate on the committed set (thresholds file). The EMSCAD run stays local and logs to MLflow. Change the notebook to call `python main.py eval scam`, so that the logic exists only once.
- [ ] Done when: the README states precision and recall on the held-out EMSCAD part, and the committed set guards the false-positive cases.

##### Step 3.4: Ranking set, then the R4 and R5 fixes (effort: M) — R4, R5

- [ ] `tests/fixtures/eval/ranking/`: one or two synthetic profiles, and 30 to 50 public jobs for each profile from the source fixtures, with a label per pair: 0 (not relevant), 1 (maybe), 2 (apply) (Questions 1 and 2).
- [ ] Baseline NDCG@10 and recall@10 for the heuristic matcher, BM25 only, dense only, and hybrid (RRF). The heuristic and BM25 runs are in CI; dense and hybrid need the embedding model and run locally.
- [ ] Fix R4 after the baseline: whole-word matching for keywords and skills (`matcher.py:228-245` and `:315-326`; "ai" matches "email" today), and a skill score that does not go down when matches go up (0 matches score 20 of 40; 1 match of many can score 10 of 40).
- [ ] Fix R5 after the baseline: dense results use `job_id` (`ranker.py:408`) and BM25 results use chunk IDs (`ranker.py:160`), so RRF (`ranker.py:436-442`) never fuses them. Fuse at job level (best chunk rank per job before RRF). Put jobs inside and outside the hybrid result on one score scale (`ranker.py:292-296`).
- [ ] Done when: the README states NDCG@10 for heuristic, BM25, dense, and hybrid on the labeled set, measured after the R5 fix.

##### Step 3.5: Dedupe set, then the R2 fix (effort: S) — R2

- [ ] `tests/fixtures/eval/dedupe/` with about 30 pairs of listings from the source fixtures: the same job from two sources, reposts, and different jobs with the same title at the same company. Label each pair "same" or "different".
- [ ] Baseline: `JobListingCollection.deduplicate` (`job_listing.py:397-416`) compares `job_id` only, and IDs carry a source prefix, so it never merges a job across sources.
- [ ] Fix: also merge on the URL when present, and on normalized company, title, and location. Keep the order that `AppliedGuard` uses (ID, URL, company and title). Report precision and recall before and after. CI gate.

##### Step 3.6: Real cost and usage tracking (effort: S) — M1, M8

- [ ] `CostTracker.track_call` (`cost_tracker.py:200`) has no caller. Call it from `LLMRouter` after each response (primary, fallback, and cache hit), through one process-wide tracker that `routes/metrics.py:24` also reads.
- [ ] Record provider, model, prompt and completion tokens, latency, cache hit, and cost (0 for Ollama). Update the cloud prices in `MODEL_PRICING` with the date of the source, or label them as estimates.
- [ ] At the end of a pipeline run, log the cost summary to MLflow (`MLflowTracker.log_cost_summary` at `mlflow_tracker.py:216` has no caller).
- [ ] Tests: one mocked call is tracked one time; a cache hit is tracked as a cache hit; a fallback call is tracked with the fallback provider.
- [ ] Done when: the Metrics page shows real token counts after a run. No cost-saving claim goes back into the README unless this data supports it.

##### Step 3.7: Schema-constrained output and context size (effort: M) — R13, R14

- [ ] Use Ollama `format` with the JSON schema of a Pydantic model for each JSON task, and parse with `model_validate_json`. 9 files still parse LLM JSON with the regex `\{.*\}`: `validator.py`, `selector.py`, `resume_writer.py`, `resume_analyzer.py`, `cover_letter_reviewer.py`, `cover_letter_validator.py` (in `src/generation/`), `resume_parser.py`, `jd_extractor.py` (in `src/extractors/`), and `classifiers/job_classifier.py`.
- [ ] Set `num_ctx` per task in the routes; no code sets it today. `jd_extractor.py:233` sends up to 50,000 characters. Cut the input to the task budget and log when the extractor falls back to rule-based parsing.
- [ ] Measure the parse-failure rate per task on a fixed local set, before and after (local; needs Ollama; MLflow).
- [ ] Done when: no code parses LLM JSON with a regex, and the parse-failure rate is recorded.

##### Step 3.8: Model comparison on the grounding set (effort: S to M) — M3

- [ ] Point `cover_letter_compare.py` at the jobs and profiles of the grounding set (`build_fixtures()` at line 127 builds its own few cases today). Use a fixed temperature, at least 3 samples per case, and the validator metrics from Step 3.2.
- [ ] Compare the installed local models with `qwen2.5:7b`. Log each model as one MLflow run with the Step 3.1 metadata. Add the table and the command to `docs/decision-log.md`.
- [ ] Done when: the model choice in the decision log rests on the grounding set, not on 3 synthetic cases.

##### Step 3.9: README and resume numbers (effort: S)

- [ ] In `README.md`, `docs/index.md`, and `docs/architecture.md`, add or change numbers only from the Step 3.2 to 3.8 reports, each with its command and date. Remove each number that no report supports.
- [ ] Update the bullets in section 7 of `tasks/review-2026-10-18.md` with the real values of N and of each metric.

##### Out of scope for Step 3

- Demo mode and the static deploy (Step 4).
- The sidebar, pruning, and the Easy Apply decision (Step 5).
- Hard-coded scoring weights and outcome feedback into scoring (M5). Change the weights only if the Step 3.4 eval shows that a change helps.

##### Decisions (2026-10-22)

All five recommendations were accepted.

1. **Labels:** the user labels the ranking pairs (about 40 for each profile, 0/1/2) and about 15 real generated cover letters. The agent writes the constructed cases and a short labeling guide.
2. **Profile in committed fixtures:** a synthetic profile with no personal data in `tests/fixtures/eval/`. The real profile is used only in local runs, with outputs in `data/` (gitignored).
3. **EMSCAD dataset:** the user downloads `fake_job_postings.csv` from Kaggle with their account into `apps/backend-py/data/kaggle/` and checks the license first. It is not committed.
4. **CI gates:** the deterministic suites (grounding, scam, dedupe, heuristic ranking, BM25) fail CI when a metric drops below its thresholds file.
5. **MLflow store:** a local store under `apps/backend-py/data/` when `MLFLOW_TRACKING_URI` is not set; the shared MLflow server (`http://localhost:5000` on the host, `http://mlflow:5000` in Compose) when it is set. Change from the plan: the local store is SQLite (`data/mlflow.db`, artifacts in `data/mlartifacts`), not a file store in `data/mlruns`. The installed MLflow 3.14.0 raises an exception for the file store unless `MLFLOW_ALLOW_FILE_STORE=true` is set, because that backend is in maintenance mode.

Suggested order: Step 3.1 first. Then Steps 3.2, 3.3, 3.5, and 3.6, which are deterministic and can go to Cursor. Step 3.4 needs your labels. Steps 3.7 and 3.8 need Ollama on your machine.

## Next

Step 3.1 (eval harness and run metadata), in progress.

## Backlog

Items here are parked. Move an item to **Next** before you start it.

### Flaky Mobile Chrome navigation smoke test (2026-10-19)

`tests/e2e/smoke.spec.ts:86` ("Primary navigation", Mobile Chrome project) times out after 30 s while it waits for `locator('nav').getByRole('link', { name })`. It passes on retry. The page is different each run, and it also fails on commits with no frontend change:

| Commit | Flaky | Pages |
|--------|-------|-------|
| `63e5e0a` | 0 | none |
| `39ce749` | 2 | Dashboard, Assessment |
| `3ae8a9e` | 1 | LinkedIn Analysis |
| `428977c` | 0 | none |
| `ca030d2` | 2 | Dashboard, Resume Analysis |
| `b5ecfed` | 1 | Metrics |
| `5a8232f` | 2 | Jobs, Career Coach |

- [x] Step 1: Find the root cause. Candidates: the mobile navigation sheet is not open or not ready when the test clicks; `next dev` compiles the route on first visit.
- [x] Step 2: Fix the test or the navigation, so that the test does not need a retry. Do not only raise the timeout.

**Root cause:** On mobile, `locator("nav")` also matched the desktop sidebar `nav` that stays in the DOM under `hidden md:flex`. The test clicked the hamburger and then raced that hidden nav before the sheet dialog was ready.

- [x] Step 3 (reopened 2026-10-20): The test flaked again in a local full run (Docker `node:20` from Windows, after the R2 fix; E2E mocks the API, so the fix does not touch this path). Mobile Chrome "opens the Settings page": a `toBeVisible` check in `navigateTo` failed after 7.1 s, then the test passed on retry. The dialog-scoped locator fixed the hidden `nav` race, but a tap on "Open navigation" before hydration can still be lost, so the sheet does not open. Candidate fix: repeat the open click until the dialog is visible (`expect(...).toPass()`), or wait for a hydration signal before the click. Watch the next CI runs.

**Review (2026-10-19):** Added a screen-reader `SheetTitle` ("Navigation") on the mobile sheet. The smoke helper opens the sheet, waits for `getByRole("dialog", { name: "Navigation" })`, and clicks the link inside that dialog. Desktop clicks use `aside`. `--repeat-each=10` on Mobile Chrome smoke: 140 passed, 0 flaky. Full Playwright suite: 42 passed.

**Done (2026-10-21):** `navigateTo` retries open until the Navigation dialog is visible (`expect(...).toPass`), and skips a second click when the dialog is already open. Soft-nav and 404 gotos also allow up to 60 s on cold `next dev` (Docker bind mounts). Proof under load (Vitest in a second container): Mobile Chrome smoke `--repeat-each=20 --retries=0` → 280 passed, 0 failed. Full Playwright suite (clean `.next`): 42 passed, 0 failed.

### Test and E2E hardening (2026-10-21)

- [ ] `tests/unit/agents/test_task_store.py::test_records_expire_after_ttl` flaked once in a full run. `TaskStore` (`src/agents/task_store.py`) measures age with `datetime.now()`, the wall clock, which can jump in WSL2, and the test leaves a 50 ms margin (TTL 1.05 s, sleep 1.1 s). Use `time.monotonic()` for the TTL check.
- [ ] Run Playwright against a production build (`next build` and `next start`) instead of `next dev`, so tests do not wait for on-demand compiles. Then set the navigation timeouts in `tests/e2e/smoke.spec.ts` and `basic.spec.ts` back to 15 s.

### Small follow-ups from completed work (2026-10-18)

These items were still open inside completed sections. Each line names its source in the archive.

- [ ] mypy reports pre-existing typing issues across the backend. *(Source: Phase 47; 195 mypy errors on 2026-10-18; review Step 1 covers this)*
- [ ] Test DISC assessment end-to-end *(Source: Phase 36 backlog; no E2E spec covers DISC on 2026-10-18)*
- [ ] Expand fixtures from real pastes during job hunt (keep PII out) *(Source: Paste-JD unstructured to structured (2026-08-07))*
- [ ] Metrics: cache hit rate already sketched on cost tracker — make real *(Source: LLM caching strategy; `CostTracker.track_call` is never called on 2026-10-18)*
- [ ] Prefer YAML single source where Python duplicates templates *(Source: LLM caching strategy)*
- [ ] Document minimum token thresholds / providers that no-op below size *(Source: LLM caching strategy)*
- [ ] Gemini CachedContent only if fallback volume justifies it *(Source: LLM caching strategy)*
- [ ] Document VRAM tradeoff *(Source: LLM caching strategy)*
- [ ] Abandon if idle CPU / main-thread cost is noticeable; do not add Three.js *(Source: Optional cinematic atmosphere)*
- [ ] Handle non-Easy Apply jobs (external site redirect) — flag, surface in UI, pre-fill clipboard *(Source: Phase 31 backlog; decide on Easy Apply first; see review Step 5)*
- [ ] Add resume upload handling in form filler *(Source: Phase 31 backlog; decide on Easy Apply first; see review Step 5)*
- [ ] Add frontend UI for LinkedIn auto-apply configuration and monitoring *(Source: Phase 31 backlog; decide on Easy Apply first; see review Step 5)*
- [ ] DISC: Extra results visualizations (radar on results, bars toggle, match-gap charts, view toggle) *(Source: DISC assessment improvements, standby ideas)*
- [ ] DISC: Richer role recommendations aligned to AI Eng / SWE+AI / DA ladder with trait-driven explanations *(Source: DISC assessment improvements, standby ideas)*

### Pipeline duration / progress honesty

**Status:** Deferred — do after Discover → Jobs is stable.

**Idea:** Improve scrape/run feedback beyond the existing stage progress bar.

- [ ] Elapsed timer on live monitor while a run is active
- [ ] Final `duration_seconds` surfaced clearly on complete + history rows
- [ ] Optional: per-stage timings (scrape usually dominates)
- [ ] Optional later: ETA from prior runs (stage-weighted; avoid fake global %)

**Note:** A smoother 0–100% bar alone is lower value than elapsed + stage timings for network-bound scraping.

### Ops and quality ideas (2026-07-21)

Source: archive, "Future-Considerations Plan (2026-07-21)", items 4 to 10. None of these items has started.

#### Frontend E2E coverage for the audit area

**Why:** The pipeline start fix and profile state are exactly the kind of cross-system behavior that should be covered by Playwright.

- Add a Playwright spec that uploads a resume, waits for profile load, starts a pipeline, and asserts a run id is returned.
- Run the spec in CI against the local backend (`make dev` stack).

#### Dependency lock file

**Why:** Fresh installs currently resolve against `requirements.txt` ranges, which can drift between machines and CI runs.

- Generate `apps/backend-py/uv.lock` or `requirements-lock.txt` from a working environment.
- Update CI to install from the lock file in the test/lint jobs.
- Keep `requirements.txt` as the human-editable source of truth.

#### Re-enable shared services (Ollama / MLflow) as opt-in

**Why:** The audit removed the external `shared-services` network to make `docker compose up` work out of the box, but the shared-services pattern is still valuable for advanced users.

- Add an override file `docker-compose.shared-services.yml` that re-attaches backend to `shared-services` and disables the internal `mlflow` service.
- Document the two modes: standalone (default) and shared-services (advanced).

#### Health-check consolidation

**Why:** Health endpoints exist in FastAPI and Docker but are not exercised automatically.

- Add a lightweight `scripts/health-check.sh` that polls `/api/health`, `/api/jobs/sources`, and the frontend proxy until all return 200.
- Call it from `make dev` after startup and from CI as a final smoke step.

#### CI artifact retention

**Why:** CI uploads Playwright reports and screenshots but the retention policy and artifact names are basic.

- Add unique artifact names per run (e.g., `playwright-report-${{ github.run_id }}`) and a 7-day retention.
- Only upload screenshots on failure to keep artifact sizes small.

#### Documentation debt sweep

**Why:** Several docs still reference the Streamlit frontend or outdated project paths.

- Audit `docs/usage.md`, `docs/architecture.md`, `docs/troubleshooting.md`, and `DOCKER.md` for stale references to `frontend-py/`, `backend-py/`, or removed files.
- Update diagrams to the current Next.js + FastAPI + shared-services/standalone layout.

#### Observability basics

**Why:** The system has Sentry and MLflow hooks but no local tracing for debugging user-reported issues.

- Add structured request logging middleware in FastAPI with correlation IDs.
- Expose a `/api/health/details` endpoint with git commit, Python version, and dependency versions.
- Add a frontend error boundary report that captures the correlation ID.

### Appearance presets UX (Odysseus-inspired, Settings-housed)

**Status:** Roadmap only — keep themes inside Settings (not a separate Theme mini-window).

**Inspired by Odysseus (display / structure, not a clone):**
- Themes tab: grid of preset cards with 3 overlapping color swatches + name; clear selected border
- Customize tab (later): Colors (bg/panel/border/text/sidebar/accent), Color harmony (accent + complementary/etc.), Font & layout (font, density, optional frost), Reset / save-export optional

**Job Raider differences:**
- Live under Settings — Appearance (same place as cinematic), not a popped Theme window
- Curated Raid-branded catalog (include our own presets Odysseus does not have)
- Still remap CSS tokens via ``data-scheme`` (+ optional overrides later)

#### Preset catalog (curated)

| Preset | Status | Notes |
|--------|--------|-------|
| Raid (default) | Shipped | Current red ops look |
| Neon | Shipped | Cyan / magenta |
| Retrowave | Shipped | Hot pink / electric blue |
| Gunmetal | Shipped | Steel ops (ours) |
| Terminal | Shipped | Console green |
| Hackerman | Shipped | Black / neon-green matrix ops |
| Midnight | Shipped | Calm dark blue |
| Paper | Shipped | Light print-like |
| Forest | Shipped | Nature green |
| Ocean | Shipped | Teal / deep blue |
| Copper | Shipped | Warm metal |
| Stained glass | Shipped | Jewel gold / violet (token remap; frost later) |
| Skip / deprioritize | - | gpt, claude, cute, organs, lavender unless novelty pack wanted |

#### Phased checklist

- [x] Replace Appearance scheme Select with swatch-card grid (Raid / Neon / Retrowave first)
- [x] Add remaining curated presets (Gunmetal through Stained glass)
- [ ] Settings Appearance sub-tabs: Themes | Customize (Customize behind feature completeness)
- [ ] Customize: token color pickers writing CSS variables; Reset to preset
- [ ] Optional later: harmony generate, density, frost (cinematic already covers motion wash)
- [ ] Stained glass frost: optional backdrop-filter on cards/sidebar only

#### Review (2026-08-06)

- Curated catalog shipped: Raid, Neon, Retrowave, Gunmetal, Terminal, Hackerman, Midnight, Paper, Forest, Ocean, Copper, Stained glass.
- Light + dark CSS token packs via ``data-scheme``; Settings swatch-card grid (3–4 cols).
- Frontend CI (Node 20 Docker): lint, type-check, format, scheme tests (8), build passed.

### ScrapeGraphAI / LLM detail enricher (standby)

**Status:** Considerations captured; **not implementing yet**.

**Problem to solve (only):** empty LinkedIn (etc.) job descriptions after selector/JSON-LD enrich fails.

#### Coupling rules (required if ever built)

- [ ] `JobDetailEnricher` (or equivalent) port — not imports of scrapegraphai inside scrapers
- [ ] Fallback-only after CSS/JSON-LD; never default for every listing
- [ ] Soft/optional dependency; feature flag + per-run cap
- [ ] Keep `JobListing.description` contract for score/RAG/shortlist
- [ ] Leave JSearch and search-card scrape unchanged

#### Go / no-go before any PR

- [ ] Measured win on empty-JD rate vs current enrich
- [ ] Latency/VRAM acceptable under Ollama load
- [ ] Session/auth story clear (reuse Playwright context or document out of scope)
- [ ] Schema-constrained output (no invented fields)

#### Notes

See `docs/decision-log.md` (2026-08-05). Stars are not a go signal; loose coupling is the firebreak.

### Design backlog: Per-section model dropdowns (Settings = baseline) (2026-08-13)

**Status:** Pilot in progress (2026-08-13) — Cover Letter **writer** ModelSelect shipped for testing the waters. Session-only override; no Save-as-default; provider stays in Settings. Inventories: Anthropic + Gemini catalogs selectable when those providers are active; Ollama = installed tags only; foreign models greyed.

**Problem:** Model choice today is global via Settings ``routing[TaskType]``. Switching models to A/B a cover letter (or try a larger tag for one write) forces a Settings trip and risks changing behavior for resume parse, selection, review, etc.

**Goal:** Convenient, low-friction per-surface model choice without turning every page into a second Settings panel. Settings remains the single place for **provider** and **baseline model**; surfaces may override **model name only**. Learn from a narrow pilot before generalizing.

#### Layering (locked)

| Layer | Owns | Does not own |
|---|---|---|
| Settings | Provider per task (or tier defaults), baseline model, fallbacks, Ollama host, API keys | Per-request experimentation UI |
| Section dropdown | Model name for that surface’s TaskType(s), scoped to Settings provider | Provider switch, host, keys |
| Response | ``model_used`` (and provider if useful) for audit | Mutating saved settings |

**Provider stays in Settings only.** Changing Ollama ↔ Anthropic ↔ Gemini never happens from Cover Letter / Profile / Assessment. The dropdown reacts to whatever provider Settings already set for that ``TaskType``.

#### Dropdown UX (locked direction)

When Settings primary provider for the relevant task is **Anthropic** (example):

- **Selectable (normal):** Anthropic models in the known catalog for that provider.
- **Visible but disabled (grey):** models belonging to other providers (e.g. installed Ollama tags, Gemini IDs) — still listed so the user understands why they cannot pick ``qwen2.5:7b`` until Settings switches back.
- Same pattern for Gemini and Ollama: current-provider set is the allowlist; cross-provider entries are grey denylist, not omitted silently.

**After a Settings provider swap:**

1. Recompute allowlist for every open surface.
2. If the section override is no longer in the allowlist, **clear the override** and fall back to Settings baseline for that task.
3. Optional short hint: “Previous model unavailable for Anthropic — using Settings default.”

**Grey-list composition (mostly locked; size still open):**

- Foreign provider entries come from the **Anthropic** and **Gemini (GCP)** curated catalogs, plus **installed** Ollama tags only.
- **Still open:** grey = full foreign inventories vs only baselines / last-used (full is clearer; last-used is quieter).

#### Surface → TaskType mapping (efficiency)

Do **not** put one “LLM model” control on a page that runs multiple tasks. Wire dropdowns to ``TaskType``:

| Surface (pilot candidates) | Dropdown(s) | TaskType |
|---|---|---|
| Cover Letter | Writer | ``cover_letter_writing`` |
| Cover Letter (when review on) | Reviewer | ``cover_letter_review`` |
| Profile / resume upload | Parse | ``resume_parsing`` |
| Resume generation | Selection + Writing | ``selection``, ``resume_writing`` |
| Assessment | Gen / Eval | ``assessment_generation``, ``assessment_evaluation`` |

**Efficiency rules:**

- Default selection = Settings baseline for that TaskType (label: “Settings default (qwen2.5:7b)” or equivalent).
- One-click **Reset to Settings default** clears the override.
- Show current effective model near Generate (and keep ``model_used`` in results).
- Do not require opening Settings to confirm what will run.
- Only show a dropdown on surfaces where model choice actually changes outcomes users care about (start with Cover Letter writer ± reviewer). Background/pipeline tasks can stay Settings-only longer.

#### Override persistence (open — pick before implement)

| Option | Pros | Cons |
|---|---|---|
| **A. Session / tab only** (local React state or sessionStorage) | Safest; no surprise tomorrow | Lost on refresh |
| **B. Per-surface sticky** (localStorage, not backend settings) | Convenient for multi-day A/B | Can drift from Settings; must invalidate on provider change |
| **C. Persist into Settings routing** on every change | Single source of truth | Destroys “baseline vs experiment”; not recommended |

**Recommendation for pilot:** **A**, with optional promote control “Save as Settings default” that writes that TaskType’s ``primary_model`` only (provider unchanged).

#### API / router contract (when built)

- Request body optional ``model`` (or ``model_overrides: { task_type: model }``) for generate/validate/review endpoints that need it.
- Router: for that call only, if override is non-empty **and** allowed for the route’s ``primary_provider``, use it as ``primary_model``; else ignore and use Settings route.
- **Never** change saved Settings from a generate call unless the user explicitly hits “Save as default.”
- Reject or ignore cross-provider model names server-side (UI greying is not enough).
- Kind-A response cache keys must include the effective model so overrides do not return another model’s cached body.

#### Model inventories (locked 2026-08-13)

External providers for v1 are **only** Anthropic and Google (GCP / Gemini). No other cloud providers in the section dropdown.

| Provider (Settings) | Selectable models in section dropdown |
|---|---|
| **Anthropic** | Curated Anthropic console / API model IDs from Job Raider’s model catalog (``model_config.yaml`` / Settings models API ``anthropic`` list) — not free-text |
| **Gemini (GCP)** | Curated Google Gemini / GCP model IDs from the same catalog (``gemini`` list) — not free-text |
| **Ollama** | **Installed tags only** from live discovery (``ollama_installed`` via ``resolve_effective_ollama_host``). Do **not** offer YAML-catalogued Ollama names that are not actually pulled |

**Grey / disabled entries** when the Settings provider is e.g. Anthropic: show Gemini catalog models + currently installed Ollama tags as grey text (and vice versa). Do not invent uninstalled Ollama tags just to fill the grey list.

**Settings vs section (pilot stance):** For the experiment, only the **section dropdown** must follow the inventories above (Ollama = installed-only; Anthropic / Gemini = curated catalogs). Whether Settings’ own Ollama picker stays catalog∪installed or also goes installed-only is **deferred** — decide after the pilot. Do not block Cover Letter on Settings UI consistency.

Dropdown disabled or linked to Settings when the provider has no usable inventory (empty install list, missing API key, unreachable Ollama host).

#### Non-goals (v1)

- Per-page provider switcher.
- Free-text arbitrary model IDs.
- Overriding fallback provider/model from the section UI.
- Changing Ollama host or API keys from a feature page.
- Forcing every pipeline stage to expose a dropdown on day one.
- Offering uninstalled Ollama catalog entries as selectable (or as “available”) in the section UI.
- Adding Azure OpenAI / other clouds until explicitly productized.

#### Open questions (resolve before coding; OK to stay soft during pilot)

1. Session-only vs sticky localStorage for overrides? (**Lean A / session for pilot** so a failed experiment leaves no sticky mess.)
2. Grey list = foreign full catalogs + installed Ollama, or only baselines / last-used?
3. Cover Letter pilot: writer only, or writer + reviewer as two controls? (**Lean writer-only first.**)
4. Should “Save as Settings default” exist in v1 at all? (**Lean no for first pilot** — Settings remains the only way to change baseline.)
5. Writer override applies to review rewrite that reuses ``COVER_LETTER_WRITING``? (Yes if rewrite shares that TaskType.)
6. Align Settings Ollama picker with installed-only? (**Deferred** — not part of testing the waters.)

#### Suggested pilot order

1. [x] Ship the smallest Cover Letter **writer** ModelSelect + optional request ``writer_model`` override + router allowlist (inventories above).
2. Use it for a few real letters; note friction (grey list noise, wrong default, provider swap confusion).
3. Only then: reviewer dropdown, sticky persistence, Save-as-default, other surfaces, Settings picker alignment.
4. If the pattern feels wrong, remove the section control and keep Settings-only — low sunk cost by design.

#### Flow

```mermaid
flowchart TD
  Settings["Settings: provider + baseline model per TaskType"] --> Route["LLMRouter route for TaskType"]
  Surface["Section ModelSelect"] --> Override{"Override set and allowed for provider?"}
  Override -->|yes| Effective["Effective primary_model = override"]
  Override -->|no| Baseline["Effective = Settings baseline"]
  Route --> Override
  ProviderSwap["Settings provider change"] --> Invalidate["Clear illegal overrides"]
  Invalidate --> Baseline
  Effective --> Call["generate / review / parse"]
  Baseline --> Call
  Call --> Meta["Response model_used"]
```

**Priority:** Medium — UX quality / workflow efficiency; not blocking job-search use of current Settings routing.

### Design backlog: Learnings from SG Jobs Dashboard (2026-08-13)

**Note (2026-10-18):** Items 1 to 3 of the suggested order below have shipped: listing lifecycle v1, MyCareersFuture, Careers@Gov, and JobStreet Singapore. See the archive. Items 4 and 5 are still open.


**Status:** Future plan only — **do not start new job portals until the current LinkedIn / JSearch / Cover Letter / Profile stack is solid.** MyCareersFuture, Careers@Gov, and JobStreet are **important** next sources (not optional nice-to-haves), but they wait on current-state quality.

**Source (public, personal project):**
- Post: multi-portal SG scrape + resume scoring + ATS resume/cover letter + daily expire cleanup
- Dashboard: [JunRong19/SG-Jobs-Dashboard](https://github.com/JunRong19/SG-Jobs-Dashboard)
- Pipeline: [JunRong19/SG-Jobs-Scraper](https://github.com/JunRong19/SG-Jobs-Scraper)

**Do not copy their code.** Use the shape of the product as a checklist against Job Raider. Their stack (Supabase + LiteLLM + OpenAI) is not a migration target; Job Raider already has local Ollama routing, FastAPI, Next.js, and file-backed storage.

#### Overlap (Job Raider already covers)

| Their feature | Job Raider today |
|---|---|
| Scrape LinkedIn into one dashboard | LinkedIn + JSearch + manual paste |
| Score listings vs resume 0–100 | Score / rank + semantic re-rank + fit explain |
| Tailored resume + cover letter | Resume generation + Cover Letter (grounded) |
| Track applications | Applications dashboard + custom statuses |
| Next.js + Python | Same shape (frontend-ts + backend-py) |

#### Gaps worth learning from (priority order)

1. **Job lifecycle (highest product value, source-agnostic)**
   - Auto-expire stale listings (age / last-seen).
   - Recheck whether a posting is still live on the source URL.
   - Hide or bucket expired jobs instead of leaving dead cards in Jobs / Applications.
   - Their UI: buckets Total / Applied / In-progress / Not interested / Rejected / **Expired**, plus a **Scraped Today** toggle.
   - Job Raider has no listing `expired` / live-status pass today (`JobSource` is linkedin / jsearch / manual / other only).

2. **Singapore-local sources (important — after current state is solid)**
   - **Must consider (not optional):** MyCareersFuture, Careers@Gov, JobStreet.
   - These are first-class SG search channels that LinkedIn + JSearch do not fully cover (public sector, gov portal, Seek/JobStreet inventory).
   - Treat as new ``JobSource`` adapters behind the existing scraper manager, not a second dashboard.
   - **Constraint:** scraping may violate site ToS. Prefer official/public APIs where they exist (especially MyCareersFuture). Same legal caution Job Raider already takes on LinkedIn.
   - **Sequence lock:** do not add adapters until Discover, scoring, cover-letter grounding, profile parse, and listing hygiene on the current two sources feel reliable in daily use.

3. **Scheduled daily pipeline (ops, not UI)**
   - Their scripts: scrape → score → generate top-match docs → expire/delete inactive.
   - Job Raider pipeline is operator-triggered. A daily schedule (Discover + score + expire) would match “set and forget” without changing generation quality.
   - Keep generation on-demand unless we explicitly want auto-docs for top-N (cost / grounding review risk).

4. **Documents library**
   - One place for every generated resume and cover letter, with in-browser PDF preview.
   - Job Raider generates per job / Cover Letter page but does not present a global library of artefacts.

5. **Re-score after customizing a resume**
   - Their `score_jobs.py` re-scores jobs that already have a tailored resume.
   - Useful later: after generating a tailored resume, refresh fit score against that variant, not only the base profile.

#### Explicit non-goals (from this comparison)

- Replacing the LLM router with LiteLLM / locking to OpenAI.
- Moving storage to Supabase.
- Cloning their junior/entry-level-only filter as a hard default (Job Raider already has target-job + apprenticeship constraints).
- Auto-generating a resume PDF for every scrape hit (wasteful; keep generate-on-apply).

#### Suggested future order (when current state is solid)

0. **Now:** Perfect current sources and generation (LinkedIn, JSearch, manual paste, scoring, grounded cover letters, profile SoT, model-select pilot). No new portal work in this phase.
1. Listing lifecycle on **existing** listings: last-seen, expire, live URL check, Expired bucket + Scraped Today filter (pays off before new scrapers). **v1 done 2026-08-13:** catalog last-seen, age/deadline expire, Jobs hide-expired + Scraped today. **Applications Expired bucket done 2026-08-14.** Still open: live URL HEAD check (optional; ToS / flaky LinkedIn).
2. MyCareersFuture adapter (structured expiry; important SG inventory).
3. Careers@Gov and JobStreet adapters after MCF proves the pattern and ToS stance.
4. Documents library of generated artefacts.
5. Optional daily schedule wrapping existing pipeline stages.

#### Flow (target, not current)

```mermaid
flowchart TD
  Sources["LinkedIn JSearch plus future SG portals"] --> Scrape["Scheduled or manual scrape"]
  Scrape --> Dedupe["Deduplicate"]
  Dedupe --> Score["Score vs resume"]
  Score --> Live["Live URL / age expiry pass"]
  Live --> Dash["Jobs and Applications buckets"]
  Dash --> Gen["On-demand resume and cover letter"]
  Gen --> Lib["Documents library"]
```

**Priority:** Medium — those three SG boards matter for coverage, but **current-state quality is the gate**. Not blocking job search on LinkedIn/JSearch today.

### Jobs desk inspired by SupCareer (parked)

Preferred direction when Jobs UX is next opened. Not the next mandatory sprint.
Roadmap: `C:/Users/James/.cursor/plans/jobs_desk_future_073ad2df.plan.md`

**Grounding rule:** Prefer structured JD skill extractor output. Use description heuristics only when structured skills are empty, and always treat them as inferred. Never present heuristic skills with the same confidence as extractor-backed skills.

**Pause gate:** Pure UI/layout (Step A shell, pane chrome, nav clustering that only moves links) may proceed alone. Any work that changes cover-letter generate, JobMatcher/fit scoring, or skill extractor / JD skill claims requires a deliberate pause and re-approve before Step B or C starts (or before merge if exploration already began).

```mermaid
flowchart LR
  filters[Filters_and_status] --> list[Job_list]
  list --> detail[JD_detail_pane]
  detail --> actions[Apply_Generate_Fit]
  detail --> skills[Required_vs_Nice_skills]
```

#### When Jobs UX is next opened

- [ ] **Step A (UI-only):** Jobs master–detail shell + open-in-pane. No claim/fit/skill changes. May start without the pause gate.
- [ ] **Pause checkpoint:** Before Step B or C, stop for review if the work touches generate wiring, JobMatcher/fit, or skill extractor / claim presentation.
- [ ] **Step B:** Prefill Cover Letter / resume generate from the selected listing. Pause if any generator or matcher change goes beyond prefill handoff.
- [ ] **Step C:** Required / nice-to-have skill chips; inferred flag on heuristic fallback. Pause before extractor or fit-facing skill claims. Tests must cover the inferred path.
- [ ] **Step D:** Saved / Applied / Not applied + seniority chips. Reuse Applications state; pause if scoring changes.
- [ ] **Step E (UI-only):** Cluster analysis tools under secondary nav so primary stays Profile → Jobs → Applications → generate tools.

Each step is its own small PR with tests. Do not start Step A until Jobs UX work is explicitly opened.

**On first implementation:** Add a short decision-log entry: Jobs desk follows SupCareer-style master–detail and on-job actions; keep Job Raider grounding and local-first identity; inferred skills never share confidence with extractor skills.

**Existing hooks:** `apps/frontend-ts/src/app/jobs/page.tsx`; Applications tracker; Cover Letter paths + assess / explain fit APIs; `apps/backend-py/src/extractors/paste_job.py` and listing models.

**Out of scope to copy:** Purple consumer SaaS theming, Headshot, Premium upsell, Community chrome; shallow match CTAs that replace Pipeline / Metrics / grounding depth; three-pane layout on every page; heuristic JD skills shown as structured extraction facts.

**Related parked item (separate):** Fresh-grad assess routing (auto-detect via `career_stage` vs explicit UI/API toggle for `fresh_grad_mode`).

### Scam detector refinement — evolving outreach patterns (parked)

Not the next mandatory sprint. Keep as a living backlog because scam tactics change faster than static rules.

**Source cue (2026-09):** Field report of polished HR-impersonation after a real company apply: offer without interview, WhatsApp as easy contact, SMS follow-up on email. Company and copy looked legit; behaviour did not match real HR. Suspected job-portal CV harvest (email + phone + target role). Singapore retrenchment context raises seeker urgency.

**Gap vs current detector:** Listing `JobScamDetector` and cover-letter `_scan_scam_flags` already cover messaging apps, personal email, no-interview / immediate-hire, and weak grammar or fake company. They miss (1) offer / contract language without a hiring process, (2) legit company + AI-clean copy, (3) multi-channel chase after apply (email → WhatsApp → SMS), (4) portal data-exposure product questions.

#### When scam detection is next opened

- [ ] **Listing / assess flags (cheap):** Add patterns for offer-before-interview, contract / onboarding without assessment, and HR contact via WhatsApp/Telegram paired with urgency or “we received your application.” Keep results as flags to review, not a hard “employer is fake” verdict. Extend tests so new patterns do not regress.
- [ ] **Separate surface (later):** Optional screening or tips for inbound recruiter email/SMS (offer without interview, SMS chase, lookalike domains). Not a JD-only change.
- [ ] **Product / privacy note (later):** Document that portals can expose CV contact data; seeker guidance when saving or applying. Out of scope for regex scoring alone.
- [ ] **Review cadence:** Revisit indicator set when new field reports land; prefer small PRs and evaluation notebook updates over a big rewrite.

**Existing hooks:** `apps/backend-py/src/scoring/scam_detector.py`; cover-letter `_scan_scam_flags` in `apps/backend-py/src/api/routes/cover_letter.py`; pipeline `filter_scams`; `notebooks/scam_detector_evaluation.ipynb`.

**Do not start** until scam-detection work is explicitly opened. Prefer additive indicators and clearer seeker-facing copy over lowering the bar with noisy false positives.

#### Employer and recruiter verification (later)

- [ ] **Deterministic checks first:** Recruiter email domain vs official company domain, lookalike-domain detection (for example `companyx-careers.com`), domain age via WHOIS, and role present on the official careers page. Small Python checks; same answer every run.
- [ ] **Agent research layer (optional, on request only):** Evaluate DeerFlow (ByteDance, v2.0 rewrite released February 2026, built on LangGraph and LangChain) or a similar agent harness when it matures. Use cases: verify a specific employer or recruiter contact with cited sources, and periodic research on new scam tactics to propose indicators for human review.

**Agent layer rules:** Never run inside `filter_scams` or cover-letter assess (volume, latency, cost, and non-deterministic output). Findings show as sourced flags to review, never an automatic scam verdict. New indicators need human review before they enter `scam_detector.py`. Re-assess DeerFlow maturity, sandbox security (bash access), and local-model performance before any spike. Borrowing ideas (Markdown skills, isolated research sub-agents) without the framework is also an option.
