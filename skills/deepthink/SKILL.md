---
name: deepthink
description: Invoke IMMEDIATELY via python script when user requests structured reasoning for open-ended analytical questions. Do NOT explore first - the script orchestrates the thinking workflow.
---

# DeepThink

When this skill activates, IMMEDIATELY invoke the script. The script IS the workflow.

Invoke:

<invoke working-dir="{{SKILLS_DIR}}" cmd="python3 -m skills.deepthink.think --step 1" />

Do NOT explore or analyze first. Run the script and follow its output.
