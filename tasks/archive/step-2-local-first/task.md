# Task: Step 2, Make Local-First True

## Goal
Resume text and API keys stay on the machine by default. Cloud LLM use is opt-in, logged, and visible in the UI. Auth is on unless the user sets an explicit bypass. The API is not reachable from other devices on the network by default.

## Constraints & Context
- The plan, the review (R1 to R11a), and the decisions are in `notes.md`.
- The Cursor handoffs are in this folder. `handoff-2026-10-19.md` and `handoff-step2.md` are not in git (the user decides).

## Acceptance Criteria
- [x] Steps 2.1 to 2.6.
- [x] Review items R1 to R11a.
- [x] Pushed (last: `629eb69`); CI run 39630302033 passed all 11 jobs, and Playwright had 42 passed with 0 flaky.

## Status
`done` (2026-10-21). One open question, not blocking, is in `tasks/backlog.md`: allow LinkedIn country hosts such as `sg.linkedin.com`.
