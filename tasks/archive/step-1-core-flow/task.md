# Task: Step 1, Make the Core Flow Run

## Goal
A full-mode pipeline run goes from scrape to the submit stage in dry run. The CLI starts. CI catches new type errors. The UI shows real progress and does not send POST requests two times.

## Constraints & Context
- Do not make auto-submit reachable. Detection and submission stay as they are until the Easy Apply decision in Step 5.
- Keep dry run as the default in every layer.
- The plan, the sub-steps 1.1 to 1.7, and the decisions are in `notes.md`.

## Acceptance Criteria
- [x] Steps 1.1 to 1.7 are done and pushed (last: `5a8232f`).
- [x] Backend checks in CI (run 39188312697).
- [x] Frontend checks in CI (run 39188312697).
- [x] Manual: start a full-mode dry run from the Pipeline page with Ollama running. The stage list moves during the run, and the run reaches `submit_applications` with zero real submissions. Done 2026-10-30: runs `run_18ae691859d2` and `run_8e8837ffb270` (see `notes.md`).

## Status
`done` (2026-10-30).
