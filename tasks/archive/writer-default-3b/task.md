# Task: Make qwen2.5:3b the Default Cover-Letter Writer

## Goal
Make `qwen2.5:3b` the default local cover-letter writer, as `docs/decision-log.md` (2026-11-02, Step 3.8) recommends, so that a new install and the Settings tier presets use it. Backlog item "Writer model findings (2026-11-02)".

```mermaid
flowchart LR
    D[Decision log 2026-11-02:<br/>recommend qwen2.5:3b] --> R[DEFAULT_ROUTES:<br/>cover_letter_writing = qwen2.5:3b]
    D --> T[Tier lists: cover_letter_writing<br/>moves from large to small,<br/>backend and frontend]
    T --> S[Settings 'Use recommended (3b / 7b)'<br/>gives the writer qwen2.5:3b]
    R --> N[New installs]
    S --> U[User applies the tiers<br/>or sets the route once]
```

## Constraints & Context
- Two places decide the writer model: the built-in routes (`DEFAULT_ROUTES` in `src/llm/router.py`) and the Settings tier presets (`OLLAMA_SMALL_TASKS` and `OLLAMA_LARGE_TASKS` in `src/api/ollama_models.py` and `apps/frontend-ts/src/lib/ollama-tiers.ts`). Applying the tiers sets every large task to the large model, so the default route alone would be undone by the next tier apply.
- Side effect: the tier also picks the default cloud fallback model when a cloud fallback is set (small tier: `claude-haiku-4-5-20251001` or `gemini-2.5-flash`; large tier: `claude-sonnet-4-6` or `gemini-2.5-pro`). In the small tier, cover-letter writing gets the small cloud model.
- A saved user setting wins over the defaults. Claude does not open `data/settings/user_settings.json`, so the user changes their own saved route once (Settings, "Use recommended (3b / 7b)", or the cover-letter writing route).
- Other cover-letter tasks are already on `qwen2.5:3b` (review, validation). Resume writing stays on the large tier.
- The Settings compare card and `scripts/compare_cover_letter_models.py` keep their pair (`qwen2.5:7b` and `qwen3.5:4b`); they compare models, they do not set the default.

## Acceptance Criteria
- [x] Plan approved by the user (including the cloud fallback side effect). (2026-11-02: "Small tier for both")
- [x] MH-1 (runner): `DEFAULT_ROUTES` gives `cover_letter_writing` the model `qwen2.5:3b`; `cover_letter_writing` is in the small tier in the backend and the frontend; tests for the default route, both tier lists, the tier apply, and the cloud fallback model. (`fa8dcb0`, 6 tests, 5 of 5 mutants)
- [x] Docs: `docs/usage.md` (the Review & rewrite tip), `docs/architecture.md` (the model table), and the 2026-11-02 decision-log entry say that the default is applied; the backlog item is checked.
- [x] Done when: the backend and frontend gates pass, and the user has changed their saved route (or chooses to keep it). (Replaced 2026-11-05: the user chose `qwen2.5:7b`, so no saved route needs a change)

## Status
`replaced` (2026-11-05: the default went back to `qwen2.5:7b` as `8679ac9`; see `tasks/archive/writer-placeholders/` and the decision log of 2026-11-05; archived)
