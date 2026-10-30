# Scratchpad & Notes

## Observations

### Copilot billing and models (checked 2026-10-31)

- Since 2026-06-01, Copilot bills chat and agent use in AI Credits (USD 0.01 each) by input, cached input, and output tokens, at the API price of the model. No model is free in agent use any more. Code completions and Next Edit suggestions stay free on paid plans. When the credits are used, Copilot does not change to a cheaper model.
- Copilot Free and Student give Auto model selection only and no third-party agents. opencode needs Pro or higher.
- opencode v2.2.3 in WSL has a GitHub Copilot OAuth login and lists 14 Copilot models. The list has no Opus, Fable, or GPT-6 Sol/Astra models, which matches the Pro plan.
- Sources: GitHub blog "GitHub Copilot is moving to usage-based billing"; docs "Models and pricing for GitHub Copilot" and "GitHub Copilot plans".

### Cost estimate

The GLM and DeepSeek handoff runs of 2026-10-28 to 2026-10-30 (`opencode stats --days 10`) used 0.36M fresh input, 5.04M cached input, and 0.03M output tokens. The same tokens at Copilot prices:

| Model | USD |
|-------|-----|
| `claude-haiku-5.5` | 0.10 to 0.15 (with cache writes) |
| `gpt-6-luna` | 0.10 |
| `gpt-5.6-luna`, `mai-code-1.1-flash` | 0.21 |
| `gpt-6.1-terra` | 0.77 |
| `claude-sonnet-5.5` | 1.50 to 2.40 |

This assumes that Copilot caches the prompt as well as those providers did. Without the cache, the input cost is 10 to 20 times higher. Claude Haiku 5.5 costs 5 times more for a request above 100K input tokens.

## Attempted Approaches

### Spec check of MH-1 (Claude, 2026-10-31, scratch clone)

Claude wrote the MH-1 tests and a reference fix as the spec says (scratch files only, not given to the agent):

- Red: on the current code, the 3 new `TestTaskStore` tests fail (`FAILED`) and 11 tests pass. The first draft of the spec patched `src.agents.task_store.time`, which the current code does not import, so the tests stopped with `ERROR`. The spec now patches the `time` module.
- Green: 15 of 15 tests pass, and the agent tests (99) pass. Black, ruff, and the mypy gate pass (180 known, 0 new; the gate says that 2 baseline errors are fixed, and the spec tells the agent not to run `--update`).
- Mutants of the reference fix, all caught by the spec tests: M1 `>` to `>=` at the TTL edge; M2 `get` does not evict; M3 an update refreshes the TTL; M4 the 1-second TTL clamp removed; M5 `to_dict` returns the monotonic time; M6 the wall clock also expires records.

Claude runs the same mutants on the agent's code after the run.

### Trial run of MH-1 (2026-10-31)

The agent was `github-copilot/claude-haiku-5.5` in opencode v2.2.3. It finished MH-1 from one prompt, with no help and no stop, and committed `c1687ab`. It reported 3 failed and 12 passed before the code change, and 15 passed after.

Claude check:

- The diff obeys the required behavior. `TaskRecord` has a `created_monotonic` field (default `lambda: time.monotonic()`, so the fake clock also works for the default), and `to_dict()` does not return it. `save` and `get` use `time.monotonic()`. An update does not change `created_monotonic`. The tests are the ones that the spec names, with a `FakeClock` and a `fake_clock` fixture.
- The six mutants of the spec check, applied to the agent's code on a scratch clone: 6 of 6 caught.
- Full backend gate: black and ruff pass; mypy gate 180 known, 0 new (2 baseline errors fixed; `--update` not run); pytest 1764 passed (1761, minus the removed sleep test, plus 4 new tests).
- Staging: only the two files. The 14 other changed files in the working tree stayed unstaged.
- Small rule misses: `JumpedDatetime.now` has no type hints, and its docstring says that `tz` is ignored "as in `datetime.now`" (`datetime.now` does not ignore it). The new test methods have no `-> None`, the same as the existing tests in the file.

Tokens and cost:

- The user sent the prompt in the opencode session that held every handoff since 2026-10-28. Each step sent 152K to 169K tokens, so all steps were above the 100K tier of Claude Haiku 5.5 (5 times the price).
- Session export, the trial prompt only: 12 steps, 1.80M cached input, 0.16M cache writes, 7.7K output with reasoning. About USD 0.21.
- `opencode stats --days 0` (also has 3 prompts sent to this session for another project): 56 steps, 4.71M cached input, 0.39M cache writes, 33K output with reasoning. About USD 0.56. The two sources do not count steps the same way.
- Credits on the GitHub billing page: not yet recorded.
- Estimate for a new session (prompts of 20K to 40K tokens, low tier): about USD 0.05.

Lesson: start each handoff in a new opencode session (`/new`). An old session sends its full history with each step.

## Decision (user, 2026-10-31)

No agent is the default. The user changes between three agent sets as their quotas run out:

1. Cursor: the preferred agent when its monthly quota allows (it was near the limit 5 days after the last reset).
2. GitHub Copilot in opencode: Claude Haiku 5.5 did this trial. Start each handoff with `/new`.
3. Open-source models in opencode (the free hosted GLM and DeepSeek models finished earlier handoffs; local Ollama models did not).

So each spec handoff must work in any of the three: one `AGENT.md`, one handoff, exact commands, and the exact `git add`. Claude changes the tool or model advice only when the user says which agent is in use. `docs/handoff-runner.md` has the rules (section "Spec handoffs for an agent").

## Review (2026-10-31, Claude)

- Goal met: a low-cost Copilot model (Claude Haiku 5.5 in opencode) did a spec handoff from one prompt. The tests and the code obey the spec, 6 of 6 mutants are caught, and the full gate passes (1764 tests). The TaskStore TTL flake is fixed (`c1687ab`).
- Cost: about USD 0.21 from the token counts (up to USD 0.56 with all of the day's prompts). It was high because the run used an old opencode session. The GitHub billing figure is not recorded (user decision).
- Decision: no default agent. Spec handoffs must work in Cursor, Copilot in opencode, and open-source models in opencode (`docs/handoff-runner.md`). The user says when they swap the agent or model, and Claude records the agent and model of each handoff in the task notes.
- Lesson added to `docs/lessons.md`: do not make one agent or model the default for handoffs.

## Blockers / Questions
- None.
