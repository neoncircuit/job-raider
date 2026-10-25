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
- [x] A2. `scam` suite (committed set) and `emscad` suite (local CSV, seeded tuning and held-out parts) in `python main.py eval`, with unit tests and a mutation proof.
- [x] A3. Baseline on the committed set, and on the EMSCAD tuning part when the CSV is present. (Committed set: 2026-10-24, Cursor. EMSCAD tuning part: 2026-10-25, Claude, in `notes.md`.)
- [x] Review of Stage A (Claude, 2026-10-25, in `notes.md`). Result: rework the written cases and close the test gaps before Stage B.
- [x] AF1. Stage A fixes: the 34 written cases rewritten in their authors' voice, with the same IDs, forms, and labels; indicator groups assigned again; dataset checks S9 to S13 (decision 1 of 2026-10-25; `handoff-stage-a-fixes.md`).
- [x] AF2. Stage A fixes: tests that catch mutations M1 to M4, and the EMSCAD part in the MLflow run name and tags (decisions 2 and 3).
- [x] AF3. Baseline A3b on the reworked committed set.
- [x] Review of the Stage A fixes (Claude, 2026-10-25, in `notes.md`). Result: accept the set for Stage B, with four recorded limits.
- [x] B1. R3 fixes: word boundaries and phrase context for the `SUSPICIOUS_PATTERNS` and `ScamFilter.REJECT_PATTERNS` false positives, including `no.*interview` and `gift cards`, each measured, with unit tests per changed pattern written first (decision 7). One round over the fixed list of the B1 stop rule (decision 5), plus at most one fix round. (`handoff-stage-b.md`)
- [x] B2. Selection and settings, with no held-out run (`handoff-stage-b.md`):
    - a pipeline sweep, the S1 and S2 selection, and Wilson intervals;
    - the held-out guard;
    - the `scam_action` setting and one shared default for the threshold and the action (backend and Pipeline page);
    - `t*` and the action chosen on the EMSCAD tuning part and set as the defaults.
- [x] Review of Stage B part 1 (Claude, 2026-10-25, in `notes.md`). Result: accept B2; B1 needs its one fix round.
- [x] B1 fix round (the one that the B1 stop rule allows, decision 8), then the B2c selection again, and Claude's measure on probe set P2 (`handoff-b1-fix-round.md`).
- [x] Review of the B1 fix round (Claude, 2026-10-25, in `notes.md`). Result: accept FR2 and close B1 with its known limits; P2 17 of 25 correct (B1b 10, old code 10); the selection stays 1.00 and `flag`.
- [x] B3. CI gate on the committed set: count pins at `t*`, and detector-score pins for the hard negatives (decision 7). (`handoff-stage-b-part-2.md`)
- [x] B4. The notebook calls `python main.py eval emscad` for the tuning part only, so the logic exists only once; the docs state the default threshold and the `flag` action. (`handoff-stage-b-part-2.md`)
- [x] Review of Stage B part 2, part A (Claude, 2026-10-26, in `notes.md`). Result: accept B3 and B4; no fix round.
- [x] Check before B5 (Claude, 2026-10-26, in `notes.md`; all four items pass): the reviewed commit, the defaults, no held-out marker, and the user's decision on the CRLF rewrites. Then the user starts B5.
- [x] B5. The held-out part run one time, reported by rule S3, and the README numbers with the limits of EMSCAD and of B1. (`handoff-stage-b-part-2.md`)
- [ ] Done when: the README states precision and recall on the held-out EMSCAD part, and the committed set guards the false-positive cases.

## Status
`in-progress` (B5 done on 2026-10-26: one held-out run and the README numbers; waiting for the final review before archive)
