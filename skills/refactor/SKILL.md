---
name: refactor
description: Invoke IMMEDIATELY via python script when user requests refactoring analysis, technical debt review, or code quality improvement. Do NOT explore first - the script orchestrates exploration.
---

# Refactor

When this skill activates, IMMEDIATELY invoke the script. The script IS the workflow.

## Invocation

<invoke working-dir="{{SKILLS_DIR}}" cmd="python3 -m skills.refactor.refactor --step 1 --n 10" />

| Argument | Required | Description                                   |
| -------- | -------- | --------------------------------------------- |
| `--step` | Yes      | Current step (starts at 1)                    |
| `--n`    | No       | Number of categories to explore (default: 10) |

Do NOT explore or analyze first. Run the script and follow its output.

## Determining N (category count)

Default: N = 10

Adjust based on user request scope:

- SMALL (single file, specific concern, "quick look"): N = 5
- MEDIUM (directory, module, standard analysis): N = 10
- LARGE (entire codebase, "thorough", "comprehensive"): N = 25

The script randomly selects N categories from the 38 available code quality categories defined in conventions/code-quality/.
