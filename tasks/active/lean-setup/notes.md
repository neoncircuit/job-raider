# Notes: lean-setup

Planned 2026-11-14 (user: make the app usable on 16 GB RAM; laptop RTX 2070). Review section to be added when the task is done.

## Progress 2026-11-14

- Recorder: added `committed_gb` (Windows `\Memory\Committed Bytes`) and `vmmem_gb` (`vmmemWSL` working set). Test sample with `make dev` running: GPU 4,840 MiB, RAM free 1.60 GB, committed 31.41 GB, `vmmemWSL` 2.81 GB.
- `make app` built on the scratch clone: `dev.sh` modes `app`, `app-api`, `app-frontend`; `APP_MODE=1` removes the uvicorn reload and runs the Next.js production server; the frontend builds only when `.next/BUILD_ID` is missing or older than `src`, `public`, `package.json`, or `next.config.*`. New `mprocs.app.yaml` and Makefile `app` target. `make dev` is unchanged (a test checks that it keeps `--reload` and the two reload directories).
- Tests: 6 new (app-api without reload; dev api keeps reload; frontend builds when there is no build; frontend reuses a current build; mprocs app config; Makefile target). Launcher and mprocs tests: 11 passed. black, ruff, and `bash -n` pass.
- Production build on the clone: 4 min 24 s, peak RSS 1.0 GB (one time, and again only after a source change).
- Frontend server memory, same pages loaded (`/`, settings, pipeline, jobs, cover letter, profile):
  - Dev server (`make dev`): `next-server` 585 MB + `next dev` 40 MB + postcss worker 89 MB + `npm` 38 MB = about 750 MB.
  - Production server (`next start`, port 3100): `next-server` 136 MB + `npm` 68 MB = about 205 MB.
  - Saving: about 550 MB. All pages returned 200 (the root 307 redirect is expected).

## Before run 2026-11-14 (today's setup: make dev, MLflow container, usual Windows apps)

Workload: 3 letters, Deep validation and Review & rewrite on (`measure_letter_flow.py`), from `main`.

| Letter | Time | Words | Stock phrases | Score | Rewrites |
|---|---|---|---|---|---|
| classifier_robotics | 1,285 s | 207 | 0 | 85 | 1 |
| fastapi_kubernetes | 140 s | 197 | 0 | 87 | 1 |
| forms_security | 50 s | 243 | 0 | 85 | 1 |

Total 1,475 s. Resources (85 samples): GPU idle 1.1 GB, peak 6.1 GB (never two models at once). RAM free fell from 1.85 GB to 0.39 GB. Committed memory rose from 29.3 GB to a peak of 34.8 GB on 15.9 GB. `vmmemWSL` grew from 2.65 GB to 5.26 GB. Pages/sec often above 1,000, peaks 19,380 and 22,909.

Finding (root cause of the slow first letter): under this memory pressure, a cold model load took longer than the client timeout (120 s). Ollama logged 9 "Load failed ... context canceled" between 16:16 and 16:36: each client timeout cancelled the load, and the retry started the load again from zero. Selection for letter 1 failed ("Request timed out after 120s") and the letter was written without it. The one-model-at-a-time before run (1,074 s for the first letter) probably had the same cause. This is a defect in how the client waits for a model load, separate from the setup. It must be fixed, or the after run measures the same retry loop.

## Handover to the laptop (2026-11-14)

- The user moves the work to the laptop (RTX 2070, 16 GB RAM). The desktop is then free to measure the lean setup.
- The session scratchpad was cleared, and the scratch clone with `make app` went with it. The change was rebuilt from the session record on a fresh clone and saved as `make-app.patch` (5 files: `scripts/dev.sh`, `mprocs.app.yaml`, `Makefile`, two test files). The 11 launcher and mprocs tests pass again; black, ruff, and `bash -n` pass. It is not applied to `main`.
- To use it on a scratch clone: `git apply tasks/active/lean-setup/make-app.patch`.
- `tools/profile_recorder.sh` (Windows host; argument: the output folder) and `tools/measure_letter_flow.py` (run from `apps/backend-py`; the eval pairs are in the repo) are the measurement tools from this task.
- Order agreed with the user: first `tasks/archive/ollama-load-timeout/`, then the lean-setup after run, then the `llama3.2:3b` experiment.
