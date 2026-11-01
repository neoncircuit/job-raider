# Task: Step 3.7 Structured Output and Context Size

## Goal
Every LLM task that returns JSON asks Ollama for that JSON with a schema (Ollama `format`) and parses it with a Pydantic model, not with the regex `\{.*\}`. Each task sets its context size (`num_ctx`) and cuts its input to fit. The parse-failure rate of each task is measured on a fixed local set before and after the change (review items R13 and R14; plan in `tasks/active/step-3-measurable-claims/notes.md`).

```mermaid
flowchart LR
    M[MH-1 output models<br/>and strict parser] --> S[MH-2 eval suite<br/>structured]
    S --> B[Baseline run<br/>current code]
    B --> R[MH-3 router: schema<br/>and num_ctx]
    R --> C[MH-4 to MH-7<br/>convert 9 call sites]
    C --> A[After run<br/>same set]
    A --> D[Record and docs]
```

## Constraints & Context
- Measure first: the baseline runs on the current code with the same suite and set as the after run.
- The fixed set uses committed synthetic fixtures only (grounding profiles, jobs, and letters; `tests/fixtures/jd_paste/`; synthetic resume texts). No personal data.
- The suite needs Ollama, so it runs locally and logs to MLflow, not in CI. Its unit tests use a fake router and run in CI.
- GPU: one model at a time, models of 7B or smaller, unload after each model group, VRAM well below 8 GB. A larger `num_ctx` uses more VRAM, so the after run records the peak VRAM.
- The existing fallbacks (rule-based selection, template resume, and so on) stay. A parse failure is logged with the task and the reason.
- Cloud fallback providers ignore the schema; the parser accepts their JSON (also inside a code fence) without a regex.

## Acceptance Criteria
- [x] MH-1: output models for the 9 JSON tasks and one strict parser (`json.loads` and `model_validate`, code fences removed), with tests. (`8e9aadf`, 2026-10-31; 35 tests; 13 of 13 mutants caught)
- [x] MH-2: eval suite `structured` and its fixed set: for each task, the share of answers that parse strictly, that only the old regex can rescue, and that fail; prompt tokens against the context size; the model of each task in the run metadata. (`0542129`, 2026-11-01; 43 cases; 29 tests; 18 of 18 mutants caught)
- [x] Baseline run on the current code, recorded in `notes.md` (command, dataset SHA-256, MLflow run ID, peak VRAM). (2026-11-01, MLflow run `ade9802558bf497ea05c2eceeaf40661`: strict 0.845, rescued 0.132, failed 0.023; peak VRAM 6,846 MiB)
- [x] MH-3: the router passes a JSON schema to Ollama as `format`, sets `num_ctx` for each task, and keeps both in the response-cache key. (`251aa83`, 2026-11-01; 13 tests; 11 of 11 mutants caught; full gate 1841 passed)
- [x] MH-4 to MH-7: the 9 call sites use the schema and the strict parser; JD extraction and resume parsing cut their input to the task budget and log when they fall back to rule-based parsing. (All by Claude Haiku 5.5 in opencode, 2026-11-01: MH-4 `a84c616`, 10 of 10 mutants; MH-5 `50e70f3`, 8 of 8; MH-6 `fa5c43b`, 9 of 9; MH-7 `a6c6ce7`, 10 of 10; full gate 1885 passed)
- [x] After run on the same set, recorded next to the baseline. (2026-11-01, MLflow run `3882e8625b774a89bd32be9d891191e1`: strict 1.000 at all 9 sites; parse-failure rate 0.155 to 0; peak VRAM 6,444 MiB)
- [x] MH-8 to MH-10: the three other JSON parsing places (the cover-letter route helpers, the LinkedIn analyzer, and the assessment engine) use the schema and the strict parser (user decision 2026-11-01; no suite rate, tests and mutants only). (MH-8 `24d6e31`, runner, 10 of 10 mutants; MH-9 `ff426f2` and MH-10 `c8aabfa`, Claude Haiku 5.5 in opencode, 8 of 8 and 9 of 9 mutants; full gate 1925 passed)
- [ ] Done when: no code parses LLM JSON with a regex (`grep` check), the parse-failure rate per task is recorded before and after, and the full backend gate passes.

## Status
`in-progress` (2026-10-31: plan approved; MH-1 to MH-3 by the runner, MH-4 to MH-7 as spec handoffs for an agent)
