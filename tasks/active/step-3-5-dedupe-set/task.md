# Task: Step 3.5, Dedupe Set, then the R2 Fix

## Goal
Measure the listing deduplication on a labeled set of listing pairs before any fix. Then fix review item R2 (`deduplicate` compares `job_id` only, and the IDs carry a source prefix, so the same job from two sources is never merged). Report precision and recall before and after, and guard the result with a CI gate.

## Constraints & Context
- Parent task: `tasks/active/step-3-measurable-claims/` (Step 3.5). Plan, code observations, and the proposed decisions are in `notes.md`.
- The system under test is `JobListingCollection.deduplicate` (`apps/backend-py/src/models/job_listing.py:397-416`). The pipeline calls it in `stage_deduplicate` (`src/pipeline/stages.py:212-233`) and in `ScraperManager` (`src/scrapers/manager.py:142-143`).
- Measure first: labels before any run, and the baseline before any fix.
- No personal data in committed fixtures. The local catalog (`data/listings/catalog.json`) has recruiter names, emails, and phone numbers; no row of it goes into the repository.
- Keep dry run as the default. Do not make auto-submit reachable.
- Two stages, each with a handoff in this folder and a review in `notes.md`: Stage A (set, suite, baseline), then Stage B (R2 fix, CI gate, docs). One fix round at most after the Stage B review (the stop rule in `notes.md`).

## Acceptance Criteria
- [x] A1. Labeling guide `apps/backend-py/tests/fixtures/eval/dedupe/README.md` and `cases.jsonl` with at least 30 labeled pairs (`same` or `different`) in the classes of `notes.md` (cross-source copies, reposts, URL variants, and the hard negatives), with structure and diversity tests.
- [x] A2. `dedupe` suite in `python main.py eval dedupe` (pair decision through `deduplicate`; precision, recall, false-merge rate, per-class counts, per-pair rows, Wilson 95% intervals; MLflow), with unit tests and a mutation proof.
- [x] A3. Baseline on the committed set (Cursor). The local catalog pairs file is written. The user still labels its 20 pairs; Claude runs the local-only baseline on them in the Stage A review (decision 3; not committed).
- [ ] Review of Stage A (Claude, in `notes.md`), including a private probe set of pairs that Cursor has not seen.
- [ ] B1. R2 fix in `deduplicate`: match on `job_id`, then the normalized URL, then normalized company, title, and location, under the precision rule of decision 2. Unit tests per rule, written first.
- [ ] B2. CI gate on the committed set (`thresholds.json` with the dataset SHA-256 and the count pins), the same form as the scam gate.
- [ ] B3. The README pipeline table (stage 2) and the docs state the new rule and the measured precision and recall, with the command.
- [ ] Review of Stage B (Claude, in `notes.md`), with the private probe set.
- [ ] Done when: the README states the dedupe precision and recall on N labeled pairs with the command that reproduces them, and CI fails when a hard negative is merged.

## Status
`in-progress` (Stage A baseline is recorded in `handoff-stage-a.md`; user labels the 20 catalog pairs; Stage B waits for review)
