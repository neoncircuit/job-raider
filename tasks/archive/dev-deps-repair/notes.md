# Notes: make dev Creates, Repairs, and Updates the Environments

## Move to the WSL filesystem (2026-11-10 and 11, Claude, on the user's request)

The repository moved from `D:\GitHub\job-raider` (reached from WSL through `/mnt/d`, a 9p file bridge) to `~/personal-projects/job-raider` (ext4 in WSL). The D: copy is kept, unchanged, as a backup.

- Fresh clone from `git@github.com:neoncircuit/job-raider.git` at `4eccf42`, the same commit as D: (nothing was unpushed). `merge.ours.driver=true` is set again; `core.hookspath` (it pointed at the D: hooks folder, which had no hooks) is not.
- Copied without reading the contents: `apps/backend-py/.env` and `apps/frontend-ts/.env.local` (byte-identical), `apps/frontend-ts/.env.example`, `apps/backend-py/data/` (WSL could not read 294 files of `data/linkedin_session/`; Windows robocopy copied them, 0 failures), root `data/`, `apps/backend-py/scripts/output/`, the 2 untracked Step 2 handoffs, `.codebase-memory/`, and the small `.claude/` folders (`PRPs`, `commands`, `agents`).
- Not copied: `.claude/worktrees/` (5.5 GB of two stale subagent worktrees from October), `.aider.tags.cache.v4/`, `htmlcov/`, and the 14 files that differed from git only in line endings.
- The new `data/` has no unreadable and no root-owned file.

## Change and checks (2026-11-11, Claude)

- `scripts/dev.sh`: `ensure_backend` recreates the `.venv` when its Python does not run or `fastapi`, `uvicorn`, `pydantic`, `setuptools` do not import; it installs again when the SHA-256 of `requirements.txt` and `requirements-optional.txt` differs from a stamp in the `.venv`. `ensure_frontend` runs `npm ci` when `node_modules/.bin/next` is missing or the lockfile hash differs from a stamp in `node_modules`. New mode `deps` (checks only), `make dev-deps`. mprocs processes skip the checks after `make dev` ran them (`DEV_DEPS_CHECKED=1`).
- `tests/unit/test_dev_deps.py` (new, 5 static tests). `tests/unit/test_dev_launcher.py`: it runs `dev.sh api` with a stub Python and no requirements file, so the new check stopped it; it now sets `DEV_DEPS_CHECKED=1`, because it tests the launch only.
- README and Makefile help describe the checks.

Scenarios, run in the new folder with `./scripts/dev.sh deps`:

| Scenario | Result | Time |
|---|---|---|
| Fresh clone (no `.venv`, no `node_modules`) | `.venv` created with the requirements and llmfit 1.1.20; `npm ci` | 509 s |
| Second run | both ready, nothing installed | 1 s |
| `fastapi` deleted from site-packages | "broken packages", `.venv` created again; fastapi imports | 244 s |
| `requirements.txt` changed, then restored | "requirements changed" both times | 4 s, 10 s |
| `node_modules/.bin/next` deleted | `npm ci` | 21 s |
| Lockfile stamp changed | `npm ci` | 19 s |

- The full backend suite passes (2,248 tests) in 49 to 64 s in the new folder; on D: it took about 150 to 180 s. 378 frontend unit tests pass in 25 s.
- Red: with the old `dev.sh`, the 5 new tests fail; the launcher tests pass with both versions.
- Mutants: 4 of 4 are caught (no package check, no backend stamp, `NO_LLMFIT` ignored, checks repeated in mprocs).
- black and ruff pass; `bash -n` passes.
- The user ran `make dev` from `~/personal-projects/job-raider` and confirmed that it starts cleanly ("Yes, it works", 2026-11-11).

## Review

Done (2026-11-11). Pushed from `~/personal-projects/job-raider` as `89d501c`; CI run 42855541242 passed (all 12 jobs).

`make dev` now works on a fresh clone and repairs a broken or outdated environment by itself, and the move to the WSL filesystem cut the backend test time to about a third. The D: copy stays as a backup; it is not used any more.
