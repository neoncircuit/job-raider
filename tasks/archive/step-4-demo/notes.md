# Scratchpad & Notes

## Plan (2026-11-05, Claude)

### What exists today

- 14 pages. All are client components, except one that does not call the API (`/lab/crawler`). There are no dynamic page routes.
- The browser calls `/api/proxy/*`: `src/lib/api/client.ts` and 3 direct `fetch` sites (`coverLetter.ts`, `profile.ts`). One WebSocket is on the Pipeline page.
- `msw` 2.13.6 is installed and the unit tests use it (`tests/setup/mocks.ts`). The E2E tests have a mock layer with fixtures (`tests/e2e/support/mock-api.ts`, `tests/setup/fixtures.ts`).
- `tests/fixtures/eval/ranking/` has a synthetic profile (`fresh_ml`) and 70 constructed jobs. The repository is public, and GitHub Pages is not enabled.

### Trial of the static export (scratch clone, repository not changed)

| Trial | Result |
|-------|--------|
| `output: "export"`, code as it is | Fails on `/api/proxy/[...path]`: an export cannot have a route handler that reads the request. |
| Proxy route renamed `route.server.ts`, `pageExtensions` without `server.ts`, config redirect replaced by `src/app/page.tsx` | Passes: 17 static pages, 6.2 MB. |
| Same files, normal build with `server.ts` in `pageExtensions` | Passes: `/api/proxy/[...path]` is still a server route. |

So one file rename and one conditional in `next.config.ts` separate the two builds. The redirect page is used by both builds, so there is one path. The trial did not use a base path, and GitHub Pages needs one (`/job-raider`), so MH-1 must test it.

### Design

1. **Two builds.** `NEXT_PUBLIC_DEMO_MODE=1` sets `output: "export"`, `basePath`, and the page extensions. Without it, the build is as it is today.
2. **MSW in the browser, as the review says.** `src/demo/` holds the handlers, the data, and the start function. `providers.tsx` waits for the worker before it shows the app, so no query runs first. The code is behind a dynamic import and `process.env.NEXT_PUBLIC_DEMO_MODE`, so the normal build drops it. `build:demo` generates `mockServiceWorker.js`, and it is not committed.
3. **Requests in the demo.** Reads return the seed data. Writes change memory only, for the session. Generating a cover letter returns the seeded letter. Any other request returns a readable "not in the demo" error, so no page waits for ever.
4. **Pages in the demo.** Dashboard, Jobs, Cover Letter, Applications, Profile, and Metrics have data. Pipeline shows its history, and Start is off, with the reason. Settings is read-only. The sidebar hides Career Coach, Assessment, Resume Analysis, LinkedIn Analysis, Logs, and Lab: they need a backend, and fixtures for them add little.
5. **Seed: real output on synthetic input.** `scripts/build_demo_data.py` reads the `fresh_ml` profile and the ranking jobs, then runs `JobMatcher` and `RAGRanker.re_rank` and serializes with the API code. It writes one letter with `qwen2.5:3b` and runs the real validator on it. The letter stays as written, flags included: the demo must show the validator as it is. Application records and metrics are constructed sample data. The output goes to `apps/frontend-ts/src/demo/seed/`, and the script runs by hand, not in CI.
6. **Onboarding checklist.** This one is for real users, not the demo. A dashboard card reads existing endpoints: backend reachable, local model available, profile added, first search run, shortlist reviewed, first application tracked. Each open item links to its page. The card hides when all items are done. A user can dismiss it (`localStorage`).
7. **CI.** A new job builds the demo and runs Playwright on the exported files: each core page shows seed data and the banner, and no request fails. Another check reads the normal build output: no `msw` and no demo data.
8. **Deploy.** GitHub Pages from a workflow on `main`. It is free for a public repository, it needs no new account, and the site is static. Recommended over Vercel, which needs an account link and a project.
9. **README.** A demo link, a GIF under 3 MB that Playwright records from the demo (`ffmpeg` is installed in WSL), and the architecture diagram moved to the top. The recording uses the demo build only, so no personal data can appear.

### Micro-handoffs

| # | Content | Needs |
|---|---------|-------|
| MH-1 | Two builds: rename, config, redirect page, `build:demo`; test with the base path | |
| MH-2 | Seed script, data, tests | GPU: embedding model and one `qwen2.5:3b` letter |
| MH-3 | Handlers, worker start, banner, demo sidebar, Pipeline and Settings limits | |
| MH-4 | CI job and E2E tests on the exported site | |
| MH-5 | Onboarding checklist, with tests | |
| MH-6 | Pages workflow | The user enables Pages; first publish needs approval |
| MH-7 | GIF and README | Real URL from MH-6 |

MH-5 does not depend on the others. Full-code handoffs go through the runner. Docs with Mermaid fences are direct commits.

### Known limits

- A demo shows sample data. It proves the interface and the flow, not that the models work on a visitor's resume. The README and the banner must say this.
- `client.ts` and the direct `fetch` calls use `/api/proxy` with no base path. A service worker sees these requests, so MSW can answer them, but MH-1 and MH-3 must test this on the base path.
- A first visit waits for the service worker. A browser that blocks service workers gets no data, so the demo needs a clear message for this case.
- Some constructed companies have plain names (for example, Meridian Capital), and a real firm can have the same name. The seed renames any such company in the demo data only, so the ranking set and its SHA-256 do not change.
- Finding F1 also says that the real app shows about 15 s of spinners without a backend. The checklist shows "backend reachable", but the retry timing is not in this step.

### Not in this step

- Sidebar grouping and pruning (Step 5).
- Fixtures for the pages that the demo hides.
- A live model in the demo.

## Decisions (user, 2026-11-05)

1. Host: GitHub Pages ("Yes, use Pages"). The user answered after the plan, so the plan and its scope are approved. Enabling Pages on the repository and the first publish still need the user's approval at MH-6.

## MH-1 written and checked (2026-11-05, Claude)

`mh-1-two-builds.md` (runner): `next.config.ts`, `src/app/page.tsx`, the `build:demo` script, and 2 test files (6 tests).

Two changes from the plan, both found while checking:

- No rename. The plan renamed the proxy route, but the runner cannot rename or delete a file. Every page and layout is `.tsx`, and the proxy is `route.ts`, so `pageExtensions: ["tsx"]` in the demo build leaves it out with no change to that file.
- The server build keeps its `redirects` entry. The plan replaced it with a page for both builds, but then Next prerenders `/`, and the server answers 200 with a client redirect, not 307. That breaks the rule that the normal build must not change. The first clone check showed this. So the page is for the demo, and the config answers first in the server build.

Scratch clone (exit codes printed; `npm ci`, because Turbopack refuses a `node_modules` symlink that points out of the project):

- Red fails (5 tests). Prettier, eslint, and tsc pass. All frontend unit tests pass (263 in 50 files).
- Server build: exit 0; `/api/proxy/[...path]` is still a server route; `/` answers 307 to `/dashboard`.
- Demo build with `NEXT_PUBLIC_BASE_PATH=/job-raider`: exit 0; no `api` folder in `out`; 17 HTML files; 6.2 MB; 186 asset references with the base path and 0 without.
- Mutants, with a passing run first: 10 of 10 caught.
- Real browser (the built-in pane; Playwright has no browser in WSL) on a local server that acts like GitHub Pages: `/job-raider/` lands on `/job-raider/dashboard`, no asset fails, the sidebar links have the base path, and client navigation to Jobs and Cover Letter works. The 4 API calls fail, as expected before MH-3.
- Runner test on a fresh clone: the red step failed (exit 1), the 4 checks passed, commit `cb75630` on the clone, and the 4 checked files are the same bytes.

- MH-1 applied on the repo (2026-11-05, Claude ran the runner on the user's word "Yes, apply it"): commit `30d2360`. The red step failed, and the 4 checks passed. The 4 checked files are the same bytes as the checked copies.

For MH-3: the API calls go to `/api/proxy/...` with no base path, because `client.ts` writes that path by hand. The service worker has scope `/job-raider/`, and it sees all requests from pages in its scope, so MSW can answer them, but MH-3 must prove this in a real browser.

## MH-2 in progress: a writer defect found (2026-11-05, Claude)

The seed script works on a clean clone (peak VRAM 4,643 MiB, no model loaded after): 20 ranked jobs from 70, and one letter. The script stops when `data/` has files, so no personal data and no saved setting can reach the output. It is not in the repository yet.

Changes from the plan: every constructed company gets an `Example` name, because Claude cannot vouch for each name against real firms. The profile gets a sample name. Only the demo data changes.

The letter from the first run has literal placeholders: `[Company]`, `[Plant Disease Classifier]`, and `[Research Engineer, Machine Learning]`. The validator gives `is_valid: True`, score 76, `needs_revision`.

Claude first suspected its own rename: the word "Example" could read as a template. A trial (`qwen2.5:3b`, 3 jobs, 2 name sets, 8 letters each, counts only) does not support this as the main cause:

| Company names | Letters with a `[...]` token | Letters without the company name |
|---------------|------|------|
| Constructed | 7 of 24 | 0 of 24 |
| `Example` | 10 of 24 | 1 of 24 |

- The writer prompt has no brackets: the rules, the job context, the selection context, and the profile context. The model writes them by itself.
- `missing_company` in the writer runs of Step 3.8: `qwen2.5:3b` 6 of 195, `qwen2.5:7b` 1 of 195. Those reports hold no letter text, so a bracket count for them is not possible.
- The validator has no check for a placeholder, so Step 3.8 could not see this, and its recommendation of `qwen2.5:3b` did not weigh it. Whether `qwen2.5:7b` does the same is not measured.
- The sample is small. It shows that the defect is common, not its exact rate.

Picking a clean letter by running the seed again would overstate the writer. The plan says that the letter stays as written.

## MH-2a and MH-2 written and checked (2026-11-05, Claude)

The defect is fixed in `tasks/archive/writer-placeholders/`, and the default writer is `qwen2.5:7b` again, so the seed uses it.

- **The seed found another bug.** The first `qwen2.5:7b` run stopped on the check in `check_letter`: `provider_used` was empty. `rewrite` and `write_why_interest_block` drop the provider, so a cloud rewrite shows no Cloud badge, and `cloud_documents` is too low. `mh-2a-rewrite-provider.md` fixes this (4 tests; red fails 2; 2 of 2 mutants caught).
- **The seed ran once more, with the fix, on a clean clone:** idle GPU 1,669 MiB, peak 6,367 MiB, no model loaded after. That run was needed for the bug, not to pick a better letter. Its letter is committed as written.
- **Claude read the letter, as the lesson of 2026-11-05 asks.** It names the company, and it has no placeholder. The validator gives 92, `approve`, and no ungrounded sentence. But the letter has claims with no support: "deployed" is not in the profile, and neither the profile nor the job says "robust" or "scalable". This is the known limit of the rules. MH-3 shows a note about it on the Cover Letter page, so the demo does not overstate the validator.
- **The folder is `src/demo/seed`, not `src/demo/data`.** The repository `.gitignore` has `data/`, so the first runner test stopped at `git add`, and the runner restored the files. Every check before that had passed, so only the commit step showed this.
- `mh-2-demo-data.md` (runner): the script, 6 JSON files, and `tests/unit/test_demo_data.py` (22 tests). A test failed once on the order of `missing_skills`: the matcher builds that list from a set, so the test compares sorted lists. The mutant script refused to run on that failure, as it should.
- Check on a scratch clone, in one session, on the final path: red fails (exit 2); black and ruff pass; 2,150 backend tests pass; the unchanged code and the control pass (22 tests); 21 of 21 mutants caught, among them a constructed name, a changed score, a placeholder, a real mail domain, and a web address in the data; the mypy gate has 0 new errors.
- Runner test on one fresh clone, both handoffs in order: the red steps failed, all checks passed, commits `4045a01` and `8858450` on the clone, and the 9 checked files are the same bytes as the copies.
- Both applied on the repo (2026-11-05, Claude ran the runner on the user's word "Yes, apply them"): `fbd7c88` (MH-2a) and `2b2bdd8` (MH-2). The red steps failed, all checks passed, and the 9 checked files are the same bytes as the copies.

Next: MH-3 needs typed exports of this data, so the type part of the MH-2 criterion closes there. It must also show the note on what the validator missed in the demo letter.

## MH-3 written and checked (2026-11-06, Claude)

`mh-3-demo-handlers.md` (runner) is applied on the repo (2026-11-06, Claude ran the runner on the user's word "Yes, apply it"): commit `0739a13`, 29 files. Both red steps failed, and the 7 checks passed. Next: MH-4, the CI job and the E2E tests on the exported site.

Changes to the plan:

- Each write returns a 501 with a message, and the demo keeps no state. Pipeline Start and Settings use the same 501, with no special disabled state.
- The type part of the MH-2 criterion closes here: `src/demo/data.ts` has typed exports, and `tsc` passes.

Corrections to earlier notes:

- The built-in browser pane cannot register a service worker. The file loads (200, `text/javascript`), but `register` fails with "An unknown error occurred when fetching the script". The same build works in Chromium, so this is a limit of the pane, not a defect of the demo.
- The MH-1 note says that Playwright has no browser in WSL. A browser is there, at a newer build: `~/.cache/ms-playwright/chromium_headless_shell-1243`. Playwright looks for build 1223, so give the path in `executablePath`. CI installs its own browser in MH-4.

Check in Chromium, on a local server that acts like GitHub Pages under `/job-raider`:

- The worker controls the page, with scope `/job-raider/`, and each API call comes from the worker.
- Dashboard, Pipeline, Jobs, Applications, Cover Letter, Profile, Metrics, and Settings all load. A deep link on a first visit and a reload work. Client navigation keeps the base path. A phone width has no sideways scroll.
- The sample letter opens on the first job with its note. Each other action shows its message, with no retry.

The check found four defects, and MH-3 fixes them:

| Defect | Cause | Fix |
|---|---|---|
| A score showed as `80.22549940382058/100` | The rows wrote the raw float | `Math.round` on the job row and the job panel |
| A letter for a second job said "Upload a resume first" | The Jobs hooks replaced the API detail with fixed text | The five hooks and the Cover Letter page use `getApiErrorMessage` |
| A date of Nov 4 sat next to "14d ago" | The seed gave each row the time of the run | The date is the run time minus the age. No model ran |
| The server build kept a 298 KB chunk with MSW and the seed data | Next.js does not inline an undefined `NEXT_PUBLIC_*` variable, so the import stayed | The server build sets `env: { NEXT_PUBLIC_DEMO_MODE: "" }`. All 6 search words now appear in 0 files |

Results:

- 311 frontend tests pass in 56 files, 3 full runs of 3. 23 seed tests pass. `tsc`, eslint, prettier, black, and ruff pass.
- One full run failed on a timeout. An existing Cover Letter test takes 6 to 7 s of its 10 s limit, and that run started cold. MH-3 gives this test a limit of 20 s, because a failed check makes the runner undo all changes.
- Mutants: the unchanged code and the control pass, and 51 of 51 are caught, each by a named test.
- Runner: the dry run passes, both red steps fail, and the 7 checks pass.

Limits:

- Unit tests do not cover the wires in `providers.tsx`, `AppShell.tsx`, and `SidebarContent.tsx`. The MH-4 E2E tests must cover them. MH-4 must also add the search of the server build to CI.
- The Applications and Settings pages keep fixed messages, such as "Failed to update status". These messages are true, and the banner explains them.
- Metrics and Settings show a line such as "Could not load models: This needs the local backend, so it is not in the demo." at the sections with no data.
- A page that the sidebar hides still opens by its URL, and its actions get the same 501.

Incident (2026-11-06): the runner test used the handoff on `D:` from a clone, and the runner takes its repository from the handoff path. It ran on the real repository and made commit `8f892ba` on local `main`, before the user said "Yes, apply it". Nothing was pushed. Claude removed the commit with `git reset --keep aa7f323`, and the user's 14 modified files did not change. Before the reset, the commit matched the checked copies, except for the 20 s limit, which came after that check. See `docs/lessons.md`.

## MH-4 written and checked (2026-11-07, Claude)

`mh-4-demo-ci.md` (runner) is applied on the repo (2026-11-07, Claude ran the runner on the user's word "Yes, apply it"): commit `2e45b68`, 8 files, the same bytes as the runner test. The red step failed, and the 5 checks passed. The first CI run with the `test-demo` job passed on GitHub (run 42317711516, commit `5370796`).

- New: `playwright.demo.config.ts`, `tests/e2e-demo/demo.spec.ts` (17 tests), `scripts/serve-demo.mjs`, `scripts/find-demo-code.mjs`, and `tests/lib/find-demo-code.test.ts`. New CI job `test-demo`, and a new `check:no-demo` step in `build-frontend`.
- Check on a clone in WSL: `tsc`, eslint, and prettier pass. 318 unit tests pass in 57 files. The demo build passes, and all 17 E2E tests pass on it, with Chromium on the Pages base path. The server build passes, and `check:no-demo` finds no demo code in 682 files.
- Mutants: the controls pass, and 13 of 13 are caught. These include the three wires that MH-3 left to this step (the gate, the banner, and the sidebar filter), a request that leaves the site, a worker on the wrong path, and no worker file. With the server flag removed, the server build still exits 0, and `check:no-demo` exits 1.
- Runner test: the handoff was in the fresh clone, and the script stopped unless the runner would stay there. The dry run passes, the red step fails, the 5 checks pass, commit `24302e6` is on the clone, the 8 files are the same bytes as the checked copies, and the HEAD of the real repository did not change.

Limits:

- The runner does not run the builds or the E2E tests, because a build on the hard disk is slow. The first proof on GitHub is the CI run after the push.
- `next/font/google` downloads the fonts at build time. The download failed on 2 of about 15 local builds, with a `module-not-found` error. The failure is in the network step, not in the code. CI can meet the same failure, and the existing `build-frontend` job has the same risk.
- CI will use the Chromium build of its Playwright version (1223). The local check used build 1243.

## MH-5 written and checked (2026-11-07, Claude)

`mh-5-onboarding.md` (runner) is applied on the repo (2026-11-07, Claude ran the runner on the user's word "Yes, apply it"): commit `907d225`, 8 files, the same bytes as the runner test. The red step failed, and the 4 checks passed. CI run 42325636575 passed on the final code (commit `a0ab746`): 42 E2E tests with the card, and 18 demo E2E tests with no card.

- New: `src/lib/onboarding.ts`, `src/components/onboarding-checklist.tsx`, and 3 test files. The dashboard shows the card in the server build only.
- Change to the plan: the backend does not record that a user read the shortlist. A saved, hidden, or tracked job is the proof of a review, and the step text says so.
- Check on a clone in WSL: `tsc`, eslint, and prettier pass. All frontend unit tests pass. The demo E2E tests pass (18), and they prove that the demo has no card. The dashboard E2E test passes with the card.
- Mutants: the unchanged code and the control pass, and 22 of 22 are caught over two runs. The first run found one survivor: the test for a saved dismiss looked for the card before it could come back. The test now reads the saved value.
- A screenshot found a defect that no test found: the step read `total`, and the E2E mock of `/pipeline/history` has only `runs`, so the step stayed open next to a listed run. The step now reads `runs`, which is the data that the page shows.
- Runner test: the handoff was in the fresh clone. The dry run passes, the red step fails, the 4 checks pass, commit `63459a7` is on the clone, the 8 files are the same bytes as the checked copies, and the HEAD of the real repository did not change.

Limits:

- The first dashboard E2E run failed because Playwright reused another server on port 3000. Set `PLAYWRIGHT_PORT` to a free port for a local run. CI does not reuse a server.
- A user who works with cloud models only sees the model step as open, and can dismiss the card.

## MH-6 written and checked (2026-11-07, Claude)

`mh-6-pages-workflow.md` (runner) is applied on the repo (2026-11-07, Claude ran the runner on the user's word "Yes, apply it"): commit `8848679`, 2 files, the same bytes as the runner test. The red step failed, and the 5 checks passed. Nothing is published. `docs/demo-site.md` describes the demo, and how to build, test, and publish it.

- `.github/workflows/pages.yml` builds the demo, runs the E2E tests, uploads the site, and deploys it. The only trigger is `workflow_dispatch`, so a push to `main` does not publish. The plan said "a workflow on `main`". A later step can add a push trigger, after the first publish.
- Repository state (read only, 2026-11-07): public, and Pages is not enabled. Claude did not change any setting.
- Check on a clone in WSL: valid YAML, `tsc` and eslint pass, 345 unit tests pass. Mutants: the control passes, and 7 of 7 are caught.
- Runner test: the handoff was in the fresh clone. The dry run passes, the red step fails, the 5 checks pass, commit `7b6f771` is on the clone, the 2 files are the same bytes as the checked copies, and the HEAD of the real repository did not change.

First publish (2026-11-07): the user set the Pages source to GitHub Actions, and said "Pages is on, publish". Claude read the setting (`build_type: workflow`) and started the workflow. Run 42364191748 on commit `92a99f1`: 18 E2E tests passed, and the deploy reported success. Then the same 18 tests passed against the live site, `https://neoncircuit.github.io/job-raider/`, in Chromium. Pages serves `mockServiceWorker.js` with status 200 and `application/javascript`.

Limit before the publish: the deploy job could not run until Pages was on, so its first run was the first proof. The test reads the workflow text, and it does not prove that GitHub accepts the deploy.

## MH-7: README and GIF (2026-11-07, Claude)

A direct commit, not a handoff: the README has Mermaid fences, and the GIF is binary, and the runner can do neither.

- `README.md`: a link to the live demo and the GIF after the first paragraph, then the Architecture section (moved up from after Measured Results), two new feature lines (onboarding checklist, public demo), and a link to `docs/demo-site.md` under Documentation. Each anchor in the README still resolves.
- `docs/assets/demo.gif`: 505 KB, 960 px wide, 6 frames, 15 s, loops. The frames come from the live site in Chromium: Dashboard, Jobs, the job panel, the sample letter with its note, Applications, and Metrics. The letter frame holds for 4 s. Claude read each frame before the commit. The first two letter frames scrolled the job list out of view, and the third did not scroll, so the capture uses `scrollIntoView` with `block: "end"` in a window 960 px high.
- The capture script is not in the repository. To make a new GIF, take the same six frames from the live site and join them with Pillow (128 colours, 2.2 s for each frame).

## Review (2026-11-07, Claude)

- Delivered: two builds from one code base; a seed made by the real scoring and writing code on synthetic input; MSW handlers that answer in the browser; a banner and a note on what the rule checks missed; E2E tests on the exported site in CI; a search of the server build for demo code; an onboarding checklist for real users; a workflow that publishes only when a person starts it; the live demo at `https://neoncircuit.github.io/job-raider/`; and the README link, GIF, and diagram.
- Each criterion is closed. Each code step has mutants with a control: 10, 21, 51, 13, 22, and 7, all caught. The 18 demo E2E tests pass on the live site.
- Real checks found defects that unit tests did not: the writer placeholders (MH-2), a rewrite with no provider (MH-2a), four defects in the browser in MH-3 (raw scores, a false resume message, wrong dates, demo code in the server build), and a step that read a field that a response did not send (MH-5).
- Claude's errors in this task: the runner test of MH-3 committed on the real `main` before the user's approval, because the runner takes its repository from the handoff path. Nothing was pushed, and the commit was removed. Also: a pane limit taken for a possible bug, until Chromium showed the truth; and a test against a server on port 3000 that ran old code. Each has a lesson in `docs/lessons.md`.
- Limits: the demo has one sample letter, and each other action gives a 501 with a message. The letter has claims with no support, and the note says so. A push to `main` does not publish the demo, so the site shows the state of the last manual run. `next/font/google` needs the network at build time.

## Blockers / Questions

- None.

## Review
