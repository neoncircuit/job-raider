# Notes: cv-stock-phrase-rewrite

Planned 2026-11-13. Review section to be added when the task is done.

## Build and checks (2026-11-14, scratch clone)

- `stock_phrase_polish.py`: the core (`_polish_texts`) works on a list of texts; targets carry their text index; the prompt words are parameters (letter values give the old prompt). `polish_stock_phrases` (letters) calls it with one text. Proof that letters are unchanged: the old module (from git) and the new one, given the same letter and the same model answer, sent the same messages and call settings and returned the same text and counts; the 36 letter tests pass unchanged.
- `polish_resume_stock_phrases(router, resume)`: prose fields as `(container, key)` slots (summary, experience highlights, project descriptions and highlights) on deep copies; one call on `resume_writing`; accepted sentences written back into their own field; returns a copy of the CV (`dataclasses.replace`; no import of `resume_writer` or `validator`, which would be an import cycle).
- `ResumeWriter.write(..., polish=True)`: polishes after writing; `GeneratedResume.stock_phrase_edits`; the template fallback is not polished.
- Resume suite: `local_resume_writer` calls `write(polish=False)`; `local_polish` runs the step; each written CV is checked before and after (`before_issues`, `before_generic_phrases`, `stock_phrase_edits`, `polish_ms`). Metrics: `before_*` rates, `cvs_gaining_accuracy_flag` (hallucinated skill, unsupported numbers, missing keyword, missing project), `cvs_losing_stock_phrases`, `stock_phrase_edits`, `polish_ms_p50`.
- Tests: 4 CV polish (prose in place; title, company, skill, project name never sent; route; copy; project description; no call; rejection), 2 writer (`polish` on and off), 3 suite (paired counts, no polish, the suite's writer turns the writer's polish off). Mutants: titles sent, original CV changed, cover-letter route, write() not polishing, gained flags read backwards, suite writer leaving the polish on: 6 of 6 caught.
- Full checks: black and ruff clean, mypy gate 177 known and 0 new, pytest 2,333 passed.
- Clone commit `e765924` on top of `f8d40a4` (= `main`).

## Measurement (2026-11-13 16:17 to 16:25 UTC) - guard passes

Run from the clone at `e765924`: `main.py eval resume --model qwen2.5:7b --samples 1`, logged into the real store. MLflow run `1bc2886ecefa4592a42b8e1785d5a1c2` (artifact in the WSL `data/mlartifacts`, none on D:). Report: `data/eval/resume/20261113T162512459055Z.json`. 65 written by `qwen2.5:7b`, 0 fallback, 0 other model, 0 errors, 0 timeouts; peak VRAM 6,275 MiB; model unloaded after. Conditions: paging 0 to 81 pages/sec, RAM 1.9 GB free, GPU 2,860 MiB before; Brave still had 23 background processes (closed to the tray).

| Metric (same 65 CVs) | Before the step | After the step |
|----------------------|-----------------|----------------|
| `generic_phrasing_rate` | 0.400 (26) | 0.031 (2) |
| `hallucinated_skill_rate` | 0.000 | 0.000 |
| `unsupported_numbers_rate` | 0.015 (1) | 0.015 (1) |
| `missing_keyword_rate`, `missing_project_rate` | 0.000, 0.000 | 0.000, 0.000 |
| `date_inconsistency_rate` | 0.046 | 0.046 |

- `cvs_gaining_accuracy_flag`: 0. `cvs_losing_stock_phrases`: 24. Sentences replaced: 24.
- Phrases before the step: "proven track record" 25, "leverage my" 1. The 2 CVs that kept "proven track record" had their rewrite rejected by the checks (0 answers in an unusable format), so the old sentence stayed.
- Polish time on the 26 CVs with a stock phrase: median 1.0 s, max 10.2 s. (`polish_ms_p50` in the report, 0.3 ms, is the median over all 65 CVs, most of which make no call; read the time from the rows with `before_generic_phrases`.)
- Writer latency p50 3.8 s (baseline 3.7 s).

Guard: fewer CVs with stock phrases (26 to 2), and no CV gained an accuracy flag. The guard passes.

## Metric fix before the apply (2026-11-14, user chose option 1)

- `polish_ms_p50` was the median over all written CVs; CVs without a stock phrase make no call and pulled it to 0.3 ms. It is now the median over CVs with a stock phrase before the step. Test with a fake clock (2 s for the CV with a phrase, 1 ms for the others): the old code gave 1 ms (red), the fix gives 2,000 ms. On the measured run the fixed metric is 1.0 s (median of the 26 CVs that called the model).
- Full checks: black and ruff clean, mypy gate 177 known and 0 new, pytest 2,334 passed.
- The clone commit was replaced: `d4dc63a`. Against the measured commit `e765924` it changes only `src/evaluation/suites/resume.py` (the summary) and `tests/unit/test_resume_suite.py`; the CV writer and the polish code are the code that was measured.

- Applied (user approved, 2026-11-14): `main` fast-forwarded to `d4dc63a`; `git diff` against it is empty. Not pushed yet.
