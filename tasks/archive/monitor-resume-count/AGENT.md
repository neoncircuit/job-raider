# Agent Brief: Monitor Resume Count

Read this file and one micro-handoff (`mh-1` or `mh-2`). Do not read other task files.

## How to work

1. Do one micro-handoff at a time, in order: `mh-1`, then `mh-2`.
2. Edit only the files that the micro-handoff names.
3. Add the test first. Run it and see it fail.
4. Change the code. Run the test again and see it pass.
5. Run the "Done when" commands of the micro-handoff. All must pass.
6. Commit with the message that the micro-handoff gives. Do not push.
7. Stop and report: the commit hash, the test output before and after, and anything that did not work.

## Rules

- Each Python function has a docstring with a description, `Args:`, and `Returns:` (or `Yields:`), and type hints. Each TypeScript function has a JSDoc comment.
- Do not rename, move, or reformat code that the micro-handoff does not name.
- Do not change a test that already exists.
- Do not open `.env`, `.env.local`, or anything in `apps/backend-py/data/`.
- If a step does not work after three tries, stop and report. Do not guess.

## Where to run commands

All commands run in WSL.

Backend (MH-1): from `apps/backend-py`. The project Python is `.venv/bin/python`.

Run one test file:

```bash
.venv/bin/python -m pytest tests/unit/test_pipeline_routes.py -q
```

Frontend (MH-2): from `apps/frontend-ts`, with Node 24.

Use Node 24 in this shell:

```bash
source ~/.nvm/nvm.sh && nvm use 24
```

Run one test file (always with `--no-cache`: the vitest cache folder in `node_modules/.vite` belongs to root, so a run without it fails with `EACCES`):

```bash
npx vitest run --no-cache tests/app/pipeline/cloud-badge.test.tsx
```

Use the file names of your micro-handoff in place of these.

## GPU

Do not start a pipeline run while the agent works.
