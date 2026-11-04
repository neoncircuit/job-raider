# Task: Stop Unfilled Placeholders in Cover Letters

## Goal
A cover letter must not reach the user with text such as `[Company]`. The validator finds these tokens, the one rewrite gets a chance to fix them, and the first-draft rate is measured on `qwen2.5:3b` and `qwen2.5:7b`, so the default writer rests on evidence.

```mermaid
flowchart LR
    W[Writer draft] --> C{Unfilled placeholder?}
    C -->|No| K[Other checks]
    C -->|Yes| R[One rewrite, with the<br/>tokens named]
    R --> C2{Still there?}
    C2 -->|No| K
    C2 -->|Yes| H[Hold for review]
```

## Constraints & Context
- Found in Step 4, MH-2 (`tasks/active/step-4-demo/notes.md`): about 3 in 10 `qwen2.5:3b` letters have `[...]` tokens with ordinary company names. The prompt has no brackets. The validator has no check for them, so Step 3.8 could not weigh this.
- The decision rule is in `notes.md`, committed before any run of this task.
- GPU: one model at a time, and unload after use. The user approved the `qwen2.5:7b` count (about 6.7 GB of VRAM) on 2026-11-05.
- Do not run the seed again to pick a clean letter. The demo letter stays as the fixed code writes it.

## Acceptance Criteria
- [ ] Rule and plan committed before any run.
- [ ] Validator check `unfilled_placeholder`, as a hard failure, with its tokens in the rewrite critique, and the writer suite counts it.
- [ ] First-draft counts on `qwen2.5:3b` and `qwen2.5:7b` before the prompt rule, in MLflow.
- [ ] Prompt rule, then the same counts again, in MLflow.
- [ ] Final-letter count through the real service, with the rewrite, on `qwen2.5:3b`.
- [ ] The default writer decided by the rule; `docs/decision-log.md` and the README updated.
- [ ] Done when: the MH-2 seed can run on the fixed code, and the README states the placeholder rate and its limits.

## Status
`in-progress` (2026-11-05: plan and rule written)
