---
name: problem-analysis
description: Invoke IMMEDIATELY via python script when user requests problem analysis or root cause investigation. Do NOT explore first - the script orchestrates the investigation.
---

# Problem Analysis

Root cause identification skill. Identifies WHY a problem occurs, NOT how to fix
it.

## Invocation

<invoke working-dir="{{SKILLS_DIR}}" cmd="python3 -m skills.problem_analysis.analyze --step 1" />

Do NOT explore or analyze first. Run the script and follow its output.
