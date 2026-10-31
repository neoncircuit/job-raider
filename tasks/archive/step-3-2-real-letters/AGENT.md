# Agent Brief: Step 3.2 Real Letters

Read this file and one micro-handoff (`mh-a`, `mh-b`, or `mh-c`). Do not read other task files.

Since 2026-10-30, the handoff runner applies these micro-handoffs without an agent (`docs/handoff-runner.md`). Each handoff has an "Apply with the runner" section. This brief stays for an agent that does the same work by hand.

## How to work

1. Do one micro-handoff at a time, in order: `mh-a`, `mh-b`, then `mh-c`.
2. Edit only the files that the micro-handoff names.
3. Add the test first. Run it and see it fail.
4. Add or change the code. Run the test again and see it pass.
5. Run the "Done when" commands of the micro-handoff. All must pass.
6. Commit with the message that the micro-handoff gives. Do not push.
7. Stop and report: the commit hash, the test output before and after, and anything that did not work.

## Rules

- Each function has a docstring with a description, `Args:`, and `Returns:`, and type hints.
- Do not rename, move, or reformat code that the micro-handoff does not name.
- Do not change a test that already exists.
- Do not open `.env`, `.env.local`, or anything in `apps/backend-py/data/`. Do not run the scripts of this task on real data: the tests use synthetic data only.
- Do not start Ollama models or a pipeline run.
- If a step does not work after three tries, stop and report. Do not guess.

## Where to run commands

From `apps/backend-py` in WSL. The project Python is `.venv/bin/python`.

Run one test file:

```bash
.venv/bin/python -m pytest tests/unit/test_make_real_grounding_set.py -q
```

Use the file names of your micro-handoff in place of this one.
