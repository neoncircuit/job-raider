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
- [x] Review of Stage A (Claude, 2026-10-26, in `notes.md`), including a private probe set of pairs that Cursor has not seen. Result: accept the Stage A code; the set leaks on the description, and the user's catalog labels (all `different`) contradict every merge rule; recommend "flag and keep" for Stage B (user decision).
- [x] B1. Flag and keep (decision 6, replaces the merge plan): `deduplicate` removes only a listing with the same `job_id`; possible duplicates stay and carry `metadata["possible_duplicates"]` (the other `job_id` and the reason: `same_url` or `same_company_title_location`). Unit tests per rule, written first. (`handoff-stage-b.md`)
- [x] B2. The suite measures the flag (identified = merged or flagged) and reports merged pairs on their own; findings 4 and 5 fixed; CI gate on the committed set (`thresholds.json` with the dataset SHA-256, the count pins, and 0 merged `different` pairs).
- [x] B3. The README pipeline table (stage 2), `docs/index.md`, and `docs/usage.md` state the rule and the measured numbers, with the command and the known limits.
- [x] Review of Stage B (Claude, 2026-10-26, in `notes.md`), with a new private probe set and the catalog check (no catalog pair merged). Result: accept Stage B; 0 merged `different` pairs on the committed set, the probes, and the catalog; eight small findings; one fix round recommended (user decision).
- [x] B4. Fix round (decision 7, the last round): findings 1 to 8 of the Stage B review, each with a test and a mutation proof (`handoff-stage-b-fix.md`).
- [ ] Check of the fix round (Claude, in `notes.md`), with the catalog check (no catalog pair merged). Then archive the task.
- [ ] Done when: the README states the duplicate-flag precision and recall on N labeled pairs with the command that reproduces them, CI fails when a `different` pair is merged, and the pipeline removes no listing other than a copy with the same `job_id`.

## Status
`in-progress` (Stage B fix round F1 to F4 done on 2026-10-26; waiting for the Claude check)
