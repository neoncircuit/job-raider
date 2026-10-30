# Task: Handoff Runner

## Goal
Apply a micro-handoff without an LLM agent. A script reads a handoff file, writes its new files and exact edits, runs its "red" command (must fail) and its "Done when" commands (must pass), and commits with the given message. No model, no GPU, no quota. Claude keeps writing, dry-running, and checking each handoff.

## Constraints & Context
- Why: the free opencode quota ran out during MH-A of `tasks/active/step-3-2-real-letters/`, and no local model (7B or smaller, below the BSOD limit) finished a handoff in opencode or Aider. The handoffs already give the complete code and the exact edits, so the agent only types and runs commands (decision of 2026-10-30, the user: "Handoff runner").
- The handoffs stay readable for people and for agents: the runner reads attributes in the fenced-block info string (` ```python new=<path>`), which Markdown shows as a normal code block.
- Safety: the runner checks everything before it writes; it touches only the files that the handoff names, never `apps/backend-py/data/` or `.env` files; it stops when files are staged or when a file to edit has other changes; on any failure it restores every file and does not commit.
- Stdlib only. The script lives in `apps/backend-py/scripts/` and its tests in `apps/backend-py/tests/unit/`, so CI runs them.
- Built by Claude in this session, test-first (the agent is not available).

## Acceptance Criteria
- [x] `scripts/run_handoff.py` with the format in `notes.md`: `new=`, `edit=` (one OLD/NEW pair, the old text exactly once), `red`, `check`, `commit`, and `cwd=`.
- [x] A validation pass before any write, a rollback on any failure, and a `--dry-run` that only prints the plan.
- [x] Tests in temporary git repositories: a full run commits; each validation error stops before a write; a failing check and a passing red command roll back with no commit; staged files stop the run. (19 tests; 16 of 16 mutations caught.)
- [x] MH-B and MH-C of `step-3-2-real-letters` use the format, and a dry run of each passes.
- [x] `docs/handoff-runner.md` (format, safety rules, flow diagram, labeled commands), and `tasks/index.md` points to it.
- [x] Done when: the runner applies MH-B for real (red fails, checks pass, one commit), and Claude checks that commit like an agent's commit. Done 2026-10-30: MH-B `befc870` and MH-C `f7c5d7a`, both the same as their handoffs; 1747 backend tests pass.

## Status
`done` (2026-10-30). Review in `notes.md`.
