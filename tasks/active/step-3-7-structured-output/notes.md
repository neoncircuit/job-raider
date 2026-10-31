# Scratchpad & Notes

## Plan (2026-10-31, Claude)

### What exists today

- 9 call sites parse LLM JSON with `re.search(r"\{.*\}", ..., re.DOTALL)` and `json.loads`, each on its own task type:

  | File | Line | Task type | temperature, max_tokens | On failure |
  |------|------|-----------|-------------------------|------------|
  | `src/generation/selector.py` | 190 | `SELECTION` | 0.5, 1000 | rule-based selection |
  | `src/generation/resume_writer.py` | 268 | `RESUME_WRITING` | 0.7, 2500 | template resume |
  | `src/generation/validator.py` | 255 | `VALIDATION` | 0.3, 500 | rule checks only |
  | `src/generation/resume_analyzer.py` | 357 | `RESUME_ANALYSIS` (2 calls) | 0.3, 2500 | rule-based assessment |
  | `src/generation/cover_letter_reviewer.py` | 141 | `COVER_LETTER_REVIEW` | 0.3, 400 | no review |
  | `src/generation/cover_letter_validator.py` | 918 | `VALIDATION` | 0.0, 400 | rule checks only |
  | `src/extractors/resume_parser.py` | 479 | `RESUME_PARSING` | 0.3 | rule-based parser |
  | `src/extractors/jd_extractor.py` | 277 | `JD_EXTRACTION` | 0.3 | rule-based extractor |
  | `src/classifiers/job_classifier.py` | 349 | `CLASSIFICATION` | 0.2 | rule-based classifier |

- `OllamaClient.generate` sends `temperature`, `num_predict`, and `top_p`, but no `format` and no `num_ctx`. Ollama 0.33.1 is installed; it accepts a JSON schema in `format`.
- `jd_extractor.py:232` cuts the input at 50,000 characters (about 12,000 tokens), far above the context that Ollama uses by default, so Ollama cuts the prompt without a message.
- The response cache key holds `temperature`, `max_tokens`, and `think` (`router.py` `_cache_extra`), so a schema or a `num_ctx` change must also go into the key.
- Cloud fallback (Claude, Gemini) runs only when the Ollama call raises; a parse failure does not trigger it.

### The measure

A new local suite, `python main.py eval structured`, with a fixed set in `tests/fixtures/eval/structured/`:

- About 5 cases for each of the 9 tasks (45 cases), built from committed synthetic data: the grounding profiles, jobs, and letters; the 4 pasted JDs in `tests/fixtures/jd_paste/`; and a few synthetic resume texts made from the grounding profiles. Each case is sampled 3 times at the task's own temperature.
- The suite runs each component's real method with a recording router around the real router, so the baseline measures the current prompts and code, and the after run measures the new ones, with the same instrument.
- For each recorded answer: `strict` (the whole answer is JSON and validates against the task's output model), `rescued` (only the old regex finds a valid object), or `failed`; also the prompt tokens against the task's context size (a prompt at the limit was cut), the latency, and the model.
- Metrics per task: strict rate, rescued rate, failure rate. The headline is the failure rate per task (`failed` plus `rescued` after the change, because the new code has no regex rescue).
- One model at a time: the suite groups the cases by model and unloads each model after its group. It records the peak VRAM (`nvidia-smi`) in the report.

### Micro-handoffs

1. **MH-1, output models and strict parser** (`src/llm/structured.py`, new). One Pydantic model for each of the 9 tasks, from the keys that each parser reads today; `parse_structured(content, model)`: `json.loads` on the whole answer (after a code fence is removed), then `model_validate`; it raises `StructuredOutputError` with the reason. Tests. No call site changes.
2. **MH-2, the `structured` suite** and its fixed set, with a fake-router unit test (in CI) and the `main.py eval structured` choice.
3. **Baseline run** (Claude, local, with the user's approval for the GPU time: about 135 calls, about 30 to 60 minutes).
4. **MH-3, router and client.** A `response_schema` keyword: the Ollama client sends it as `format`; other clients ignore it. `num_ctx` for each route (default 4096; 8192 for JD extraction and resume parsing), sent as `options.num_ctx` to Ollama only. Both go into the cache key. Tests.
5. **MH-4 to MH-7, the call sites**, in 4 groups: resume pipeline (selector, resume writer, resume validator); cover letters (reviewer, validator LLM path); extraction (JD extractor with an input budget, job classifier); resume parsing and analysis (resume parser with an input budget, resume analyzer). Each site passes its model's schema, parses with `parse_structured`, logs a parse failure with the task and the reason, and keeps its fallback. The regex goes.
6. **After run** on the same set, then the record (`notes.md`, decision log), and the full gate.

### Choices for the check-in

- **Handoff style.** MH-1 to MH-3 set the shared code, so Claude writes them in full for the handoff runner. MH-4 to MH-7 repeat one pattern 9 times; they can be spec handoffs for whichever agent has quota, with the same mutant check after each run. Or Claude writes them in full too (exact, but more Claude time).
- **Context sizes.** 4096 for most tasks, 8192 for JD extraction and resume parsing. The after run records the peak VRAM; if it is too high, the 8192 tasks go back to 4096 with a smaller input budget.

## Decisions (user, 2026-10-31)

1. The plan is approved.
2. MH-1 to MH-3: Claude writes the full code; the handoff runner applies them.
3. MH-4 to MH-7: spec handoffs for whichever agent has quota (`docs/handoff-runner.md`, "Spec handoffs for an agent"). Claude checks each with a reference fix and mutants before and after the run, and records the agent and model of each handoff here.

## MH-1 written and checked (2026-10-31, Claude)

`mh-1-output-models.md`: `src/llm/structured.py` (9 output models, `OUTPUT_MODELS` by call site, `parse_structured`, `strip_code_fence`, `StructuredOutputError` with the reasons `not_json`, `not_object`, and `schema`, and `extract_braced_object` for the suite's "rescued" count without a regex) and `tests/unit/test_structured_output.py` (35 tests, one sample answer in each prompt's shape).

- Model choices: a field that the prompt allows to be empty is `Optional` without a default (required, `null` allowed), so Ollama's schema makes the model write every key. The analysis fields that only the job-specific prompt asks for have defaults. Recommendations are `approve`, `needs_revision`, or `reject`; scores are 0 to 100; confidences 0 to 1. The resume parser model has grouped skills (the prompt also allows a flat list; MH-7 removes that sentence).
- Scratch clone: the runner's red step fails (no module), then 35 tests pass, black makes no change, ruff passes, the mypy gate has 0 new errors, and the runner commits (`fd982b2` on the clone).
- Mutants (13 of 13 caught): no fence removal, closing fence kept, no object check, any recommendation text, no score range, first closing brace, no brace order check, alignment score required, a call site missing from `OUTPUT_MODELS`, the `schema` and `not_json` reasons swapped, a nullable field made required, an optional list made required.

## Blockers / Questions
- None.
