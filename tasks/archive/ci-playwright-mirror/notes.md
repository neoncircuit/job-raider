# Notes: CI Playwright Install Without the Ubuntu Mirror

## Failed attempts of CI run 43049667237 (2026-11-11, UTC)

| Attempt | Started by | E2E result | Cause |
|---------|-----------|------------|-------|
| 1 | Push of the `AGENTS.md` commit, 15:34 | Both failed at 15:45 | `Temporary failure resolving 'azure.archive.ubuntu.com'` in `npx playwright install --with-deps chromium` |
| 2 | Claude re-run, 15:46 | Both failed at 15:57 | Same |
| 3 | Claude re-run, 16:14 | Both failed | Same (52 resolve errors in the log) |
| 4 | User re-run, about 16:33 | Both failed by 16:44 | Same (52 resolve errors in the log) |

The other 10 jobs passed in each attempt. The Docker image job was skipped.

## Proof run on the temporary branch (2026-11-11)

- The change was made on a scratch clone (no links to this repository's environments). It replaced 2 install lines in `ci.yml` and 1 in `pages.yml`. Both files load as valid YAML (13 and 2 jobs). `actionlint` is not installed, so it did not run.
- The clone's commit was pushed to the temporary branch `ci-playwright-no-apt` (user approved), and CI was started with `gh workflow run ci.yml --ref ci-playwright-no-apt`: run 43062631470.
- Result: `Test Frontend (E2E Tests)` passed (45 tests) and `Test Demo (E2E on the Static Site)` passed (18 tests). The install step log has 0 lines with `apt`. The other 10 test and check jobs passed.
- `Build Docker Image` failed at `Login to Docker Hub` ("Username and password required"). The cause is the manual start, not the change: this job runs on `workflow_dispatch` and on `v*` tags, and the Docker Hub secrets are not set. It did not build or push an image. On push runs to `main`, the job is skipped.
- The temporary branch was deleted on GitHub. `origin` has only `main`.

## Applied on main (2026-11-12)

- The user said "Yes, apply it".
- The scratch clone was gone (the session scratchpad was cleared at a session restart). The proven commit was fetched from GitHub by its full SHA, after the temporary branch had been deleted.
- Its parent was the tip of `main`, so `main` was fast-forwarded to it. `main` now holds the same commit that CI run 43062631470 tested, and `git diff` against it (without `tasks/`) is empty.

## Push and CI on main (2026-11-12)

- Before the push, `actionlint` 1.7.7 (Docker image `rhysd/actionlint:1.7.7`, read-only, with shellcheck) checked `ci.yml` and `pages.yml`: no findings, exit code 0. The user asked for this local check after the apply step.
- The user approved the push. `main` was pushed to `origin` with the fix and the task folder.
- CI run 43143067148 passed: 12 jobs passed, and `Build Docker Image` was skipped (push run). `Test Frontend (E2E Tests)` passed 45 tests and `Test Demo (E2E on the Static Site)` passed 18 tests. The install step logs have 0 lines with `apt`.

## Review

The E2E jobs no longer use the Ubuntu mirror. The change is one flag in three places, with a comment in each. It was proven on the GitHub runner before it landed, and `main` holds the exact commit that was tested. The lesson is in `docs/lessons.md` ("CI and the Ubuntu mirror").
