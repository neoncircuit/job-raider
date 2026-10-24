# Task: Step 3.3, Scam Set, then the R3 Fixes

## Goal
Measure the scam filter on a labeled set before any fix, then fix the false positives of review item R3 (`.*` patterns and plain substrings) and choose the threshold on data. The README states precision and recall on a held-out part of EMSCAD.

## Constraints & Context
- Parent task: `tasks/active/step-3-measurable-claims/` (Step 3.3). Plan, code observations, and decisions are in `notes.md`.
- The system under test is the pipeline decision: `ScamFilter.is_potential_scam` (quick reject) or `JobScamDetector.detect(...).is_scam` (threshold 0.7). The notebook scores only the detector.
- Measure first: labels before any detector run, and the baseline before any fix.
- EMSCAD (`fake_job_postings.csv`) is not committed (decision 3 of 2026-10-22). The user downloads it into `apps/backend-py/data/kaggle/` after checking the license. Its held-out part runs one time, after the threshold is chosen.
- No personal data in committed fixtures. Keep dry run as the default. Do not make auto-submit reachable.
- Two stages, each with a handoff in this folder and a review in `notes.md`: Stage A (set, suites, baselines), then Stage B (R3 fixes, threshold, held-out run, CI gate, notebook).

## Acceptance Criteria
- [x] A1. Labeling guide and `apps/backend-py/tests/fixtures/eval/scam/cases.jsonl` with at least 40 postings (legitimate fixture postings, written legitimate postings, hard negatives, and written scams for each indicator group), with structure and diversity tests.
- [ ] A2. `scam` suite (committed set) and `emscad` suite (local CSV, seeded tuning and held-out parts) in `python main.py eval`, with unit tests and a mutation proof.
- [ ] A3. Baseline on the committed set, and on the EMSCAD tuning part when the CSV is present.
- [ ] Review of Stage A (Claude).
- [ ] B1. R3 fixes: word boundaries and phrase context for the `SUSPICIOUS_PATTERNS` and `ScamFilter.REJECT_PATTERNS` false positives, each measured.
- [ ] B2. Threshold chosen on the EMSCAD tuning part; the held-out part run one time.
- [ ] B3. CI gate on the committed set (count pins in a thresholds file).
- [ ] B4. The notebook calls `python main.py eval emscad`, so the logic exists only once.
- [ ] Done when: the README states precision and recall on the held-out EMSCAD part, and the committed set guards the false-positive cases.

## Status
`in-progress` (Stage A handed to Cursor: `handoff-stage-a.md`)
