# planner/

Planning and execution skill with quality review gates.

## Files

| File        | What                               | When to read                 |
| ----------- | ---------------------------------- | ---------------------------- |
| `SKILL.tpl.md`  | Skill activation and invocation    | Using the planner skill      |
| `INTENT.md` | Authoritative design specification | Understanding system design  |
| `README.md` | Architecture, workflows, rationale | Understanding planner design |

## Subdirectories

| Directory    | What                   | When to read                        |
| ------------ | ---------------------- | ----------------------------------- |
| `resources/` | Plan format, diff spec | Editing plan structure, diff format |
| `architect/` | Plan design sub-agent  | Understanding planning workflow     |

Python code: `scripts/skills/planner/` (planner.py, executor.py, explore.py, qr/, tw/, dev/)

## Universal Conventions

Scripts reference these conventions from `.claude/conventions/`:

| Convention          | When to read                                 |
| ------------------- | -------------------------------------------- |
| `documentation.tpl.md` | Understanding CLAUDE.md/README.md format   |
| `structural.md`     | Updating QR RULE 2 or planner decision audit |
| `temporal.md`       | Updating TW/QR temporal contamination logic  |
| `severity.md`       | Understanding QR severity levels             |
| `intent-markers.md` | Understanding :PERF:/:UNSAFE: markers        |
