# Notes: Measure and Reduce Generic Phrasing

## Step 1: Detector (2026-11-12, scratch clone)

- `src/generation/generic_phrasing.py`: 51 phrases in 5 groups (opening 9, self-description 15, filler 19, closing 4, CV filler 4). Whole-word, case-insensitive; a space or hyphen matches either; a curly apostrophe matches a straight one; overlapping phrases count once (longest first).
- `tests/unit/test_generic_phrasing.py`: 15 tests pass.
- Checks on the clone: black and ruff clean on the CI scope. mypy gate with the CI pins (`mypy==2.4.0`, `types-requests==2.33.0.20261006`, `types-PyYAML==6.0.12.20260906`): 177 known errors, 0 new.
- Found on the way (not in this task): the local `.venv` does not install the CI type-check pins (it has mypy 2.4.1 and no stub packages), so the local gate on `main` reports 2 errors in `jobstreet_scraper.py` and `mycareersfuture_scraper.py` that CI does not. Follow-up: install the CI pins in the local environment.

## Step 2: Precision check on the real letters (2026-11-12)

Run on `data/eval/grounding_real/letters_all.jsonl` (the 15 letters of Step 3.2). The script printed counts only; no letter text was read or shown.

- 12 of 15 letters have at least one hit. Hits per letter: 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 4. Hits per 100 words: median 0.32, highest 1.11.
- Phrases found (hits / letters): "i am confident that" 7/7, "i am excited to apply" 4/4, "cutting-edge" 3/3, "leverage my" 2/2, "invaluable" 1/1, "furthermore" 1/1. The other 45 phrases had no hits.
- "i am excited to apply" is in 4 of 15 letters, although rule 7 of the cover letter prompt bans it by name. A prompt rule alone does not stop the model.

- The user kept all 51 phrases (2026-11-12).

## Step 3: Writer suite metrics (2026-11-12, scratch clone)

- `src/evaluation/suites/writer.py`: each written letter goes through the detector. Rows keep `generic_phrases` (one entry per occurrence) and `generic_per_100w`. New metrics: `generic_phrasing_rate` (share of written letters with one or more hits) and `generic_per_100w_p50`. Fallback and other-model letters are not analysed.
- Tests: 2 new tests in `tests/unit/test_writer_suite.py` with a fake writer (expected values worked out by hand: rate 0.667, median 16.67 per 100 words).
- Red step: with the suite change reverted, both new tests fail. Mutants: counting all rows instead of written letters survived, because fallback rows never have phrases, so the result is the same (an equivalent mutant). Analysing letters before the fallback check is caught, after a test assertion was added on the fallback row.
- Full checks on the clone: black and ruff clean, mypy gate with the CI pins 177 known and 0 new, pytest 2,265 passed.
- Clone commit: steps 1 and 3 together.

## Steps 1 and 3 applied on main (2026-11-12)

- The user said "yes, apply it". `main` was fast-forwarded to the clone commit (its parent was the tip of `main`), so `main` holds the checked commit; `git diff` against it (without `tasks/`) is empty. 4 files: the detector, its tests, the suite change, its tests.
- The new tests pass with the real `.venv` too (35 passed). Not pushed yet.
- GPU before the baseline: no model loaded, but 4,463 MiB of the 8 GB already in use, 2,747 MiB of it by `dwm`. RuneScape was not running.

## Step 4: Baseline (2026-11-12)

Run: `main.py eval writer --model qwen2.5:7b --samples 1`, 12:33 to 12:39 UTC, on `main` with steps 1 and 3 (no prompt or validator change). 65 letters written, 0 fallback, 0 other model, 0 errors, all by `qwen2.5:7b` (still the default writer: the switch to `qwen2.5:3b` was reverted on 2026-11-05). Peak VRAM 5,704 MiB. MLflow run `77fa2c72eb7449f6a45bd1fa47c79942` (local store `data/mlflow.db`, see below). Report: `data/eval/writer/20261112T123857641056Z.json`.

Conditions: 4.8 hours after a Windows restart; RAM about 0.5 GB free with heavy paging; Brave still had 13 processes; GPU 1,369 MiB in use before the model loaded. Latency may be higher than on a quiet machine.

| Metric | Baseline |
|--------|----------|
| `generic_phrasing_rate` | 0.831 (54 of 65 letters) |
| `generic_per_100w_p50` | 0.50 |
| `ungrounded_claims_rate` | 1.000 (at its ceiling, as in Step 3.8) |
| ungrounded sentences in a letter | 1 to 9 |
| `scope_inflation_rate` | 0.246 |
| `fabricated_technology_rate`, `fabricated_experience_rate` | 0.000, 0.015 |
| valid share, mean score | 0.831, 91.43 |
| words p50, latency p50 and p95 | 244, 3.0 s and 3.6 s |

Phrases (occurrences over 65 letters): "i am confident that" 36, "i am excited to apply" 21, "invaluable" 11, "proven track record" 6, "responsible for" 4, "furthermore" 4, "i am writing to express my interest" 3, "moreover" 2, "i am writing to apply" 2, "a testament to" 1, "tasked with" 1, "cutting-edge" 1. Three of the top phrases are banned by name in the current prompt ("i am excited to apply", "i am writing to express my interest", "proven track record").

Findings:
- The planned guard "`ungrounded_claims` rate not higher" cannot show a change: the rate is 1.0 (Step 3.8 found the same ceiling, 195 of 195). Step 3.8 used the mean flagged sentences per letter (S1, paired bootstrap) and the `scope_inflation` share (S2) instead (`scripts/compare_writer_reports.py --secondary`).
- MLflow store (corrected 2026-11-12): without `MLFLOW_TRACKING_URI`, eval runs log to `apps/backend-py/data/mlflow.db` (by design, `src/evaluation/report.py`). This store did come across in the move: the Step 3.8 baseline run `66ea7f01...` and this run are both in experiment 1. Claude first concluded that the store was new, because MLflow printed "Creating initial MLflow database tables"; MLflow prints that line each time it opens a SQLite store. The real problem: the experiment and its runs still record the artifact folder as `file:///mnt/d/GitHub/job-raider/apps/backend-py/data/mlartifacts`, so this run wrote its JSON report artifact into the D: backup. The artifact files were copied to WSL in the move (58 files, all equal to the D: copies), but MLflow does not use that copy.

## MLflow artifact paths fixed (2026-11-12, user approved)

- Backup: `data/mlflow.db.bak-2026-11-12` (equal to the store before the fix).
- One transaction rewrote the D: paths: `file:///mnt/d/GitHub/job-raider/` to `file:///home/jamestjy/personal-projects/job-raider/` (1 experiment, 59 runs), and the plain path `/mnt/d/GitHub/job-raider/` to `/home/jamestjy/personal-projects/job-raider/` (experiment 0, "Default"). The first try found the plain-path row with its safety check and rolled back; nothing was committed then.
- Today's artifact moved from the D: backup to `data/mlartifacts/77fa2c72.../` (copy checked with `diff -r`, then removed from D:). The D: artifact folder has its 58 files from before today.
- Check through MLflow: 2 experiments, 59 runs, 0 runs with a missing artifact folder, 0 rows on `/mnt/d`. The baseline run and the Step 3.8 run list their artifacts from the WSL folder.

## Step 5: Changes (2026-11-12, new scratch clone; the first one was cleared with the scratchpad)

- Validator (`cover_letter_validator.py`): the detector runs over the whole letter. Opening-group phrases keep `GENERIC_OPENING` (-20, as before); other stock phrases give the new `GENERIC_PHRASING` (-5 each, up to -20). Classic style skips the opening and closing groups. `details` has `generic_phrases` (one entry per occurrence); `has_generic_opening` and `has_call_to_action` stay. `GENERIC_OPENINGS` (5 phrases) is gone. Deviation from the plan: `GENERIC_OPENING` was kept, not replaced, so saved results and the frontend type list stay valid and the opening keeps its own penalty.
- Call to action: a closing passes when it has one of the old phrases or asks for a next step (`CALL_TO_ACTION_INTENT`: discuss, conversation, chat, call, interview, meeting, walk you through, next steps, hear from/back, and speak/talk/meet/connect followed by with/about/soon/further). A first version matched a bare "speak" ("my results speak for themselves"); it was tightened before the tests.
- Grounding is unchanged: `cover_letter_grounding` skips sentences with `CALL_TO_ACTION_PHRASES`, and that list stays as it was, so S1 measures the same thing before and after. A test pins the list.
- Writer (`cover_letter_writer.py`): modern rule 9 and classic rule 8 list the detector's phrases (`phrases_for_prompt`; classic without the opening and closing groups). The modern prompt is about 160 words longer. Model output goes through `strip_invisible_characters` (`text_normalizer.py`) at the 3 places that read the model's text.
- Frontend: `generic_phrasing` added to `CoverLetterIssue` in `src/lib/types/api.ts`. The UI makes the label from the name ("Generic Phrasing").
- Generic phrasing is a soft issue: `cover_letter_service` rewrites only on hard-fail issues, so it does not start a rewrite.
- Tests: 15 new (validator 7, writer 3, normalizer 3, prompt helper 2). Red step: 13 fail without the source change; the 2 that pass are guards (a closing without an ask stays flagged; the grounding list is unchanged). Mutants: bare "speak" as an ask, a wider grounding list, no penalty cap, classic skipping nothing: 4 of 4 caught.
- Full checks on the clone: black and ruff clean (one import-order fix by ruff), mypy gate with CI pins 177 known and 0 new, pytest 2,280 passed; frontend tsc, eslint, prettier clean, vitest 378 passed.
- The existing `GOOD_COVER_LETTER` fixture in `tests/test_cover_letter_validator.py` now gets `GENERIC_OPENING` and `GENERIC_PHRASING` ("I am excited to apply", "results-driven"); its tests do not check tone issues and still pass. Not changed.
- Clone commit `6e7acdd` (on top of `301372b`). The clone's default cover-letter route is Ollama `qwen2.5:7b` with no fallback, so the after run can run from the clone, before anything lands on `main`.

## Step 6: After run (2026-11-12) - guard fails

Run from the clone at `6e7acdd`: `main.py eval writer --model qwen2.5:7b --samples 1`, 13:44 to 13:48 UTC, logged into the real store (`MLFLOW_TRACKING_URI=sqlite:///.../apps/backend-py/data/mlflow.db`). MLflow run `be2f389063ab4e79acf014002cdee5c8`; artifact in the WSL `data/mlartifacts` (none on D:). Report: `data/eval/writer/20261112T134829788555Z.json`. 65 written by `qwen2.5:7b`, 0 fallback, 0 other model, 0 errors; peak VRAM 6,402 MiB; model unloaded after. Conditions: GPU 2,130 MiB in use before, RAM 2.0 GB free, 332 pages/sec, Brave running (15 processes).

| Metric | Baseline | After |
|--------|----------|-------|
| `generic_phrasing_rate` | 0.831 (54 of 65) | 0.892 (58 of 65) |
| stock phrase occurrences | 92 | 100 |
| `generic_per_100w_p50` | 0.50 | 0.61 |
| S1: flagged ungrounded sentences per letter | 3.708 | 4.185 (difference +0.477, 95% interval +0.031 to +0.908) |
| S2: `scope_inflation` share | 0.246 | 0.185 (difference -0.062, 95% interval -0.215 to +0.077) |
| `fabricated_technology_rate`, `fabricated_experience_rate` | 0.000, 0.015 | 0.000, 0.031 |
| words p50, latency p50 | 244, 3.0 s | 248, 3.4 s |
| valid share, mean score | 0.831, 91.43 | 0.800, 86.29 (not comparable: the validator changed) |

`compare_writer_reports.py --secondary` decision: keep (the baseline).

Phrases (baseline to after): "i am confident that" 36 to 40, "i am excited to apply" 21 to 13, "invaluable" 11 to 13, "proven track record" 6 to 9, "moreover" 2 to 4, "i am writing to express my interest" 3 to 0, "i am writing to apply" 2 to 0, and new: "feel free to contact me" 0 to 3, "thank you for your time and consideration" 0 to 2, "leverage my" 0 to 2, "detail-oriented" 0 to 1.

Result: the guard fails on the stock-phrase rate (higher) and on S1 (interval above 0). Step 5 is not applied to `main`. Reading: the opening bans partly worked, but a list of 51 "never use" phrases seems to prime the 7B model to use some of them, and the longer prompt may weaken the grounding rules. Limit: 1 letter per pair at temperature 0.8, so part of the change is noise; nothing points to an improvement.

## Item 1: keep the safe parts of step 5 (2026-11-12, user approved)

- On the clone, the prompt change was reverted: modern rule 9 and classic rule 8 are the original 4-phrase rule again, and the writer prompt text is the same as on `main`. `phrases_for_prompt` and its 4 tests were removed (no use left). The writer differs from `main` only by `strip_invisible_characters` at its 3 output points.
- Kept: the validator (`GENERIC_PHRASING`, whole-letter detector, call to action by intent, grounding list unchanged), the normalizer, the frontend issue type.
- No new eval run is needed for this part: the prompt is the baseline prompt, so the letters do not change; the validator only scores them.
- Checks: black and ruff clean, mypy gate with CI pins 177 known and 0 new, pytest 2,276 passed (2,280 minus the 4 removed tests). Frontend unchanged since step 5 (tsc, eslint, prettier, vitest 378 passed).
- The clone commit was replaced (amend) so that `main` never gets the failed prompt change: `c241b8d` on top of `301372b`, 7 files.

- Applied (user approved, 2026-11-12): `main` fast-forwarded to `c241b8d`; `git diff` against it (without `tasks/`) is empty. Not pushed yet.

## Attempt 2 built: targeted sentence rewrite (2026-11-12, scratch clone)

- `src/generation/stock_phrase_polish.py`: `polish_stock_phrases(router, content, style, model)` picks up to 5 sentences with stock phrases (`split_letter_sentences`; classic skips the opening and closing groups), makes one call on the cover-letter route (temperature 0.2, max 600 tokens, no thinking), and names only the phrases each sentence uses. `accept_sentence`: not empty, no stock phrase, no new number, at most 1.5 times the old word count plus 5 words. A wrong answer format or an error keeps the letter. Accepted sentences replace the old ones in place (first match, any whitespace between words). A greeting joined to a sentence ("Dear team, ...") is never sent or changed.
- `CoverLetterWriter.write` calls it after the output cleanup; `GeneratedCoverLetter.stock_phrase_edits` counts the replaced sentences; the writer suite rows keep `stock_phrase_edits`. `rewrite` and `write_why_interest_block` do not call it.
- Limit: the token fields of the letter count only the writer call, not the polish call.
- Tests: 14 in `tests/unit/test_stock_phrase_polish.py` and 1 writer-level test. 4 existing writer tests read the most recent router call; they now read the writer's own (first) call, and `test_successful_generation` states the 2 calls.
- Red step (the step returns the letter unchanged): 10 tests fail. Mutants: no stock-phrase check on rewrites, no new-number check, greeting sent and replaced, exact-text splice only, no sentence cap: 5 of 5 caught.
- Full checks: black and ruff clean, mypy gate with CI pins 177 known and 0 new, pytest 2,291 passed. Frontend unchanged.
- Clone commit `da2bcc1` on top of `c241b8d` (= `main`).

## Attempt 2 measured (2026-11-12 15:30 to 16:05 UTC) - guard passes

Run from the clone at `da2bcc1`, same settings as the baseline, logged into the real store. MLflow run `6da45e1ca53a4b5599ceade95c22a4f6`; artifact in the WSL `data/mlartifacts` (none on D:). Report: `data/eval/writer/20261112T160416996870Z.json`. 63 written by `qwen2.5:7b`, 2 template fallback, 0 other model, 0 errors; peak VRAM 6,409 MiB; model unloaded after.

| Metric | Baseline | Attempt 2 |
|--------|----------|-----------|
| `generic_phrasing_rate` | 0.831 (54 of 65) | 0.095 (6 of 63) |
| stock phrase occurrences | 92 | 14 |
| `generic_per_100w_p50` | 0.50 | 0.00 |
| S1: flagged ungrounded sentences per letter (63 pairs) | 3.708 | 3.794 (difference +0.095, 95% interval -0.476 to +0.651) |
| S2: `scope_inflation` share | 0.246 | 0.175 (difference -0.079, 95% interval -0.238 to +0.063) |
| `fabricated_technology_rate`, `fabricated_experience_rate` | 0.000, 0.015 | 0.000, 0.016 |
| words p50 | 244 | 240 |
| latency median, max (s) | 3.03, 59.5 | 3.94, 335.6 |

Polish step: 55 letters had at least one target sentence. 49 had all their target sentences replaced (1 sentence: 18, 2: 16, 3: 12, 4: 3); in 6 the answer was not in the numbered format, so the letter was kept. Phrases left in the written letters: "i am confident that" 3, "i am excited to apply" 2, "invaluable" 2, "proven track record" 2, and 1 each of "furthermore", "i am writing to apply", "leverage my", "moreover", "responsible for".

Guard: the stock-phrase rate is lower; the S1 and S2 intervals are not above 0. The guard passes. (`compare_writer_reports.py` printed "decision: keep"; that line is the writer-model switch rule of Step 3.8, not this guard.)

Limits:
- 63 of 65 pairs: the 2 fallback letters came from the writer's own call timing out after 120 s (at 23:43 and 23:52 local time), not from the polish step. The first 25 minutes of the run were slow for a reason these logs do not show (GPU peak was normal; Brave was running); from about 23:59 letters came at the normal rate. This made the run 35 minutes long.
- The median cost of the step is about 0.9 s per letter.
- 1 letter per pair at temperature 0.8: the S1 interval is wide.

- Applied (user approved, 2026-11-13): `main` fast-forwarded to `da2bcc1`; `git diff` against it (without `tasks/`) is empty. Not pushed yet.

## Push and CI (2026-11-13)

- The user approved the push. `main` was pushed to `origin` with the detector, the validator changes, the targeted rewrite, and the task notes.
- CI run 43265943842 passed: 12 jobs passed, `Build Docker Image` skipped (push run). Backend 2,291 passed; frontend unit 378 passed; `Test Frontend (E2E Tests)` 45 passed; `Test Demo (E2E on the Static Site)` 18 passed.
- Cover letters are done. Step 7 (CVs) is open.

## Step 7 built: stock phrases in CVs (2026-11-13, new scratch clone; the old one was cleared again)

- `src/generation/validator.py`: `ValidationResult.generic_phrases` (one entry per occurrence, default empty). `_stock_phrases` runs the detector on the summary, experience highlights, and project descriptions and highlights only. Both `validate` and the LLM path of `validate_with_llm` fill it. The score, recommendation, and issues do not change.
- `src/pipeline/stages_generate.py`: each generated item keeps `generic_phrases`; one log line per CV with hits; stage metadata `resumes_with_stock_phrases` (count) and `resume_stock_phrases` (job ID to phrases, only CVs with hits). The file has 215 lines (limit 600).
- Status API: `resumes_with_stock_phrases` in `PipelineStatusResponse`, read from the Generate Resumes metadata (0 for older runs).
- Pipeline page: the resume line adds " · N with stock phrases" when N is above 0; `resumes_with_stock_phrases` added to `PipelineStatusResponse` in `api.ts`.
- CV writer prompt unchanged (no CV eval suite).
- Tests: 4 validator (`tests/unit/test_resume_stock_phrases.py`: prose only with stock phrases in the title, company, and project name on purpose; skill names; score unchanged; LLM path), 2 stage, 2 status API, 1 Vitest. Red step: all 9 fail without the source change. Mutants: titles and names counted, LLM path without phrases, map listing CVs without phrases, API reading the wrong key, page suffix at 0: 5 of 5 caught.
- Full checks on the clone: black and ruff clean, mypy gate with CI pins 177 known and 0 new, pytest 2,299 passed; frontend tsc and eslint clean, Prettier clean after one formatting fix in `page.tsx`, Vitest 379 passed. No E2E test reads the resume line (the E2E mock API does not send the new field), so E2E runs in CI after the push.
- Clone commit `f4891ab` on top of `607399b` (= `main`).

- Applied (user approved, 2026-11-13): `main` fast-forwarded to `f4891ab`; `git diff` against it (without `tasks/` and `docs/lessons.md`) is empty. Not pushed yet.
- Checks on `main` with the real environments after the apply: pytest 2,299 passed; frontend tsc clean, Vitest 379 passed.

## Push and CI for the CV step (2026-11-13)

- The user approved the push. `main` was pushed to `origin` with the CV step and the docs commit.
- CI run 43357140402 passed: 12 jobs passed, `Build Docker Image` skipped (push run). Backend 2,299 passed; frontend unit 379 passed; E2E 45 passed; demo E2E 18 passed.

## Review (2026-11-13)

The user asked to link Turnitout-Humanizer so that cover letters and CVs do not sound generic. It could not be linked (no engine code, a closed cloud API, a license that forbids use, and personal letters would leave the machine), so the same goal was met inside the project, local and measured.

- Measurement: a deterministic detector (51 stock phrases in 5 groups), checked on the 15 real letters (counts only), and two metrics in the writer eval suite.
- Cover letters: a baseline with `qwen2.5:7b` (stock phrases in 83% of letters). Attempt 1 (all phrases listed in the prompt) failed its guard and was not applied. Attempt 2 (a checked rewrite of only the sentences with stock phrases) brought the share to 9.5% with the grounding measures not worse, at about 0.9 s more per letter. The validator now flags stock phrases over the whole letter and accepts a call to action in any wording.
- CVs: each generated CV reports its stock phrases (no prompt change, because there is no CV eval suite); the Pipeline page shows how many CVs have them.
- Found on the way: the moved MLflow store still pointed its artifacts at the D: copy (fixed with a backup), and the local `.venv` does not have the CI type-check pins (in Next Up).
- Open: a CV eval suite (optional, in Next Up).
