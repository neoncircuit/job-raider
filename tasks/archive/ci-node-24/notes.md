# Scratchpad & Notes

## Observations

- **Where the Node version is read.**

    ```mermaid
    flowchart LR
        N[".nvmrc (24)"] --> CI["CI frontend jobs: setup-node node-version-file"]
        N --> S["setup.sh: REQUIRED_NODE_MAJOR"]
        D["apps/frontend-ts/Dockerfile: node:24-alpine"] --> I["Frontend image"]
        CI --> L["npm ci from package-lock.json"]
        D --> L
    ```

    The Dockerfile names the image tag directly, because a `FROM` line cannot read `.nvmrc`. A later Node change must edit both files.
- **Action versions (2026-10-25).** Each latest release runs on `node24` (from its `action.yml`). Breaking changes that apply to this workflow:
    - `codecov/codecov-action` v5: the `file` input became `files`. Changed in both upload steps.
    - The others need no change: `checkout` v6 and v7 change the credentials file and fork checks for `pull_request_target`; `setup-node` v5 and later cache automatically only with a `packageManager` field (there is none, and the jobs set `cache: 'npm'`); `setup-python` v7 removes `pip-install` (not used); `upload-artifact` v7 adds an opt-in direct upload; `gitleaks-action` v3 changes only the runtime; the three Docker actions removed inputs and environment variables that this workflow does not use.
- **The old lock file fails on npm 11.** The committed `package-lock.json` had only the two Linux x64 builds of `@tailwindcss/oxide` and left out other optional platform packages (a known npm gap). npm 10 (Node 20) accepts this; `npm ci` on npm 11 (Node 24) stops with "Missing: ... from lock file". `npm install` on npm 11.19.1 rewrote the lock:
    - 109 entries added, all optional platform packages (`@rollup`, `@esbuild`, `@img`, `@unrs`, `@tailwindcss`, `lightningcss`, and others); none removed;
    - 3 version changes: the root version (stale `0.1.0` to `0.2.0`, the `package.json` version), `@types/node` 20.19.39 to 24.19.2, and its dependency `undici-types` 6.21.0 to 7.24.6.
- **`--frozen-lockfile` removed from the Dockerfile.** It is a yarn flag. npm ignored it, and npm 11 warns that it will stop working in the next major. `npm ci` already fails when the lock does not match `package.json`.
- **npm 11.19 install scripts.** npm 11.19 does not run dependency install scripts that are not listed in `allowScripts`, and asks for approval (`npm install-scripts approve`).
    - In WSL, `npm ci` skipped `unrs-resolver`. In the Docker build, it skipped `esbuild`, `msw`, `sharp`, and `unrs-resolver`.
    - `esbuild`, `sharp`, and `unrs-resolver` only check or fetch a binary that the optional platform packages already install. The `msw` script copies the browser worker only when `package.json` sets `msw.workerDirectory`, and it does not. Lint, the tests, the build, and the image all work without the four scripts.
    - Watch for this warning if a later dependency needs its install script. An `allowScripts` list is the fix then.
- **Worktree.** The branch is in `.claude/worktrees/ci-node-24` (ignored by git), created with WSL git. Windows git cannot read this worktree (its links are WSL paths), so all git commands for it run in WSL.

## Attempted Approaches

- The first Docker build ran at the same time as the `npm install` in the worktree. It saw the new `package.json` with the old lock, and `npm ci` failed. The second build ran after the install (see Results).

## Results (2026-10-26, Claude)

Local frontend gate on Node v24.22.1 (npm 11.19.1, WSL), in the worktree:

| Check | Result |
|-------|--------|
| `npm ci` from the new lock | passed |
| `npm run lint` | passed |
| `npm run type-check` | passed |
| `npm run format:check` (whole tree) | passed |
| `npm run test:coverage -- --run` | 46 files, 252 tests passed |
| `npm run build` | compiled |
| Docker image on `node:24-alpine` | built; Node v24.22.1 in the image; `GET /dashboard` 200; no npm config warning (test image and container removed) |

No backend file changed, so the backend gate was not run. The CI run on GitHub is still open (see `task.md`).

## Blockers / Questions

- None. Pushing the branch and opening a PR into `main` needs the user's approval.
