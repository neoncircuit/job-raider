# Scratchpad & Notes

## Plan (2026-11-02, Claude)

Request (user): "Make 3b the default", after Step 3.8 recommended `qwen2.5:3b` (`tasks/archive/step-3-8-writer-models/`).

### What exists today

- `src/llm/router.py` `DEFAULT_ROUTES`: `cover_letter_writing` uses `ollama/qwen2.5:7b` with no fallback. `cover_letter_review` uses `qwen2.5:3b` (fallback `gemma3:4b`).
- `src/api/ollama_models.py`: `OLLAMA_LARGE_TASKS` has `cover_letter_writing`; `apply_ollama_tier_models` sets each large task to the large model; `default_cloud_fallback_model` gives a small task the small cloud model. `RECOMMENDED_OLLAMA_SMALL = "qwen2.5:3b"`, `RECOMMENDED_OLLAMA_LARGE = "qwen2.5:7b"`.
- `apps/frontend-ts/src/lib/ollama-tiers.ts`: the same two lists and the same cloud fallback rule, for the Settings page.
- No existing test pins the tier of `cover_letter_writing` (search of `tests/unit/test_ollama_models.py`, `test_settings_api.py`, `test_router_settings.py`, `test_cloud_fallback_none.py`, and `apps/frontend-ts/tests/lib/ollama-tiers.test.ts`).
- Docs that name `qwen2.5:7b` for cover letters: `docs/usage.md` (Review & rewrite tip) and the 2026-08-25 decision-log entry (history; it stays). `docs/architecture.md` "Writer (qwen2.5:7b)" is the resume writer, so it stays.

### Micro-handoff

- MH-1 (runner, full code): the default route, the two tier lists, and tests (backend: a new test file; frontend: new cases in `tests/lib/ollama-tiers.test.ts`). Checks: the new and related backend tests, the frontend tier tests, black, ruff, the mypy gate, eslint, prettier, and `tsc`.
- Docs and the backlog in Claude's record commit.

## Decisions (user, 2026-11-02)

1. "Small tier for both": `cover_letter_writing` moves to the small tier, and its default cloud fallback becomes the small cloud model. Plan approved.

## MH-1 written and checked (2026-11-02, Claude)

`mh-1-writer-default.md` (runner): the `cover_letter_writing` route uses `qwen2.5:3b`; `cover_letter_writing` moves from the large to the small tier in `src/api/ollama_models.py` and `src/lib/ollama-tiers.ts`; `tests/unit/test_writer_default.py` (5 tests) and one new case in `tests/lib/ollama-tiers.test.ts`. This is the first runner handoff with frontend checks: the commands start with `source ~/.nvm/nvm.sh && nvm use 24 &&`, and a scratch clone links the repo's `node_modules` (Linux builds) as it links the `.venv`.

- Scratch clone: red backend 5 failed; red frontend 1 failed and 4 passed. After the edits: black leaves the files unchanged; ruff clean; 45 backend tests pass (the new file and the routing, Settings, fallback, override, and cache tests); the mypy gate has 0 new errors; 5 frontend tier tests pass; prettier, eslint, and `tsc --noEmit` clean.
- Mutants 5 of 5 caught (route keeps `qwen2.5:7b`, writer not in the small tier, writer in both backend tiers, frontend writer not in the small tier, frontend writer in the large tier).
- First runner test failed at the frontend `vitest` check (exit 1), and the runner restored every file. Cause: `apps/frontend-ts/node_modules/.vite/vitest/` and its `results.json` belong to `root` (written 2026-10-18 and 2026-10-21), so `vitest run` as the WSL user cannot write its results cache and exits with 1 after the tests pass. Claude's own check had missed this, because it read the test summary lines, not the exit codes; so its frontend red step and the frontend mutants P4 and P5 counted that exit, not a test result. Fix: the vitest commands use `--no-cache`. Re-check with exit codes: frontend red exit 1 (the new test fails), green exit 0 (5 passed); mutants 5 of 5 caught again, P4 and P5 now on real test failures. The root-owned cache folder is in the backlog (a `chown` is the user's call).
- Runner test on a fresh clone (with `--no-cache`): both red steps failed, the 8 checks passed (4 backend, 4 frontend), commit `fa09db2` on the clone, and the five files are the same bytes as the checked copies.

## Blockers / Questions
- None.
