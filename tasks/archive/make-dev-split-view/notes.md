# Notes: One Split View for make dev

## Why (2026-11-10)

The user asked for a `make dev` like the Turborepo terminal UI: one terminal, each service's status shown, instead of separate terminals. Options were mprocs, tmux, and Turborepo; the user chose mprocs.

## Measure (2026-11-10, Claude)

- `scripts/dev.sh both` ran `start_api & start_frontend` in one shell, so both logs were mixed. There is no root `package.json`, so Turborepo would need a pnpm workspace and a Node wrapper around the Python backend.
- npm `mprocs` 0.9.6 (MIT, about 9 MB unpacked): its `cli.js` launcher has the platform binaries bundled, so it needs no install script. It runs in WSL; it needs `node` on the PATH.
- Under a pseudo-terminal, mprocs renders a process list with "UP" status and the selected process's output. Its help bar lists: Ctrl+A focus, q quit, j/k next/prev, s start, x stop, r restart, z zoom, p all commands.

## Change written and checked (2026-11-10, Claude)

Applied on the repo (2026-11-10, Claude, on the user's word "Yes, apply it"): commit `e1cdebd`, a cherry-pick of `dd2528a`; `git diff dd2528a HEAD`, without `tasks/`, is empty. In the real `apps/frontend-ts`, `npm install` added mprocs 0.9.6 (lockfile unchanged).

One commit was ready on the WSL clone `~/s4_work`, on top of `21a895e`: `dd2528a` `feat(dev)`.

- `mprocs.yaml` (new): processes `backend` (`./scripts/dev.sh api`) and `frontend` (`./scripts/dev.sh frontend`).
- `scripts/dev.sh`: `start_both` uses `node_modules/.bin/mprocs` from the frontend when stdout is a terminal, the binary is there, and `DEV_PLAIN` is not set; it runs from the project root. Otherwise it keeps the plain mixed output. The file is now executable in git (100644 to 100755): `make dev` and `mprocs.yaml` both run `./scripts/dev.sh`.
- `apps/frontend-ts/package.json` and the lockfile: `mprocs` 0.9.6, exact.
- README (Development), `docs/usage.md`, and the Makefile help describe the view and its keys.
- `apps/backend-py/tests/unit/test_dev_processes.py` (new, 3 tests).

Checks on the clone:

- Red: before the change, 2 of the 3 tests fail (no `mprocs.yaml`, no switch in `dev.sh`; the pin test passed because mprocs was installed first).
- The 3 tests pass; black (after one reformat) and ruff pass; `bash -n scripts/dev.sh` passes.
- With a stub in place of mprocs, `bash scripts/dev.sh both` under a pseudo-terminal called it with `--config <root>/mprocs.yaml` from the project root, and printed "Starting backend API + Next.js frontend in mprocs (q quits)...".
- The real mprocs rendered the real `mprocs.yaml` with its two commands replaced by echoes: both processes listed, the selected output shown. The real commands were not started, because the user's dev servers use ports 8000 and 3000.
- The new files first had mode 100755 (copied from the Windows drive); they are 100644 in the commit.

Not checked here: the plain fallback at run time (it would start servers on the ports in use). The user ran `make dev` on this machine and confirmed the split view with both services ("Yes, it works", 2026-11-10).

## Review

Done (2026-11-10). Pushed as `86c5469`; CI run 42844773681 passed (all 12 jobs).

After the first `make dev` the frontend logged `ChunkLoadError ... SyntaxError: Unexpected end of input` for `/settings`: Next.js read a server chunk in `apps/frontend-ts/.next` while Turbopack was still writing it (slow writes on the Windows drive under WSL; several first-compile requests at once). The chunk on disk was complete a moment later, and CI was green, so the code was fine. `.next` (670 MB, with leftovers of older production builds) was deleted, and a clean `make dev` served `/settings` with HTTP 200 and no error after an 80 s first compile.

## Review

`make dev` now gives the Turborepo-style view the user asked for, with no new setup step: `npm ci` installs the pinned mprocs, and the old mixed output stays as the fallback. Two lessons: copying files from the Windows drive with `cp` makes them executable in git, so check the mode before a commit; and on the Windows drive a cold Next.js dev cache is slow and can race, so delete `.next` when chunk errors appear and let the first page compile alone.
