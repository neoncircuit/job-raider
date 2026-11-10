# Notes: Stable Jobs Page E2E Search

## Why (2026-11-10)

The font task measured the Jobs page E2E search tests as flaky before and after its change (2 to 4 failures in 24 runs). The user chose to fix it next ("Yes, fix the flake").

## Cause

- A failure screenshot: the Search button has the focus, the Keywords field is empty (placeholder shown), and no result shows.
- A probe (12 runs with timing logs) shows a second main-frame navigation to `/jobs` 100 to 250 ms after `goto` returns. No app code changes the URL, so this is the App Router's `history.replaceState` at hydration. In every probe run the fill came after it, and the search ran with the typed keywords.
- So a fill that comes before hydration is lost: hydration resets the controlled input, and the click searches nothing. `goto` waits for the `load` event, but the Next.js scripts load asynchronously, so hydration can finish after `goto` returns.

## Handoff written and checked (2026-11-10, Claude)

`mh-1-jobs-search.md` (runner) is applied on the repo (2026-11-10, Claude ran the runner on the user's word "Yes, apply it"): commit `f7d2462`. The 3 checks passed, and `git diff 6a863c3 HEAD`, without `tasks/`, is empty. Before the run, the attribution line in the handoff's commit message changed to the current one; the code blocks did not change. A `searchJobs` helper in `tests/e2e/jobs-page.spec.ts` retries the fill and the click until the first result shows (`expect.toPass`, 3 s per try, 20 s in all); both search tests use it. The app does not change.

Runner test on the clone (the handoff was in the clone): there is no red step (a flake cannot fail on demand); the 3 checks pass (prettier, eslint with no warnings, tsc), and commit `6a863c3` is on the clone. The HEAD of the real repository did not change.

Proof on the clone:

- Forced race (temporary spec copies; the page's JavaScript chunks delayed by 3 s, and `goto` returns at `domcontentloaded`, so the fill comes before hydration): the old spec fails 2 of 3; the new spec passes 3 of 3. A first attempt with the delay alone did not reproduce the race, because `goto` then also waited for the delayed chunks.
- The real Jobs spec, 8 repeats on both projects: 48 of 48 pass (before: 2 to 4 failures in 24).
- The full E2E suite: 45 pass, 1 skipped (the phone test on desktop).

## Review
