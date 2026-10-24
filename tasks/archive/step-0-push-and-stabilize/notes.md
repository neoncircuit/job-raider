# Notes: Step 0, Push and Stabilize

This text moved here from `tasks/todo.md` on 2026-10-24, without changes. Paths in it are as of that date: a reference to a section of `tasks/todo.md` now means a section of this file or of another task's `notes.md`, and a `tasks/handoff-*.md` file is now in its step's task folder (Step 2 and Step 3.2 handoffs are in `tasks/archive/`). `tasks/lessons.md` is now `docs/lessons.md`.

- [x] Step 0: Push and stabilize.
  - [x] Add LF rules for `*.ts`, `*.tsx`, `*.js`, `*.jsx`, `*.mjs`, `*.cjs`, and `*.css` to `.gitattributes`. Restore LF in the 16 files that had CRLF on disk.
  - [x] Run all local checks (2026-10-18). Backend: ruff and Black clean; pytest 983 passed. Frontend (`node:20` container, same as CI): `npm ci`, ESLint (0 warnings), tsc, Prettier, Vitest 202 passed in 38 files, `next build`, and Playwright 41 passed with 1 flaky (Mobile Chrome Dashboard link timed out on a cold dev-server start, then passed on retry). Gitleaks: no leaks in the unpushed commits. mypy is still non-blocking (195 errors); Step 1.4 makes it a gate.
  - Note: `npm ci` fails with npm 11 (Node 24) because `package-lock.json` lacks the optional `@tailwindcss/oxide-*` platform packages. npm 10 (Node 20, as in CI) accepts it. Regenerate the lock file when CI moves to Node 24.
  - [x] Push to `origin/main` (approved 2026-10-18). Pushed `dbac242..63e5e0a` from WSL (Git Bash on Windows has no GitHub SSH key). CI run 39094293658 passed all 11 jobs; Docker build skipped by design. Note: the mypy "Type Check" and "Security Scan" jobs cannot fail yet.
