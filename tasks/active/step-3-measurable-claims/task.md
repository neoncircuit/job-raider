# Task: Step 3, Make Claims Measurable

## Goal
Every number in the README and in the resume framing (review section 7) comes from a command in this repository that anyone can run again. Each fix in this step is measured on a labeled set before and after the change.

## Constraints & Context
- Measure first. For each fix (R2, R3, R4, R5, M7), record the baseline before the change and the numbers after it.
- No personal data in committed fixtures. Runs with the real profile stay local; their outputs stay in `apps/backend-py/data/` (gitignored).
- Deterministic suites run in CI without Ollama. Suites that need Ollama or embeddings run locally and log to MLflow.
- Keep dry run as the default. Do not make auto-submit reachable (Step 5).
- The plan of each open sub-step and the decisions of 2026-10-22 are in `notes.md`. Done sub-steps are in `tasks/archive/step-3-1-eval-harness/` and `tasks/archive/step-3-2-grounding-validator/`.

## Acceptance Criteria
- [x] 3.1 Eval harness and run metadata.
- [x] 3.2 Grounding set, validator fixes, holdout run, and CI gate.
- [ ] 3.2 About 15 real generated letters, labeled by the user and run locally (decision 1 of 2026-10-22): the realistic false-positive measure.
- [x] 3.3 Scam set, then the R3 fixes (`tasks/archive/step-3-3-scam-set/`; done 2026-10-26: held-out EMSCAD numbers in the README, CI gate on the committed set).
- [ ] 3.4 Ranking set, then the R4 and R5 fixes.
- [x] 3.5 Dedupe set, then the R2 fix (`tasks/archive/step-3-5-dedupe-set/`; done 2026-10-27: flag and keep, identified precision and recall in the README, CI gate with 0 merged `different` pairs).
- [ ] 3.6 Real cost and usage tracking (`tasks/active/step-3-6-cost-tracking/`).
- [ ] 3.7 Schema-constrained output and context size.
- [ ] 3.8 Model comparison on the grounding set.
- [ ] 3.9 README and resume numbers, with the known limits of the grounding rules (`tasks/archive/step-3-2-grounding-validator/notes.md`).
- [ ] Done when: the README can say "grounding validator: precision P and recall R per check on N labeled letters", with the command that reproduces it.

## Status
`in-progress`
