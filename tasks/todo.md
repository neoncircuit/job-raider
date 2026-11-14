# Current Priorities

## Active Focus
- [ ] Laptop as the workstation until the desktop upgrades; start each laptop session from `tasks/active/laptop-workstation/task.md`.
- [ ] Lean setup for 16 GB RAM machines: `make app`, measured before and after (`tasks/active/lean-setup/`); the after run is measured on the laptop.

## Next Up
- [ ] Scoring calibration: in the pipeline test (2026-11-14) 58 of 59 profile-matched jobs scored below 60 (best 61), so Max Jobs 2 gave 1 document. Find out if the scoring (fresh graduate mode) or broad keywords cause it, and measure before changing (`tasks/archive/scrape-keyword-search/`).
- [ ] Lighter writer: `qwen2.5:7b` took total GPU use to 7.2 to 7.3 of 8 GB on this machine. Measure `qwen2.5:3b` and `llama3.2:3b` (Meta Llama-3.2-3B-Instruct) for letters and CVs with the writer and resume suites (quality guard first) to make the app usable on smaller GPUs.
- [ ] RAM during `make dev`: 0.6 to 1.1 GB free with heavy paging; the Next.js dev server is part of it. Measure a production build (`next start`) for everyday use.
- [ ] Small clean-up: remove the old "Phase 36 to 44" feature list at the end of `setup.sh`.

## Done
- [x] Ollama load timeout: the client loads the model first with a 600 s timeout, so the 120 s chat timeout no longer cancels a slow load and the retry no longer starts it again; laptop run: 0 cancelled loads, 0 timeouts, 3 letters in 218 s (`tasks/archive/ollama-load-timeout/`; done 2026-11-15)
- [x] Relative paths in documentation: no full host paths in tracked files; `test_no_host_paths.py` fails CI on a new one (`tasks/archive/relative-paths-in-docs/`; done 2026-11-14)
- [x] Setup on a fresh machine: `setup.sh` and `make dev` find a suitable Python or install `.python-version` into `.tools/` with a pinned uv (no sudo); checked on the laptop (`tasks/archive/python-version-setup/`; done 2026-11-14)
- [x] One local model in GPU memory at a time by default, with a Settings switch; the no-op VRAM guard removed (`tasks/archive/one-model-at-a-time/`; done 2026-11-14)
- [x] Cover letters: stock-phrase polish after every rewrite (Review & rewrite and the grounding rewrite) (`tasks/archive/letter-rewrite-polish/`; done 2026-11-14)
- [x] Pipeline searches each keyword (was: all keywords at once, 0 jobs), a run with no jobs stops with a warning, Request Cancel hidden after a run (`tasks/archive/scrape-keyword-search/`; done 2026-11-14)
- [x] CVs: checked rewrite of stock-phrase sentences (26 to 2 of 65 CVs, no new accuracy flags) (`tasks/archive/cv-stock-phrase-rewrite/`; done 2026-11-14)
- [x] CV eval suite: `main.py eval resume` with a `qwen2.5:7b` baseline (`tasks/archive/cv-eval-suite/`; done 2026-11-13)
- [x] LinkedIn country hosts such as `sg.linkedin.com` are accepted and stored as `www.linkedin.com` (`tasks/archive/linkedin-country-hosts/`; done 2026-11-13)
- [x] The local `.venv` uses the CI versions of black, ruff, mypy, and the mypy stubs, pinned in `requirements.txt` (`tasks/archive/ci-type-check-pins/`; done 2026-11-13)
- [x] Cover letters and CVs that do not sound generic: stock-phrase detector, checked sentence rewrite for letters, stock-phrase count for CVs (`tasks/archive/generic-phrasing/`; done 2026-11-13)
- [x] Review follow-up (2026-10-18), Steps 0 to 5 (`tasks/archive/review-follow-up/`; closed 2026-11-12)
- [x] CI E2E jobs install Chromium without `apt` and the Ubuntu mirror (`tasks/archive/ci-playwright-mirror/`; done 2026-11-12)
- [x] Move to the WSL file system (ext4), and make dev creates, repairs, and updates the environments (`tasks/archive/dev-deps-repair/`; done 2026-11-11)
- [x] One split view for `make dev` with mprocs (`tasks/archive/make-dev-split-view/`; done 2026-11-10)
- [x] Hardware fit: file-size floor and one unit (`tasks/archive/hardware-fit-floor/`; done 2026-11-10)
- [x] Local cleanup (2026-11-10): the Step 5 leftovers `frontend-py/` (521 MB of `.venv` and caches) and `apps/backend-py/src/database/` (`__pycache__` only) are deleted. `apps/frontend-ts/node_modules` had root-owned folders in WSL (`@types`), so `npm install` failed with EACCES; it was deleted from Windows and rebuilt with `npm ci` (lockfile unchanged, `@types/node` 24.19.2, tsc and 378 unit tests pass).
- [x] Stable Jobs page E2E search (`tasks/archive/jobs-e2e-flake/`; done 2026-11-10)
- [x] Self-hosted fonts (`tasks/archive/self-hosted-fonts/`; done 2026-11-10)
- [x] Local models table on a phone (`tasks/archive/phone-model-table/`; done 2026-11-09)
- [x] Step 6: Hardware fit with llmfit, optional and recommended (`tasks/archive/step-6-llmfit/`; done 2026-11-09)

*(Agent Note: When starting a task above, ensure a corresponding folder exists in `tasks/active/`)*
