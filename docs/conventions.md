# Job Raider Documentation Conventions

## Language

Write plans and documentation in ASD-STE100 Simplified Technical English (STE) where practical:

- Use short sentences and approved common words when meaning stays clear.
- Prefer active voice and consistent terminology.
- Do not use emojis in documentation.

## Structure

- Put commands in their own labeled code snippets.
- Include a flow diagram (Mermaid preferred) for non-trivial workflows.
- Keep tone professional and easy to understand.

## Code Layout

- Backend Python code belongs under `apps/backend-py`.
- Frontend TypeScript code belongs under `apps/frontend-ts`.

## Local Quality Gate

Before push, run the same checks as CI where feasible:

```bash
# Backend (from apps/backend-py)
black --check src/ tests/
ruff check src/ tests/
pytest tests/ -q
```

```bash
# Frontend (from apps/frontend-ts)
npm ci
npm run lint
npm run type-check
npm run format:check
npm run test:coverage -- --run
```
