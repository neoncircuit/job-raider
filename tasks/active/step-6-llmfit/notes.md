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

## Blockers / Questions

- None.

## Review
