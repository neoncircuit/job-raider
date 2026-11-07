# Notes: Step 5, Focus and Prune

## Measure (2026-11-07, Claude)

Each fact comes from `git ls-files`, `git grep`, or `wc -l` on `main` at `bf842ce`.

| Item | Fact | Plan |
|---|---|---|
| `frontend-py/` | 36 tracked files, 5,015 lines. Only the README tree names it. | Delete (MH-1) |
| `src/database/` and `alembic.ini` | 7 files, 678 lines. No import outside the folder. Needs `sqlalchemy`, `alembic`, `psycopg2-binary`, `pgvector`, and `supabase`. | Delete, and remove the 5 requirements if nothing else imports them (MH-1) |
| `src/reports/` | 2 files, 558 lines. No import outside the folder. | Delete (MH-1) |
| `config/scrapers_config.yaml`, `config/search_config.yaml` | No reference in code or tests. | Delete (MH-1) |
| `experiments/ab_testing.py` | Not in the repository now. | Nothing to do |
| Root `data/` | Not tracked by git. | Do not touch: local data |
| Agent bus (`src/agents/communication.py`) | The coordinator uses it, and `/api/agents` uses the coordinator (Career Coach). | Keep. The review called it unused, and it is used now |
| `src/linkedin/` | 3,332 lines: an Easy Apply form filler, an answer engine, a session, and anti-detection code. No import outside the folder. `/apply` answers "not implemented". | User decision (MH-2) |
| Sidebar | 13 entries in 3 groups. The core loop is mixed with Career Coach, Assessment, Resume Analysis, LinkedIn Analysis, and Logs. | Core loop first, then a collapsed "Extras" group (MH-3) |
| Themes | 13 colour schemes. | User decision (MH-3) |
| Large files | `outcome_tracker.py` 1,691, `cover-letter/page.tsx` 1,348, `stages.py` 1,343 lines. | Split (MH-4 to MH-6) |

Also measured, not in the review list: `cover_letter_grounding.py` has 3,293 lines, the largest file. It is a candidate for a later split, not part of this step.

## Plan

| # | Content | How |
|---|---------|-----|
| MH-1 | Delete the dead code and its requirements and references | Direct commit; full backend tests, mypy gate, ruff, and a fresh `pip install -r` on a clone first |
| MH-2 | Easy Apply: carry out the user's decision | Measure the submit stage first. Direct commit if it deletes files |
| MH-3 | Sidebar groups and themes | Runner handoff, unit tests, E2E, mutants |
| MH-4 | Split `cover-letter/page.tsx` into components | Runner handoff; the existing page tests and E2E pass with no change |
| MH-5 | Split `stages.py` into stage modules; `stages.py` re-exports them | Runner handoff; the backend tests pass with no change |
| MH-6 | Split `outcome_tracker.py` the same way | Runner handoff; the backend tests pass with no change |

The sidebar after MH-3:

- Core loop: Dashboard, Profile, Pipeline, Jobs, Cover Letter, Applications.
- System: Metrics, Settings.
- Extras, collapsed: Career Coach, Assessment, Resume Analysis, LinkedIn Analysis, Logs. The group opens by itself when the current page is in it.

## Open questions for the user

1. Easy Apply. Option B (recommended): delete `src/linkedin/` and the "not implemented" auto-submit branch, and keep "Applied elsewhere" tracking. The code is not reachable now, and auto-apply has legal and ethical risk. Option A: keep it as a human-in-the-loop assistant, delete the anti-detection code, and add tests.
2. Themes. Recommended: keep Raid (the default), Paper (light), and Midnight. Or keep all 13.

## Decisions (user, 2026-11-07)

1. Plan: approved ("Yes, approve it").
2. Themes: keep all 13. MH-3 groups the sidebar only.
3. Easy Apply: "only delete it if there is a massive downside to what's happening right now". Claude's assessment: there is no massive downside. The package is dormant: no route or stage imports it, so it runs no code, sends no request, and loads no model. Two of its parts have tests (`test_structured_trust_and_forms.py`). The real costs are small: 3,332 lines to maintain, and anti-detection code in a public repository, which a reader can see. So `src/linkedin/` stays, and MH-2 is dropped. If a later change makes this code reachable, decide again first.

## MH-1 written and checked (2026-11-07, Claude)

Applied on the repo (2026-11-07, Claude, on the user's word "Yes, apply it"): commit `374c4a3`, a cherry-pick of `0c957b6` from the clone. Its code is the same as the checked commit; only the task notes differ. Untracked files stay in the working tree: `frontend-py/` holds an old `.venv` and caches (521 MB), and `src/database/` holds `__pycache__` files. Git does not track them, and Claude did not delete them.

A direct commit, because the runner cannot delete files. Commit `0c957b6` was made on the WSL clone `~/s4_work`, on top of `6e975fd`. To apply it, the real repository fetches the clone and cherry-picks that commit, so the bytes are the ones that were checked.

- Deleted: `frontend-py/` (36 files), `src/database/` and `alembic.ini`, `src/reports/`, `config/scrapers_config.yaml`, and `config/search_config.yaml`. 56 files changed, 6,683 lines deleted.
- Requirements removed: `sqlalchemy`, `alembic`, `asyncpg`, `psycopg2-binary`, `pgvector`, and `supabase`. Only `src/database/` imported them. `asyncpg` was not in the plan, and the measure showed the same fact for it.
- `.env.example`: the Supabase section and the Easy Apply YAML comment are gone.
- Docs: the README (tech stack, tree, config table, and the false example "edit `search_config.yaml`"), `DOCKER.md`, `COMPREHENSIVE_TESTING_STRATEGY.md`, `docs/architecture.md`, `docs/index.md`, and `docs/troubleshooting.md`. Four troubleshooting tips told users to set `rate_limit_delay` in `scrapers_config.yaml`. No code read that file, so the tips were false before this change. They now give advice that works. The history entries in `docs/index.md` and `docs/decision-log.md` stay as written.

Checks on the clone:

- The full backend suite passes, 2,151 tests, with an import blocker on. The blocker makes an import of the 6 packages from project code fail, and it lets a third-party library import them: MLflow uses SQLAlchemy, so `sqlalchemy` stays installed as an MLflow dependency. A self-test from a project file shows that the blocker refuses the import.
- The first run blocked every import, and one MLflow test failed for that reason. That is how the MLflow dependency came to light.
- Ruff on the CI paths passes. Ruff on all of `scripts/` finds 8 errors, and these are in files outside the CI paths.
- The mypy gate passes: 179 known errors, 0 new. It reports 3 baseline errors as fixed, because their file is deleted. The baseline keeps them until a person runs `--update`.
- No tracked file outside the history docs names a deleted path.

A fresh install was not run locally. After the push, CI run 42372115580 passed: its Test Backend job installs `requirements.txt` in a new environment and runs the tests, so that run covers the fresh install.

## MH-3 written and checked (2026-11-07, Claude)

`mh-3-sidebar-groups.md` (runner) is applied on the repo (2026-11-07, Claude ran the runner on the user's word "Yes, apply it"): commit `a266ed9`, 4 files, the same bytes as the runner test. The red step failed, and the 4 checks passed.

- New: `SidebarExtras.tsx` (the collapsed group) and `tests/components/sidebar-content.test.tsx` (6 tests). `SidebarContent.tsx` now has Workflow (Dashboard, Pipeline, Jobs, Cover Letter, Applications), System (Metrics, Settings), and Extras (Career Coach, Assessment, Resume Analysis, LinkedIn Analysis, Logs). Profile stays at the top.
- The smoke E2E test clicked the extra links directly, so its helper now opens Extras first.
- Check on a clone in WSL: `tsc`, eslint, and prettier pass. 351 unit tests pass. The smoke E2E test passes on desktop and mobile (28). The demo E2E tests pass (18).
- Mutants: the unchanged code and the control pass, and 10 of 10 are caught.
- Claude read screenshots of the sidebar, closed and open. With the group open at a height of 900 px, Logs is below the fold in the sidebar's own scroll area.
- Runner test: the handoff was in the fresh clone. The dry run passes, the red step fails, the 4 checks pass, commit `adfb170` is on the clone, the 4 files are the same bytes as the checked copies, and the HEAD of the real repository did not change.

## MH-4 written and checked (2026-11-07, Claude)

Applied on the repo (2026-11-07, Claude, on the user's word "Yes, apply it"): commits `53fc412` and `8179f60`, cherry-picks of `c525922` and `5da2d45` from the clone. The code is the same as the checked commits: `git diff 5da2d45 HEAD`, without `tasks/`, is empty.

Two commits were ready on the WSL clone `~/s4_work`, on top of `8970fd3`. They are direct commits, not a runner handoff: a runner edit of the whole page would copy 1,348 old lines into the handoff. To apply them, the real repository fetches the clone and cherry-picks both.

1. `c525922` `test(e2e)`: the smoke test helper from MH-3 clicked "Extras" once. On a cold dev server that click can come before hydration and be lost, and the test timed out on Resume Analysis. The helper now retries until the link shows, as the mobile helper already does. Then the smoke test passed twice from a cold server (28 each).
2. `5da2d45` `refactor(cover-letter)`: the page is split by a script that cuts at checked line numbers and moves the code with no change.

| File | Lines |
|---|---|
| `src/app/cover-letter/page.tsx` | 38 (was 1,348) |
| `src/lib/hooks/use-cover-letter-page.ts` (state, queries, actions) | 571 |
| `src/components/cover-letter/cover-letter-result.tsx` | 392 |
| `src/components/cover-letter/cover-letter-form.tsx` | 306 |
| `src/components/cover-letter/job-fit-panel.tsx` | 172 |
| `src/components/cover-letter/cv-indicator.tsx` | 61 |

Each section component takes one prop, the result of the hook, so no prop list needed a rewrite. `tests/lib/module-size.test.ts` keeps each of these files under 600 lines.

Checks:

- Red: before the split, the size test fails because the page has 1,349 lines.
- The 14 Cover Letter page tests pass with no change to a test file. 358 unit tests pass. `tsc`, eslint with no warnings, and prettier pass.
- E2E: 42 pass with the API mock, and 18 pass on the demo build. The first full E2E run stopped because its dev server did not start within 300 s, so no test ran. The rerun passed.
- Screenshots of the page, before and after, in three states (empty, assessed, with a letter): 91 of 1,400,000 pixels differ, by at most 24 of 255. That is anti-aliasing and the animated connection dot, not a layout change.
- Both versions log the same hydration error on the Cover Letter page in the dev server. It was there before the split.

## Blockers / Questions

- None.

## Review
