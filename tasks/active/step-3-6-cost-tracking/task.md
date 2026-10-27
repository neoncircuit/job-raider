# Task: Step 3.6, Real Cost and Usage Tracking

## Goal
Record every LLM call that goes through `LLMRouter` (task, provider, model, tokens, latency, cache hit, fallback, cost), give each pipeline run a cost summary in a file and in MLflow, and show real token counts on the Metrics page. This fixes review items M1 (the cost tracker is never called) and M8 (prices are hard-coded, out of date, and in more than one place).

## Constraints & Context
- Parent task: `tasks/active/step-3-measurable-claims/` (Step 3.6). The plan, the code observations, and the proposed decisions are in `notes.md`.
- The tests are deterministic and need no Ollama: they use fake clients. One real local run with Ollama is part of the review.
- Recording never makes an LLM call fail. A recording error is logged and the call result is returned.
- A call record has no prompt text and no response text, only counts, names, and times.
- Keep dry run as the default. Do not make auto-submit reachable.
- Do not add a cost claim to the README or the docs unless a recorded run supports it.
- One Cursor round, one Claude review, and at most one fix round (the stop rule in `notes.md`).

## Acceptance Criteria
- [x] A1. One price table: `config/model_config.yaml` holds the cloud prices, each provider with the source URL and the date the prices were checked. The three Python tables (`cost_tracker.py`, `claude_client.py`, `gemini_client.py`) read it or are removed. Gemini is a provider. A model that is not in the table has an unknown cost (`None`), not a cost of 0 under the provider "ollama".
- [x] A2. Real Ollama token counts: the client uses `prompt_eval_count` and `eval_count` from the `/api/chat` response. When they are missing, it uses the length estimate and marks the counts as estimated. No extra HTTP request is made for each message.
- [x] A3. One process-wide recorder: `LLMRouter.generate` and `generate_async` record each primary call, each fallback call (with the primary that failed), each cache hit, and each failed attempt, in one thread-safe tracker that every router instance shares. Unit tests for each path, with fake clients.
- [x] A4. Per-run summary: `PipelineOrchestrator.run` and `run_with_agents` open a run scope. Calls in that scope carry the run ID. At the end of the run, the summary goes to `data/metrics/cost_run_<id>.json` and to MLflow (fail open). Two runs at the same time do not mix their calls. Unit tests.
- [x] A5. Metrics API: `/metrics/costs` and `/metrics/summary` read the shared tracker and the last saved run summary. They report prompt, completion, and total tokens, and how many counts are estimated. `pipeline_runs` is a run count, not the call count. `cost_per_application` comes from data or is removed. Unit tests.
- [x] A6. Metrics page: it shows the token totals and the tokens of each recent call. Frontend unit tests and the E2E mock change with it.
- [x] A7. Docs: the README and `docs/` say what is recorded, with the command or the page to see it, and the limits (for example, embeddings are not recorded). No cost claim without a recorded run.
- [x] Review (Claude, 2026-10-27, in `notes.md`): diffs, mutation proofs, the local gate (backend and frontend), and a real check with Ollama through the router (run file and MLflow in a scratch store). Result: accept with one fix round for findings 1 to 7; A3 and A5 stay open for findings 1 and 2. A discover run makes no LLM calls, so the real pipeline run moves to "Done when": a full-mode dry run by the user.
- [x] Fix round (decision 9, the last round): findings 1 to 7 of the review, each with a test, and the mutation proofs (`handoff-fix.md`).
- [x] Check of the fix round (Claude, 2026-10-28, in `notes.md`). Result: accept; findings 1 to 7 fixed; 9 of 10 mutations caught. One residual (finding R1: a price value that is not a number can repeat a paid cloud call in the client) waits for the user's decision.
- [ ] Real pipeline run: one full-mode dry run from the Pipeline page by the user, with Ollama running. Claude checks the Metrics page, the run file, and the MLflow run. This also closes the Step 1 manual check.
- [ ] Done when: after a real pipeline run, the Metrics page shows real token counts, the run's cost summary is in MLflow, and no cost claim in the README is without recorded data.

## Status
`in-progress` (fix round checked on 2026-10-28; waiting for the user's decision on finding R1, then the user's full-mode dry run)
