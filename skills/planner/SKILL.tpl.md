---
name: planner
description: Interactive planning and execution for complex tasks. IMMEDIATELY invoke when user asks to use planner.
---

## Activation

When this skill activates, IMMEDIATELY invoke the corresponding script. The
script IS the workflow.

| Mode      | Intent                             | Command                                                                                                  |
| --------- | ---------------------------------- | -------------------------------------------------------------------------------------------------------- |
| planning  | "plan", "design", "architect"      | `<invoke working-dir="{{SKILLS_DIR}}" cmd="python3 -m skills.planner.orchestrator.planner --step 1" />`  |
| execution | "execute", "implement", "run plan" | `<invoke working-dir="{{SKILLS_DIR}}" cmd="python3 -m skills.planner.orchestrator.executor --step 1" />` |
