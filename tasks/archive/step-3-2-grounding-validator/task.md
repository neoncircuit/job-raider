# Task: Step 3.2, Grounding Set and Validator Fixes

## Goal
A labeled grounding set, and validator fixes that are measured on it before and after each change, with one holdout run and a CI gate.

## Constraints & Context
- The full record is in `notes.md`: the labeling rules, Baselines 1 to 3b, the fix plan and the review of each round (F1 to F7, F5a, F6a, F5b, F6b, and the curly-apostrophe fix), D5 and D6, the known limits of the rule checks, the holdout run, and the CI gate. The Cursor handoffs are in this folder.
- The holdout set is spent: a later round of fixes needs a new holdout set.
- To distill at Step 3.9: the known limits of the rule checks and the dataset limit (templated filler) belong in `docs/` with the README numbers.

## Acceptance Criteria
- [x] Labeling guide and 65 constructed cases (`apps/backend-py/tests/fixtures/eval/grounding/`).
- [x] Validator fixes F1 to F7, F5a, F6a, F5b, F6b, and the curly-apostrophe fix, each with tests and a mutation proof.
- [x] Dataset pass D5 and D6 (sentence-level `ungrounded_claims`), and Baseline 3b.
- [x] The one holdout run (2026-10-24).
- [x] The CI gate on pinned counts (`apps/backend-py/tests/fixtures/eval/grounding/thresholds.json`).
- Moved, not done: the set of about 15 real generated letters is an open criterion of `tasks/active/step-3-measurable-claims/task.md`.

## Status
`done` (2026-10-24), pushed in `2a1f202..9ef70c5`.
