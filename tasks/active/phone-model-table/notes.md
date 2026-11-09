# Notes: Local Models Table on a Phone

## Why (2026-11-09)

The Step 6 review listed it as an open item. The user chose it next ("Fix the phone table").

## Handoff written and checked (2026-11-09, Claude)

`mh-1-phone-table.md` (runner) is applied on the repo (2026-11-09, Claude ran the runner on the user's word "Yes, apply it"): commit `3bd7c0f`. The red step failed, the 4 checks passed, and `git diff b7aaa57 HEAD`, without `tasks/`, is empty. Below the `sm` breakpoint (640 px), the Parameters header and cells get `hidden sm:table-cell`, the model name gets `break-all`, and the size gets `whitespace-nowrap`. New: `tests/components/ollama-models-card-phone.test.tsx` (2 tests). Changed: `tests/e2e/hardware-fit.spec.ts` (a Mobile Chrome test: the Parameters header is hidden, and the delete button is inside the screen).

Runner test on the clone (the handoff was in the clone): the red step fails, the 4 checks pass (vitest, prettier, eslint with no warnings, tsc), and commit `b7aaa57` is on the clone. The HEAD of the real repository did not change.

Other checks on the clone:

- Unit tests: 375 pass (373 before). The MSW "Cannot bypass a request" log lines change from run to run (86, 92, 94); the new test adds none.
- E2E, hardware fit spec: 3 pass, and 1 is skipped (the phone test on the desktop project).
- E2E red: with the old card, the phone test fails ("Expected: hidden, Received: visible").
- Screenshots: on a phone, the table shows Model, Size, Fit, and the delete button, with no sideways scroll; the desktop table is the same as before.

## Review
