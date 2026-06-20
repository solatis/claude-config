# Planner

Planning and execution workflows with QR (Quality Review) gates, TW (Technical Writer) passes, and Dev (Developer) execution phases.

This document is authoritative for the planner skill architecture.

## Architecture: Python Scripts vs LLM

Python scripts emit workflow prompts and routing. The LLM operates BETWEEN script invocations:

1. Script outputs prompt/guidance for current step
2. LLM reads prompt, performs reasoning/assessment
3. LLM decides outcome (e.g., QR PASS/FAIL)
4. LLM invokes next script based on outcome

QR PASS/FAIL is determined by LLM reading QR output, not Python. Gate routing is LLM's decision based on QR outcome. Python scripts provide structure; LLM provides intelligence.

## State Files

All state mutations (except initial context.json) happen via Python CLI commands. Step 1 honors an explicit `--state-dir` (resumable); otherwise it mints a fresh persistent directory under `<project>/.claude/planner-state/` (git-ignored) -- never `/tmp`, which a session-limit restart would wipe (F1).

| File              | Schema         | Created     | Mutated By     | Lifecycle              |
| ----------------- | -------------- | ----------- | -------------- | ---------------------- |
| `plan.json`       | Pydantic v2    | Step 1 init | CLI commands   | mutable -> frozen      |
| `context.json`    | Loose JSON     | Step 2      | LLM Write tool | frozen after step 2    |
| `qr-{phase}.json` | QA item schema | QR dispatch | LLM during QR  | ephemeral per QR cycle |

### plan.json Schema

```
Plan
  schema_version: 2
  plan_id: UUID
  created_at: timestamp
  frozen_at: Optional[timestamp]

  overview:
    title, problem, approach

  planning_context:
    decision_log[]: id (DL-XXX), decision, reasoning_chain, timestamp
    rejected_alternatives[]: id (RA-XXX), alternative, rejection_reason, decision_ref
    constraints[]: id (C-XXX), type, description, source
    known_risks[]: id (R-XXX), risk, mitigation, anchor?, decision_ref?

  invisible_knowledge:
    architecture: {diagram_ascii, description}
    data_flow: {diagram_ascii, description}
    structure_rationale, invariants[], tradeoffs[]

  milestones[]:
    id (M-XXX), number, name, files[], flags[], requirements[], acceptance_criteria[]
    tests: files[], type?, backing?, scenarios{normal[], edge[], error[]}, skip_reason?
    code_intents[]: id (CI-XXX), file, function?, behavior, decision_refs[], params{}
    code_changes[]: id (CC-XXX), intent_ref, file, diff, context_lines, why_comments[]
    documentation: module_comment?, docstrings[], algorithm_blocks[], inline_comments[]
    is_documentation_only, delegated_to?

  milestone_dependencies:
    diagram_ascii
    waves[]: wave number, milestones[]
```

Reference integrity: code_change.intent_ref -> code_intent.id, decision_refs -> decision_log.id

### context.json Schema

User-provided context captured during planning:

```json
{
  "task_spec": ["goal", "scope", "out-of-scope"],
  "constraints": ["MUST: X", "SHOULD: Y"],
  "entry_points": ["file:function - why"],
  "rejected_alternatives": ["alternative - why dismissed"],
  "current_understanding": ["how system works"],
  "assumptions": ["inference (confidence)"],
  "invisible_knowledge": ["design rationale", "invariants"],
  "user_quotes": ["verbatim quote"]
}
```

### qr-{phase}.json Schema

Phases: `qr-plan-design`, `qr-plan-code`, `qr-plan-docs`, `qr-impl-code`, `qr-impl-docs`

```json
{
  "schema_version": "1.0",
  "phase": "plan-design",
  "items": [
    {
      "id": "qa-001",
      "scope": "*",
      "check": "...",
      "status": "TODO|PASS|FAIL",
      "finding": null
    }
  ]
}
```

## Workflow Phases and Mutations

### Planner Workflow (11 steps)

| Step | Name                | Pattern Function          | Mutates              | Agent        |
| ---- | ------------------- | ------------------------- | -------------------- | ------------ |
| 1    | plan-init           | `init_step()`             | Creates plan.json    | Orchestrator |
| 2    | context-verify      | `verify_step()`           | Creates context.json | Orchestrator |
| 3    | plan-design-execute | `execute_dispatch_step()` | plan.json            | Architect    |
| 4    | plan-design-qr      | `qr_dispatch_step()`      | qr-plan-design.json  | QR           |
| 5    | plan-design-qr-gate | `qr_gate_step()`          | -                    | Orchestrator |
| 6    | plan-code-execute   | `execute_dispatch_step()` | plan.json            | Developer    |
| 7    | plan-code-qr        | `qr_dispatch_step()`      | qr-plan-code.json    | QR           |
| 8    | plan-code-qr-gate   | `qr_gate_step()`          | -                    | Orchestrator |
| 9    | plan-docs-execute   | `execute_dispatch_step()` | plan.json            | TW           |
| 10   | plan-docs-qr        | `qr_dispatch_step()`      | qr-plan-docs.json    | QR           |
| 11   | plan-docs-qr-gate   | `qr_gate_step()`          | Sets frozen_at       | Orchestrator |

**Mutation details**:

- Step 3 (Architect): Populates planning_context, milestones[], code_intents[], invisible_knowledge
- Step 6 (Developer): Populates code_changes[] per milestone
- Step 9 (TW): Populates documentation[] per milestone, creates plan.md

### Executor Workflow (9 steps)

| Step | Name              | Mutates           | Agent        |
| ---- | ----------------- | ----------------- | ------------ |
| 1    | init              | -                 | Orchestrator |
| 2    | load-verify       | -                 | Orchestrator |
| 3    | impl-execute      | Codebase files    | Developer    |
| 4    | impl-code-qr      | qr-impl-code.json | QR           |
| 5    | impl-code-qr-gate | -                 | Orchestrator |
| 6    | impl-docs-execute | Codebase docs     | TW           |
| 7    | impl-docs-qr      | qr-impl-docs.json | QR           |
| 8    | impl-docs-qr-gate | -                 | Orchestrator |
| 9    | reconcile         | -                 | QR           |

## Components

```
orchestrator/
  planner.py      11-step planning workflow
  executor.py     9-step execution workflow

architect/
  plan_design.py  Plan creation (exploration, milestones, code_intents)

developer/
  plan_code.py    Code Intent -> Code Changes (unified diffs)
  exec_implement.py  Wave-aware implementation

technical_writer/
  plan_docs.py    Documentation planning (WHY comments, temporal cleanup)
  exec_docs.py    Post-implementation docs (CLAUDE.md, README.md)

quality_reviewer/
  plan_design_qr.py   Plan completeness validation
  plan_code_qr.py     Code diff validation
  plan_docs_qr.py     Documentation quality
  impl_code_qr.py     Post-impl code review
  impl_docs_qr.py     Post-impl doc review
  exec_reconcile.py   Plan vs implementation reconciliation

shared/
  resources.py    Path derivation, context loading
  builders.py     XML output builders
  constraints.py  Orchestrator constraint AST builders
  qr/             QR utilities (types, constants, utils, schema)

state/
  models.py       Pydantic v2 schemas for plan.json
  validator.py    Validation functions
  decisions.py    Decision lifecycle enum (reserved for future use)

cli/
  plan.py         plan.json manipulation commands
```

## QR Gate Mechanics

QR gates use LoopState enum: INITIAL -> RETRY -> COMPLETE

```
INITIAL -> PASS -> COMPLETE (terminal)
INITIAL -> FAIL -> RETRY (iteration++)
RETRY   -> FAIL -> RETRY (iteration++)
RETRY   -> PASS -> COMPLETE (terminal)
```

Blocking severity by iteration:

| Iteration | Blocks              |
| --------- | ------------------- |
| 1-2       | MUST, SHOULD, COULD |
| 3-4       | MUST, SHOULD        |
| 5+        | MUST only           |

## Step Handler Architecture

Closures capture static config, handlers receive dynamic state:

```python
def execute_dispatch_step(title, agent, script, ...):
    def handler(ctx):  # Receives state_dir, qr, qr_fail
        return {"title": ..., "actions": ..., "next": ...}
    return handler

STEPS = {
    1: init_step("plan-init", ...),
    3: execute_dispatch_step("plan-design-execute", agent="architect", ...),
    4: qr_dispatch_step("plan-design-qr", ...),
    5: qr_gate_step("plan-design-qr-gate", ...),
}
```

## Design Decisions

**Closure-based step dispatch**: STEPS dict maps step numbers to handler closures. Pattern functions capture static config (title, agent, script), handlers receive dynamic state via ctx. Replaces magic keys with explicit patterns.

**Convention-based paths**: Sub-agents receive --state-dir, derive file paths via get_context_path(). Changing context.json location requires only updating resources.py.

**LLM-managed state**: State files written by LLM agents reading step guidance, not Python scripts. Leverages LLM capabilities for understanding context and following formats.

**JSON-IR-First**: plan.json is authoritative; plan.md derived from it.

**QR iteration blocking**: Severity thresholds vary by iteration. Early iterations block all severities. Later iterations block only MUST to prevent infinite loops.

**No temp directory cleanup**: OS handles /tmp cleanup on reboot.

## Invariants

1. Every skill entry point defines exactly ONE Workflow
2. discover_workflows() finds all Workflows without import errors
3. plan.json is self-contained for execution
4. Frozen plan.json is immutable (frozen_at timestamp means no writes)
5. qr-{phase}.json files are ephemeral (exist only during QR cycle)
6. QR iteration blocking: iter 1-2 all; iter 3-4 MUST/SHOULD; iter 5+ MUST only
