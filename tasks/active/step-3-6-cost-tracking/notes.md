# Notes: Step 3.6, Real Cost and Usage Tracking

## Plan (2026-10-27, Claude)

```mermaid
flowchart LR
    C[Caller: stage, route, or CLI] --> R[LLMRouter.generate]
    R -->|cache hit| T[Shared cost tracker]
    R -->|primary call| T
    R -->|primary failed, fallback call| T
    O[Orchestrator run scope] -.->|run ID in a context variable| T
    T --> F["data/metrics/cost_run_ID.json"]
    T --> M[MLflow run for the pipeline run]
    T --> A["/metrics/costs and /metrics/summary"]
    F --> A
    A --> P[Metrics page]
```

### What a call record holds

| Field | Meaning |
|-------|---------|
| `timestamp` | When the call ended |
| `run_id` | The pipeline run ID, or empty for a call outside a run (for example a cover letter from its page) |
| `task_type` | The router task type value (`jd_extraction`, `cover_letter_writing`, ...) |
| `provider`, `model` | What served the call |
| `prompt_tokens`, `completion_tokens`, `total_tokens` | Token counts |
| `tokens_estimated` | True when the counts are a length estimate and not from the provider |
| `latency_ms` | Call time |
| `cache_hit` | True for a response cache hit (0 tokens, cost 0) |
| `fallback` | True when the primary failed and the fallback served the call |
| `error` | True for a failed attempt (0 tokens) |
| `cost_usd` | Cost from the price table; `None` when the model has no price |

No prompt text and no response text.

### Measure first

Today nothing is recorded, so the baseline is 0 records. The review checks the new numbers on one real run: the token counts from Ollama, the calls per stage, and the share of estimated counts.

## Observations (2026-10-27, Claude, code at `f629528`)

1. **No caller.** `CostTracker.track_call` (`src/metrics/cost_tracker.py:200`) has no caller outside the tests. `MLflowTracker.log_cost_summary` (`src/metrics/mlflow_tracker.py:222`) has no caller, and the pipeline does not use `MLflowTracker` at all.
2. **The Metrics page reads an empty tracker.** `src/api/routes/metrics.py:24` makes its own `CostTracker()`, and nothing writes to it. So the page always shows 0 calls. `/metrics/costs` returns the call count as `pipeline_runs` (line 48). `cost_per_application` is the constant 0.0 (`cost_tracker.py:340`).
3. **Many routers.** `create_router` or `LLMRouter(` is called 22 times in 12 files. Each caller has its own router. So the recorder must be one tracker for the process, not one tracker for each router. The router also has its own counters (`stats`, `router.py:905`), with a `_total_cost`.
4. **One path for generation.** Every generation call goes through `LLMRouter.generate` or `generate_async` (`router.py:647` and `:746`): the cache hit return (`:685`, `:783`), the primary call (`:689-703`), the fallback call (`:717-731`), and the error raise. Embeddings use `EmbeddingClient` directly (`src/api/routes/jobs.py:597`, `src/pipeline/stages.py:1128`), not the router.
5. **Four price tables (M8).** `cost_tracker.MODEL_PRICING` (`:81`), `claude_client.MODEL_PRICING` (`:32`), `gemini_client.MODEL_PRICING` (`:35`), and `cost_per_input` and `cost_per_output` in `config/model_config.yaml`. They do not agree: Claude Haiku 4.5 is 1.0 and 5.0 USD per million tokens in the tracker, and 0.8 and 4.0 in the client and the YAML. The tracker has no Gemini model and no Gemini provider. An unknown model gets the provider "ollama" and cost 0 (`cost_tracker.py:221-229`), so a Gemini call would count as a free local call. No price has a source or a date.
6. **Ollama token counts are estimates.** The client does not read `prompt_eval_count` and `eval_count` from the `/api/chat` response. It calls `/api/tokenize` one time for each message and one time for the reply, each with a 5 s timeout, and then uses length / 4 (`ollama_client.py:242-244` and `:328-342`). I do not know of an `/api/tokenize` endpoint in the Ollama API, so each call probably makes extra failed requests and then uses the estimate.
7. **Two task-type lists.** The router has 17 task types (`router.py:28`). The cost tracker has 6 (`cost_tracker.py:29`), with other names.
8. **Runs can overlap.** The API runs `orchestrator.run` in `asyncio.to_thread` (`src/api/routes/pipeline.py:250`), with no guard against a second run. `CostTracker.start_run` clears the call list (`cost_tracker.py:194`), so one shared tracker with `start_run` would delete the calls of the other run. `asyncio.to_thread` copies context variables into the worker thread, so a run ID in a context variable reaches the calls of that run.
9. **CLI runs are other processes.** `main.py:297` and `:393` run the pipeline in the CLI process. Its calls are not in the memory of the API process. Only a saved run file reaches the Metrics page.
10. **The Metrics page shows no tokens.** `apps/frontend-ts/src/app/metrics/page.tsx` shows cost, calls, the local share, and the 10 recent calls (task, provider, model, cost, time). The types are in `src/lib/types/api.ts:664`.
11. **The README has no cost number now.** The "80% cost reduction" claim is gone. `README.md:42` says that a local run has no per-token API cost. That is true for the default routes (all Ollama), but nothing measures it until this step.

## Decisions (2026-10-27)

The user accepted the plan and decisions 1 to 8 as written, and asked Claude to check the official prices before the handoff.

1. **Prices (M8).** The one price table is `config/model_config.yaml`, which already lists the allowed cloud models. Before the handoff, Claude reads the official Anthropic and Google pricing pages and writes the price of each catalog model with the URL and the date. The default routes are all Ollama (cost 0), so the cloud prices matter only for a cloud fallback or a cloud route that the user selects.
2. **Cache hit.** A cache hit is a call record with `cache_hit` true, 0 tokens, and cost 0. The cache hit rate is the cache hits divided by all records.
3. **Failed attempts.** A failed attempt is a record with `error` true and 0 tokens. Then the fallback count and the failure count are measured, not only the successes.
4. **Scope.** Only calls through `LLMRouter`. Embeddings stay out of scope and go to the limits in the docs. Local embeddings have no API cost.
5. **Storage.** In memory for the process (the last 1000 calls), and one JSON file for each pipeline run in `data/metrics/` (the existing `_save_run_summary` format, with the new fields). No database. The Metrics page shows the process totals since the backend started and the last saved run.
6. **MLflow.** One MLflow run for each pipeline run, in an experiment named `pipeline-runs`, made with `create_mlflow_tracker` as the eval reports do. It logs the calls, tokens, cache hit rate, fallback count, error count, cost, and the share of estimated counts, with the run ID, mode, and git SHA as tags. Fail open: an MLflow error is logged, and the pipeline result does not change.
7. **Task types.** The call record stores the router task type value. The 6-value enum in `cost_tracker.py` stays only if `get_cost_estimate` keeps a caller; today only the package exports use it.
8. **Stages and the real run.** One Cursor round in parts A1 to A7, with one commit each. Then the Claude review, then at most one fix round (stop rule). The real run in the review needs Ollama: Claude runs a short CLI run from WSL when Ollama answers there; if not, the user runs one from the Pipeline page.

9. **The fix round and the real run (accepted after the review, 2026-10-27).** The user accepted the review of the Step 3.6 round and its recommendations 1 and 2.
    - Cursor fixes findings 1 to 7 of the review in one round: `handoff-fix.md`. This is the last round that decision 8 permits. Finding 1 goes first, with its test before the code.
    - After the fix round and Claude's check, the user does one full-mode dry run from the Pipeline page with Ollama running. It closes the "Done when" item of this step and the open Step 1 manual check. Then Claude checks the Metrics page, the run file in `data/metrics/`, and the MLflow run, and closes Step 3.6.
    - What is still wrong after the fix round goes to the README limits.

### Price check (2026-10-27, Claude)

Standard (not batch) prices in USD per million tokens, from the official pages. The repository values are from `config/model_config.yaml`.

| Model | Input | Output | Repository now | Source |
|-------|------:|-------:|----------------|--------|
| `claude-sonnet-4-6` | 3.00 | 15.00 | 3.0 and 15.0 (correct) | Anthropic |
| `claude-opus-4-7` | 5.00 | 25.00 | 15.0 and 75.0 (wrong, the old Opus 4 and 4.1 price) | Anthropic |
| `claude-haiku-4-5-20251001` | 1.00 | 5.00 | 0.8 and 4.0 (wrong, the Haiku 3.5 price) | Anthropic |
| `gemini-2.5-flash` | 0.30 | 2.50 | 0.15 and 0.60 (wrong) | Google |
| `gemini-2.5-pro` | 1.25 (prompt of 200k tokens or less), 2.50 (more) | 10.00 (prompt of 200k tokens or less), 15.00 (more) | 1.25 and 10.0 (no tier) | Google |
| `gemini-2.0-flash` | not on the pricing page | not on the pricing page | 0.10 and 0.40 | Google deprecations page: deprecated, shutdown date 2026-06-01 (the earliest date) |

- Anthropic: `https://platform.claude.com/docs/en/about-claude/pricing` (read on 2026-10-27; the page shows no date). Prompt cache: a 5-minute cache write costs 1.25 times the base input price, and a cache hit costs 0.1 times the base input price. The client sends `cache_control: {"type": "ephemeral"}` (5 minutes) when the prompt cache setting is on (`claude_client.py:152`).
- Google: `https://ai.google.dev/gemini-api/docs/pricing` ("Last updated 2026-10-26 UTC"). The output price includes the thinking tokens. `https://ai.google.dev/gemini-api/docs/deprecations` ("Last updated 2026-10-22 UTC"): `gemini-2.0-flash` is deprecated, with the shutdown date 2026-06-01 and the replacement `gemini-3.6-flash`. The 2.5 models are not deprecated.

Results for the handoff (part of decision 1):

- Use the prices in the table. For `gemini-2.5-pro`, store both tiers and use the higher tier when the prompt has more than 200,000 tokens.
- Remove `gemini-2.0-flash` from the catalog, the Gemini client list, and their tests. It has no price and is past its shutdown date, so a call to it would fail. Do not add `gemini-3.6-flash` in this step (no route uses it, and adding a model is a separate decision).
- Two usage counts are missing today, so the cost is too low when they occur:
    - The Claude client reads only `input_tokens` and `output_tokens` (`claude_client.py:164-170`). With the prompt cache on, the API also returns `cache_creation_input_tokens` and `cache_read_input_tokens`. Record them and price them at 1.25 and 0.1 times the input price.
    - The Gemini client reads `prompt_token_count` and `candidates_token_count` (`gemini_client.py:170-189`). The 2.5 models also return `thoughts_token_count`, which Google bills as output. Count it in the completion tokens.

## Review of the Step 3.6 Round (2026-10-27, Claude, code at `d8b2f84`)

Result: accept the round with one fix round (the last one, decision 8). The recording, the run files, MLflow, the API, and the page work with real Ollama. One defect breaks the main rule of the handoff ("recording never breaks a call"), and four tests are missing.

### What I checked and found correct

- A1: `config/model_config.yaml` has the checked prices, `price_source`, and `price_checked`. The 200k tier for `gemini-2.5-pro` and the cache multipliers for Anthropic are there. `gemini-2.0-flash` is removed. The three Python price tables are gone; the clients keep their context sizes (`MODEL_CONTEXT`). The Claude client reads the cache tokens, and the Gemini client counts the thinking tokens.
- A2: the Ollama client reads `prompt_eval_count` and `eval_count`, and it makes no extra HTTP request.
- A3: the router records cache hits, primary calls, failed attempts, and fallback calls in one process-wide tracker with a lock. A record has no prompt or response text.
- A4: `cost_run_scope` uses a context variable. `run` writes the summary in a `finally` block, so a cancelled or failed run also writes it. The API passes its run ID, and the CLI passes a UUID. `close_run` frees the run's records.
- A5 and A6: the routes and the page show tokens, the share of estimated counts, the last run, and "unknown" for a cost with no price.
- A7: the README section, its Mermaid diagram, and its limits; the "no per-token API cost" sentences now say "by default".
- The gate: black, ruff, mypy gate (180 known, 0 new), pytest (1659 passed); frontend lint, type check, vitest (47 files, 253 tests), and Prettier on the changed files. Playwright did not start in WSL (Chromium missing), as Cursor said; CI runs it.

### Real check with Ollama (local, not a pipeline run)

Two calls through `LLMRouter` to `qwen2.5:3b` on the WSL Ollama (0.33.1), inside `cost_run_scope`. The run file and MLflow went to a scratch folder and a scratch MLflow store, not to `data/`.

| Item | Result |
|------|--------|
| Token counts | 41 prompt and 26 completion tokens for each call, from Ollama (`tokens_estimated` false). The old length estimate gave 13 prompt tokens for the same prompt, about one third of the real count. |
| Same prompt again | 41 prompt tokens again: on this Ollama version, the prompt cache does not lower `prompt_eval_count`. |
| Run file | `cost_run_review-real-check.json` with the 2 calls. |
| MLflow | One run in `pipeline-runs` with calls 2, prompt 82, completion 52, total 134, cost 0, and the run ID and mode tags. |
| API blocks | The process block and the last-run block show the same counts. |

A real pipeline run (the "Done when" item) is still to do. Only `stage_generate_resumes` calls the router in a pipeline run, so a discover-mode run records 0 calls. The run must be a full-mode dry run, which is also the open Step 1 manual check.

### Mutation proofs (Claude)

Each mutation was a fixed-string replace with a count of 1. The file checksum changed, and the restore matched the original checksum.

| Mutation | Result | Test that failed |
|----------|--------|------------------|
| K1 Ollama `prompt_eval_count` ignored | caught | `test_chat_response_counts_are_used` |
| K2 Claude cache read tokens ignored | caught | `test_claude_cache_tokens_are_priced` |
| K3 Gemini thinking tokens ignored | caught | `test_thinking_tokens_count_as_output` |
| K4 the 200k tier ignored | caught | `test_gemini_pro_uses_the_200k_tier` |
| K5 a fallback success is not flagged | caught | `test_primary_failure_and_fallback_success_are_two_records` |
| K6 the run scope is not reset | caught | `test_scope_sets_run_id_and_outside_has_none` |
| K7 the run's records are not freed (`close_run` not called) | **not caught** | none |
| K8 the recent-call limit is 10 | caught | `test_recent_call_limit_is_1000_and_totals_count_every_call` |
| K9 an unknown cost is not counted in the process totals | **not caught** | none |
| K10 `pipeline_runs` is the call count again | **not caught** | none |
| K11 the last run file is chosen by name, not by time | **not caught** | none |
| K12 an Ollama call has an unknown cost | caught | three tests |

Each mutation that was not caught changes behaviour: K7 keeps every finished run in memory; K9 shows a dollar total instead of "unknown"; K10 brings back the bug of observation 2; K11 shows a random run as the last run (the run IDs are UUIDs).

### Findings

1. **A price error breaks a call and repeats it on the fallback (high).** `_record_attempt` computes the price outside `_safe_record`, inside the `try` block of the primary call (`router.py:798` and the async copy). `get_model_price` raises `KeyError` when a catalog model has no `cost_per_input` or `cost_per_output` (`cost_tracker.py:108`). I proved it with fake clients: for a catalog model `claude-new-model` with no price fields, the primary call succeeded, the router recorded it as an error, called the Ollama fallback, and returned the fallback answer. A paid answer is lost, its cost is not recorded, and with no fallback the call raises. The test "a tracker that raises does not change the router result" passed because it makes `record_call` raise, which is inside `_safe_record`. Fix:
    - record after the client call, outside its `try` block, so that no recording error can start the fallback path;
    - put the price lookup and the cost calculation inside the safe wrapper;
    - `get_model_price` returns `None` (unknown cost) for a row with no price, and logs a warning.
    - Test: a price lookup that raises does not change the router result and does not call the fallback, in `generate` and in `generate_async`.
2. **Four test gaps (medium).** K7, K9, K10, and K11 above. Add a test for each: the run's records are freed after `run`; the process cost is unknown when one call has no price; `pipeline_runs` counts run files; the last run is the newest file by time, with names that sort the other way.
3. **The default run ID has 1-second resolution (low).** `run` and `run_with_agents` use `datetime.now().strftime("%Y%m%d_%H%M%S")` when no run ID is given. Two such runs in one second share their records and their file. The API and the CLI pass UUIDs, so only other callers are affected. Fix: a UUID.
4. **A late record makes a new run bucket (low).** `record_call` uses `setdefault` for the run ID, so a record that comes after `close_run` (for example from an asyncio task that the run started) makes a bucket that nothing frees. Fix: add a record to a run bucket only while the run is open.
5. **Test-only branches in production code (low).** `write_cost_run_summary` reads `PYTEST_CURRENT_TEST` to skip the file and MLflow. The default path is then not tested, and production code changes with a test runner variable. Fix: an autouse fixture in `tests/conftest.py` that points `_default_metrics_dir` to a temporary folder and replaces the MLflow logger, and no `PYTEST_CURRENT_TEST` check in `src/`.
6. **`api_usd` and `api_costs_usd` are always `None` (low).** The frontend does not read them. Compute them (the cost of the non-Ollama calls) or remove them.
7. **README limits (documentation).** Add: in a pipeline run, only resume generation (full mode) calls the LLM, so a discover-mode run records 0 calls; the process totals start at 0 when the backend starts again, and the last run comes from its file.

### Recommendations

1. **One fix round, the last one (needs the user's decision).** Findings 1 to 7 in one handoff for Cursor. Finding 1 first, with its test before the code.
2. **Then one full-mode dry run from the Pipeline page, by the user, with Ollama running.** It closes the "Done when" item of this step and the open Step 1 manual check together. Then Claude checks the Metrics page, the run file in `data/metrics/`, and the MLflow run, and closes Step 3.6.

## Blockers / Questions

- None. The fix round (decision 9, the last round) is with Cursor: `handoff-fix.md`. After it, the user does one full-mode dry run.
