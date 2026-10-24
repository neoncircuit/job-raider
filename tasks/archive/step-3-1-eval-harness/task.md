# Task: Step 3.1, Eval Harness and Run Metadata

## Goal
One command, `python main.py eval <suite>`, writes a JSON report and an MLflow run with the git SHA and the dataset hash, so that each number can be traced to its code and data.

## Constraints & Context
- The plan items and the review are in `notes.md`. The usage is in `docs/usage.md` (Offline Evaluation).

## Acceptance Criteria
- [x] Shared pieces in `src/evaluation/`: case loader, metrics, and run metadata.
- [x] The `eval` command and the MLflow store.
- [x] Tests for the metrics, the metadata, and the report.
- [x] `python main.py eval grounding` on a small set writes a report and an MLflow run.

## Status
`done` (2026-10-22), pushed in `2a1f202`.
