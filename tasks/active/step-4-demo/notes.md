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
5. **Seed: real output on synthetic input.** `scripts/build_demo_data.py` reads the `fresh_ml` profile and the ranking jobs, then runs `JobMatcher` and `RAGRanker.re_rank` and serializes with the API code. It writes one letter with `qwen2.5:3b` and runs the real validator on it. The letter stays as written, flags included: the demo must show the validator as it is. Application records and metrics are constructed sample data. The output goes to `apps/frontend-ts/src/demo/data/`, and the script runs by hand, not in CI.
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

## Blockers / Questions

- None.

## Review
