# Task: Move CI and the Frontend off Node 20

## Goal
Move CI, the frontend Docker image, and the local setup from Node 20 (end of life on 2026-04-30) to Node 24 LTS, and move every GitHub Action to a major version that runs on Node 24. This closes review item H2 (`tasks/active/review-follow-up/review-2026-10-18.md`).

## Constraints & Context
- CI run 40202984846 (2026-10-25) passed, but its annotations said that Node 20 is deprecated on the runners and that the actions are forced to run on Node 24.
- Node 24 ("Krypton") is the LTS line until April 2028. Node 22 ends in April 2027. Node 26 is not LTS yet.
- One source for the version: the root `.nvmrc`, read by CI (`node-version-file`) and by `setup.sh`. The same idea as `.python-version`.
- No application code changes. Branch `chore/ci-node-24`, in a separate worktree. Do not push without the user's approval; push only from WSL.

## Acceptance Criteria
- [x] Root `.nvmrc` is `24`. CI reads it in the six frontend jobs; no `node-version: '20'` is left.
- [x] Every action is on its latest major, all `node24`: `checkout` v7, `setup-node` v7, `setup-python` v7, `upload-artifact` v7, `gitleaks-action` v3, `codecov-action` v7 (`file` renamed to `files`), `setup-buildx-action` v4, `login-action` v4, `build-push-action` v7.
- [x] The frontend Dockerfile uses `node:24-alpine` in all three stages.
- [x] `@types/node` is `^24`, with the lock file updated.
- [x] `setup.sh` reads the required major from `.nvmrc`; `scripts/dev.sh`, `README.md`, `docs/index.md`, and `docs/architecture.md` say Node 24.
- [x] The frontend gate passes on Node 24 locally: `npm ci`, lint, type check, Prettier, vitest with coverage, and `next build`. (2026-10-26; the lock file had to be rewritten by npm 11, see `notes.md`.)
- [x] The frontend Docker image builds and starts on `node:24-alpine`. (2026-10-26; `--frozen-lockfile` removed.)
- [ ] The CI workflow passes on GitHub with the new actions (needs a PR or a push to `main`; the user decides). The Docker job runs only on a `v*` tag or a manual run, so its three action bumps are checked at the next release.

## Status
`review` (local checks pass on 2026-10-26; the GitHub CI run waits for the user's decision on the PR)
