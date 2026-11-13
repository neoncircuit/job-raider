# Current Priorities

## Active Focus
- [ ] To be decided with the user.

## Next Up
- [ ] Install the CI type-check pins (`mypy==2.4.0`, `types-requests`, `types-PyYAML`) in the local backend `.venv`: without them the local mypy gate reports 2 errors on `main` that CI does not (found in `tasks/archive/generic-phrasing/`).
- [ ] Optional: a CV eval suite, so that a change to the CV writer (prompt rule or sentence rewrite) can be measured like the cover letters (`tasks/archive/generic-phrasing/`, step 7 decision).
- [ ] Open question from Step 2, not blocking: allow LinkedIn country hosts such as `sg.linkedin.com` (`tasks/archive/review-follow-up/notes.md`).

## Done
- [x] Cover letters and CVs that do not sound generic: stock-phrase detector, checked sentence rewrite for letters, stock-phrase count for CVs (`tasks/archive/generic-phrasing/`; done 2026-11-13)
- [x] Review follow-up (2026-10-18), Steps 0 to 5 (`tasks/archive/review-follow-up/`; closed 2026-11-12)
- [x] CI E2E jobs install Chromium without `apt` and the Ubuntu mirror (`tasks/archive/ci-playwright-mirror/`; done 2026-11-12)
- [x] Move to `~/personal-projects/job-raider`, and make dev creates, repairs, and updates the environments (`tasks/archive/dev-deps-repair/`; done 2026-11-11)
- [x] One split view for `make dev` with mprocs (`tasks/archive/make-dev-split-view/`; done 2026-11-10)
- [x] Hardware fit: file-size floor and one unit (`tasks/archive/hardware-fit-floor/`; done 2026-11-10)
- [x] Local cleanup (2026-11-10): the Step 5 leftovers `frontend-py/` (521 MB of `.venv` and caches) and `apps/backend-py/src/database/` (`__pycache__` only) are deleted. `apps/frontend-ts/node_modules` had root-owned folders in WSL (`@types`), so `npm install` failed with EACCES; it was deleted from Windows and rebuilt with `npm ci` (lockfile unchanged, `@types/node` 24.19.2, tsc and 378 unit tests pass).
- [x] Stable Jobs page E2E search (`tasks/archive/jobs-e2e-flake/`; done 2026-11-10)
- [x] Self-hosted fonts (`tasks/archive/self-hosted-fonts/`; done 2026-11-10)
- [x] Local models table on a phone (`tasks/archive/phone-model-table/`; done 2026-11-09)
- [x] Step 6: Hardware fit with llmfit, optional and recommended (`tasks/archive/step-6-llmfit/`; done 2026-11-09)

*(Agent Note: When starting a task above, ensure a corresponding folder exists in `tasks/active/`)*
