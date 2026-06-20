#!/usr/bin/env python3
"""Plan design execution - first-time creation workflow.

6-step workflow for architect sub-agent:
  1. Task Analysis & Exploration Planning
  2. Codebase Exploration (inline: Glob, Grep, Read)
  3. Testing Strategy Discovery (may use question relay)
  4. Approach Generation
  5. Assumption Surfacing (may use question relay)
  6. Milestone Definition & Plan Writing

This is the EXECUTE script for first-time plan creation.
For QR fix mode, see plan_design_qr_fix.py.
Router (plan_design.py) dispatches to appropriate script.
"""

from skills.lib.workflow.constants import SUB_AGENT_QUESTION_FORMAT
from skills.planner.shared.resources import (
    STATE_DIR_ARG_REQUIRED,
    get_context_path,
    render_context_file,
    validate_state_dir_requirement,
    PlannerResourceProvider,
)


STEPS = {
    1: "Task Analysis & Exploration Planning",
    2: "Codebase Exploration",
    3: "Testing Strategy Discovery",
    4: "Approach Generation",
    5: "Assumption Surfacing",
    6: "Milestone Definition & Plan Writing",
}


def get_step_guidance(
    step: int, module_path: str = None, **kwargs) -> dict:
    """Return guidance for the given step."""
    _provider = PlannerResourceProvider()
    MODULE_PATH = module_path or "skills.planner.architect.plan_design_execute"

    if step == 1:
        state_dir = kwargs.get("state_dir")
        validate_state_dir_requirement(step, state_dir)
        context_file = get_context_path(state_dir)
        context_display = render_context_file(context_file)

        return {
            "title": STEPS[1],
            "actions": [
                "PLANNING CONTEXT (from orchestrator):",
                "",
                context_display,
                "",
                SUB_AGENT_QUESTION_FORMAT,
                "",
                "TASK: Create implementation plan from user request.",
                "",
                "You will follow a 6-step workflow:",
                "  1. Task Analysis & Exploration Planning (current)",
                "  2. Codebase Exploration (inline: Glob, Grep, Read)",
                "  3. Testing Strategy Discovery (may ask user)",
                "  4. Approach Generation",
                "  5. Assumption Surfacing (may ask user)",
                "  6. Milestone Definition & Plan Writing",
                "",
                "If you need user input at any step, use <needs_user_input> XML.",
                "IMPORTANT: Save state to plan.json BEFORE yielding with <needs_user_input>.",
                "The orchestrator will relay the question and REINVOKE you fresh with the answer.",
                "When reinvoked, plan.json will contain your saved progress.",
                "",
                "STEP 1: TASK ANALYSIS",
                "",
                "Parse the user's task description. Identify:",
                "  - What needs to change (files, modules, behavior)",
                "  - What exploration is needed (patterns, constraints, existing code)",
                "  - What directories/files are relevant",
                "",
                "Read project context files to understand structure:",
                "  - Project root CLAUDE.md",
                "  - Subdirectory CLAUDE.md files in relevant areas",
                "  - All paths in context.json reference_docs field (if any)",
                "",
                "CONTEXT.JSON CONTRACT: READ-ONLY.",
                "  - context.json is owned by the orchestrator",
                "  - You MUST NOT write, modify, or append to context.json",
                "  - Your outputs go to plan.json (step 6) -- never context.json",
                "",
                "DO NOT write any files yet. Gather understanding for step 2.",
                "Record your analysis mentally for use in subsequent steps.",
            ],
            "next": f"python3 -m {MODULE_PATH} --step 2 --state-dir {state_dir}",
        }

    elif step == 2:
        state_dir = kwargs.get("state_dir", "")
        state_dir_arg = f" --state-dir {state_dir}" if state_dir else ""
        return {
            "title": STEPS[2],
            "actions": [
                "STEP 2: CODEBASE EXPLORATION",
                "",
                "Use Glob, Grep, Read tools directly to discover:",
                "  - Existing patterns and implementations",
                "  - Constraints from code structure",
                "  - Conventions to follow",
                "",
                "Read conventions/ files as needed:",
                "  - structural.md (architectural patterns)",
                "  - temporal.md (comment hygiene)",
                "  - diff-format.md (diff specification)",
                "",
                "NUDGE: If you need additional context to plan well, read more files.",
                "Better to over-explore than under-explore.",
                "",
                "Record discoveries for use in steps 4-6. Do NOT write files.",
            ],
            "next": f"python3 -m {MODULE_PATH} --step 3{state_dir_arg}",
        }

    elif step == 3:
        state_dir = kwargs.get("state_dir", "")
        state_dir_arg = f" --state-dir {state_dir}" if state_dir else ""
        return {
            "title": STEPS[3],
            "actions": [
                "STEP 3: TESTING STRATEGY DISCOVERY",
                "",
                "DISCOVER testing strategy from:",
                "  - User conversation hints",
                "  - Project CLAUDE.md / README.md",
                "  - conventions/structural.md domain='testing-strategy'",
                "",
                "If testing approach is unclear, use <needs_user_input> to ask.",
                "",
                "Record confirmed strategy for use in step 6.",
                "Decisions will be recorded via CLI in step 6.",
            ],
            "next": f"python3 -m {MODULE_PATH} --step 4{state_dir_arg}",
        }

    elif step == 4:
        state_dir = kwargs.get("state_dir", "")
        state_dir_arg = f" --state-dir {state_dir}" if state_dir else ""
        return {
            "title": STEPS[4],
            "actions": [
                "STEP 4: APPROACH GENERATION",
                "",
                "GENERATE 2-3 approach options:",
                "  - Include 'minimal change' option",
                "  - Include 'idiomatic/modern' option",
                "  - Document advantage/disadvantage for each",
                "",
                "TARGET TECH RESEARCH (if new tech/migration):",
                "  - What is canonical usage of target tech?",
                "  - Does it have different abstractions?",
                "",
                "Use exploration findings from step 2 to ground tradeoffs.",
                "Record approach analysis for step 6.",
            ],
            "next": f"python3 -m {MODULE_PATH} --step 5{state_dir_arg}",
        }

    elif step == 5:
        state_dir = kwargs.get("state_dir", "")
        state_dir_arg = f" --state-dir {state_dir}" if state_dir else ""
        return {
            "title": STEPS[5],
            "actions": [
                "STEP 5: ASSUMPTION SURFACING",
                "",
                "FAST PATH: Skip if task involves NONE of:",
                "  - Migration to new tech",
                "  - Policy defaults (lifecycle, capacity, failure handling)",
                "  - Architectural decisions with multiple valid approaches",
                "",
                "FULL CHECK (if any apply):",
                "  Audit each category with OPEN questions:",
                "    Pattern preservation, Migration strategy, Idiomatic usage,",
                "    Abstraction boundary, Policy defaults",
                "",
                "  For each assumption needing confirmation:",
                "    Use <needs_user_input> BEFORE proceeding",
                "",
                "Record assumptions and user answers for step 6.",
            ],
            "next": f"python3 -m {MODULE_PATH} --step 6{state_dir_arg}",
        }

    elif step == 6:
        plan_json_schema = _provider.get_resource("plan-json-schema.md")
        return {
            "title": STEPS[6],
            "actions": [
                "STEP 6: MILESTONE DEFINITION & PLAN WRITING (JSON-IR)",
                "",
                "JSON-IR ARCHITECTURE:",
                "  plan.json is AUTHORITATIVE until TW translates to Markdown.",
                "  Use CLI commands to build plan.json - DO NOT write JSON directly.",
                "",
                "EVALUATE approaches: P(success), failure mode, backtrack cost",
                "",
                "SELECT and record in Decision Log with MULTI-STEP chain:",
                "  BAD:  'Polling | Webhooks unreliable'",
                "  GOOD: 'Polling | 30% webhook failure -> need fallback anyway'",
                "",
                "CLI COMMANDS (single invocation syntax):",
                "",
                "  python3 -m skills.planner.cli.plan --state-dir $STATE_DIR <command>",
                "",
                "  Commands:",
                "    set-decision --decision '<what>' --reasoning '<premise->implication->conclusion>'",
                "    set-milestone --name '<name>' --files 'path/a.py,path/b.py'",
                "    set-intent --milestone M-001 --file path/a.py --behavior '<what>' --decision-refs 'DL-001'",
                "",
                "BATCH MODE (preferred - reduces process invocations):",
                "",
                "JSON-RPC format: [{\"method\": \"...\", \"params\": {...}, \"id\": N}, ...]",
                "",
                "  python3 -m skills.planner.cli.plan --state-dir $STATE_DIR batch '[",
                "    {\"method\": \"set-decision\", \"params\": {\"decision\": \"Use polling\", \"reasoning\": \"30% webhook failures\"}, \"id\": 1},",
                "    {\"method\": \"set-milestone\", \"params\": {\"name\": \"Auth stack\", \"files\": \"src/auth.py\"}, \"id\": 2},",
                "    {\"method\": \"set-intent\", \"params\": {\"milestone\": \"M-001\", \"file\": \"src/auth.py\", \"behavior\": \"Add token validation\", \"decision_refs\": \"DL-001\"}, \"id\": 3}",
                "  ]'",
                "",
                "Response: [{\"id\": 1, \"result\": {\"id\": \"DL-001\", ...}}, ...]",
                "Errors: [{\"id\": N, \"error\": {\"code\": -32000, \"message\": \"...\"}}]",
                "",
                "DIAGRAM CREATION (if applicable):",
                "",
                "SKIP diagrams if:",
                "  - Pure refactoring (no new components)",
                "  - Single-file change",
                "  - Documentation-only milestone",
                "",
                "CREATE diagram if plan involves:",
                "  - Multiple services/components interacting",
                "  - Data flow through pipeline stages",
                "  - Protocol with state transitions",
                "  - SDK/API layer boundaries",
                "",
                "CLI WORKFLOW:",
                "",
                "1. Create diagram:",
                "   python3 -m skills.planner.cli.plan --state-dir $STATE_DIR set-diagram \\",
                "     --type architecture --scope overview --title 'System Overview'",
                "",
                "2. Add nodes (3-7 recommended, prevents visual overload):",
                "   python3 -m skills.planner.cli.plan --state-dir $STATE_DIR add-diagram-node \\",
                "     --diagram DIAG-001 --node-id client --label 'Client' --type service",
                "   python3 -m skills.planner.cli.plan --state-dir $STATE_DIR add-diagram-node \\",
                "     --diagram DIAG-001 --node-id server --label 'Server' --type service",
                "",
                "3. Add edges (label every edge):",
                "   python3 -m skills.planner.cli.plan --state-dir $STATE_DIR add-diagram-edge \\",
                "     --diagram DIAG-001 --source client --target server --label 'sends request' --protocol gRPC",
                "",
                "SCOPE VALUES:",
                "  - overview: Hero diagram, rendered after Overview section",
                "  - invisible_knowledge: Context for future LLM sessions",
                "  - milestone:M-XXX: Specific to what milestone implements",
                "",
                "NOTE: ascii_render is populated by Technical Writer, not Architect.",
                "      Separation of concerns: Architect validates connectivity, TW optimizes layout.",
                "",
                "NOTE: plan.json skeleton already exists (created by orchestrator).",
                "      CLI commands ADD to it, do not need 'init'.",
                "",
                "MILESTONES (each deployable increment):",
                "  - Files: exact paths (each file in ONE milestone only)",
                "  - Requirements: specific behaviors",
                "  - Acceptance: testable pass/fail criteria",
                "  - Code Intent: WHAT to change (Developer converts to code_changes later)",
                "  - Tests: type, backing, scenarios",
                "",
                "PARALLELIZATION:",
                "  Vertical slices (parallel) > Horizontal layers (sequential)",
                "  BAD: M1=models, M2=services, M3=controllers (sequential)",
                "  GOOD: M1=auth stack, M2=users stack, M3=posts stack (parallel)",
                "  If file overlap: extract to M0 (foundation) or consolidate",
                "",
                "VALIDATION: After building plan.json, run BOTH:",
                "  python3 -m skills.planner.cli.plan validate --phase plan-design",
                "  python3 -m skills.planner.cli.plan validate-planning-context",
                "",
                "PLANNING_CONTEXT SHAPE (F6 -- self-correct before PASS):",
                "  - constraints is a list of plain STRINGS, not objects.",
                "  - each rejected_alternatives entry needs both a rejection_reason",
                "    and a decision_ref (DL-XXX).",
                "  If validate-planning-context reports <planning_context_errors>,",
                "  fix the shape via CLI and re-run until it passes -- do NOT hand a",
                "  malformed planning_context to a later step.",
                "",
                "REFERENCE SCHEMA:",
                "",
                plan_json_schema,
                "",
                "When plan.json written and BOTH validations pass, output: PASS",
            ],
            "next": "",
        }

    return {"error": f"Invalid step {step}"}


if __name__ == "__main__":
    from skills.lib.workflow.cli import mode_main

    mode_main(
        __file__,
        get_step_guidance,
        "Plan-Design-Execute: Architect planning workflow",
        extra_args=[STATE_DIR_ARG_REQUIRED],
    )
