# Old todo.md Conventions

The first lines of `tasks/todo.md` before the restructure (2026-10-24), without changes. They are replaced by `tasks/index.md`. The archive they name is now `tasks/archive/legacy/todo-done.md`.

# Job Raider Tasks

This file lists active work only. Completed work is in [archive/todo-done.md](archive/todo-done.md).

## How to use this file

```mermaid
flowchart LR
    B[Backlog] -->|Planned| N[Next]
    N -->|Started| W[Now]
    W -->|All steps done| A[archive/todo-done.md]
    B -->|Dropped| A
```

1. Put each work item under one of three sections: **Now**, **Next**, or **Backlog**.
2. Give each work item a level-3 heading with a name and a date. Example: `### Pipeline elapsed timer (2026-10-18)`.
3. Do not give work items numbers. Do not use the word "Phase" for new work.
4. Number the steps inside a work item: "Step 1", "Step 2", and so on. If a step needs its own sub-steps, number them "Step 1.1", "Step 1.2", and so on.
5. When all steps are done, add a "Review" subsection. Then move the work item to the end of [archive/todo-done.md](archive/todo-done.md).
6. "Phase 1" to "Phase 54" are old labels. They are in the archive only. Do not reuse them.
