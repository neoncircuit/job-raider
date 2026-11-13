# Notes: ci-type-check-pins

Planned 2026-11-13. Review section to be added when the task is done.

## Build and checks (2026-11-13, fresh scratch clone, nothing installed by hand)

- Versions from the last CI run (43430058153): lint job black 26.10.1, ruff 0.17.5; type-check job mypy 2.4.0, types-requests 2.33.0.20261006, types-PyYAML 6.0.12.20260906. The local `.venv` had ruff 0.17.4 and mypy 2.4.1 without stubs, so the drift was already there.
- `requirements.txt`: exact pins for the five tools, with the baseline comment. `ci.yml`: the lint and type-check jobs install only `requirements.txt` (all backend jobs run in `apps/backend-py`). actionlint 1.7.7: no findings.
- Clean clone, `make dev-deps`: the `.venv` got exactly the pinned versions. With no extra install: mypy gate 177 known and 0 new; black and ruff clean on the CI paths; pytest 2,299 passed.
- Update path (the user's real `.venv`): the clone was put in the old state (old `requirements.txt`, mypy 2.4.1, no stubs); with the new file, `make dev-deps` printed "Backend requirements changed -- updating the .venv", installed the pins, and the gate passed with 0 new.
- Side finding, not from this change: in Claude's shell after a session restart, nvm was not loaded, so `make dev-deps` stopped at the frontend step with "node not found". The user's terminal loads nvm, so `make dev` works there. With nvm loaded, `make dev-deps` passed (exit 0).
- Clone commit `848ae96` on top of `a2c645d` (= `main`).

- Applied (user approved, 2026-11-13): `main` fast-forwarded to `848ae96`; `git diff` against it is empty. Not pushed yet. The real `.venv` is updated at the next `make dev` (or `make dev-deps`).

## Pushed; the user's real `.venv` (2026-11-13)

- The user approved the push; `main` was pushed with the pins.
- The user ran `make dev`; it updated the real `.venv` (stamp 21:42) to black 26.10.1, ruff 0.17.5, mypy 2.4.0, types-requests 2.33.0.20261006, types-PyYAML 6.0.12.20260906.
- Checks in the real repository: mypy gate 177 known and 0 new (the 2 false local errors are gone); black and ruff clean; pytest 2,299 passed. The running app answered (backend `/api/health` 200, frontend 307).
- The gate also says that 5 baseline errors are fixed. The baseline only shrinks when the user decides (`mypy_gate.py --update` is not run).

## CI (2026-11-13)

- CI run 43436243204 passed: 12 jobs passed, `Build Docker Image` skipped (push run). The lint and type-check jobs installed only `requirements.txt` and got black 26.10.1, ruff 0.17.5, mypy 2.4.0, types-requests 2.33.0.20261006, types-PyYAML 6.0.12.20260906. Mypy gate 177 known and 0 new (the same as local); pytest 2,299 passed; E2E 45 and demo E2E 18 passed; Vitest 68 files passed.

## Review

The local `.venv` and CI now use the same lint and type-check tool versions from one file (`requirements.txt`). The local mypy gate on `main` reports 0 new errors, as CI does; before, it reported 2 errors that CI did not. `make dev` moves an existing `.venv` to the pins by itself (checked on a clone and on the user's real `.venv`). To change a tool version later: change `requirements.txt`, and for mypy or a stub package, regenerate the baseline with the user's approval.
