# Notes: cv-eval-suite

Planned 2026-11-13. Review section to be added when the task is done.

## Build and checks (2026-11-13, scratch clone)

- `src/evaluation/suites/resume.py` (`SUITE = "resume"`): reuses the writer suite's `load_pairs`, `percentile`, model allow-list, and the structured suite's router, VRAM probe, and unload. `local_resume_writer` stops before any call unless the `resume_writing` route resolves to `ollama/<model>`, and sets its fallback to none (`ResumeWriter.write` has no model override). Each written CV: `ResumeValidator().validate` (as in Generate Resumes), `flag_unsupported_number_sentences` on the CV prose (`unsupported_numbers`), and the stock-phrase detector on the prose. Fallback and other-model CVs are counted, not scored. Metrics: the check rates (`hallucinated_skill`, `unsupported_numbers`, `missing_project`, `missing_keyword`, `date_inconsistency`), `valid_rate`, `mean_score`, `generic_phrasing_rate`, `generic_per_100w_p50`, `prose_words_p50`, latency p50 and p95, `peak_vram_mib`.
- `validator.py`: `resume_prose_text(resume)` (summary, experience highlights, project descriptions and highlights) is now one public function, used by the validator's stock-phrase list and by the suite.
- `resume_writer.py`: the system prompt moved to `RESUME_SYSTEM_PROMPT` (text checked identical to `main`); the suite records its SHA-256 as `prompt_sha256`, so a later prompt change shows in each run.
- `suites/__init__.py` and `main.py`: `eval resume --model <tag> --samples N` (both options shared with the writer suite; the run refuses to start without `--model`).
- Tests: 9 in `tests/unit/test_resume_suite.py` (fake writer and validator; the number check runs for real on the synthetic profiles with "987%"). `test_scam_suite.py` pins the suite list; `resume` added. Mutants: titles counted in the number check, fallback CVs scored, no route check, rates over all rows, no prompt hash: 5 of 5 caught. CLI smoke: without `--model` it prints "The resume suite needs --model".
- Full checks: black and ruff clean, mypy gate 177 known and 0 new, pytest 2,324 passed. (One full run took 4 minutes and failed on the pinned suite list, before the fix.)
- Clone commit `0515d7b` on top of `3c4d2eb` (= `main`).

## Applied, and the baseline (2026-11-13)

- Applied (user approved): `main` fast-forwarded to `0515d7b`; `git diff` against it is empty.
- Baseline: `main.py eval resume --model qwen2.5:7b --samples 1` from `main`, 14:32 to 14:46 UTC. MLflow run `0b67332260044171b3aca2288eb2397a` (artifact in the WSL `data/mlartifacts`, none on D:). Report: `data/eval/resume/20261113T144620477287Z.json`. Prompt hash starts `c41e6d23ebc9`. The user's real settings route `resume_writing` to `ollama/qwen2.5:7b`. Conditions: `make dev` stopped, Brave quit from the tray (Windows still listed 18 Brave processes just before the run), paging near 0, RAM 2.6 GB free, GPU 2,298 MiB before the model loaded. Peak VRAM 6,206 MiB; model unloaded after.

| Metric | Baseline |
|--------|----------|
| CVs written / fallback / other model / errors | 64 / 1 / 0 / 0 |
| `hallucinated_skill_rate` | 0.000 |
| `unsupported_numbers_rate` | 0.016 (1 of 64) |
| `missing_project_rate`, `missing_keyword_rate` | 0.000, 0.000 |
| `date_inconsistency_rate` | 0.016 (1 of 64) |
| `valid_rate`, `mean_score` | 1.000, 100.0 |
| `generic_phrasing_rate` | 0.406 (26 of 64) |
| `generic_per_100w_p50` | 0.0 |
| prose words p50 (min, max) | 84 (48, 114) |
| latency p50 and p95 | 3.7 s and 5.4 s |

Findings:
- The only stock phrase is "proven track record", in 26 of 64 CVs. One phrase, not a spread, so a later fix can be narrow.
- The accuracy checks are almost clean on the grounding set: no skill off the profile, 1 CV with a number not in the profile.
- `valid_rate` 1.0 and `mean_score` 100: the validator's score counts only missing projects, missing keywords, and skills off the profile, and the fixed selection is built from each job, so these two metrics cannot separate CV writers. The accuracy rates and the stock-phrase rate are the useful metrics. The date mismatch does not change the score (by design of `ResumeValidator`).
- The 1 fallback was the CV writer's call timing out after 120 s (22:41 local time), mid-run, with low paging at the start.
