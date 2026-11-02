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

## MH-2 and MH-3 run by the agent (2026-11-02)

Agent and model: opencode, `claude-haiku-5.5` (from the session export), a new session (user: "for the sake of cost efficiency"); one prompt for both handoffs, one commit each: `0566703` (MH-2) and `97ac87d` (MH-3). The agent reported MH-2 red 16 failed (no error), green 34 and 90 passed; MH-3 red one collection error (as the spec says), green 30 passed; black, ruff, and the mypy gate (0 new) clean for both.

- Deviations reported by the agent: some MH-2 tests pass `FakeValidator({})` where the spec table names only `writer_for()` (the checks are the same, and the fake validator keeps the tests fast); it ran the MH-2 tests before black and not again after it (the full gate below covers that); its first edit left a duplicate `details` block in `run_writer_suite`, which it removed before any test run.
- Claude check (diff at each commit): the code matches the specs. Small differences from the reference: `run_writer_suite` makes the router before it loads the pairs, and the allow-list message says "not on the writer allow-list". `test_scam_suite.py` changed only in the one assertion (black wraps it).
- Claude check (scratch clone at `97ac87d`): the test names match the specs (14 and 12 functions). Mutants on the agent's code: MH-2 11 of 11 caught, MH-3 11 of 11 caught. Full gate: black and ruff pass on the CI paths, the mypy gate has 0 new errors (179 known), pytest 1994 passed (1948, plus 18, 16, and 12). `main.py eval --help` shows `--model`, `--samples`, and the writer example.
- Tokens and cost (session export): 34 steps, none above the 100K tier, largest prompt 87,600 tokens, about USD 0.049 for both handoffs.

## Baseline run and a problem with the main metric (2026-11-02, Claude, with the user's approval for the GPU time)

The four runs started at 20:58 (`run_models.sh`, baseline first). Baseline `qwen2.5:7b`, 20:58 to 21:11: 195 letters written, 0 fallback, 0 other model, 0 errors; peak VRAM 6,656 MiB (suite and watchdog). MLflow run `66ea7f014fc2461db21f916f087f055c`, report `data/eval/writer/20261102T131044235540Z.json`.

| Metric | `qwen2.5:7b` |
|--------|--------------|
| `ungrounded_claims_rate` | 1.000 (195 of 195) |
| ungrounded sentences in each letter | 1 to 8 (4 letters with 1; median 4) |
| `scope_inflation_rate` | 0.205 |
| `fabricated_technology_rate` | 0.000 |
| `fabricated_experience_rate` | 0.010 |
| `analogical_claim` (not a ranked check) | 25 of 195 |
| `valid_rate`, mean score | 0.851, 90.52 |
| words p50, latency p50 and p95 | 243, 2.9 s and 3.5 s |

Problem: the main metric is at its ceiling. The validator flags at least one ungrounded sentence in every letter, so the letter-level share is 1.0, and the paired rule of the plan cannot show a difference (a model that is also at 1.0 gives differences of 0, so the rule says `keep` for any such model). The plan took the letter-level precision 0.875 from the 10 real letters of Step 3.2, but all of those letters had real errors, so that number did not measure flags on clean letters; on the constructed main set the letter-level precision was 0.523, and the sentence-level precision is 0.15 to 0.18 on every set. The plan's assumption was wrong.

Proposed secondary analysis, committed at 21:12:23 (`b442783`), after the baseline and while `qwen3.5:4b` was running (started 21:11:31), before any other model's run ended (Claude has not seen another model's numbers). The runs after the baseline report this commit as their git SHA; it changed only `tasks/`, so the code is the same. The user decides whether to use it:

- S1, the main secondary metric: for each pair, the mean number of flagged ungrounded sentences in each letter; the paired difference against the baseline, with the same bootstrap (2,000 resamples, seed 0). Limit: most flagged sentences are false flags (sentence precision 0.15 to 0.18), and longer letters can have more flags, so the report also gives the words for each model.
- S2: the `scope_inflation` share for each pair (the only check with precision and recall 1.0 on the real letters, but with support 2), with the same paired bootstrap.
- Rule: change the default writer only when the S1 interval is below 0, the S2 interval is not above 0, and the `fabricated_technology` rate is not higher. Else keep `qwen2.5:7b`.
- The original rule is also reported, as fixed in the plan.

The other three runs continue as approved: the letters do not depend on the metric, and the rows keep each letter's issues and sentence count, so either rule can use the same runs.

Decision (user, 2026-11-02, "Yes, use it", given while `gemma3:4b` was running): use the secondary analysis (S1, S2, and its rule) to choose the writer. The original rule is still reported. MH-4 (runner) adds the secondary analysis to `src/evaluation/writer_compare.py` and `--secondary` to the comparison script, so the numbers come from a command in the repository.

## MH-4 written and checked (2026-11-02, Claude)

`mh-4-secondary-analysis.md` (runner): `sentence_means`, `sentence_differences`, `mean_sentences`, and `compare_secondary` in `src/evaluation/writer_compare.py`, `--secondary` in `scripts/compare_writer_reports.py`, and `tests/unit/test_writer_compare_secondary.py` (11 tests). Scratch clone: red 10 failed and 1 passed (the test of the unchanged default output); black leaves the three files unchanged; ruff clean; 41 tests pass with the other writer tests; the mypy gate has 0 new errors. Mutants 10 of 10 caught (S1 reversed, S1 counts other rows, S1 rule on the low end, S2 ignored, S2 on the high end, technology ignored, no dataset check, script ignores `--secondary`, mean counts other rows, S2 on the wrong check). Runner test on a fresh clone: the red step failed, the 4 checks passed, commit `3b40763` on the clone, and the three files are the same bytes as the checked copies.

## All four runs and both analyses (2026-11-02)

The runs ended at 21:39; no model was loaded after them; the watchdog never stopped a run. Each run: 195 letters written, 0 fallback, 0 other model, 0 errors. Reports in `data/eval/writer/` (gitignored). Git SHA `662e9bd` (baseline) and `b442783` (the other three; only `tasks/` differs).

| Model | MLflow run | Peak VRAM | Latency p50 | Words p50 | Valid share | Mean score |
|-------|------------|-----------|-------------|-----------|-------------|------------|
| `qwen2.5:7b` | `66ea7f014fc2461db21f916f087f055c` | 6,656 MiB | 2.9 s | 243 | 0.851 | 90.5 |
| `qwen3.5:4b` | `b1268a2c64d243568208541326231987` | 5,848 MiB | 2.0 s | 185 | 0.703 | 85.5 |
| `qwen2.5:3b` | `3eecbd310e48427e8cc2d5175c500cd4` | 4,189 MiB | 1.6 s | 223 | 0.892 | 92.0 |
| `gemma3:4b` | `bd83bdb368c94a27935dd6c583be488e` | 5,890 MiB | 1.8 s | 160 | 0.938 | 82.7 |

Original rule (`scripts/compare_writer_reports.py`, baseline `qwen2.5:7b`, 65 pairs):

| Model | `ungrounded_claims` share | Mean pair difference (95% interval) | `fabricated_technology` | Decision |
|-------|---------------------------|-------------------------------------|-------------------------|----------|
| `qwen3.5:4b` | 0.969 | -0.031 (-0.056 to -0.010) | 0.010 | keep |
| `qwen2.5:3b` | 0.969 | -0.031 (-0.062 to -0.005) | 0.000 | switch |
| `gemma3:4b` | 0.856 | -0.144 (-0.195 to -0.092) | 0.000 | switch |

The original rule says `switch` for two models only because the baseline is at 1.0 on every pair: any model that leaves a few letters unflagged has an interval below 0.

Secondary analysis (the MH-4 reference code on a scratch clone, `--secondary`; the same numbers come from the repository command after MH-4 is applied):

| Model | Flagged sentences in a letter | S1 difference (95% interval) | `scope_inflation` share | S2 difference (95% interval) | Flags per 100 words | Decision |
|-------|-------------------------------|------------------------------|-------------------------|------------------------------|---------------------|----------|
| `qwen2.5:7b` | 3.96 | | 0.205 | | 1.63 | baseline |
| `qwen3.5:4b` | 2.97 | -0.99 (-1.27 to -0.73) | 0.026 | -0.18 (-0.25 to -0.11) | 1.61 | keep (technology 0.010) |
| `qwen2.5:3b` | 3.10 | -0.86 (-1.11 to -0.60) | 0.113 | -0.09 (-0.15 to -0.04) | 1.37 | switch |
| `gemma3:4b` | 1.71 | -2.25 (-2.56 to -1.94) | 0.005 | -0.20 (-0.27 to -0.13) | 1.15 | switch |

Other checks of the validator (letters out of 195; not part of either rule):

| Check | `qwen2.5:7b` | `qwen3.5:4b` | `qwen2.5:3b` | `gemma3:4b` |
|-------|--------------|--------------|--------------|-------------|
| `too_short` | 0 | 20 | 5 | 89 |
| `poor_structure` | 0 | 0 | 3 | 85 |
| `no_call_to_action` | 33 | 182 | 23 | 186 |
| `missing_job_title` | 17 | 55 | 0 | 46 |
| `missing_selected_project` | 6 | 0 | 20 | 0 |
| `technique_mismatch` | 2 | 8 | 13 | 12 |
| `analogical_claim` | 25 | 41 | 18 | 6 |
| `fabricated_experience` | 2 | 13 | 3 | 3 |

What the results show:

- The secondary rule has two models that qualify and no rule to choose between them.
- `gemma3:4b` has the fewest flags, but its letters are short (median 160 words; 89 `too_short`, 85 `poor_structure`, 186 without a call to action) and its mean score is the lowest. Part of its S1 drop comes from length: S1 counts flags in a letter, and a short letter has fewer sentences. Per 100 words it is still lower (1.15 against 1.63).
- `qwen2.5:3b` qualifies with letters of nearly the same length (223 words), a higher valid share and mean score than the baseline, fewer flags per 100 words (1.37), less scope inflation, the lowest latency and VRAM. It has more `technique_mismatch` (13 against 2) and more `missing_selected_project` (20 against 6).
- `qwen3.5:4b` is out under both rules (`fabricated_technology` 0.010) and has 13 letters with `fabricated_experience`.
- Limit: most flagged sentences are false flags (sentence precision 0.15 to 0.18), and the validator does not see analogical claims in real letters. The numbers rank how often the rules fire, not a measured error rate.

Decisions (user, 2026-11-02): the decision log recommends `qwen2.5:3b` as the default writer (Claude's recommendation; the Settings default is a separate change, now in the backlog), and MH-4 is applied with the runner.

- MH-4 applied on the repo (Claude ran the runner on the user's word "Yes, apply it"): commit `9b49850`. The red step failed, and the 4 checks passed. The three files are the same bytes as the checked copies. `scripts/compare_writer_reports.py --secondary`, run from the repository on the four reports, gives the same output as the scratch-clone run above.

## Review (2026-11-02, Claude)

- Goal met: the writer choice in `docs/decision-log.md` rests on 65 profile-job pairs of the grounding set with 3 letters each (780 letters over four models), not on 3 synthetic cases. Recommended writer: `qwen2.5:3b`.
- The plan's main metric did not work: the validator flags every baseline letter, so the letter-level share was at its ceiling. The plan took the letter-level precision from real letters that all had errors, so it never measured flags on clean letters. The secondary analysis was fixed after the baseline and committed before the other results (`b442783`). Lesson: before a model comparison, check that the metric is below its ceiling on the baseline (one model run or a few letters) before the full set of runs.
- Work: 4 micro-handoffs. The runner applied MH-1 and MH-4 (full code). Claude Haiku 5.5 in opencode did the spec handoffs MH-2 and MH-3 in one prompt of a new session (about USD 0.049). Mutants: 11, 11, 11, and 10, all caught. Full gate at `9b49850`: black and ruff pass on the CI paths, the mypy gate has 0 new errors (179 known), pytest 2005 passed.
- GPU: four runs of about 10 minutes each, one model at a time, peak VRAM 4,189 to 6,656 MiB, no watchdog stop.
- Limits (also in the decision log): validator evidence only, false flags dominate, no analogical claims, first draft only, 3 synthetic profiles.

## Blockers / Questions
- None.
