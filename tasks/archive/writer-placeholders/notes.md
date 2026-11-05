# Scratchpad & Notes

## Plan and decision rule (2026-11-05, Claude, before any run of this task)

### Fix

1. **Check.** `flag_unfilled_placeholders` finds `[...]` tokens of 2 to 80 characters on one line. A new hard issue, `unfilled_placeholder`, sets `is_valid` to false and triggers the existing one rewrite. The rewrite critique names the tokens. The writer suite counts the issue, so the count reaches the report and MLflow.
2. **Prompt rule.** A new rule in the modern and classic rules: write real names as plain text, with no square brackets and no placeholders. It comes after the first counts, so the counts show its effect.

The check comes first, because the reports hold no letter text, so nothing can count the defect until the check exists.

### Measure

Metric: the share of first-draft letters with `unfilled_placeholder`, on the grounding pairs (65 pairs, 3 letters each, 195 letters), with the production writer. The same bootstrap as Step 3.8: pair by pair, 95% interval, 2,000 resamples, seed 0.

| Run | Model | Prompt rule |
|-----|-------|-------------|
| R1 | `qwen2.5:3b` | No |
| R2 | `qwen2.5:7b` | No |
| R3 | `qwen2.5:3b` | Yes |
| R4 | `qwen2.5:7b` | Yes |
| R5 | `qwen2.5:3b` | Yes; final letters through the real service, with the rewrite: 3 jobs of the ranking set, 8 letters each |

### Rule (fixed before any result)

- The prompt rule stays when the interval of R3 minus R1 is below 0.
- `qwen2.5:3b` stays the default unless the interval of R3 minus R4 is above 0, which means that it is worse than `qwen2.5:7b` after the rule. In that case Claude does not change the default, and it asks the user, because this reverses the decision of 2026-11-02.
- R5 is reported as it is. It has no pass mark: it shows what a user gets, and how many letters are held for review.

### Limits

- The check is a text pattern. It finds square brackets only, so it misses `<Company>` and `XYZ Corp`.
- The grounding pairs use 3 synthetic profiles, and the first-draft metric does not count the rewrite. R5 covers the rewrite on a small sample.

## Check applied (2026-11-05, Claude)

`mh-1-placeholder-check.md` (runner), on the user's word "Yes, apply it": commit `c107816`. The red step failed (exit 2), the 5 checks passed, and the files are the same bytes as the checked copies. Before that, on a scratch clone: all 2,124 backend tests passed, and 14 of 14 mutants were caught, with a passing run and a control first. The first mutant run left P6 alive, because the test tokens were in alphabetical order as well as first-use order; a new case covers this.

## R1 and R2, before the prompt rule (2026-11-05, Claude)

Command: `python main.py eval writer --model <model>`. Git SHA `c10781638b65` (`git_dirty`: true; the CRLF-only files). Dataset SHA-256 `92cb028b...`. 195 letters for each model; 0 fallback, 0 other model, 0 errors.

| Run | Model | Letters with placeholders | Share | Valid share | Mean score | Time | Peak VRAM | MLflow run |
|-----|-------|------|------|------|------|------|------|------|
| R1 | `qwen2.5:3b` | 81 of 195 | 0.415 | 0.508 | 91.87 | 13 min | 5,674 MiB | `3811465f2e4a43a38093e41449fe0578` |
| R2 | `qwen2.5:7b` | 1 of 195 | 0.005 | 0.815 | 90.56 | 21 min | 7,733 MiB | `d8a9652fd8b24bfdbde40cd8e514a7ed` |

`qwen2.5:3b` minus `qwen2.5:7b`, pair by pair: 0.410 (95% interval 0.333 to 0.487).

- This is the defect that Step 3.8 could not see. The recommendation of `qwen2.5:3b` on 2026-11-02 did not weigh it. The rate is higher than the trial suggested (7 of 24).
- The valid share falls from 0.892 to 0.508 for `qwen2.5:3b`, because the new check is a hard failure. These are first drafts: the suite has no rewrite.
- VRAM: the GPU holds about 2.7 GB with no model loaded (Windows and desktop apps). So peak VRAM here is higher than in Step 3.8 (6,656 MiB for `qwen2.5:7b`). The R2 peak of 7,733 MiB is above the watchdog limit of 7,700, but not for 3 samples in a row.
- In R2, 194 of 195 letters logged the app's guard, "VRAM usage at 9x%, falling back to CPU" (`ollama_client.py`, limit 90%). So R2 took 21 min, not 13, and its latency is not comparable. The model is the same, so the letter counts stand. On this host today, `qwen2.5:7b` does not fit well.

## Change to the plan: R4 skipped (2026-11-05, user's decision, "Yes, skip R4")

R4 would run `qwen2.5:7b` with the rule. It is skipped, and R2 stands in for it in the rule. Reasons: R2 is 1 of 195, so R4 can only move the comparison by about 0.005; and R4 repeats a load of about 7.7 GB on a host where heavy GPU load has caused blue screens. Limit: nothing measures the rule on `qwen2.5:7b`. If the default ever goes back to `qwen2.5:7b`, run R4 first, with GPU-heavy apps closed.

## R3 and R5, with the prompt rule (2026-11-05, Claude)

The prompt rule is applied: `mh-2-prompt-rule.md`, commit `55d5d53`, on the user's word "Yes, skip R4". The red step failed (exit 1), and the 3 checks passed. On a fresh clone before that: both mutants caught, with a passing control.

R3: `python main.py eval writer --model qwen2.5:3b`, 13:52 to 14:01. Git SHA `55d5d53fbe7d` (`git_dirty`: true; the CRLF-only files). Dataset SHA-256 `92cb028b...`. MLflow run `a77fe8b778724e7f82bcbb1b62e97588`. Peak VRAM 5,299 MiB, 0 CPU fallback lines in the app log of R5, no model loaded after.

| Run | Model | Prompt rule | Letters with placeholders | Share | Valid share | Mean score | Words (median) | Time |
|-----|-------|------|------|------|------|------|------|------|
| R1 | `qwen2.5:3b` | No | 81 of 195 | 0.415 | 0.508 | 91.87 | 230 | 13 min |
| R3 | `qwen2.5:3b` | Yes | 18 of 195 | 0.092 | 0.779 | 92.7 | 217 | 9 min |
| R2 | `qwen2.5:7b` | No | 1 of 195 | 0.005 | 0.815 | 90.56 | 242 | 21 min, on the CPU guard |

R5, the real service with the rewrite, `qwen2.5:3b`, a clean clone at `55d5d53`, 3 jobs of the ranking set, 8 letters each, counts only: 0 of 24 final letters have a token (Wilson upper limit 0.138). The rewrite ran on 5 of 24. 20 of 24 final letters are valid. No other model wrote a letter. Peak VRAM 5,421 MiB.

The rule, as fixed before any run:

- **The prompt rule stays.** R3 minus R1: -0.323 (95% interval -0.400 to -0.251), below 0.
- **The default goes to the user.** R3 minus R2, with R2 in place of R4: 0.087 (95% interval 0.041 to 0.138), above 0. `qwen2.5:3b` is still worse on first drafts, so Claude does not change the default.

Claude's recommendation: keep `qwen2.5:3b`. A user gets the final letter, not the first draft. In R5 no final letter has a token, and a letter that keeps one fails validation and is held. `qwen2.5:7b` no longer fits this host: it peaks at 7,733 MiB and runs under the CPU guard. Limits: 24 letters is a small sample, so the rate of final letters with a token can be up to 0.138. About 1 in 5 letters needs one more model call. The other trade-offs of `qwen2.5:3b` from Step 3.8 remain.

## Decision (user, 2026-11-05)

The default writer goes back to `qwen2.5:7b` ("Switch back to 7b"). This is against Claude's recommendation to keep `qwen2.5:3b`, and it reverses the decision of 2026-11-02. Claude said that R4 runs first in this case, with GPU-heavy apps closed, because the rule has no measure on `qwen2.5:7b`.

## MH-3 written and checked (2026-11-05, Claude)

`mh-3-restore-7b.md` (runner) reverses the default of `fa8dcb0`: the route, both tier lists, and their tests. A saved Settings route still wins.

- The first scratch check is void for the frontend. `/tmp` was wiped between WSL sessions, so the copied `node_modules` was empty, and eslint, tsc, vitest, and mutant W4 did not really run. The check now uses `npm ci` and stops when that fails.
- Repeat, in one session: red fails on both sides (backend 5 tests, frontend 1 test); black and ruff pass; 2,124 backend tests and 263 frontend tests pass; prettier, eslint, and tsc pass; 4 of 4 mutants caught (route, large set, small set, frontend large list).
- Runner test on a fresh clone: both red steps failed, the 7 checks passed, commit `fc54daa` on the clone. Its file comparison is void, because the clone it compared with was gone. The apply compares the files with the edits, in one session.

The GPU at idle is 2,936 MiB: `dwm` 1,677 MiB, and `rs2client` (the RuneScape client) 1,006 MiB. R4 waits for the user to close it. With `rs2client` closed, R4 should peak near 6.9 GB.

## Paused (2026-11-05)

The user will go on later, from home. Nothing is running. When the user says that RuneScape is closed:

1. Apply `mh-3-restore-7b.md`, then compare each file with HEAD~1 plus the edits, in one WSL session.
2. Read the idle GPU memory. Stop if it is above about 2.3 GB.
3. Run R4: `qwen2.5:7b` with the rule. Compare it with R3 (`compare_runs`, the same bootstrap).
4. Write the decision-log entry of 2026-11-05, with a pointer in the entry of 2026-11-02. Update the README ("Measured Results", "Two-Model Approach", "Writer Model") and `docs/architecture.md` (the writing line and the model table).
5. Close this task, and close `tasks/active/writer-default-3b/` as replaced. Its open item, the saved Settings route, no longer applies.
6. Go back to Step 4, MH-2: set `WRITER_MODEL` to `qwen2.5:7b` in the seed script, write the tests, and run the seed once, on a clean clone, with RuneScape closed. Keep the letter as it comes.

The seed script and its first output are in the session scratchpad, not in the repository. If that is gone, write the script again from the design in `tasks/active/step-4-demo/notes.md`.

## Restore and R4 (2026-11-05, Claude, on the user's word "Alright I'm back. Lets continue")

RuneScape was closed; the GPU was at 1,445 MiB, then 1,605 MiB before R4. The restore is applied as `8679ac9`: both red steps failed, the 7 checks passed, and all 5 files are the same as HEAD~1 plus the edits. R4 ran after all, so R2 no longer stands in for it.

R4: `qwen2.5:7b` with the rule, 22:09 to 22:23. Git SHA `8679ac9583fe` (`git_dirty`: true; the CRLF-only files). MLflow run `ca8f6f433ef44a19b397054aa8a37b9a`. 0 of 195 letters with a placeholder, valid share 0.810, mean score 90.10, 250 words (median). Peak VRAM 6,722 MiB, 0 CPU fallback lines, no model loaded after.

- R3 minus R4: 0.092 (95% interval 0.046 to 0.138). The result of the rule does not change.
- R4 minus R2: -0.005 (95% interval -0.015 to 0.000). The rule has no measurable effect on `qwen2.5:7b`, which was at 1 of 195.
- With RuneScape closed, the run took 14.5 min and had no CPU fallback. With it open (R2), 21 min and 194 fallback lines. So the rule for running `qwen2.5:7b` is to close GPU-heavy apps first.

## Review (2026-11-05, Claude)

- Delivered: the check, the prompt rule, the counts on both models, the default back on `qwen2.5:7b`, and the corrected decision log, README, architecture, and usage docs.
- The defect came to light only because the demo showed a real letter. The recommendation of 2026-11-02 rested on checks that could not see it. `docs/lessons.md` has the lesson.
- Claude recommended keeping `qwen2.5:3b` after the fix, and the user chose `qwen2.5:7b`. R4 supports that choice on first drafts: 0 of 195 against 18 of 195.
- Claude's errors in this task: two runs of a check before it was valid (a heredoc that broke `\n`, and a `/tmp` clone with no dependencies), and a guess at the cause (the `Example` names) that the trial did not support. None reached the repository.
- Limit: no run measures final letters on `qwen2.5:7b`. The demo seed gives one.

## Blockers / Questions

- None.

## Review
