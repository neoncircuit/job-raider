# Notes: one-model-at-a-time

Planned 2026-11-14 after the cover letter test. Review section to be added when the task is done.

## Before measurement (2026-11-14 06:06 to 06:27 UTC, `make dev` running, user approved)

Script `measure_letter_flow.py` (scratchpad): `generate_cover_letter_sync(deep=True, review=True)`, no selection given (as on the Cover Letter page), first 3 grounding pairs, from the clone at `301ded7` (= `main` code). Full app log kept (`before_app.log`). Resource recorder every 10 s (it started about 30 s late, before any model loaded; it also overwrote the log of the earlier UI letter test, whose numbers are in the task plan).

| Pair | Time | Words | Stock phrases (final) | Score | Rewrites |
|------|------|-------|-----------------------|-------|----------|
| analogical_claim__classifier_robotics | 1,074 s | 226 | "feel free to contact me", "moreover" | 85 | 1 |
| analogical_claim__fastapi_kubernetes | 21 s | 242 | none | 85 | 1 |
| analogical_claim__forms_security | 16 s | 272 | none | 60 | 1 |

- Total 1,111 s (mean 370 s; pair 1 is almost all of it).
- Polish step logs: pair 1 twice "answer format not usable, letter kept" (after the draft and after the rewrite); pairs 2 and 3: 2 of 2, 1 of 1, 1 of 1 sentences replaced. This explains the earlier unchanged letter: for that pair the 7B model does not answer in numbered lines.
- Recorder: GPU before the run 4.0 GB (no model). Peak 10.8 GB summed at 14:14 with only `qwen2.5:7b` loaded; two models together in 2 of 54 samples (the 3B model with the 7B, at 14:26). For about 6 minutes at the start the GPU rose while `ollama ps` listed no model, and some samples came back empty (machine overloaded). RAM 0.8 to 1.8 GB free.
- The no-op VRAM guard printed "VRAM usage at 95.5%, falling back to CPU" 14 times.
- Reading: the main cost on this machine is the GPU total (a 4 GB idle baseline plus the 4.7 GB model is more than 8 GB), not only two models at once; warm letters take 16 to 21 s.

## Build and checks (2026-11-14, scratch clone)

- `ollama_client.py`: `_unload_other_models()` (GET `/api/ps`, then POST `/api/generate` with `keep_alive: 0` for each other model; errors logged at debug and ignored) runs before each chat request when `one_model_at_a_time` is on (client default off). The no-op guard `_check_vram_before_inference` and the client's `gpu_monitor` argument are removed; a module logger replaces the guard's `print`.
- `router.py`: `_ollama_one_model_at_a_time` (default True, from `cost_limits.ollama_one_model_at_a_time`) passed to each `OllamaClient`.
- `settings.py`: `CostLimits.ollama_one_model_at_a_time: bool = True`. Frontend: the type field, the form field (default true for an old backend), and a "One local model at a time" switch under Ollama keep_alive.
- Not changed: the embedding client has its own copy of the guard (`_check_vram`; only a warning). RAG is off by default; note for later.
- Tests: 6 backend (`tests/unit/test_ollama_one_model.py`: unload before the chat, same model not unloaded, option off makes no call, failing `/api/ps` or unload does not block, guard gone, router passes the setting) and 3 Vitest (`tests/app/settings/one-model-setting.test.tsx`). Red step: 4 backend and 3 frontend fail without the change; the 2 that pass are guards (option off; errors do not block). Mutants: own model unloaded, option ignored, unload error not caught, router hard-codes off, page default off: 5 of 5 caught.
- Full checks: black and ruff clean (one import-order fix), mypy gate 177 known and 0 new, pytest 2,355 passed; frontend tsc, eslint, Prettier clean, Vitest 385 passed.
- Clone commit `5337f67` on top of `f1de701` (= `main`).

## After measurement (2026-11-14 06:52 to 06:55 UTC, clone `5337f67`, `make dev` running, user approved)

Same script, pairs, and options as the before run; the recorder started before the run this time.

| Pair | Time | Words | Stock phrases (final) | Score | Rewrites |
|------|------|-------|-----------------------|-------|----------|
| analogical_claim__classifier_robotics | 40 s | 232 | none | 85 | 1 |
| analogical_claim__fastapi_kubernetes | 46 s | 245 | none | 87 | 1 |
| analogical_claim__forms_security | 42 s | 296 | none | 85 | 1 |

| | Before | After |
|---|---|---|
| Samples with two models loaded | 2 of 54 | 0 of 13 |
| Peak GPU (summed Windows counters) | 10.8 GB | 8.8 GB |
| Time per letter | 1,074 s, 21 s, 16 s | 40 s, 46 s, 42 s |
| Total for 3 letters | 1,111 s | 127 s |
| RAM free at the start | 1.0 GB | 3.2 GB |

- The log shows 12 unloads (the 3B and 7B models swap about 4 times per letter: selector, writer, reviewer, writer, validator).
- Polish step: 2 of 2, 1 of 1, 3 of 3, 1 of 1, 3 of 3, 1 of 1 sentences replaced; no "answer format not usable".
- Guard: never two models together after the change. It passes.
- Reading: the slow worst case (GPU memory over 8 GB while RAM was short; 18 minutes for the first letter) did not happen; GPU use stayed at the idle baseline plus one model. A warm letter is slower (about 40 to 46 s against 16 to 21 s), because each swap reloads a model. Limits: the before run started with less free RAM (1.0 against 3.2 GB), so part of the first letter's gain comes from the calmer machine; peak GPU is still above 8 GB on the summed counters (4.1 GB baseline plus the 7B model).

- Applied (user approved, 2026-11-14): `main` fast-forwarded to `5337f67`; `git diff` against it is empty; the running `make dev` reloaded (the OpenAPI schema shows `ollama_one_model_at_a_time`). Not pushed yet.
