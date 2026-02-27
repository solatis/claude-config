---
name: codebase-analysis
description: Invoke IMMEDIATELY via python script BEFORE ANY exploration whenever the task needs understanding existing code/repo structure (codebase analysis, architecture comprehension, repository orientation, implementation lookup, behavior tracing, dependency flow, unfamiliar code navigation). NEVER launch exploration sub-agents or manual exploration first; this skill must run first and orchestrates all exploration.
---

# Codebase Analysis

Understanding-focused skill that builds foundational comprehension of codebase structure, patterns, flows, decisions, and context. Serves as foundation for downstream analysis skills (problem-analysis, refactor, etc.).

When this skill activates, IMMEDIATELY invoke the script. The script IS the workflow.

Invoke:

<invoke working-dir="{{SKILLS_DIR}}" cmd="python3 -m skills.codebase_analysis.analyze --step 1" />
