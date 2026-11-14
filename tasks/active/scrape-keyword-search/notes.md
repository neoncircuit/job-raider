# Notes: scrape-keyword-search

Planned 2026-11-14 after the test run run_d6a88288 scraped 0 jobs. Review section to be added when the task is done.

## Diagnosis (2026-11-14)

- Test run `run_d6a88288…`: 0 scraped; all stages done within 1 s; the resource recorder (every 10 s, 08:36 to 09:10) showed no Ollama model loaded at any time.
- Direct calls: MyCareersFuture "Backend Developer" 18 jobs; the three keywords together 0. `mycareersfuture_scraper.py`, `jobstreet_scraper.py`, `jsearch_scraper.py`, and `linkedin_scraper.py` build one query with `" ".join(params.keywords)`; `careersatgov_scraper.py` keeps rows that contain every keyword.
- Claude first read 5 results for the three keywords; that was a script error (it listed the 5 fields of the collection object). The real count was 0.

## Build and checks (2026-11-14, scratch clone)

- `scrapers/manager.py`: `keyword_searches(params)` (one search per phrase, blanks and repeats dropped, limit shared with a minimum of `MIN_RESULTS_PER_KEYWORD = 10`; one phrase keeps the full limit; no phrase keeps the scraper default). `search_all` submits each source x keyword search to the thread pool, merges and removes copies as before, and keeps `metadata["searches"]` (source, keyword, count, error).
- `stages_collect.py`: scrape metadata `searches`.
- `orchestrator.py`: after the after-stage hooks, a Scrape result with no data sets `NO_JOBS_WARNING` and stops; `success` is true for this early stop; `metadata["warning"]`.
- `api/routes/pipeline.py` and `responses.py`: the run keeps `warning`; the completion broadcast and `PipelineStatusResponse.warning_message` carry it.
- `page.tsx` and `api.ts`: `runStatusQuery` (shared by the Live Monitor and the header); an amber `role="status"` box for `warning_message`; "Request Cancel" hidden when the run status is completed, failed, or cancelled.
- Tests: 7 manager, 2 orchestrator, 1 async run, 2 status, 3 page. Two older tests had fake stages that returned empty data for Scrape (`TestCooperativeCancel`, `test_cost_run_scope._ok`); they test cancel and cost, so their fakes now return a token. Red step: every new test fails without the change, except the guard "Request Cancel shows while running" (passes before and after). Mutants: no limit split, all keywords in one search, failed search not recorded, no stop on an empty scrape, early stop counted as a failure, warning not stored by the API, cancel shown on a finished run, no warning box: 8 of 8 caught.
- Live check (MyCareersFuture, the fixed `search_all`, the three keywords from the screenshot, Singapore): 34 + 34 + 18, 86 unique listings (was 0).
- Full checks: black and ruff clean, mypy gate 177 known and 0 new, pytest 2,346 passed; frontend tsc, eslint, Prettier clean, Vitest 382 passed. No E2E test reads the cancel button or the warning.
- Clone commit `08b43f0` on top of `4b942b8` (= `main`).

## Pipeline test with the fix in the working tree (2026-11-14, user chose option 1: uncommitted `git apply`)

- The clone's diff was applied to the working tree with `git apply` (no commit); `make dev` reloaded (the OpenAPI schema showed `warning_message`). Run `run_11daca02…`: full mode, dry run, MyCareersFuture, profile keywords, Singapore, Max Jobs 2, Min Score 60, fresh graduate scoring on. Result file `data/results/pipeline_run_20261114_095635.json`; counts read with the user's approval (stage names and numbers only).
- Duration 142 s. Stage counts: scrape 100; deduplicate 100 to 100 (14 flagged, 0 removed); filter scams 100 to 100; filter by profile 100 to 59; score and rank 59 to 1 (58 below 60; best 61); RAG off (1 passed through); detect auto-submit 1 manual; present selection 1; generate resumes 1 CV and 1 letter (validation 100, `resumes_with_stock_phrases` 0); submit: dry run, 0 submitted, 1 manual.
- Generated files (written 09:56:21): letter 332 words, 0 stock phrases; CV (docx) 349 words, 0 stock phrases (detector, counts only, with the user's approval).
- Pipeline page: "100 scraped · 1 scored · 1 shortlisted", "Resumes: 1 job selected (Max Jobs) · 1 generated", Complete, no "Request Cancel".
- Resources (recorder, every 10 s): only `qwen2.5:7b` seen loaded (4.7 GB, 100% GPU) from 09:56:01 to the end; total GPU 7.2 to 7.3 GB of 8 GB (idle baseline about 2.5 GB); RAM 0.6 to 1.1 GB free with paging spikes up to 7,600 pages/sec. The first run (0 jobs) loaded no model at all.
- Result: the fix works as intended. Open questions for later (not this task): 58 of 59 jobs scored below 60 (scoring calibration or broad keywords); GPU close to the 90% guard on this machine.

- Applied (user approved, 2026-11-14): the working tree was checked identical to clone commit `08b43f0` (11 files, and the 2 new test files byte for byte), the uncommitted copy was removed, and `main` was fast-forwarded to `08b43f0`; `git diff` against it is empty. Not pushed yet.
