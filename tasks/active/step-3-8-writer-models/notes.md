# Scratchpad & Notes

## Plan (2026-11-02, Claude)

### What exists today

- `src/evaluation/cover_letter_compare.py` (used by `scripts/compare_cover_letter_models.py`, `api/routes/evaluation.py`, and the Settings compare card): `build_fixtures()` makes 3 synthetic cases, one letter for each case and model, ranked on the validator's mean score. Allow-list: `qwen2.5:7b` and `qwen3.5:4b` only (decision of 2026-08-25, after a blue screen with `qwen3.5:9b`).
- Result of 2026-08-25: `qwen2.5:7b` mean 83.0, `qwen3.5:4b` mean 77.67, on 3 cases with 1 sample each. About 3.4 seconds for each letter on `qwen2.5:7b` after the model loaded.
- The grounding set (`tests/fixtures/eval/grounding/`): 3 synthetic profiles (`ml`, `backend`, `grad`) and 65 cases, each with a distinct job (26, 24, and 15 for each profile). The labels of the cases belong to the fixed letters of the set, not to new letters, so the comparison uses the jobs and profiles only.
- `CoverLetterWriter.write` uses temperature 0.8, `max_tokens` 1200, and `think=False`. The router's response cache key has no sample number, so the cache must be off for the samples to differ.

### The measure

For each letter, the validator gives its issues. For each model, the report gives:

| Metric | Why |
|--------|-----|
| Share of letters with `ungrounded_claims` (main metric) | The best check on real letters: precision 0.875, recall 0.778 at the letter level |
| Share with `fabricated_technology`, `fabricated_experience`, and `scope_inflation` | Each check separately; their real-letter support is small (1, 0, and 2) |
| Share of valid letters, mean score | For continuity with the 2026-08-25 result; the score mixes the checks |
| Words (p50), latency (p50 and p95), peak VRAM | Cost of the model on this host |

Not used to rank: the count of ungrounded sentences (precision 0.182 and recall 0.154 on real letters).

Decision rule (fixed before the runs): for each pair, take the share of the 3 samples that have `ungrounded_claims`. Compare a model with `qwen2.5:7b` pair by pair (paired difference, bootstrap 95% interval over the 65 pairs, fixed seed). Change the default writer only when the whole interval is below 0 (the other model is better) and the model's `fabricated_technology` share is not higher. Otherwise keep `qwen2.5:7b`.

### Size and time

65 pairs times 3 samples = 195 letters for each model. At about 3 to 5 seconds for each letter, one model takes about 10 to 16 minutes, plus the validator (deterministic, fast).

### Micro-handoffs

- MH-1 (runner, full code): `src/evaluation/suites/writer.py` core: the pairs from the grounding set, the sample loop with an injected writer, the letter-level metrics, and the summary; tests with a fake writer.
- MH-2 (spec handoff for an agent): the suite in the registry, `main.py eval writer --model --samples`, the real writer on a router with the cache off, unload after the model, peak VRAM, and the allow-list check.
- MH-3 (spec handoff for an agent): the paired comparison of two writer reports and its command.
- Runs (Claude, with the user's approval for the GPU time): the baseline first, then the other models one at a time.
- Docs: the decision-log entry and the `docs/usage.md` section.

For the agent: a new opencode session for each handoff costs much less than a long session (Step 3.7: USD 0.018 for MH-12 in a new session, USD 0.83 for a late prompt in a long one).

### Choices for the check-in

1. Models (all installed, 7B or smaller): `qwen2.5:7b` (baseline, always), `qwen3.5:4b` (the 2026-08-25 candidate), `gemma3:4b`, `qwen2.5:3b`. Other installed models of 7B or smaller: `mistral:latest` (7B), `olmo-3:7b`, `nemotron-3-nano:4b`. Not allowed: `qwen3.5:9b`, `deepseek-r1:8b`, `granite4.1:8b`, `ornith:9b`, `qwen2.5:14b`, and `gemma4:e4b` (9.6 GB file). The chosen models go into `ALLOWED_MODELS`.
2. Extra check: validator only (state that it does not see analogical claims), or also a blind label check: Claude drafts labels for a few letters of each model with the model names hidden, and the user checks them, as in Step 3.2.

## Decisions (user, 2026-11-02)

1. Models: `qwen3.5:4b`, `qwen2.5:3b`, and `gemma3:4b`, against the baseline `qwen2.5:7b` (not the other 7B models). `ALLOWED_MODELS` becomes `qwen2.5:7b`, `qwen3.5:4b`, `qwen2.5:3b`, and `gemma3:4b`. Change (user, same day): `gemma3:4b` added after Claude explained that it is not `gemma4:e4b`. `gemma4:e4b` stays out: 8.0B stored parameters (about 4B active), a 9.6 GB file with vision and audio parts, more than the free VRAM of the RTX 3070 Ti (8,192 MiB, about 1,574 MiB used by the desktop), and above the 7B limit. `gemma3:4b` is 4.3B and 3.3 GB (Q4_K_M), the same size class as `qwen3.5:4b`.
2. Check: validator only. The decision log states that the validator does not see analogical claims.
3. The user left the order of the work to Claude ("whatever is sensible"), with a new opencode session when that is better for an agent handoff.

## MH-1 written and checked (2026-11-02, Claude)

`mh-1-writer-suite.md`: `src/evaluation/suites/writer.py` (`load_pairs`, `write_and_check`, `summarize`, `pair_counts`, `profile_rates`, `percentile`, `run_writer_suite`) and `tests/unit/test_writer_suite.py` (18 tests, fake writer and fake validator). It uses `fixed_selection` and `load_suite_data` of the structured suite, so every model gets the same selection. A letter from the template fallback or another model is counted, not scored; a writer exception is an `error` row. The suite is not in the registry yet (MH-2).

- Scratch clone: red is an import error; 47 tests pass (with the structured suite tests); black and ruff clean; the mypy gate has 0 new errors (179 known).
- Mutants 11 of 11 caught (fallback letters scored, other-model letters scored, rates over all letters, pairs in file order, one sample short, writer errors not caught, percentile rounded down, profile rates over all letters, pair counts over all letters, no temperature in the metadata, strict validator).
- Runner test on a fresh clone: the red step failed, the 4 checks passed, commit `8a8cbf0` on the clone, and both files are the same bytes as the checked copies.
- MH-1 applied on the repo (2026-11-02, Claude ran the runner on the user's word "Yes, apply it"): commit `c84adc9`. The red step failed, and the 4 checks passed. Both files are the same bytes as the checked copies.

Found for MH-2 (from `LLMRouter.generate` and `resolve_primary_model`): the writer's `model` override is used only when the Settings route for cover letters has Ollama as its primary provider (else the route's own model writes), and a failed local call goes to the route's fallback provider when one is set. MH-2 must stop the run before any call when the route is not Ollama with the requested model, and set the route's fallback to `none` for the run. MH-1 already counts any letter from another model as `other_model`.

## MH-2 and MH-3 spec handoffs written and checked (2026-11-02, Claude, while the user was away)

The user said "Just do whatever is necessary for the timebeing". Claude wrote and checked the two specs and the agent brief (`AGENT.md`); nothing was applied, pushed, or run on the GPU.

Change from the plan: the suite has its own allow-list, `WRITER_MODELS` in `writer.py` (the four approved models), not `ALLOWED_MODELS` of `cover_letter_compare.py`. Reason: `ALLOWED_MODELS` is also the default model list of the Settings compare (`api/routes/evaluation.py`, the Metrics card text names two models), so four models there would change the app's compare; and the test that pins it (`test_compare_cover_letter_models.py`) is one of the files with CRLF-only changes in the working tree, which no handoff may touch.

- `mh-2-real-writer-and-command.md`: `check_model`, `local_writer` (stops before any call when the cover-letter route does not resolve to `ollama/<model>`; sets the route's fallback provider to `none`), `run_writer_suite` with the default router (cache off), unload once in `finally`, and the peak VRAM; the registry; `main.py eval writer --model --samples`; one assertion in `test_scam_suite.py` (it pins `SUITE_NAMES`). 16 tests in a new file. Reference check on a clone with MH-1: red 16 failed (no error); ruff clean; the mypy gate has 0 new errors; `eval --help` shows both options and the example. Mutants 11 of 11 caught (no allow-list check, route model not checked, fallback kept, writer ignores the model, no unload on failure, peak is the last reading, no default VRAM probe, no default unload, command drops samples, command needs no model, suite not in the registry). The first green run found the pinned `SUITE_NAMES` in `test_scam_suite.py`; the spec now names that change. Green re-check with it: 124 passed (the new file, MH-1, `test_cli`, `test_dedupe_suite`, `test_structured_suite`, and `test_scam_suite`); black wraps the new tuple line.
- `mh-3-paired-comparison.md`: `src/evaluation/writer_compare.py` (`load_writer_report`, `pair_differences`, `bootstrap_interval`, `compare_reports` with the decision rule) and `scripts/compare_writer_reports.py`. 12 tests. Reference check (on a clone with MH-1 and the MH-2 reference): red is one collection error (new module; the spec says so); green 30 passed; ruff clean; the mypy gate has 0 new errors. Mutants 11 of 11 caught (difference reversed, empty other pair kept, pairs in baseline order, seed ignored, median instead of the interval, decision ignores technology, decision on the low end, no dataset check, equal technology refused, any suite loads, script hides errors).

## Blockers / Questions
- None.
