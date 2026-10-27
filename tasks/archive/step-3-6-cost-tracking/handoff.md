# Handoff: Step 3.6, Real Cost and Usage Tracking (2026-10-27)

Read this file first. Then read, in this order:

1. `tasks/index.md` (the task system).
2. `tasks/todo.md`.
3. `task.md` and `notes.md` in this folder: all of `notes.md` (the plan, the call record, observations 1 to 11, decisions 1 to 8, and the price check).
4. `CLAUDE.md`.
5. These sections of `docs/lessons.md`:
    - "Prove that a mutation was applied with a fixed-string check, not the regex that applied it";
    - "A safety limit needs a test that checks the limit itself";
    - "Before you call a mutation "not caught", prove that it changes behaviour".
6. The code to follow for MLflow: `log_report_to_mlflow` in `apps/backend-py/src/evaluation/report.py:114` (reachability check, fail open, SQLite default store).

Do not read `tasks/archive/`.

Claude reviews this round with mutation proofs, the local gate, and one real pipeline run with Ollama.

## 1. Status

| Item | State |
|------|-------|
| `main` | Ahead of `origin/main` (not pushed). Do not push. |
| Decisions | 1 to 8 in `notes.md` are accepted. The prices in "Price check" are checked on the official pages (2026-10-27). Use them as written. |
| Ollama | Not needed for any test. Every test uses a fake client or a fake HTTP response. |
| This handoff | A1 to A7. **Stop after A7.** One round; the review can ask for one fix round. |

## 2. The task

```mermaid
flowchart LR
    A1[A1 one price table] --> A2[A2 Ollama counts]
    A2 --> A3[A3 recorder in the router]
    A3 --> A4[A4 run scope, file, MLflow]
    A4 --> A5[A5 metrics API]
    A5 --> A6[A6 Metrics page]
    A6 --> A7[A7 docs]
    A7 --> S[Stop: summary for the user]
```

**The rules that matter most:**

- **Recording never breaks a call.** Wrap each record in `try` and `except`, log a warning, and return the call result. A test proves this: a tracker that raises does not change the router result.
- **No text in a record.** A call record has counts, names, flags, and times only. No prompt, no response, no profile data.
- **One tracker for the process.** Every `LLMRouter` instance writes to the same tracker (observation 3). Do not give each router its own tracker.
- **Runs do not mix.** Two pipeline runs at the same time keep their calls apart (observation 8). Do not clear a shared list at the start of a run.
- **Tests first** for A3 and A4. Show that the new tests fail before the code.

There are seven commits (A1 to A7), then the results section of this file. Before each commit, run all the checks in section 5 that apply to the files of that part.

### A1. One price table (decision 1, the price check)

- `config/model_config.yaml` is the only price table. For each cloud provider, add `price_source` (the URL) and `price_checked` (`2026-10-27`). Set the prices from the table in `notes.md` "Price check":
    - `claude-opus-4-7`: 5.0 and 25.0. `claude-haiku-4-5-20251001`: 1.0 and 5.0. `claude-sonnet-4-6` stays 3.0 and 15.0.
    - `gemini-2.5-flash`: 0.30 and 2.50. `gemini-2.5-pro`: 1.25 and 10.0, and add the tier for a prompt of more than 200,000 tokens: 2.50 and 15.0.
    - Under `anthropic`, add the prompt cache multipliers from the same page: a cache write is 1.25 times the input price, and a cache read is 0.1 times the input price.
- Remove `gemini-2.0-flash` from the YAML catalog, from the Gemini client model list (`gemini_client.py:46` and `:65`), and from `tests/unit/test_gemini_client.py`. It is past its shutdown date. Do not add another model.
- One price function, for example `get_model_price(provider, model)` in `src/metrics/cost_tracker.py`, reads the YAML through the existing config loader. `ollama` always has cost 0. A cloud model that is not in the table returns `None`.
- Remove the Python tables `MODEL_PRICING` in `cost_tracker.py:81`, `claude_client.py:32`, and `gemini_client.py:35`. The clients' `estimate_cost` uses the price function. Keep the client context sizes where they are used (move them, do not lose them).
- `ModelProvider` gets `GEMINI`. A call is recorded with the provider that served it, never with a guessed provider.
- **Missing usage counts:**
    - The Claude client also reads `cache_creation_input_tokens` and `cache_read_input_tokens` when they are present, and the cost uses the multipliers.
    - The Gemini client counts `thoughts_token_count` in the completion tokens when it is present (Google bills it as output).
    - Add the fields that the clients need to `LLMResponse` (`src/llm/base.py:39`), for example `cache_read_tokens`, `cache_write_tokens`, and `tokens_estimated` (default `False`).
- Tests: each price from the YAML; the 200k tier; the cache multipliers; an unknown cloud model gives `None`; an Ollama model gives 0; the thinking tokens count as output.

Commit A1: `fix(llm): one dated price table and complete cloud usage counts`.

### A2. Ollama token counts (observation 6)

- In `ollama_client.py:242-244`, use `prompt_eval_count` and `eval_count` from the `/api/chat` response. When a value is missing, use the length estimate (characters / 4) for that value and set `tokens_estimated` to `True`.
- Remove the `/api/tokenize` request from the generation path. `count_tokens` can keep it for other callers, but no generation call may make an extra HTTP request for each message.
- Tests with a fake HTTP response: the counts from the response; the estimate and the flag when the counts are missing; the number of HTTP requests for one generation call is 1.

Commit A2: `fix(llm): read Ollama token counts from the chat response`.

### A3. The recorder in the router (decisions 2, 3, 5, and 7)

Write the tests first in `tests/unit/test_cost_recording.py`, with fake clients. Show that they fail.

- **The tracker:** a process-wide, thread-safe tracker in `src/metrics/cost_tracker.py`, for example `get_cost_tracker()`. It keeps:
    - the last 1000 call records (decision 5);
    - totals since the process started (calls, prompt, completion, and total tokens, estimated counts, cache hits, fallbacks, errors, and cost);
    - the records of each open run, until that run's summary is written (A4). A run summary counts every call of the run, also when the run has more than 1000 calls.
- **The call record** has the fields in `notes.md` "What a call record holds". `task_type` is the router task type value as a string (decision 7). `cost_usd` comes from the A1 price function, and it is `None` when the price is unknown.
- **The router** (`router.py:647` and `:746`) records:
    - a cache hit: `cache_hit` true, 0 tokens, cost 0 (decision 2);
    - a primary success;
    - a primary failure: `error` true, 0 tokens (decision 3), then the fallback call, if one is set;
    - a fallback success: `fallback` true, with the provider and the model that served it;
    - a fallback failure: `error` true.
- The router measures `latency_ms` around the client call, so that it is the same for every provider.
- `CostTracker.start_run` must not clear the shared records. Change it or remove it.
- The 6-value `TaskType` in `cost_tracker.py` stays only if `get_cost_estimate` keeps a caller (decision 7). Search first, and say in the summary what you did.
- Tests:
    - one primary call is recorded one time, with its tokens, provider, model, and cost;
    - a cache hit is recorded as a cache hit with 0 tokens;
    - a primary failure and a fallback success give two records (one error, one fallback);
    - two router instances write to the same tracker;
    - `generate_async` records the same as `generate`;
    - a tracker that raises does not change the router result;
    - a record has no prompt or response text;
    - the recent-call limit is 1000, and the totals still count every call.

Commit A3: `feat(metrics): record every router call in one process-wide tracker`.

### A4. Run scope, run file, and MLflow (decisions 5 and 6)

Write the tests first. Show that they fail.

- **Run scope:** a context manager, for example `cost_run_scope(run_id)`, that sets the run ID in a `contextvars.ContextVar`. The tracker reads it for each record. `asyncio.to_thread` copies context variables, so the calls in the API worker thread get the run ID (observation 8).
- **The orchestrator:** `PipelineOrchestrator.run` and `run_with_agents` get an optional `run_id` argument. The API passes its pipeline run ID (`src/api/routes/pipeline.py:165`). The CLI (`main.py:303` and `:398`) gets a generated ID. The stage loop runs inside the run scope. A cancelled run and a failed run also write their summary.
- **At the end of each run:**
    - write `data/metrics/cost_run_<run_id>.json` (the existing `_save_run_summary` format, with the new fields: tokens by type, estimated counts, cache hits, fallbacks, errors, and the calls of the run);
    - put a short cost summary in `PipelineResult.metadata["cost"]`;
    - log the summary to MLflow: one MLflow run in the experiment `pipeline-runs`, in the same way as `log_report_to_mlflow` (reachability check, the SQLite default store). Metrics: calls, prompt, completion, and total tokens, estimated share, cache hit rate, fallback count, error count, and cost (skip a metric whose value is `None`). Tags: the run ID, the mode, and the git SHA.
    - **Fail open:** an MLflow error or a file error is logged. The pipeline result does not change.
- Tests:
    - the calls inside a scope carry its run ID, and a call outside every scope has none;
    - two scopes in two threads at the same time keep their calls apart;
    - a run file is written with the run's calls only;
    - a cancelled run writes its file;
    - MLflow is called one time with the expected metrics (use a fake tracker factory), and an MLflow error does not change the pipeline result.

Commit A4: `feat(pipeline): write a cost summary for each run to a file and MLflow`.

### A5. Metrics API (observation 2)

- `src/api/routes/metrics.py` uses the shared tracker (remove the local `CostTracker()` at line 24) and the last saved run file (observation 9: a CLI run is another process).
- `/metrics/costs` and `/metrics/summary` report, for the process since it started and for the last run:
    - calls, prompt tokens, completion tokens, total tokens, and the number of calls with estimated counts;
    - cache hits, fallbacks, errors, and cost (`None` when a call had no price; say "unknown", not 0);
    - the local share of calls.
- `pipeline_runs` is the number of saved run files, not the call count.
- `cost_per_application`: compute it from data (cost of the last run divided by the jobs that got a document in it) or remove it. Say in the summary which one, and why.
- `recent_calls` gets the token counts, `tokens_estimated`, `cache_hit`, `fallback`, and `error`.
- Change the response models in `src/api/models/responses.py` and the tests in `tests/unit/test_metrics_api.py`. Keep the existing keys that the frontend reads, or change the frontend in A6 in the same way.

Commit A5: `feat(api): report real tokens and the last run on the metrics routes`.

### A6. Metrics page

- `apps/frontend-ts/src/app/metrics/page.tsx`: show the total tokens (prompt and completion), the share of estimated counts, and the last run (run ID, time, calls, tokens). The recent-calls table gets a tokens column, and it marks cache hits, fallbacks, and errors.
- Change the types (`src/lib/types/api.ts:664`), the E2E mock (`tests/e2e/support/mock-api.ts:143`), and add or change a unit test for the page under `tests/app/metrics/`.
- Show an unknown cost as "unknown", not as $0.00.
- Keep the page layout and style. Do not add a new chart.

Commit A6: `feat(frontend): show real token counts on the Metrics page`.

### A7. Docs

- `README.md`: one short section or a few sentences on what is recorded (each router call: tokens, latency, cache hit, fallback, error, cost), where to see it (the Metrics page, `data/metrics/cost_run_<id>.json`, and the MLflow experiment `pipeline-runs`), and the limits:
    - embeddings are not recorded (decision 4);
    - Ollama counts come from Ollama, and the page marks the counts that are estimates;
    - cloud prices are from the official pages on 2026-10-27 and can change.
- `README.md:42` and the same sentence in `docs/index.md:68` and `docs/architecture.md:261`: keep "no per-token API cost" only for the default local routes, and say that the Metrics page shows the recorded cost.
- Do not add a cost number. The review run gives the first real numbers.
- A Mermaid diagram of the recording flow in the README section (you can use the one in `notes.md`).
- Write in ASD-STE100, with no emojis. Do not link to `tasks/`.

Commit A7: `docs: state what the cost tracker records and its limits`.

## 3. Traps

- **Do not change routing.** Which provider and model serve a task stays the same. This step records calls; it does not change them.
- **The response cache stays the same.** `CACHEABLE_TASK_TYPES` and the cache keys do not change. A cache hit is only recorded.
- **The router `stats` counters** (`router.py:905`) can stay. Do not remove a key that a route or a test reads.
- **Module state in tests.** The tracker is process-wide, so each test must start from an empty tracker (a fixture that resets it). Do not let one test see the calls of another test.
- **Paths.** `CostTracker(storage_dir="data/metrics")` is relative to the working directory. Make the run file path absolute under `apps/backend-py/data/metrics/`, in the same way as the other data paths, and use a temporary folder in tests.
- **MLflow in tests.** No test may write to `data/mlflow.db`. Use a fake tracker factory.
- **No real data and no secrets.** Never open `.env`, `.env.local`, or `apps/backend-py/data/settings/user_settings.json`. Do not run the pipeline against the real profile.
- **Startup time.** `main.py` takes about 100 s to start on `/mnt/d`, and the full backend suite takes 3 to 8 minutes. Run long commands in the background. `pytest.ini` has `--maxfail=5`.
- **Line endings and scratch files.**
    - The IDE keeps rewriting 14 cover-letter, profile, and frontend files with CRLF (no content change). Do not commit them.
    - Check `git ls-files --eol` before each commit, and stage only the files of that part.
    - Put scratch files and commit messages outside the repository, and use `git commit -F <file>`.

## 4. Summary to leave for the user

At the end of this file, add "Cursor results (date)" with:

- The commits (hash and subject).
- For each part (A1 to A7): what changed, the files, and the test names. For A3 and A4, the failure output of the new tests before the code.
- A1: the price table as it is now, and every place that read the old tables.
- What you did with `start_run`, the 6-value `TaskType`, and `cost_per_application`, and why.
- Mutation proofs, each a fixed-string replacement with the checksum before and after, the count of the new string, the failing test, and a restore that matches the backup. At least these:
    1. the router does not record a cache hit;
    2. the router does not record a failed primary;
    3. the tracker clears the shared records at the start of a run;
    4. the run ID is not read from the context variable;
    5. an unknown cloud model gets cost 0;
    6. the Ollama client ignores `eval_count`;
    7. a recording error is not caught.
- Anything that you think is wrong in this plan.
- Every check that you ran and its result. Say clearly what you did not run. A real pipeline run with Ollama must be in the "not run" list (Claude does it in the review).

## 5. Checks

Backend (WSL, from `apps/backend-py`):

Check formatting (the CI paths plus the catalog script):

```bash
.venv/bin/python -m black --check main.py scripts/mypy_gate.py scripts/prepare_dedupe_catalog_pairs.py src/ tests/
```

Run the linter (the CI paths plus the catalog script):

```bash
.venv/bin/python -m ruff check main.py scripts/mypy_gate.py scripts/prepare_dedupe_catalog_pairs.py src/ tests/
```

Run the mypy baseline gate:

```bash
.venv/bin/python scripts/mypy_gate.py
```

Run the tests:

```bash
.venv/bin/python -m pytest tests/ -q
```

Frontend (WSL, from `apps/frontend-ts`, for A5 and A6). Use Node 24 (`.nvmrc`); the WSL default can still be Node 20.

Select Node 24:

```bash
nvm use 24
```

Run the linter:

```bash
npm run lint
```

Check the types:

```bash
npm run type-check
```

Run the unit tests:

```bash
npx vitest run
```

Check the formatting of the files that you changed (the whole tree has pre-existing CRLF files):

```bash
npx prettier --check src/app/metrics/page.tsx src/lib/types/api.ts tests/e2e/support/mock-api.ts
```

Run the E2E tests (if Playwright does not start in WSL, say so in the summary; CI runs them):

```bash
npm run test:e2e
```

## 6. Rules (unchanged)

- Follow `CLAUDE.md`:
    - docstrings with description, arguments, and returns;
    - type hints;
    - ASD-STE100 for documentation;
    - no emojis;
    - a Mermaid diagram in documentation.
- Before each commit, run `git status --short` and stage only the files of that part.
- Never run `scripts/mypy_gate.py --update` to accept a new error.
- Keep dry run as the default. Do not make auto-submit reachable.
- Do not push. Push only from WSL, and only after the user approves.

## Cursor results (2026-10-27)

### Commits

| Hash | Subject |
|------|---------|
| `b242e4a` | fix(llm): one dated price table and complete cloud usage counts |
| `4c96736` | fix(llm): read Ollama token counts from the chat response |
| `d48a0c7` | feat(metrics): record every router call in one process-wide tracker |
| `81afe6b` | feat(pipeline): write a cost summary for each run to a file and MLflow |
| `4a06765` | feat(api): report real tokens and the last run on the metrics routes |
| `3c20add` | feat(frontend): show real token counts on the Metrics page |
| `d8b2f84` | docs: state what the cost tracker records and its limits |

Not pushed.

### A1. One price table

What changed: `config/model_config.yaml` is the only price table. Anthropic and Gemini rows have `price_source` and `price_checked` `2026-10-27`. Opus is 5.0/25.0, Haiku is 1.0/5.0, Sonnet stays 3.0/15.0. Flash is 0.30/2.50. Pro is 1.25/10.0 and 2.50/15.0 above 200,000 prompt tokens. Anthropic cache write 1.25x and cache read 0.1x. `gemini-2.0-flash` is removed. `get_model_price` / `calculate_usage_cost` read the YAML through `ConfigLoader` (lazy import, to avoid a load-time cycle with settings). Ollama is always 0. An unknown cloud model returns `None`. Claude reads cache write/read tokens. Gemini adds `thoughts_token_count` to completion tokens. `LLMResponse` has `cache_read_tokens`, `cache_write_tokens`, and `tokens_estimated`. Client `MODEL_PRICING` tables are now `MODEL_CONTEXT` (context windows only). `ModelProvider.GEMINI` exists.

Price table now (USD per million tokens):

| Model | Input | Output |
|-------|------:|-------:|
| `claude-sonnet-4-6` | 3.0 | 15.0 |
| `claude-opus-4-7` | 5.0 | 25.0 |
| `claude-haiku-4-5-20251001` | 1.0 | 5.0 |
| `gemini-2.5-flash` | 0.30 | 2.50 |
| `gemini-2.5-pro` | 1.25 (prompt 200k or less), 2.50 (more) | 10.0 / 15.0 |

Places that read the old Python tables: `cost_tracker.MODEL_PRICING` (removed), `claude_client.MODEL_PRICING` (moved to `MODEL_CONTEXT`), `gemini_client.MODEL_PRICING` (moved to `MODEL_CONTEXT`). Client `estimate_cost` and the tracker use `get_model_price`.

Files: `apps/backend-py/config/model_config.yaml`, `src/metrics/cost_tracker.py`, `src/metrics/__init__.py`, `src/llm/base.py`, `src/llm/claude_client.py`, `src/llm/gemini_client.py`, `tests/unit/test_model_pricing.py`, `tests/unit/test_gemini_client.py`.

Tests: `test_yaml_prices_for_each_catalog_model`, `test_gemini_pro_uses_the_200k_tier`, `test_anthropic_cache_multipliers`, `test_unknown_cloud_model_has_no_price`, `test_ollama_model_has_zero_cost`, `test_claude_cache_tokens_are_priced`, `test_thinking_tokens_count_as_output`, `test_estimate_cost_known_model`. Backend gate: 1641 passed.

### A2. Ollama token counts

What changed: generation reads `prompt_eval_count` and `eval_count` from `/api/chat`. A missing value uses characters / 4 and sets `tokens_estimated`. Generation does not call `/api/tokenize`. `count_tokens` still may.

Files: `src/llm/ollama_client.py`, `tests/unit/test_ollama_token_counts.py`.

Tests: `test_chat_response_counts_are_used`, `test_missing_counts_use_length_estimate`, `test_one_generation_makes_one_http_request`. Backend gate: 1644 passed.

### A3. Process-wide recorder

What changed: `get_cost_tracker()` is one process-wide, thread-safe tracker. It keeps the last 1000 records, process totals, and per-run lists until `close_run`. `CallRecord` has the fields from the notes (no prompt or response text). The router records cache hits (0 tokens, cost 0), primary success, primary failure (error, 0 tokens), fallback success (`fallback` true), and fallback failure. Latency is measured around the client call. `_safe_record` swallows tracker errors. `CostTracker.start_run` no longer clears `_calls`.

`get_cost_estimate` / 6-value `TaskType`: searched first. The only caller is `tests/unit/test_metrics.py` (plus the package export). There is no production caller. Both stay, because decision 7 keeps them when `get_cost_estimate` has a caller.

Files: `src/metrics/cost_tracker.py`, `src/metrics/__init__.py`, `src/llm/router.py`, `tests/unit/test_cost_recording.py`.

Tests (written first): `test_primary_call_is_recorded_once`, `test_cache_hit_is_recorded_with_zero_tokens`, `test_primary_failure_and_fallback_success_are_two_records`, `test_two_router_instances_share_one_tracker`, `test_generate_async_records_the_same`, `test_recording_error_does_not_change_router_result`, `test_record_has_no_prompt_or_response_text`, `test_recent_call_limit_is_1000_and_totals_count_every_call`.

A3 tests before the code (collection error):

```
ImportError: cannot import name 'get_cost_tracker' from 'src.metrics.cost_tracker'
ERROR tests/unit/test_cost_recording.py
```

Backend gate: 1652 passed.

### A4. Run scope, file, MLflow

What changed: `cost_run_scope(run_id)` sets a `ContextVar`. The tracker reads it on each record. `PipelineOrchestrator.run` and `run_with_agents` take optional `run_id`. The stage loop runs inside the scope. A cancelled or failed run still writes the summary. The API passes its pipeline run ID. The CLI generates a UUID. The file is `apps/backend-py/data/metrics/cost_run_<id>.json` (absolute default). `PipelineResult.metadata["cost"]` holds the summary. MLflow experiment `pipeline-runs` uses the same fail-open path as `log_report_to_mlflow`. Tests do not write `data/mlflow.db` (no factory and `PYTEST_CURRENT_TEST` skips file and MLflow unless the test passes a folder or factory).

Files: `src/metrics/cost_tracker.py`, `src/pipeline/orchestrator.py`, `src/api/routes/pipeline.py`, `main.py`, `tests/unit/test_cost_run_scope.py`, `tests/unit/test_cli.py`, `tests/unit/test_pipeline_run_async.py`.

Tests (written first): `test_scope_sets_run_id_and_outside_has_none`, `test_two_threads_keep_run_ids_apart`, `test_run_file_contains_only_that_run`, `test_cancelled_run_writes_its_file`, `test_mlflow_called_once_and_error_is_fail_open`, `test_orchestrator_mlflow_error_does_not_change_result`.

A4 tests before the code (collection error):

```
ImportError: cannot import name 'cost_run_scope' from 'src.metrics.cost_tracker'
ERROR tests/unit/test_cost_run_scope.py
```

Backend gate: 1658 passed.

### A5. Metrics API

What changed: `/metrics/costs` and `/metrics/summary` use `get_cost_tracker()` and the last saved run file. They report process totals and last-run tokens, estimated counts, cache hits, fallbacks, errors, cost (`None` when unknown), and local share. `pipeline_runs` is the number of `cost_run_*.json` files. `recent_calls` includes token counts and flags.

`cost_per_application`: computed from the last run (last-run cost divided by `resumes_generated` / `documents` on that run). It is `None` when the last run has no document count or an unknown cost. Not removed, because the last-run file already stores `documents`.

Files: `src/api/routes/metrics.py`, `src/api/models/responses.py`, `src/metrics/cost_tracker.py`, `src/metrics/__init__.py`, `tests/unit/test_metrics_api.py`.

Tests: existing route tests plus `test_summary_recent_calls_include_token_flags`. Backend gate: 1659 passed.

### A6. Metrics page

What changed: the Metrics page shows total tokens, prompt/completion, estimated share, and the last run (run ID, time, calls, tokens). The recent-calls table has a tokens column and marks cache hits, fallbacks, errors, and estimates. Unknown cost renders as "unknown". Dashboard cost tiles use the same rule so types stay valid. No new chart.

Files: `apps/frontend-ts/src/app/metrics/page.tsx`, `src/lib/types/api.ts`, `src/app/dashboard/page.tsx`, `tests/e2e/support/mock-api.ts`, `tests/app/metrics/page.test.tsx`.

Tests: `tests/app/metrics/page.test.tsx` ("shows token counts, last run, and unknown cost"). Frontend: lint pass, `tsc --noEmit` pass, vitest 47 files / 253 passed.

### A7. Docs

What changed: README has a Cost and usage tracking section (what is recorded, where to see it, limits, mermaid). The "no per-token API cost" sentence in README, `docs/index.md`, and `docs/architecture.md` now applies only to default local routes, and says the Metrics page shows the recorded cost. No cost number. No link to `tasks/`.

Files: `README.md`, `docs/index.md`, `docs/architecture.md`.

### start_run, TaskType, cost_per_application

- **`start_run`:** left on the old `CostTracker` for existing unit tests. It no longer clears `_calls`. The process tracker uses `open_run` / `close_run` and does not clear the shared recent list.
- **6-value `TaskType`:** kept, because `get_cost_estimate` still has a caller (`test_metrics.py`). Router records use the router task type string.
- **`cost_per_application`:** computed from last-run cost / documents (`resumes_generated`). `None` when that ratio cannot be formed. Not a constant 0.

### Mutation proofs

Each proof used an exact-string replacement, SHA-256 before and after, a fixed-string count, the named test, and `git checkout -- <file>` so the restore hash matched HEAD.

1. **Router does not record a cache hit.** File `src/llm/router.py`. Removed both `self._record_attempt(..., cache_hit=True)` blocks (2). `cache_hit=True` count 2 → 0. SHA-256 before `32330c5b39cdb78552df8925e9f8c96e6e1794a21f234adab5e02c6542d5410e`, after `70d89b5c2bbbf4c6b61078d9b4ffe7ae3301f2104ef5615e7181ab3cf91e5256`. Failed `test_cache_hit_is_recorded_with_zero_tokens` (`assert 1 == 2`). Restore matched before.

2. **Router does not record a failed primary.** File `src/llm/router.py`. Replaced both `self._record_attempt(..., error=True)` primary lines (2) with `pass`. That string count 2 → 0. SHA-256 after `7b1f557230472ae2b2494bae925d033ab999492170d70d1c684acd0ff26d946e`. Failed `test_primary_failure_and_fallback_success_are_two_records` (`assert 1 == 2`). Restore `32330c5b...`.

3. **Tracker clears shared records at the start of a run.** File `src/metrics/cost_tracker.py`. In `open_run`, added `_recent.clear()` and `_run_calls.clear()`. SHA-256 HEAD `81a4fb4527eb26bf3f16d4801c472d0df97dbd356e22d8731257fe0e3052b178`, after `99f9c15c0b0eb294b8af1ec67086f3a8645a51f7c95ddc57aa688a0b1e6ff2f0`. Failed `test_run_file_contains_only_that_run` (`len([]) == 0` vs 1). Restore matched HEAD.

4. **Run ID is not read from the context variable.** File `src/metrics/cost_tracker.py`. Replaced `resolved_run = run_id if run_id is not None else (_cost_run_id.get() or "")` with `resolved_run = run_id or ""`. SHA-256 after `760e6cbf4f3a6f39c6994c204920f519c21e6a3acd85c5ce8f964eff90199f09`. Failed `test_scope_sets_run_id_and_outside_has_none` (`'' == 'run-inside'`). Restore matched HEAD.

5. **Unknown cloud model gets cost 0.** File `src/metrics/cost_tracker.py`. `if not model_cfg: return None` became `return ModelPrice(0.0, 0.0)`. New string count 2 (Ollama already returned a zero price). SHA-256 after `0aa1c9aa35c337ee2b07909dcef0d60add8eb7174af61e222db9cfbce72303eb`. Failed `test_unknown_cloud_model_has_no_price` (got a `ModelPrice`, not `None`). Restore matched HEAD.

6. **Ollama client ignores `eval_count`.** File `src/llm/ollama_client.py`. `eval_raw = data.get("eval_count")` → `eval_raw = None`. New string count 1. SHA-256 HEAD `76ef79caa9d9836803eaf3adee777c58fd2aac5d5832f902c502ff1455e7a1ae`, after `8ea3c3535b4a4e1715aeb7fad4b895fe762fcd38ed731d76e194a715eba73252`. Failed `test_chat_response_counts_are_used` (`completion_tokens` 0 == 7). Restore matched HEAD.

7. **A recording error is not caught.** File `src/llm/router.py`. Removed the `try` / `except` around `record_call`. SHA-256 after `2aa4a969cdd25d27ec057f26ed452cd5ca6349378085ff1ff55fd71e1d6bad34`. Failed `test_recording_error_does_not_change_router_result` (`RuntimeError: tracker down`). Restore `32330c5b...`.

### Plan notes

- `get_model_price` uses `ConfigLoader.load_model_config` via a lazy import. A top-level import of `ConfigLoader` would pull `UserSettings` at tracker import time.
- Tests skip the default metrics file and default MLflow log when `PYTEST_CURRENT_TEST` is set and the caller did not pass a folder or factory. That keeps `data/mlflow.db` clean. Production still writes the absolute metrics folder and logs to the SQLite default store.
- A3/A4 "tests first" failed at collection (`ImportError`) before the symbols existed. That is a fail, but it is not an assertion failure.
- `cost_per_application` uses `resumes_generated` only. Cover letters that are not counted there will not enter the ratio.

### Checks

Ran (WSL, `apps/backend-py` unless noted):

- `black --check` and `ruff check` on the CI paths, before each backend commit: pass.
- `scripts/mypy_gate.py` before each backend commit: pass (A1 needed `response.text or ""` in the Gemini client).
- `pytest tests/ -q` before each backend commit: 1641 (A1), 1644 (A2), 1652 (A3), 1658 (A4), 1659 (A5).
- Frontend A6 (`nvm use 24`): `npm run lint` pass, `npm run type-check` pass, `npx vitest run` 253 passed, `npx prettier --check` on the changed files pass.

Not run:

- A real pipeline run with Ollama (Claude does this in the review).
- Playwright E2E: `npm run test:e2e` started the Next server, then failed because Chromium is not installed at `/home/jamestjy/.cache/ms-playwright/chromium_headless_shell-1223/...`. CI runs these.
- No read of `.env`, `.env.local`, or `user_settings.json`.
- `data/dedupe_catalog/` was not opened.
