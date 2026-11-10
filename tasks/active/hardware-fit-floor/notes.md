# Notes: File-Size Floor and One Unit for Hardware Fit

## Why (2026-11-10)

The user's screenshot of Settings showed `gemma4:e4b` as "Fits" next to an 8.9 GB file, on an 8 GB card. The user chose to fix it ("Yes, fix it here").

## Cause

- llmfit's plan for `gemma4:e4b` at Q4_K_M is 5.79 GB, below the 9.61e9-byte file. A Gemma "e" model can keep part of its weights off the GPU in some runtimes; Ollama loads the whole file.
- It was the only mapped model whose plan was below its file size.
- `fit.py` divided bytes by 10^9, while the VRAM (nvidia-smi and llmfit: 8192 MiB is 8.0) and the Size column use 1024^3.

## Handoff written and checked (2026-11-10, Claude)

`mh-1-file-size-floor.md` (runner) is written. It is not applied. In `label_installed`, a plan below the file size (in GiB) is not used; the rough estimate (file size plus 1 GB) takes its place, with the source `rough_estimate`. `BYTES_PER_GB` is 1024^3. The docs explain the floor and the unit. Tests: 2 new, 3 values updated.

A first version used the file size plus 1 GB as the floor. The smoke run showed that it replaced good plans by 0.01 GB (`qwen2.5-coder:7b`: plan 5.35, floor 5.36). The floor is now the file size alone, and mutant M4 guards it. The first handoff text also said that no other label changed; the smoke run showed `granite4.1:8b` moving to Fits, and the text now says so.

Runner test on the clone (the handoff was in the clone): the red step fails (4 tests), the 4 checks pass (63 tests, black, ruff, mypy gate with 179 known and 0 new), and commit `3509f0d` is on the clone. The HEAD of the real repository did not change.

Other checks on the clone:

- The full backend suite passes: 2,240 tests.
- Mutants: 4 of 4 are caught (no floor, decimal GB, plan ignored without a file size, floor with the allowance).
- Smoke run with the real llmfit 1.1.20 and the local Ollama (read-only; no model loaded): 15 fit, 4 over the budget, 2 too large (before: 15, 5, 1). `gemma4:e4b` is Too large (9.95 GB, rough estimate). `granite4.1:8b` is Fits (5.98 GB in GiB against the 6.0 GB budget; 6.35 in decimal GB before). The mapped models keep their plans: `qwen2.5-coder:7b` and `qwen2.5:7b` 5.35, `gemma3:4b` 4.06, `deepseek-r1:8b` 6.16 (over the budget).

Limit: suggestions do not change. A model that is not installed has no file size yet, so a Gemma "e" suggestion can still show llmfit's lower number.

## Review
