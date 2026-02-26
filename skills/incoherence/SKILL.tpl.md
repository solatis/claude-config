---
name: incoherence
description: Detect and resolve incoherence in documentation, code, specs vs implementation.
---

# Incoherence Detector

When this skill activates, IMMEDIATELY invoke the script. The script IS the
workflow.

## Invocation

<invoke working-dir="{{SKILLS_DIR}}" cmd="python3 -m skills.incoherence.incoherence --step-number 1 --thoughts '<context>'" />

| Argument        | Required | Description                               |
| --------------- | -------- | ----------------------------------------- |
| `--step-number` | Yes      | Current step (starts at 1)                |
| `--thoughts`    | Yes      | Accumulated state from all previous steps |

Do NOT explore or detect first. Run the script and follow its output.

## Workflow Phases

1. **Detection (steps 1-12)**: Survey codebase, explore dimensions, verify
   candidates
2. **Resolution (steps 13-15)**: Present issues via AskUserQuestion, collect
   user decisions
3. **Application (steps 16-21)**: Apply resolutions, present final report

Resolution is interactive - user answers structured questions inline. No manual
file editing required.
