# Notes: Review Follow-up

This text moved here from `tasks/todo.md` on 2026-10-24, without changes. Paths in it are as of that date: a reference to a section of `tasks/todo.md` now means a section of this file or of another task's `notes.md`, and a `tasks/handoff-*.md` file is now in its step's task folder (Step 2 and Step 3.2 handoffs are in `tasks/archive/`). `tasks/lessons.md` is now `docs/lessons.md`.

## Status lines before the restructure (2026-10-24)

### Review follow-up (2026-10-18)

Source: [review-2026-10-18.md](review-2026-10-18.md), section 6. Each step has its own checklist in that file.
- [ ] Step 1: Make the core flow run. The plan is below. Approved on 2026-10-18. Steps 1.1 to 1.7 are done and pushed (last: `5a8232f`). Only the manual check in "Verification for Step 1" is open.
- [x] Step 2: Make local-first true. Done on 2026-10-21. Steps 2.1 to 2.6 and review items R1 to R11a are pushed (last: `629eb69`; CI run 39630302033 passed all 11 jobs, Playwright 42 passed with 0 flaky). Open question, not blocking: allow LinkedIn country hosts such as `sg.linkedin.com`.
- [ ] Step 3: Make claims measurable. The plan is below. Decisions recorded on 2026-10-22.
- [ ] Step 4: Make it demo-able.
- [ ] Step 5: Focus and prune.

## Review (2026-11-12)

All six steps of section 6 of `review-2026-10-18.md` are done. Each step's folder is in `tasks/archive/` (Step 6, hardware fit with llmfit, was added later and is in `tasks/archive/step-6-llmfit/`).

- Step 1 was done on 2026-10-30, but this file still showed it as open. The manual dry runs `run_18ae691859d2` (the user) and `run_8e8837ffb270` (Claude) are recorded in `tasks/archive/step-1-core-flow/notes.md`: both reached `submit_applications` with `dry_run` true, 0 applied, 0 simulated, 2 manual, and no application record. On 2026-11-11 the user and Claude both took the open checkbox here as the truth, and a new dry run was nearly planned. The archived Step 1 task showed the real state on 2026-11-12.
- After the move to `~/personal-projects/job-raider` (2026-11-11), the user built the Docker images from the new path on 2026-11-12. Both containers were up and healthy. No new pipeline run was made: the pipeline code runs inside the image and has not changed since the October runs.
- The status lines above (from 2026-10-24) are kept without changes as a record.
- One open question moves to `tasks/todo.md` (Next Up): allow LinkedIn country hosts such as `sg.linkedin.com`.
