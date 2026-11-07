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

A direct commit, because the runner cannot delete files. Commit `0c957b6` is ready on the WSL clone `~/s4_work`, on top of `6e975fd`. It is not applied. To apply it, the real repository fetches the clone and cherry-picks that commit, so the bytes are the ones that were checked.

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

Not checked: a fresh `pip install -r requirements.txt` in a new environment. The removal only takes lines out, and the blocked-import run shows that no project code needs those packages.

## Blockers / Questions

- None.

## Review
