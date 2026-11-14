# Notes: letter-rewrite-polish

Planned 2026-11-14 after the cover letter test. Review section to be added when the task is done.

## Build and checks (2026-11-14, scratch clone)

- `CoverLetterWriter.rewrite` runs `polish_stock_phrases` on its output (same style and model) and records `stock_phrase_edits`; option `polish=True` (a measurement can turn it off), as in `ResumeWriter.write`. Both service rewrite paths (after the reviewer, and the grounding rewrite) call it.
- Tests: 3 new in `tests/test_cover_letter_writer.py` (`TestRewritePolish`: a stock phrase is replaced and counted, the polish call uses the letter route at temperature 0.2; no stock phrase means one call; `polish=False` returns the raw rewrite). 2 older tests read the rewrite's prompt from the most recent call; they now read the rewrite's own call. Red step: the polish test fails without the change (the no-stock-phrase guard passes both ways). Mutant (edit count not recorded): caught.
- Full checks: black and ruff clean, mypy gate 177 known and 0 new, pytest 2,349 passed.
- Clone commit `301ded7` on top of `9ca6ddb` (= `main`).

## Real-letter check (2026-11-14 03:45 to 03:57 UTC, clone `301ded7`, user approved)

Script `rewrite_polish_check.py` (scratchpad, not committed): for the first 3 grounding pairs, `write`, the reviewer's critique, `rewrite(polish=False)`, then `polish_stock_phrases` on the same rewrite; the deterministic validator and the detector on both texts. The 3B reviewer was unloaded after each review, so only one model was in GPU memory at a time.

| Pair | Stock phrases, raw rewrite | After polish | Ungrounded sentences | Time |
|------|---------------------------|--------------|----------------------|------|
| analogical_claim__classifier_robotics | "i am confident that", "invaluable", "proven track record" | the same 3 | 6 to 6 | 567 s |
| analogical_claim__fastapi_kubernetes | none | none | 2 to 2 | 57 s |
| analogical_claim__forms_security | "i am excited to apply" | none | 4 to 4 | 21 s |

- Letters with stock phrases: 2 before, 1 after. No letter gained a grounding flag. The guard passes on this small sample.
- In pair 1 the step changed nothing (3 target sentences): the answer was not in the numbered format, or each new sentence failed a check. The step's own log lines say which, but the script's output filter dropped INFO lines, so the reason is not known. Limit.
- Pair 1 took 567 s (first model loads under memory pressure); pairs 2 and 3 took 57 s and 21 s.
- The no-op VRAM guard printed "VRAM usage at 95.5%, falling back to CPU" and "93.9%" and did nothing (to be removed in `one-model-at-a-time`).

- Applied (user approved, 2026-11-14): `main` fast-forwarded to `301ded7`; `git diff` against it is empty. Not pushed yet.
