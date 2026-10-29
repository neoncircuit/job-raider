# Task: Monitor Resume Count

## Goal
The Live Monitor shows how many jobs a full-mode run selected for resumes (the Max Jobs limit) and how many resumes it generated. Today it shows only "N shortlisted", the ranked list for the Jobs page, and the user read that number as the Max Jobs count in two runs.

## Constraints & Context
- Found in the resume generation fix (`tasks/archive/resume-generation-fix/notes.md`, the two full-mode dry runs on 2026-10-29). Backlog item: "The Live Monitor shows 'N shortlisted'" in `tasks/backlog.md`.
- Do not change the meaning of `jobs_selected` (the ranked shortlist). The database column and the History tab stay as they are.
- The implementer is an agent in opencode (GLM-5.3-Flash Free or DeepSeek). Each micro-handoff gives its test in full. The agent reads `AGENT.md` and one `mh-*.md` file, nothing else.
- Keep dry run as the default. Do not make auto-submit reachable.

## Acceptance Criteria
- [x] MH-1 (`f4dad31`, checked 2026-10-30). `GET /api/pipeline/status/{run_id}` returns `jobs_for_resumes` (Select Jobs `selected_count`) and `resumes_generated` (Generate Resumes `generated_count`), 0 when the stage did not run. (`mh-1-status-resume-counts.md`)
- [ ] MH-2. The Live Monitor shows "Resumes: N jobs selected (Max Jobs) · M generated" when `jobs_for_resumes` is greater than 0, and hides the line when it is 0. (`mh-2-monitor-resume-line.md`)
- [ ] Check (Claude, in `notes.md`): the diffs, mutation proofs, the backend gate, and the frontend checks (vitest, eslint, prettier, type-check).
- [ ] Done when: a full-mode dry run shows the resume line on the Live Monitor with the Max Jobs count.

## Status
`in-progress` (MH-1 checked on 2026-10-30; MH-2 is with the agent)
