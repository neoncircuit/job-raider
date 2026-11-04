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

## Blockers / Questions

- None.

## Review
