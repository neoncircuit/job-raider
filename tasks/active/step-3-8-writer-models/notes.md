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

1. Models: `qwen3.5:4b` and `qwen2.5:3b`, against the baseline `qwen2.5:7b` (not `gemma3:4b`, not the other 7B models). `ALLOWED_MODELS` becomes `qwen2.5:7b`, `qwen3.5:4b`, and `qwen2.5:3b`.
2. Check: validator only. The decision log states that the validator does not see analogical claims.
3. The user left the order of the work to Claude ("whatever is sensible"), with a new opencode session when that is better for an agent handoff.

## MH-1 written and checked (2026-11-02, Claude)

`mh-1-writer-suite.md`: `src/evaluation/suites/writer.py` (`load_pairs`, `write_and_check`, `summarize`, `pair_counts`, `profile_rates`, `percentile`, `run_writer_suite`) and `tests/unit/test_writer_suite.py` (18 tests, fake writer and fake validator). It uses `fixed_selection` and `load_suite_data` of the structured suite, so every model gets the same selection. A letter from the template fallback or another model is counted, not scored; a writer exception is an `error` row. The suite is not in the registry yet (MH-2).

- Scratch clone: red is an import error; 47 tests pass (with the structured suite tests); black and ruff clean; the mypy gate has 0 new errors (179 known).
- Mutants 11 of 11 caught (fallback letters scored, other-model letters scored, rates over all letters, pairs in file order, one sample short, writer errors not caught, percentile rounded down, profile rates over all letters, pair counts over all letters, no temperature in the metadata, strict validator).
- Runner test on a fresh clone: the red step failed, the 4 checks passed, commit `8a8cbf0` on the clone, and both files are the same bytes as the checked copies.

## Blockers / Questions
- None.
