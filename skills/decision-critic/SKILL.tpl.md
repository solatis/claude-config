---
name: decision-critic
description: Invoke IMMEDIATELY via python script to stress-test decisions and reasoning. Do NOT analyze first - the script orchestrates the critique workflow.
---

# Decision Critic

When this skill activates, IMMEDIATELY invoke the script. The script IS the
workflow.

## Invocation

<invoke working-dir="{{SKILLS_DIR}}" cmd="python3 -m skills.decision_critic.decision_critic --step 1 --decision '<decision text>'" />

| Argument     | Required | Description                             |
| ------------ | -------- | --------------------------------------- |
| `--step`     | Yes      | Current step (1-7)                      |
| `--decision` | Step 1   | The decision statement being criticized |

Do NOT analyze or critique first. Run the script and follow its output.
