# Current Priorities

## Active Focus
- [ ] To be decided with the user.

## Next Up
- [ ] No open items.

## Done
- [x] One split view for `make dev` with mprocs (`tasks/archive/make-dev-split-view/`; done 2026-11-10)
- [x] Hardware fit: file-size floor and one unit (`tasks/archive/hardware-fit-floor/`; done 2026-11-10)
- [x] Local cleanup (2026-11-10): the Step 5 leftovers `frontend-py/` (521 MB of `.venv` and caches) and `apps/backend-py/src/database/` (`__pycache__` only) are deleted. `apps/frontend-ts/node_modules` had root-owned folders in WSL (`@types`), so `npm install` failed with EACCES; it was deleted from Windows and rebuilt with `npm ci` (lockfile unchanged, `@types/node` 24.19.2, tsc and 378 unit tests pass).
- [x] Stable Jobs page E2E search (`tasks/archive/jobs-e2e-flake/`; done 2026-11-10)
- [x] Self-hosted fonts (`tasks/archive/self-hosted-fonts/`; done 2026-11-10)
- [x] Local models table on a phone (`tasks/archive/phone-model-table/`; done 2026-11-09)
- [x] Step 6: Hardware fit with llmfit, optional and recommended (`tasks/archive/step-6-llmfit/`; done 2026-11-09)

*(Agent Note: When starting a task above, ensure a corresponding folder exists in `tasks/active/`)*
