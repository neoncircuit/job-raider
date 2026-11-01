# Scratchpad & Notes

## Plan (2026-10-31, Claude)

### What exists today

- 9 call sites parse LLM JSON with `re.search(r"\{.*\}", ..., re.DOTALL)` and `json.loads`, each on its own task type:

  | File | Line | Task type | temperature, max_tokens | On failure |
  |------|------|-----------|-------------------------|------------|
  | `src/generation/selector.py` | 190 | `SELECTION` | 0.5, 1000 | rule-based selection |
  | `src/generation/resume_writer.py` | 268 | `RESUME_WRITING` | 0.7, 2500 | template resume |
  | `src/generation/validator.py` | 255 | `VALIDATION` | 0.3, 500 | rule checks only |
  | `src/generation/resume_analyzer.py` | 357 | `RESUME_ANALYSIS` (2 calls) | 0.3, 2500 | rule-based assessment |
  | `src/generation/cover_letter_reviewer.py` | 141 | `COVER_LETTER_REVIEW` | 0.3, 400 | no review |
  | `src/generation/cover_letter_validator.py` | 918 | `VALIDATION` | 0.0, 400 | rule checks only |
  | `src/extractors/resume_parser.py` | 479 | `RESUME_PARSING` | 0.3 | rule-based parser |
  | `src/extractors/jd_extractor.py` | 277 | `JD_EXTRACTION` | 0.3 | rule-based extractor |
  | `src/classifiers/job_classifier.py` | 349 | `CLASSIFICATION` | 0.2 | rule-based classifier |

- `OllamaClient.generate` sends `temperature`, `num_predict`, and `top_p`, but no `format` and no `num_ctx`. Ollama 0.33.1 is installed; it accepts a JSON schema in `format`.
- `jd_extractor.py:232` cuts the input at 50,000 characters (about 12,000 tokens), far above the context that Ollama uses by default, so Ollama cuts the prompt without a message.
- The response cache key holds `temperature`, `max_tokens`, and `think` (`router.py` `_cache_extra`), so a schema or a `num_ctx` change must also go into the key.
- Cloud fallback (Claude, Gemini) runs only when the Ollama call raises; a parse failure does not trigger it.

### The measure

A new local suite, `python main.py eval structured`, with a fixed set in `tests/fixtures/eval/structured/`:

- About 5 cases for each of the 9 tasks (45 cases), built from committed synthetic data: the grounding profiles, jobs, and letters; the 4 pasted JDs in `tests/fixtures/jd_paste/`; and a few synthetic resume texts made from the grounding profiles. Each case is sampled 3 times at the task's own temperature.
- The suite runs each component's real method with a recording router around the real router, so the baseline measures the current prompts and code, and the after run measures the new ones, with the same instrument.
- For each recorded answer: `strict` (the whole answer is JSON and validates against the task's output model), `rescued` (only the old regex finds a valid object), or `failed`; also the prompt tokens against the task's context size (a prompt at the limit was cut), the latency, and the model.
- Metrics per task: strict rate, rescued rate, failure rate. The headline is the failure rate per task (`failed` plus `rescued` after the change, because the new code has no regex rescue).
- One model at a time: the suite groups the cases by model and unloads each model after its group. It records the peak VRAM (`nvidia-smi`) in the report.

### Micro-handoffs

1. **MH-1, output models and strict parser** (`src/llm/structured.py`, new). One Pydantic model for each of the 9 tasks, from the keys that each parser reads today; `parse_structured(content, model)`: `json.loads` on the whole answer (after a code fence is removed), then `model_validate`; it raises `StructuredOutputError` with the reason. Tests. No call site changes.
2. **MH-2, the `structured` suite** and its fixed set, with a fake-router unit test (in CI) and the `main.py eval structured` choice.
3. **Baseline run** (Claude, local, with the user's approval for the GPU time: about 135 calls, about 30 to 60 minutes).
4. **MH-3, router and client.** A `response_schema` keyword: the Ollama client sends it as `format`; other clients ignore it. `num_ctx` for each route (default 4096; 8192 for JD extraction and resume parsing), sent as `options.num_ctx` to Ollama only. Both go into the cache key. Tests.
5. **MH-4 to MH-7, the call sites**, in 4 groups: resume pipeline (selector, resume writer, resume validator); cover letters (reviewer, validator LLM path); extraction (JD extractor with an input budget, job classifier); resume parsing and analysis (resume parser with an input budget, resume analyzer). Each site passes its model's schema, parses with `parse_structured`, logs a parse failure with the task and the reason, and keeps its fallback. The regex goes.
6. **After run** on the same set, then the record (`notes.md`, decision log), and the full gate.

### Choices for the check-in

- **Handoff style.** MH-1 to MH-3 set the shared code, so Claude writes them in full for the handoff runner. MH-4 to MH-7 repeat one pattern 9 times; they can be spec handoffs for whichever agent has quota, with the same mutant check after each run. Or Claude writes them in full too (exact, but more Claude time).
- **Context sizes.** 4096 for most tasks, 8192 for JD extraction and resume parsing. The after run records the peak VRAM; if it is too high, the 8192 tasks go back to 4096 with a smaller input budget.

## Decisions (user, 2026-10-31)

1. The plan is approved.
2. MH-1 to MH-3: Claude writes the full code; the handoff runner applies them.
3. MH-4 to MH-7: spec handoffs for whichever agent has quota (`docs/handoff-runner.md`, "Spec handoffs for an agent"). Claude checks each with a reference fix and mutants before and after the run, and records the agent and model of each handoff here.

## MH-1 written and checked (2026-10-31, Claude)

`mh-1-output-models.md`: `src/llm/structured.py` (9 output models, `OUTPUT_MODELS` by call site, `parse_structured`, `strip_code_fence`, `StructuredOutputError` with the reasons `not_json`, `not_object`, and `schema`, and `extract_braced_object` for the suite's "rescued" count without a regex) and `tests/unit/test_structured_output.py` (35 tests, one sample answer in each prompt's shape).

- Model choices: a field that the prompt allows to be empty is `Optional` without a default (required, `null` allowed), so Ollama's schema makes the model write every key. The analysis fields that only the job-specific prompt asks for have defaults. Recommendations are `approve`, `needs_revision`, or `reject`; scores are 0 to 100; confidences 0 to 1. The resume parser model has grouped skills (the prompt also allows a flat list; MH-7 removes that sentence).
- Scratch clone: the runner's red step fails (no module), then 35 tests pass, black makes no change, ruff passes, the mypy gate has 0 new errors, and the runner commits (`fd982b2` on the clone).
- Mutants (13 of 13 caught): no fence removal, closing fence kept, no object check, any recommendation text, no score range, first closing brace, no brace order check, alignment score required, a call site missing from `OUTPUT_MODELS`, the `schema` and `not_json` reasons swapped, a nullable field made required, an optional list made required.
- Applied on the repo (2026-10-31, Claude ran the runner on the user's word "Yes, apply it"): commit `8e9aadf`. The red step failed, and the 4 checks passed. The two committed files are the same blobs as on the mutant clone, with LF line endings.

## MH-2 written and checked (2026-11-01, Claude)

`mh-2-structured-suite.md`: `src/evaluation/suites/structured.py`, the fixed set `tests/fixtures/eval/structured/cases.jsonl` (43 cases: 5 for each site, 3 for resume parsing), `tests/unit/test_structured_suite.py` (29 tests with a fake `generate`), the registry in `src/evaluation/suites/__init__.py`, and the exact-tuple registry test in `tests/unit/test_scam_suite.py`.

- Inputs: the grounding set's 3 synthetic profiles, jobs, and letters; the 4 pasted JDs; resume texts and one JD text written from the grounding data by the suite (`render_resume_text`, `render_job_text`). The steps after selection get a fixed selection (first 3 profile projects, up to 5 profile skills that the job names) and, for the resume validation, a resume made only of profile facts.
- Found while writing: `CoverLetterValidator.validate_with_llm` returns the rule result without an LLM call when the rules find a hard fail. The first draft used 2 letters with a made-up technology, which gave no call; the set now uses clean letters for that site.
- The response cache is turned off in the suite's router (`_response_cache.enabled = False`), so each sample is a new answer; the report also counts cached calls. `default_router` is not unit-tested, because it reads the saved Settings.
- Scratch clone: black makes no change, ruff passes, 29 tests pass, the mypy gate has 0 new errors. The runner applies the handoff (red step fails, 5 checks pass, commit `ee301f5` on the clone).
- Mutants (18 of 18 caught): rescued counted as strict; the two legacy flags; the truncation boundary; no unload; no model order; no task-type filter; samples ignored; the lowest VRAM kept; an empty rate as 0; content kept for strict answers; no_call counted as failed; local calls counted as non-local; references not checked; keywords not from the job; a wrong task type; JD inputs not checked; resume text without projects.
- Applied on the repo (2026-11-01, Claude ran the runner on the user's word "Yes, apply it"): commit `0542129`. The red step failed, and the 5 checks passed. The suite, its tests, the registry, and the fixed set are the same bytes as the scratch copies that the mutants ran on (LF line endings); `test_scam_suite.py` changes by the one expected line. (The `/tmp` clones were gone after a WSL restart, so the compare used the scratchpad copies.)

## Baseline run (2026-11-01, Claude, with the user's approval for the GPU time)

Command (WSL, from `apps/backend-py`), one time, on the current code (no schema, no `num_ctx`):

```bash
.venv/bin/python main.py eval structured
```

Git SHA `a190fd0c09f5c3d2dd18f0483021a2ab8d015e19` (`git_dirty`: true; the 14 CRLF-only files). Dataset SHA-256 `2fce5d5296db542024fcbe8dd285cc1929cac8eec5a4b2436c13bd236bbd3e7e`. MLflow run `ade9802558bf497ea05c2eceeaf40661`. Report `data/eval/structured/20261101T023903125197Z.json`. 10:26 to 10:39 (13 minutes). 129 calls, all to the local Ollama, 0 from the cache, 0 without an answer. Peak VRAM 6,846 MiB (suite) and 6,856 MiB (watchdog, limit 7,700); no model loaded after the run. Ollama gave both models a context of 4,096 tokens.

| Site | Model | Calls | Strict | Rescued | Failed | Old parsing found no JSON | Latency p50 |
|------|-------|-------|--------|---------|--------|---------------------------|-------------|
| selection | 3b | 15 | 1.000 | 0 | 0 | 0 | 2.0 s |
| resume_writing | 7b | 15 | 1.000 | 0 | 0 | 0 | 3.8 s |
| resume_validation | 3b | 15 | 1.000 | 0 | 0 | 0 | 0.6 s |
| resume_analysis | 7b | 15 | 1.000 | 0 | 0 | 0 | 10.1 s |
| cover_letter_review | 3b | 15 | 1.000 | 0 | 0 | 0 | 0.5 s |
| cover_letter_validation | 3b | 15 | 0.400 | 0.400 | 0.200 | 0.200 | 3.4 s |
| resume_parsing | 7b | 9 | 1.000 | 0 | 0 | 0 | 7.2 s |
| jd_extraction | 7b | 15 | 1.000 | 0 | 0 | 0 | 1.6 s |
| job_classification | 7b | 15 | 0.267 | 0.733 | 0 | 0 | 7.8 s |
| all | | 129 | 0.845 | 0.132 | 0.023 | 0.023 | |

What the baseline shows:

- 7 of 9 sites already answer with one clean JSON object every time on this set.
- **Job classification:** 11 of 15 answers are a fenced JSON object followed by a prose explanation of each field. Only the old regex takes these; the strict parser does not (text after the fence).
- **Cover letter validation (3b, temperature 0):** 9 of 15 answers start with "Here is the evaluation of the cover letter"; 6 have the JSON inside the prose, and 3 (one case, three identical samples) have no JSON at all, so the validator used its rule result. At temperature 0 the 3 samples of a case are the same, so this site has 5 distinct answers, not 15.
- **No prompt was cut:** the longest prompt was 1,331 tokens (resume parsing) and the longest answer 926 tokens (resume analysis), against a context of 4,096. The inputs of this set are short (pasted JDs up to 800 characters, short synthetic resumes), so the set measures the answer format, not the input size. The input-size risk is still in the code: the JD extractor sends up to 50,000 characters (about 12,500 tokens), and nothing cuts a long resume.
- Resume parsing: the model wrote "not provided" for missing URLs, and the profile mapping dropped them (`url_parsing` messages in the log). The schema allows any string there, so MH-7 asks for `null`.

## MH-3 written and checked (2026-11-01, Claude)

`mh-3-router-schema-context.md`: 5 edits in `src/llm/router.py` and 3 in `src/llm/ollama_client.py`, and `tests/unit/test_router_structured_options.py` (13 tests).

- `context_size(task_type)`: `TASK_NUM_CTX` gives 8,192 tokens to JD extraction and resume parsing, and `DEFAULT_NUM_CTX` 4,096 to the other tasks. The router sets `num_ctx` with `setdefault` in `generate` and `generate_async`, so a caller value wins. A module-level map, not a `RouteConfig` field, because the Settings reload builds the routes again.
- Ollama loads a model again when `num_ctx` changes. The pipeline tasks all use 4,096, so a run does not reload; a pasted JD or a CV upload (8,192) can reload `qwen2.5:7b` one time. KV cache estimate for `qwen2.5:7b` (28 layers, 4 KV heads, head size 128, fp16): about 56 KB a token, so 8,192 tokens add about 0.23 GB over 4,096.
- `response_schema` passes through the router; the Ollama client sends it as `format`, and the Claude and Gemini clients ignore it (they read only the keys they know).
- The response-cache key gets `num_ctx` and `schema_key(schema)` (16 hex characters of the SHA-256 of the sorted schema).
- `payload: Dict[str, Any]` in the Ollama client removes one baseline mypy error.
- Scratch clone: black and ruff clean, 13 new tests and 72 router, client, and cost tests pass, the mypy gate has 0 new errors (3 baseline errors fixed). The runner applies the handoff (red step fails, 5 checks pass, commit `44be61b` on the clone).
- Mutants (11 of 11 caught): no `options.num_ctx`; no `format`; no context size in `generate`; none in `generate_async`; a caller value replaced; the JD size and the default size changed; the cache key without the context size; without the schema; the schema key without sorted keys; the full-length schema key.
- Applied on the repo (2026-11-01, Claude ran the runner on the user's word "Yes, apply it"): commit `251aa83`. The red step failed, and the 5 checks passed. The three files are the same bytes as the checked copies.
- Full backend gate after MH-3: black and ruff pass on the CI paths, the mypy gate has 0 new errors (179 known, 3 baseline errors fixed; `--update` not run), and pytest has 1841 passed (1764 before MH-1, plus 35, 29, and 13 new tests).

## MH-4 spec handoff written and checked (2026-11-01, Claude)

`AGENT.md` (the brief for MH-4 to MH-7) and `mh-4-resume-pipeline.md`: the selector, the resume writer, and the LLM resume validation send their schema and parse with `parse_structured`; 13 named tests; two existing tests change.

- A probe of the reference fix against the existing tests found two that send answers the schema refuses: `test_keywords_are_only_profile_skills` (missing keys and an integer keyword) and `test_writer_returns_a_flat_skill_list` (skills grouped by category). The handoff names both changes. Grouped skills now fall back to the template resume; with Ollama's `format`, the model cannot write them, and `flatten_skills` stays for other callers.
- `pytest.ini` has `--maxfail=5`, so the red command adds `--maxfail=20` (also noted in `AGENT.md`).
- Reference check on a scratch clone (Claude's own tests and fix, not given to the agent): red 10 failed and 3 passed; the two changed tests pass on the current code; with the fix, 95 tests of the components, the pipeline, and the suite pass; no `DOTALL` left; ruff clean; the mypy gate has 0 new errors.
- Mutants on the reference fix (10 of 10 caught): no schema at each site (3); prose rescued at each site (3); the selection summary dropped; the writer experience dropped; a fixed validation recommendation; keywords not filtered by the profile.

## MH-4 run by the agent (2026-11-01)

Agent and model: opencode, `github-copilot/claude-haiku-5.5`, a new session (user). One prompt, no help, no stop; commit `a84c616`. The agent reported red 10 failed and 3 passed, then 21 and 82 tests passing, no `DOTALL`, black and ruff clean, and the mypy gate with 0 new errors.

Claude check:

- The code diff is the same as the reference fix, line for line. The 13 tests have the names, inputs, and checks of the spec, and the two existing tests changed only as the spec says. The commit has the 6 named files only.
- The 10 mutants on the agent's code, with the agent's tests: 10 of 10 caught.
- Full backend gate: black and ruff pass on the CI paths, the mypy gate has 0 new errors (179 known), pytest has 1854 passed (1841 plus 13).
- Tokens (session export): 25 steps, 1.106M cached input, 50.5K cache writes, 13.6K output with reasoning; the largest prompt was 55,843 tokens, so all steps stayed below Haiku 5.5's 100K price tier. About USD 0.024 (2.4 credits), against about USD 0.21 for the trial in an old session.

## MH-5 spec handoff written and checked (2026-11-01, Claude)

`mh-5-cover-letters.md`: the cover-letter review and the LLM cover-letter validation send their schema and parse with `parse_structured`; 9 named tests; one existing test is removed.

- The probe of the reference fix found one existing test that checks the old behavior on purpose: `test_review_extracts_json_from_extra_text` (JSON taken from inside explanatory text). The handoff removes it; the new prose test checks the new behavior.
- The validator's recommendation normalization (case, spaces, unknown words) goes: the schema allows only the three values, and no test covered the normalization.
- Reference check on a scratch clone: red 7 failed and 2 passed; with the fix, 151 cover-letter, grounding, and suite tests pass; no `DOTALL` left; ruff clean; the mypy gate has 0 new errors.
- Mutants on the reference fix (8 of 8 caught): no schema at each site (2); prose rescued at each site (2); a fixed rewrite flag; the score from the structure score; the LLM feedback dropped; the critique not stripped.

## MH-6 and MH-7 spec handoffs written and checked (2026-11-01, Claude)

`mh-6-extraction.md` (JD extractor and job classifier, 11 named tests) and `mh-7-resume-parsing.md` (resume parser and resume analyzer, 12 named tests). They touch other files than MH-5, so they were written while the agent ran MH-5. Probes of both reference fixes: no existing test breaks (44 and 106 tests).

- MH-6, JD extractor: the posting is cut to `MAX_JD_CHARS = 18_000` (was 50,000) and the answer limited to `JD_MAX_TOKENS = 1_500`, to fit the 8,192-token context; the parsed answer goes to the mapping as `model_dump(exclude_none=True)`. Found: a `null` `experience_level` reaches `.title()` and ends the LLM path ("'NoneType' object has no attribute 'title'" in the red run); `exclude_none` fixes it, and a test covers it. The old no-JSON branch returned `success=False`; a parse failure now goes to the rule-based result like any other failure.
- MH-6, both files: a module logger (`Components.LLM`) logs a warning on each fallback; the result's `errors` still carries the reason. The `errors` and `warnings` lists get type hints, because mypy cannot infer `errors` after the branch goes (2 new errors in the first probe).
- MH-7, resume parser: `MAX_RESUME_CHARS = 8_000` (unchanged size, now a named constant with a warning log when it cuts) and `RESUME_MAX_TOKENS = 3_000` (was the client default of 4,096, which shared the 8,192 context with the prompt). The prompt asks for `null` for missing URLs and GPA (the baseline had "not provided"), and no longer allows a flat skills list.
- MH-7, resume analyzer: both calls send the schema; `_parse_llm_assessment` returns the same 11 keys from the parsed answer.
- Reference checks on scratch clones: MH-6 red 9 failed and 2 passed, green 55 passed; MH-7 red 10 failed and 2 passed, green 118 passed. No `DOTALL` left, ruff clean, the mypy gate has 0 new errors for both.
- Mutants on the reference fixes: MH-6 9 of 9 caught (no schema, no answer limit, prose rescued, the 50,000-character limit, no fallback log, null fields kept; classifier: no schema, prose rescued, no fallback log); MH-7 10 of 10 caught (no schema, no answer limit, prose rescued, a 20,000-character limit, the cut log not a warning, the prompt still "if present"; analyzer: no schema in each call, prose rescued, the summary dropped).

## MH-5 run by the agent (2026-11-01)

Agent and model: opencode, `github-copilot/claude-haiku-5.5`, the same session as MH-4 (the user keeps one session a day). One prompt; commit `50e70f3`.

Claude check (scratch clone at `50e70f3`, because the agent was already running MH-6 in the repo):

- The code diff is the same as the reference fix. The 9 tests have the spec's names; only `test_review_extracts_json_from_extra_text` was removed from `test_cover_letter_reviewer.py`. The commit has the 4 named files only.
- The 8 mutants on the agent's code, with the agent's tests: 8 of 8 caught.
- Full backend gate at `50e70f3`: black and ruff pass on the CI paths, the mypy gate has 0 new errors (179 known), pytest has 1862 passed (1854 plus 9 new, minus 1 removed).
- Tokens (session export, second prompt): 31 steps, 2.54M cached input, 86.8K cache writes, 12.6K output with reasoning; the largest prompt was 92,188 tokens, still below the 100K tier. About USD 0.043. The longer session context (MH-4 history) shows in the cached input: 2.3 times that of MH-4.

## MH-6 and MH-7 run by the agent (2026-11-01)

Agent and model: opencode, `github-copilot/claude-haiku-5.5`, the same session again; one prompt for both handoffs, one commit each: `fa5c43b` (MH-6) and `a6c6ce7` (MH-7). The agent reported red 9 failed and 2 passed (MH-6) and 10 failed and 2 passed (MH-7), then all checks passing.

Claude check (scratch clones at each commit):

- MH-6: the code matches the spec (the parsed answer goes straight into the mapping calls as `model_dump(exclude_none=True)`, without a `data` name). The 11 tests have the spec's names. Mutants 9 of 9 caught. Full gate at `fa5c43b`: black, ruff, and the mypy gate pass (0 new); pytest 1873 passed.
- MH-7: the code matches the spec, with the `Raises:` line in `_parse_llm_assessment`. The 12 tests have the spec's names. Mutants 10 of 10 caught. Full gate at `a6c6ce7`: black, ruff, and the mypy gate pass (0 new); pytest 1885 passed.
- Tokens and cost per prompt of the session (session export; Haiku 5.5 prices per step, 5 times above 100K prompt tokens):

  | Prompt | Handoffs | Steps | Steps above 100K | Largest prompt | USD |
  |--------|----------|-------|------------------|----------------|-----|
  | 1 | MH-4 | 25 | 0 | 55,843 | 0.024 |
  | 2 | MH-5 | 31 | 0 | 92,188 | 0.043 |
  | 3 | MH-6 and MH-7 | 42 | 41 | 156,966 | 0.395 |
  | all | | 98 | 41 | | 0.462 |

  The third prompt carried the history of the first two; in a new session it would have cost about USD 0.05 to 0.08.

All 9 call sites now send their schema and parse strictly. A search of `src/` finds no regex `\{.*\}` any more. Three other places parse LLM JSON in their own way, outside the 9 call sites of review item R13: `generation/linkedin_analyzer.py` (a code-fence regex, then brace matching), `assessment/engine.py` (removes a fence, then `json.loads`; questions are a JSON list), and `api/routes/cover_letter.py` `_parse_json_object` (removes a fence, then the text from the first `{` to the last `}`, without a regex). They are not in the structured suite.

## After run (2026-11-01, Claude, with the user's approval for the GPU time)

Command (WSL, from `apps/backend-py`), one time, on the new code, with the same set as the baseline:

```bash
.venv/bin/python main.py eval structured
```

Git SHA `6e1e590598384ac0ad761858202887113b5b213b` (`git_dirty`: true; the 14 CRLF-only files). Dataset SHA-256 `2fce5d5296db542024fcbe8dd285cc1929cac8eec5a4b2436c13bd236bbd3e7e` (the same as the baseline). MLflow run `3882e8625b774a89bd32be9d891191e1`. Report `data/eval/structured/20261101T132424867497Z.json`. 21:16 to 21:25 (9 minutes; the baseline took 13). 129 calls, all local, 0 from the cache, 0 without an answer. Peak VRAM 6,444 MiB (suite) and 6,452 MiB (watchdog), below the baseline's 6,846 MiB; no model loaded after the run.

| Site | Model | Strict before | Strict after | Failed before | Failed after | Latency p50 before | after | Answer tokens p50 before | after |
|------|-------|---------------|--------------|---------------|--------------|--------------------|-------|--------------------------|-------|
| selection | 3b | 1.000 | 1.000 | 0 | 0 | 2.0 s | 1.8 s | 299 | 276 |
| resume_writing | 7b | 1.000 | 1.000 | 0 | 0 | 3.8 s | 3.5 s | 315 | 300 |
| resume_validation | 3b | 1.000 | 1.000 | 0 | 0 | 0.6 s | 0.4 s | 60 | 60 |
| resume_analysis | 7b | 1.000 | 1.000 | 0 | 0 | 10.1 s | 3.2 s | 832 | 278 |
| cover_letter_review | 3b | 1.000 | 1.000 | 0 | 0 | 0.5 s | 0.5 s | 67 | 62 |
| cover_letter_validation | 3b | 0.400 | 1.000 | 0.200 | 0 | 3.4 s | 1.2 s | 400 | 176 |
| resume_parsing | 7b | 1.000 | 1.000 | 0 | 0 | 7.2 s | 6.2 s | 530 | 511 |
| jd_extraction | 7b | 1.000 | 1.000 | 0 | 0 | 1.6 s | 1.4 s | 130 | 122 |
| job_classification | 7b | 0.267 | 1.000 | 0 | 0 | 7.8 s | 3.6 s | 647 | 302 |
| all | | 0.845 | 1.000 | 0.023 | 0 | | | | |

The parse-failure rate (failed plus rescued, because the new code has no regex rescue) went from 0.155 (20 of 129) to 0 (0 of 129). The old parsing's fallback rate (no JSON object) went from 0.023 (3 of 129) to 0.

What the after run shows:

- **Cover letter validation:** 15 of 15 strict; the "Here is the evaluation" prose is gone, and the answer is 56% shorter (400 to 176 tokens), so the 3b model is 2.8 times faster.
- **Job classification:** 15 of 15 strict; the field-by-field explanation after the JSON is gone (647 to 302 tokens), 2.2 times faster.
- **Resume analysis:** the answer shrank from 832 to 278 tokens and the call is 3.2 times faster. The YAML prompt still asks for `skills_assessment`, `experience_insights`, and `project_insights`, which the code never used (they come from the parsed profile); the schema leaves them out, so the model no longer writes them.
- **Resume parsing:** the log had 8 `url_parsing` messages ("not provided" URLs) in the baseline and 0 now.
- **Context size:** the suite reads the context length from `/api/ps` once for each model, after the model's last case. The last `qwen2.5:7b` case is resume writing (4,096), so the report shows 4,096 for both models; it cannot show the 8,192 of JD extraction and resume parsing. The VRAM readings after each case include those cases, so 6,444 MiB is the peak with the 8,192 context. The unit tests of MH-3 show that the router sends 8,192 for these two tasks.
- No prompt was cut; as in the baseline, the inputs of this set are short (longest prompt 1,327 tokens).

## MH-8 to MH-10: the three other JSON parsing places (2026-11-01, Claude)

Decision (user): convert them in Step 3.7. Split as before: MH-8 adds the output models (runner, full code), MH-9 and MH-10 change the call sites (spec handoffs for the agent). These places are not in the `structured` suite, so there is no before and after rate; the tests and the mutants are the check.

- `mh-8-more-output-models.md`: `PrepSheetAnswer`, `ScoreExplanationAnswer`, `LinkedInAnalysisAnswer` (with `LinkedInSectionScore` and `LinkedInInsight`), `AssessmentQuestionsAnswer` (with `AssessmentQuestion` and `AssessmentOption`), and `AssessmentScoreAnswer`, and 22 tests. The question list is inside an object (`questions`), because Ollama's `format` and `parse_structured` take one object. A question needs no hint, options, or time limit, and a score needs no `is_correct` (defaults). The models are not in `OUTPUT_MODELS`, because the suite has no cases for them. Scratch clone: 82 tests pass (with the first models and the suite), ruff clean, the mypy gate has 0 new errors, and the runner applies the handoff (`cf159ec` on the clone). Mutants 10 of 10 caught (a free priority text, no section score range, a free question type, the hint, options, correct flag, and time limit made required, no score range, a prep-sheet field dropped, the LinkedIn metadata made required).
- `mh-9-route-and-linkedin.md`: the prep sheet and `_generate_explanation` in `api/routes/cover_letter.py` (and `_parse_json_object` removed), and the LinkedIn analyzer (`_extract_json` removed; the `ValueError` keeps "Failed to extract JSON" and adds the reason). 11 named tests; one existing test (`test_parse_json_with_markdown`) gets a full answer. Reference check: red 9 failed and 2 passed; green 91 passed; the source changes are ruff clean; the mypy gate has 0 new errors. Mutants 8 of 8 caught.
- `mh-10-assessment.md`: the assessment engine (question generation and answer scoring) and one prompt line (`Return a JSON object with one key, "questions"`). 11 named tests; five existing tests change (four send `{"questions": [...]}`, one looks for the new prompt text). Reference check: red 10 failed and 1 passed; green 75 passed; ruff clean; the mypy gate has 0 new errors. Mutants 9 of 9 caught.

## Blockers / Questions
- None.
