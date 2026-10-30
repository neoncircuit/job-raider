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

## Blockers / Questions
-
