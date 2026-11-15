# Current Priorities

## Active Focus
- [ ] Laptop as the workstation until the desktop upgrades; start each laptop session from `tasks/active/laptop-workstation/task.md`.

## Next Up
- [ ] Project scoring in fresh graduate mode: projects give about 6 of 35 points (only overlap with the job's skill list counts), so passed scores are close together (50 to 63). Match projects against the job description too, and measure with the ranking suite and a live run (`tasks/archive/scoring-calibration/notes.md`). Also: `config/scoring_config.yaml` is not loaded by any code.
- [ ] CV writer for smaller GPUs: `qwen2.5:3b` passed the CV checks with half the GPU memory and time (`tasks/archive/lighter-writer/`). The user decides on a default change; measure the model changes per CV first.
- [ ] Small clean-up: remove the old "Phase 36 to 44" feature list at the end of `setup.sh`.

## Done
- [x] Scoring calibration (fresh graduate mode): per-run score and filter counts, senior roles capped, whole-word internship check, MyCareersFuture levels, Min Score 50 in fresh graduate mode; same 68 jobs: 1 passed to 21 passed, no senior titles, most fit (user) (`tasks/archive/scoring-calibration/`; done 2026-11-16)
- [x] Job details readable on laptop screens: one scroll area and a fixed Apply row; description area 40 to 414 px at 1366 x 768 (`tasks/archive/responsive-job-detail/`; done 2026-11-15)
- [x] Lighter writer on the laptop: letters stay on `qwen2.5:7b` (neither `qwen2.5:3b` nor `llama3.2:3b` passed); for CVs `qwen2.5:3b` passed and `llama3.2:3b` failed; low-memory guide section (`tasks/archive/lighter-writer/`; done 2026-11-15)
- [x] `setup.sh` ignores a carriage return when it reads `API_KEY`: env files with Windows line endings and an empty key now get a generated shared key (`tasks/archive/setup-env-crlf-key/`; done 2026-11-15)
- [x] Lean setup for 16 GB RAM: `make app` (production frontend, backend without reload), `docs/low-memory-guide.md`; laptop run 168 s against 204 s for 3 letters, committed memory peak 4.5 GB lower, paging peak halved (`tasks/archive/lean-setup/`; done 2026-11-15). Closes the Next Up item "RAM during make dev".
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
