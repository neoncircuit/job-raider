# Task: Laptop as the Workstation

## Goal
Continue the project on the laptop while the desktop waits for its SSD and RAM upgrades. Each new session on the laptop starts from this file.

## Context (2026-11-14)
- Laptop: RTX 2070 (expected 8 GB VRAM; to be confirmed), 16 GB RAM, WSL Ubuntu 22.04, system Python 3.10.
- `setup.sh` installed Python 3.11 into `.tools/python` (pinned uv, no sudo). `make dev` starts the backend and the frontend.
- Ollama runs on the laptop; the models must be `qwen2.5:7b` and `qwen2.5:3b`.
- No MLflow container: the eval suites log to `apps/backend-py/data/mlflow.db`.
- Private files (`apps/backend-py/.env`, `apps/frontend-ts/.env.local`, `apps/backend-py/data/`) are copied by the user only when needed. Agents never read them.
- The desktop is not used for the project until its upgrades. Its RAM figures in `tasks/active/lean-setup/notes.md` are for the desktop only; measure again on the laptop.

```mermaid
flowchart TD
    S[New session on the laptop] --> R[Read CLAUDE.md, AGENTS.md, tasks/todo.md, docs/lessons.md, this file]
    R --> C[Check the laptop: GPU, RAM, Ollama service, models]
    C --> T1[ollama-load-timeout: build on a scratch clone]
    T1 --> T2[lean-setup: after run on the laptop]
    T2 --> T3[Lighter writer: qwen2.5:3b and llama3.2:3b]
```

## Work order
1. `tasks/active/ollama-load-timeout/` (plan complete, ready to build).
2. `tasks/active/lean-setup/`: apply `make-app.patch` on a scratch clone, then measure before and after on the laptop (the desktop before run is a reference only).
3. Lighter writer (`tasks/todo.md`, Next Up): `qwen2.5:3b` and `llama3.2:3b` with the writer and resume suites.

## Acceptance Criteria
- [x] `setup.sh` runs to the end on the laptop; `make dev` starts both services (2026-11-14).
- [ ] Laptop hardware recorded in `notes.md`: GPU name and VRAM, RAM, idle GPU and RAM use with `make dev` running.
- [ ] Ollama checked: WSL systemd service (one instance only), `qwen2.5:7b` and `qwen2.5:3b` present.
- [ ] The three tasks in the work order are done or moved on with the user.
- [ ] When the desktop is upgraded and back in use: this task closed and archived.

## Status
`in-progress`
