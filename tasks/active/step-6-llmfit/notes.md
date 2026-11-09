# Notes: Step 6, Hardware Fit with llmfit

## Why (user, 2026-11-08)

The user supports open-source models (the open-source-first rule) and wants people to decide for themselves which models their system can run. Decision: llmfit is "an optional but recommended option".

## Measure (2026-11-08, Claude)

Facts from the llmfit repository (through `gh`) and from read-only runs in WSL on the user's machine.

| Item | Fact |
|---|---|
| Project | `AlexsJones/llmfit`, MIT, about 38,700 stars, active (last push 2026-11-08). Latest release v1.1.20 (2026-11-03). Also on PyPI (`uv tool install llmfit`, pip). |
| Installed here | v1.1.6 at `/usr/local/bin/llmfit` in WSL. It does not have `--memory-percent` (a newer flag). |
| Privacy | The README says it contacts external services only for features the user asks for (downloads, the leaderboard). `system`, `fit`, `recommend`, and `plan` are read-only. It reads the local Ollama at `localhost:11434` (`GET /api/tags`). |
| Hardware in WSL | `llmfit --json system` works: CUDA, RTX 3070 Ti, 8.0 GB VRAM, 608 GB/s, 12 CPU threads, 7.72 GB RAM. WSL sees the GPU through `/usr/lib/wsl/lib/nvidia-smi`. |
| Runtimes | `mlx`, `llamacpp`, `vllm`. There is no `ollama` runtime: Ollama runs GGUF files, which llmfit scores as `llamacpp`. |
| JSON fields we need | `name`, `ollama_name`, `best_quant`, `fit_level` (`Perfect`, `Good`, `Marginal`, `Too Tight`), `memory_required_gb`, `memory_available_gb`, `utilization_pct`, `estimated_tps`, `installed`, `score`, `use_case`, `license`. |
| Raw recommendations | Noisy. Of the top 30 `llamacpp` picks, only 3 have an `ollama_name`; most are random Hugging Face fine-tunes. We must not show them as they are. |
| Catalog mapping | `fit -n all`: 4,822 rows, 118 distinct `ollama_name` values. Only 5 of the 21 installed Ollama tags map by name. The user's own tags (for example `qwen2.5-coder-7b-16k`) never map. |
| Labels are permissive | `deepseek-r1:8b` is "Perfect" at 7.92 of 8 GB (99.1%). `qwen2.5-coder:7b` is "Perfect" at 87.9%. |
| Quant mismatch | llmfit scores its `best_quant` (Q6_K for the 7B models). The Ollama default tags are usually Q4_K_M. So its memory number is for a different file than the one installed. `plan` takes `--quant`. |
| Existing code | `src/api/ollama_admin.py` lists models with size and refuses pulls at 9B or more (`MAX_PARAMS_BILLION`). `ollama-models-card.tsx` shows the installed models in Settings. |

## Design

1. **Two sources, one budget.** llmfit gives the hardware (`system`) and the catalog. Ollama gives what is installed, with the real file size and quantization. The budget is the detected VRAM times the user's headroom setting. On v1.1.6 the budget is passed as `--memory <budget>`; that flag works on all versions, so we do not need `--memory-percent`.
2. **A label for each installed model.** When a tag maps to the catalog, use `plan --quant <the installed quant>` so the number matches the real file. When it does not map, compare the Ollama file size plus a context allowance with the budget, and mark the label "rough estimate". The card shows our label and, where present, llmfit's own label and use percent.
3. **Suggestions.** Only catalog rows with an `ollama_name`, within the budget, under the 9B pull limit, sorted by score. Embedding models are listed apart.
4. **Pull guard.** The existing 9B refusal stays. A model over the budget gets a warning (see the questions below).
5. **Pinned version.** One pinned version, with a contract test on saved samples. A newer version with changed JSON gives "not available", not a crash.

## Plan

| # | Content | How |
|---|---------|-----|
| MH-1 | Measure the pinned version (v1.1.20): samples, mapping, run time, wheel | Install into a scratch venv (needs the user's approval: download); read-only runs |
| MH-2 | Backend client, parser, budget, headroom setting | Runner handoff; unit tests on fixtures |
| MH-3 | `GET /api/hardware/fit`, pull warning | Runner handoff; route tests |
| MH-4 | Card labels, suggestions, install hint, demo handler | Runner handoff; unit tests, E2E, demo E2E |
| MH-5 | `setup.sh` install with skip flag, docs page, README | Direct commit or handoff; fresh-setup check |
| MH-6 | Optional: hardware profile in MLflow evaluation runs | Runner handoff |

## Open questions for the user

1. Safety margin. Recommended: the budget is 75% of the detected VRAM by default, and the user can change it in Settings. On this machine that is 6 GB of 8 GB.
2. Setup default. Recommended: `setup.sh` installs the pinned llmfit by default (with `--no-llmfit` to skip), because "optional but recommended". A failed install prints a note and setup continues.
3. Pull guard for a model over the budget. Recommended: a warning that the user must confirm, so the user decides. Or: refuse it, as the 9B limit does.

## Decisions (user, 2026-11-08)

1. Safety margin: 75% of the detected VRAM by default, and the user can change it in Settings.
2. Setup: `setup.sh` installs the pinned llmfit by default, with `--no-llmfit` to skip it. A failed install does not stop setup.
3. Pull guard: a model over the budget gets a warning, and the pull starts only after the user confirms. The 9B refusal stays.

## MH-1 measured (2026-11-08, Claude)

The user approved the plan and the download ("Yes, approve and start"). llmfit v1.1.20 is installed from PyPI into the scratch venv `~/llmfit_scratch/.venv` in WSL. The real repository did not change. The raw JSON samples are in the Claude scratchpad (`s6mh1/`); they hold the real hardware names, so they are not committed.

| Item | Fact (v1.1.20) |
|---|---|
| Package | `llmfit-1.1.20-py3-none-manylinux_2_17_x86_64.whl`, 7.9 MB. pip puts a 42 MB binary at `.venv/bin/llmfit`. So `setup.sh` can install it into the backend `.venv` with one pinned pip line. |
| Run time | `--json system` 0.8 s; `--json fit -n <all>` 2.4 to 2.8 s; `plan` 0.8 s. The API must cache the results and not run llmfit on each request. |
| Flags | `--memory`, `--memory-percent`, `--ram`, `--max-context` are global flags before the subcommand. `fit` has no `--runtime` flag, so we filter on the `runtime` field (`llama.cpp`; the others are `vLLM` and `bitnet.cpp`). |
| Errors | A bad flag exits 2 with plain text on stderr (no JSON). The client must treat any non-zero exit or non-JSON output as "not available". |
| `system` JSON | `system.gpu_vram_gb`, `gpu_name`, `backend`, `has_gpu`, `total_ram_gb`, `available_ram_gb`, `gpus[]`, and a new `providers` block. Free VRAM is not in it now. |
| `fit` JSON | `{system, models}`. 13,112 `llama.cpp` rows and 132 distinct `ollama_name` values. New fields: `quantization`, `runnable`, `estimate_confidence`. |
| Mapping | 8 of the 21 installed tags map by `ollama_name` (v1.1.6: 5). Not mapped: the user's own tags (3), newer families (`qwen3.5`, `granite4.1`, `olmo-3`, `nemotron-3-nano`, `ornith`), `mistral:latest`, `deepseek-coder:6.7b`, and one embedding model. |
| Labels | Less permissive than v1.1.6: `deepseek-r1:8b` is "Marginal" at 87% (v1.1.6: "Perfect" at 99%). Still, each label is for `best_quant` (Q6_K, Q5_K_M, Q8_0), and every installed tag here is Q4_K_M (or Q4_0, F16). |
| `plan --quant` | `plan "Qwen/Qwen2.5-Coder-7B-Instruct" --quant Q4_K_M --context 8192 --json` gives the installed file's need: minimum 5.35 GB VRAM, recommended 7.1 GB, `disk_size_gb` 4.42 (the Ollama file is 4.68 GB). It grades the GPU path against the VRAM that is free now (5.7 GB here), not the total. |
| Free VRAM | `nvidia-smi` shows 2.3 GB of 8 GB in use while idle (the Windows desktop and any loaded model). |

Consequences for MH-2 and MH-3:

1. The budget is `gpu_vram_gb` times the headroom (75%). It is stable, so labels do not change when a model loads. The card also shows that the desktop uses some VRAM.
2. Mapped tags: run `plan` with the installed quant and compare its minimum VRAM with the budget. Unmapped tags: compare the Ollama file size plus a context allowance with the budget, and mark the label "rough estimate".
3. Cache `system` and `fit` (for example 10 minutes) and run `plan` only for mapped tags, in the background, with one call per tag at most per cache period.
4. The minimum version is 1.1.20, because `--memory-percent` and the current field names start in that range. An older binary (such as the 1.1.6 in `/usr/local/bin`) gives "update recommended", and the client then uses only `system`.
5. The test fixtures use made-up hardware ("Example GPU", 12 GB) and a few catalog rows copied in shape, not in value.

- [x] MH-1 is done. The acceptance criterion is checked.

## MH-2 written and checked (2026-11-08, Claude)

`mh-2-llmfit-client.md` (runner) is applied on the repo (2026-11-08, Claude ran the runner on the user's word "Yes, apply it"): commit `9b7b2be`. The red step failed, the 4 checks passed, and `git diff 686be0c HEAD`, without `tasks/`, is empty. Pushed as `edc64c2`; CI run 42475903565 passed (all 12 jobs, on a runner without llmfit installed). It adds `src/hardware/` (`llmfit_client.py`, `fit.py`), the `hardware.vram_headroom_percent` setting (30 to 100, default 75), 3 fixtures with made-up hardware, and 2 test files (40 tests).

Runner test on the clone `~/s4_work` (the handoff was in the clone; `git rev-parse --show-toplevel` gave the clone): the dry run is valid, the red step fails for the right reason (`ImportError: HardwareSettings`), the 4 checks pass (62 tests, black, ruff, mypy gate with 179 known and 0 new), and commit `686be0c` is on the clone. The HEAD of the real repository did not change.

Other checks on the clone:

- The full backend suite passes: 2,204 tests. That run was before one test was added for mutant M3; the runner check ran the changed test file again.
- black and ruff on all CI paths pass.
- Mutants: 12 of 12 are caught. The first run caught 11: with the low-quant filter removed, the tests still passed, because the only Q3 row in the fixture was also above 9B. A new test with a small Q3 row now catches it.
- Smoke run against the real llmfit 1.1.20 and the local Ollama (read-only; no model loaded): budget 6.0 GB of 8.0 GB. Of 21 installed tags, 8 use an llmfit plan for the installed quant and 13 use the rough estimate. 15 fit, 5 are over the budget (`deepseek-r1:8b` at 6.16 GB, `qwen3.5:9b`, `qwen3.5-9b-16k`, `ornith:9b`, `granite4.1:8b`), and 1 is too large (`qwen2.5:14b` at 10.57 GB). There are 8 suggestions, such as `gemma4:e2b`, `phi3`, and `llama3.2:3b`. The old binary in `/usr/local/bin` gives "update recommended", and a missing binary gives "not installed".
- The smoke run took 11.7 s, with 8 `plan` calls and 2 catalog runs. MH-3 must cache the results and run them in the background.

## MH-3 written and checked (2026-11-08, Claude)

`mh-3-hardware-api.md` (runner) is applied on the repo (2026-11-09, Claude ran the runner on the user's word "Yes, apply it"): commit `1f96f22`. The red step failed, the 4 checks passed, and `git diff 3e8d820 HEAD`, without `tasks/`, is empty. Pushed as `e7a4b08`; CI run 42571909728 passed (all 12 jobs). It adds `src/hardware/service.py` (the cached report and the pull check), `src/api/routes/hardware.py` (`GET /api/hardware/fit`), the over-budget 409 on `POST /api/settings/ollama/pull` with `confirm_over_budget`, the `quantization` field in `ollama_admin.list_models`, a conftest guard so tests never run a real llmfit, and 20 tests.

Runner test on the clone (the handoff was in the clone): the dry run is valid, the red step fails for the right reason (`ImportError: service`), the 4 checks pass (115 tests, black, ruff, mypy gate with 179 known and 0 new), and commit `3e8d820` is on the clone. The HEAD of the real repository did not change. The first run passed.

Other checks on the clone:

- The full backend suite passes: 2,225 tests.
- Mutants: 12 of 12 are caught (cache, plan cache, refresh, budget passed to the catalog, plans used, FP16 name, quant from the tag, no warning for an unknown tag, the pull warning, the confirm flag, the too-large message, and the quantization field). In the first run, two mutants did not apply because of an indent error in the mutant script, and the file did not change; the rerun with the correct text caught both.
- Smoke run through the API (a TestClient with the real llmfit 1.1.20 and the local Ollama; read-only): the cold report took 5.0 s (the MH-2 smoke took 11.7 s without the cache and the parallel plans), and the warm report took 0.0 s. The labels match MH-2: 15 fit, 5 over the budget, 1 too large, and the same 8 suggestions. A pull of `deepseek-r1:8b` answered 409: "needs about 6.2 GB of GPU memory, above your safety budget of 6.0 GB (75% of 8.0 GB). Confirm to pull it anyway." The pull state stayed `idle`, so no download started.
- The first smoke run failed in the smoke script, not in the code: TestClient's default host `testserver` is not in the trusted hosts. The script now uses `http://localhost`.

## MH-4 written and checked (2026-11-09, Claude)

`mh-4-settings-card.md` (runner) is applied on the repo (2026-11-09, Claude ran the runner on the user's word "Yes, apply it"): commit `1b1939a`. The red step failed, the 4 checks passed, and `git diff ab7fb94 HEAD`, without `tasks/`, is empty. Pushed as `f90d284`; CI run 42584411567 passed (all 12 jobs, including the E2E and demo E2E jobs). It adds the fit badge column, the hardware fit panel (budget, suggestions with Pull, or the install hint without llmfit), the over-budget confirm dialog, the "GPU memory budget (%)" settings field, `ApiError.details`, the demo answers, the E2E mock answers, and 4 test files (16 unit tests, 1 E2E test).

Decision during the work: the demo data rule is "no invented GPU or host readings", so the demo fit report is `available: false`, with a reason and the install hint. The demo now lists the two sample models that its settings already name as installed.

Runner test on the clone (the handoff was in the clone): the red step fails for the right reason (`Failed to resolve import "@/lib/hardware-fit"`, and the card tests find no "Fits", no panel, no Pull or Refresh button), the 4 checks pass (vitest, prettier, eslint with no warnings, tsc), and commit `ab7fb94` is on the clone. The HEAD of the real repository did not change.

Fixes before the final runner test:

- A test asked for a custom "30 to 100" error. The browser's own check (`min=30`, also in jsdom) stops the submit first, so that message could never show. The message is removed, and the test checks that the field is invalid and nothing is saved.
- In the E2E spec, `getByLabel("Hardware fit")` also matched the "Refresh hardware fit" button (Playwright matches a substring). The spec uses `exact: true`.

Other checks on the clone:

- Unit tests: 373 pass (358 before). The 86 MSW "Cannot bypass a request" log lines are the same before and after this change.
- E2E with the API mock: 43 of 44 pass. The one failure was the Jobs page search test, which this change does not touch; it passed in the run before, and 3 repeats of the Jobs and hardware fit specs passed (24 of 24).
- Demo E2E: 18 pass, after a build with `NEXT_PUBLIC_BASE_PATH=/job-raider` (as in CI). The first demo run failed for a setup reason: the build had no base path, so the demo did not start.
- Mutants: 15 of 15 are caught (13 with the unit tests; the client that drops `details` and the request body that drops `confirm_over_budget` with the E2E spec).
- Screenshots (API mock, desktop and mobile): the card shows the budget line, the suggestion with its Pull button, and the Fits and Over budget badges. The confirm dialog shows the backend's message.
- Observation: on a phone, the model table now has 5 columns, so the Fit column and the delete button need a sideways scroll (the table already scrolls). A later change can hide the Parameters column on small screens.
- Setup note: the main E2E config does not read `PLAYWRIGHT_CHROMIUM_PATH`, so local runs in WSL use an untracked config that sets the browser path for both projects (as in Step 5).

## MH-5 written and checked (2026-11-09, Claude)

Applied on the repo (2026-11-09, Claude, on the user's word "Yes, apply it"): commit `1535e07`, a cherry-pick of `277b2c5`, with the mode change of `setup.sh`. The only difference from the clone commit, outside `tasks/`, is the lesson in `docs/lessons.md`, which is in the commit below it. Pushed as `9ecab41`; CI run 42590359420 passed (all 12 jobs; the new setup tests ran in Test Backend).

One commit was ready on the WSL clone `~/s4_work`, on top of `a51b2e9`: `277b2c5` `feat(setup)`. It is a direct commit, not a runner handoff: the runner cannot carry a file that has code fences in it, and `docs/hardware-fit.md` has Mermaid and bash blocks. To apply it, the real repository fetches the clone and cherry-picks it.

- `apps/backend-py/requirements-optional.txt` (new): `llmfit==1.1.20`. CI does not install it.
- `setup.sh`: `install_llmfit` runs after the requirements (user decision: on by default); `--no-llmfit` skips it; a failed install records a warning and setup goes on; an unknown option exits 2 with the usage; `main` runs only when the file is executed, so a test can source it; the summary names hardware fit. The file is now executable in git (mode 100644 to 100755), so `./setup.sh` works on a fresh Linux clone.
- `docs/hardware-fit.md` (new): the labels, the budget, where the numbers come from, the install commands, and the limits (Docker, WSL, privacy, demo), with a flow diagram. README (feature, setup note, doc link) and `docs/index.md` link it.
- `tests/unit/test_setup_llmfit.py` (new, 6 tests): it checks the guard in the file text, and only then sources `setup.sh` with a fake `pip`.

Checks on the clone (second, safe run):

- Red: before the change, the 6 tests fail, and none of them sources the old file.
- `bash -n setup.sh` passes; `bash setup.sh --help` exits 0; `bash setup.sh --bogus` exits 2 with "Unknown option". shellcheck is not installed.
- The 6 tests pass; black and ruff pass.
- A real install through `install_llmfit` into a new temporary venv installed llmfit 1.1.20, and `llmfit -V` answered.
- Mutants: 5 of 5 are caught (flag ignored, failure stops setup, unknown option accepted, main runs on source, pin drifts from the client minimum).
- No file of the real `.venv` changed during this run.

### Incident: the first MH-5 check ran the whole setup (2026-11-09)

In the first check run, the red step and the "main runs on source" mutant sourced a `setup.sh` without the guard, so each source ran the whole setup, about ten times, on the clone. The clone's `apps/backend-py/.venv` is a symlink to the real `.venv`. Effects:

- Real `.venv` (16:24 to 16:33): pip 26.3, wheel 0.48.0, and setuptools 84.2.1 were installed, and llmfit 1.1.20. A test timeout killed one pip run while the next one started, so setuptools was left half installed: `import setuptools` failed (`No module named '_distutils_hack'`), and a `~distutils_hack` stash stayed. `pip check` passed, and fastapi, pydantic, and mlflow still imported.
- `~/.cache/ms-playwright`: Chromium 1228 and its headless shell were downloaded (641 MB).
- The clone only: a generated `apps/backend-py/.env`, a `post-checkout` hook, and a frontend `.env.local`.

Repair (user decisions, 2026-11-09): setuptools 84.2.1 was reinstalled with `--force-reinstall --no-deps`, and the stash was removed; `import setuptools` works, `pip check` passes, and the core imports work. llmfit stays in the real `.venv` (user: keep it). The Chromium 1228 folders were deleted (user: delete them). The clone files were removed. The test now checks the guard before it sources the file, and `docs/lessons.md` has the lesson.

## Blockers / Questions

- None.

## Review
