# skills/intake-bugs-analysis/

## Overview

Automated bug analysis for Intake team. Matches Notion exports to bug IDs, runs
AI analysis with Claude CLI, and discovers patterns bottom-up.

## Files

| File                        | What                       | When to read               |
| --------------------------- | -------------------------- | -------------------------- |
| `SKILL.md`                  | Workflow and invocation    | Using this skill           |
| `NOTION_OUTPUT_TEMPLATE.md` | Output format template     | Generating final report    |
| `README.md`                 | User-facing documentation  | Explaining skill to users  |

## Subdirectories

| Directory    | What                              | When to read                    |
| ------------ | --------------------------------- | ------------------------------- |
| `scripts/`   | Python pipeline scripts           | Debugging or modifying pipeline |
| `resources/` | Troubleshooting and monitoring    | Errors or tracking progress     |

## Key Point

SKILL.md is the single source of truth for the workflow. Read resources only
when the specific situation arises (errors, monitoring, advanced options).
