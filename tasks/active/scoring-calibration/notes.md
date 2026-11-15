# Notes: scoring-calibration

Planned 2026-11-15 on the laptop, from the Next Up item in `tasks/todo.md` (pipeline test of 2026-11-14).

## Fixture measurement (2026-11-15)

The 70 ranking jobs (`tests/fixtures/eval/ranking/`), scored with `JobMatcher` for each profile in both modes. Labels: 2 apply, 1 maybe, 0 not relevant. Component means are points (weights in brackets).

```mermaid
flowchart LR
    J[70 fixture jobs] --> F[Fresh graduate mode]
    J --> S[Standard mode]
    F --> T[Totals and components per label]
    S --> T
```

`fresh_ml` (a fresh graduate profile), fresh graduate mode (projects 35, skills 30, education 20, experience 10, location 5; matcher threshold 50):

| Label | Jobs | Min / median / max | At 50 or more | At 60 or more | Projects | Skills | Education | Experience | Location | Jobs without a skill list |
|---|---|---|---|---|---|---|---|---|---|---|
| 2 | 8 | 35 / 59 / 78 | 6 | 4 | 12.5 | 25.1 | 15 | 10.0 | 5 | 3 (median 58) |
| 1 | 19 | 32 / 53 / 76 | 12 | 3 | 12.4 | 13.1 | 15 | 6.9 | 5 | 0 |
| 0 | 43 | 29 / 32 / 59 | 8 | 0 | 8.3 | 4.1 | 15 | 4.7 | 5 | 8 (median 53) |

`fresh_ml`, standard mode (keyword 30, skills 40, experience 20, location 10; threshold 60): label 2 median 68.5, 6 of 8 at 60 or more; label 1: 1 of 19; label 0: 1 of 43.

`mid_backend` (standard profile), standard mode: label 2 median 80, 10 of 11 at 60 or more; label 1: 6 of 18; label 0: 1 of 41. In fresh graduate mode: label 2 median 58, 5 of 11 at 60 or more.

Findings:
- At the pipeline cut-off 60, fresh graduate mode passes only 4 of 8 apply jobs (standard mode: 6 of 8). This matches the live run (1 of 59 passed).
- A cut-off of 50 alone is not safe: it passes 8 of 43 not-relevant jobs. The 8 not-relevant jobs without a skill list have a median of 53: the fallback credit for jobs without a skill list lifts them.
- Projects do not separate the labels: mean 12.5 (apply) against 12.4 (maybe) of 35.
- Education (15 of 20) and location (5 of 5) are the same for every job: 20 fixed points that lift every total and do not help the order.
- The live run must show how many real postings have no skill list; that decides how much the fallback matters.

## Code change A on a scratch clone (2026-11-15)

```mermaid
flowchart LR
    S[score_and_rank scores every job] --> K[Keep jobs at min_score or more: unchanged]
    S --> D[score_distribution over all jobs]
    D --> M[metadata.distribution: numbers only]
```

- New `src/scoring/distribution.py`, `score_distribution(pairs)`: `count`, `bands` (10-point bands, 100 in "90-100"), `at_or_above_50`, `at_or_above_60`, `component_means` (over all scored jobs), `without_skill_list` (`count`, `median`, the two cut counts). Numbers only; no job text, no profile data. A score without a breakdown dict still counts in the bands.
- `stages_rank.py`, `stage_score_and_rank`: keeps every `(job, score)` pair in `all_scored` and adds `metadata["distribution"] = score_distribution(all_scored)`. The kept jobs, their order, and the other metadata keys do not change.
- Tests: `test_score_distribution.py` (6): bands and cut counts; component means over all jobs; jobs without a skill list apart; no jobs; a score without a breakdown; the stage metadata covers a job below the cut-off while the stage result keeps only the job above it. Red: collection error (no module). Green: 6 passed.
- Checks on the clone: stage and orchestrator tests (39), ranking pins (10), black (after formatting `distribution.py`), ruff, mypy gate (0 new), full backend pytest (2419 passed).
- Reading the live run: `GET /api/pipeline/results/{run_id}` returns each stage's `metadata`; agents print only `score_and_rank.metadata.distribution`.
