# Task: Step 3.2 Real Letters

## Goal
Measure the grounding validator on about 15 cover letters that the app generates for real shortlisted jobs with the real profile. This is the realistic false-positive measure that the constructed set and the holdout cannot give. It is the last open item of Step 3.2 (`tasks/active/step-3-measurable-claims/`).

## Constraints & Context
- Labels follow the guide in `apps/backend-py/tests/fixtures/eval/grounding/README.md`. Claude drafts them and the user corrects them (decision 1 of 2026-10-30 in `notes.md`). Nobody sees validator output for these letters before the labels are frozen.
- Privacy: the real profile, the letters, and the labels stay in `apps/backend-py/data/eval/grounding_real/` (gitignored). The scripts are committed, and their tests use synthetic data only. The hosted agent does not open `apps/backend-py/data/`.
- GPU: the generator loads the app's models one at a time and unloads them at the end. No agent model is loaded while it runs.
- The implementer is an agent in opencode (GLM-5.3-Flash Free or DeepSeek). Each micro-handoff gives its code and test in full. The agent reads `AGENT.md` and one `mh-*.md` file, nothing else.

## Acceptance Criteria
- [x] MH-A (`7465502`, checked 2026-10-30). `scripts/make_real_grounding_set.py` writes `profiles.json` and `letters.jsonl` (no validator output, no `cases.jsonl`) for up to 15 shortlisted jobs, one per company. (`mh-a-generator.md`)
- [x] MH-B (`befc870`, checked 2026-10-30). `scripts/build_grounding_label_page.py` writes a self-contained `label.html` with the draft labels filled in and an export of `labels.json`. (`mh-b-label-page.md`)
- [x] MH-C (`f7c5d7a`, checked 2026-10-30). `scripts/import_grounding_labels.py` turns `letters.jsonl` and `labels.json` into a valid `cases.jsonl`. (`mh-c-import-labels.md`)
- [x] Check of each handoff (Claude, in `notes.md`): the diff, mutation proofs, and the backend gate. Done 2026-10-30: MH-A, MH-B, and MH-C match their handoffs; 34 of 34 preview mutations caught; 1747 backend tests pass.
- [ ] The letters are generated, Claude drafts the labels, the user corrects them, and the labels are frozen.
- [ ] Done when: one `eval grounding` run on `data/eval/grounding_real` is recorded in `notes.md` with its command, dataset SHA-256, and MLflow run ID, and the 3.2 criterion in the Step 3 `task.md` is checked.

## Status
`in-progress` (2026-10-30: the tooling and three fixes are committed; 15 real letters generated; draft labels written; the user corrects them in `label.html`)
