# Agent Brief: Resume Generation Fix

Read this file and one micro-handoff (`mh-1` to `mh-7`). Do not read other task files.

## How to work

1. Do one micro-handoff at a time, in order: `mh-1` to `mh-7`.
2. Edit only the files that the micro-handoff names. In Aider, `/add` only those files.
3. Add the test first. Run it and see it fail.
4. Change the code. Run the test again and see it pass.
5. Run the "Done when" commands of the micro-handoff. All must pass.
6. Commit with the message that the micro-handoff gives. Do not push.
7. Stop and report: the commit hash, the test output before and after, and anything that did not work.

## Rules

- Each function has a docstring with a description, `Args:`, and `Returns:`, and type hints.
- Do not rename, move, or reformat code that the micro-handoff does not name.
- Do not change a test that already exists, unless the micro-handoff names the change (only MH-6 does).
- Do not open `.env`, `.env.local`, or anything in `apps/backend-py/data/`.
- If a step does not work after three tries, stop and report. Do not guess.

## Where to run commands

From `apps/backend-py` in WSL. The project Python is `.venv/bin/python`.

Run one test file:

```bash
.venv/bin/python -m pytest tests/unit/test_resume_writer_skills.py -q
```

Format the files you changed (do this before the checks):

```bash
.venv/bin/python -m black src/generation/resume_writer.py tests/unit/test_resume_writer_skills.py
```

Check the format of the files you changed:

```bash
.venv/bin/python -m black --check src/generation/resume_writer.py tests/unit/test_resume_writer_skills.py
```

Check the lint of the files you changed:

```bash
.venv/bin/python -m ruff check src/generation/resume_writer.py tests/unit/test_resume_writer_skills.py
```

Use the file names of your micro-handoff in place of these.

## GPU

The agent model and the app's models share one 8 GB GPU. Do not start a pipeline run while the agent works.
