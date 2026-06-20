#!/usr/bin/env python3
"""Plan design QR fix - targeted repair workflow.

3-step workflow for architect sub-agent in fix mode:
  1. Load QR failures and understand issues
  2. Apply targeted fixes to plan.json
  3. Validate fixes locally

This is the FIX script for post-QR repair.
For first-time creation, see plan_design_execute.py.
Router (plan_design.py) dispatches to appropriate script.

Fix scripts separate from execute scripts:
- Execute: first-time creation (blank slate)
- Fix: targeted repair (QR failures guide changes)
- Separation prevents fix logic from polluting execute logic
- Fix scripts are shorter, focused on QR findings
"""

from skills.planner.shared.resources import (
    STATE_DIR_ARG_REQUIRED,
    validate_state_dir_requirement,
    get_context_path,
    render_context_file,
)
from skills.planner.shared.fix_mode import CLASS_SWEEP_DIRECTIVE
from skills.planner.shared.qr.utils import (
    load_qr_state,
    format_failed_items_for_fix,
    get_qr_iteration,
)


STEPS = {
    1: "Load QR Failures",
    2: "Apply Targeted Fixes",
    3: "Validate Fixes",
}


def get_step_guidance(
    step: int, module_path: str = None, **kwargs) -> dict:
    """Return guidance for the given step."""
    MODULE_PATH = module_path or "skills.planner.architect.plan_design_qr_fix"
    state_dir = kwargs.get("state_dir", "")
    PHASE = "plan-design"

    if step == 1:
        validate_state_dir_requirement(step, state_dir)

        qr_iteration = get_qr_iteration(state_dir, PHASE)

        # Load failed items from qr-{phase}.json
        qr_state = load_qr_state(state_dir, PHASE)
        failed_items_block = format_failed_items_for_fix(qr_state) if qr_state else ""

        # Load context for semantic validation reference
        context_file = get_context_path(state_dir) if state_dir else None
        context_display = render_context_file(context_file) if context_file else ""

        return {
            "title": STEPS[1],
            "actions": [
                f"FIX MODE - QR Iteration {qr_iteration}",
                "",
                "QR-COMPLETENESS found issues in the plan.",
                "",
                failed_items_block if failed_items_block else "Read QR report from: STATE_DIR/qr-plan-design.json",
                "",
                CLASS_SWEEP_DIRECTIVE,
                "",
                "PLANNING CONTEXT (reference for semantic validation):",
                "",
                context_display,
                "",
                "For EACH failed item:",
                "  1. Read the 'finding' field to understand the issue and its CLASS",
                "  2. Identify what in plan.json needs to change -- and every other",
                "     instance of that class across the plan",
                "  3. Note the fix approach for step 2",
                "",
                "CONTEXT PRESERVATION:",
                "  - Do NOT remove valid decision_log entries",
                "  - Do NOT change milestones outside the flagged classes",
                "",
                "CONTEXT.JSON CONTRACT: READ-ONLY.",
                "  - context.json is owned by the orchestrator",
                "  - You MUST NOT write, modify, or append to context.json",
                "  - Your fixes go to plan.json -- never context.json",
            ],
            "next": f"python3 -m {MODULE_PATH} --step 2 --state-dir {state_dir}",
        }

    elif step == 2:
        return {
            "title": STEPS[2],
            "actions": [
                "APPLY targeted fixes to plan.json using CLI commands.",
                "",
                "SINGLE COMMAND EXAMPLES:",
                "",
                "Missing decision_log entry:",
                "  python3 -m skills.planner.cli.plan --state-dir $STATE_DIR set-decision \\",
                "    --decision '<what was decided>' \\",
                "    --reasoning '<premise -> implication -> conclusion>'",
                "",
                "Missing code_intent:",
                "  python3 -m skills.planner.cli.plan --state-dir $STATE_DIR set-intent \\",
                "    --milestone <milestone-id> --file <path> \\",
                "    --behavior '<what to implement>' \\",
                "    --decision-refs '<DL-001,DL-002>'",
                "",
                "Updating existing intent (requires --version from current state):",
                "  python3 -m skills.planner.cli.plan --state-dir $STATE_DIR set-intent \\",
                "    --id <intent-id> --version <current-version> \\",
                "    --behavior '<updated description>'",
                "",
                "BATCH MODE (preferred - reduces process invocations):",
                "",
                "  python3 -m skills.planner.cli.plan --state-dir $STATE_DIR batch '[",
                "    {\"method\": \"set-decision\", \"params\": {\"decision\": \"Use polling\", \"reasoning\": \"30% webhook failures\"}, \"id\": 1},",
                "    {\"method\": \"set-intent\", \"params\": {\"milestone\": \"M-001\", \"file\": \"src/a.py\", \"behavior\": \"Add handler\", \"decision_refs\": \"DL-001\"}, \"id\": 2},",
                "    {\"method\": \"set-intent\", \"params\": {\"id\": \"CI-M-001-001\", \"version\": 1, \"behavior\": \"Updated description\"}, \"id\": 3}",
                "  ]'",
                "",
                "COMMON FIX PATTERNS:",
                "",
                "Invalid decision_refs:",
                "  - If decision exists but ref is wrong: update the intent",
                "  - If decision is missing: add it first, then update ref",
                "",
                "Policy default without backing:",
                "  - Add decision_log entry explaining user confirmation",
                "  - Or use <needs_user_input> to get confirmation NOW",
                "",
                "CONSTRAINT: Fix EVERY instance of the flagged classes (not just the",
                "named findings). Don't refactor unrelated, passing items.",
            ],
            "next": f"python3 -m {MODULE_PATH} --step 3 --state-dir {state_dir}",
        }

    elif step == 3:
        return {
            "title": STEPS[3],
            "actions": [
                "VALIDATE your fixes before returning to orchestrator.",
                "",
                "Run structural validation:",
                f"  python3 -m skills.planner.cli.plan validate --phase plan-design --state-dir {state_dir}",
                "",
                "Validate planning_context SHAPE (F6 -- self-correct before PASS):",
                f"  python3 -m skills.planner.cli.plan validate-planning-context --state-dir {state_dir}",
                "  - constraints must be plain strings (not objects).",
                "  - each rejected_alternatives entry needs rejection_reason + decision_ref.",
                "  If it reports <planning_context_errors>, fix the shape and re-run;",
                "  never hand a malformed planning_context to a downstream step.",
                "",
                "SELF-CHECK each fixed item:",
                "  For each FAIL item you addressed:",
                "    - Does the fix address the specific finding?",
                "    - Did you sweep the WHOLE plan for siblings of that class,",
                "      or only patch the named instance?",
                "    - Does the fix introduce new issues?",
                "    - Is the reasoning chain multi-step (not single assertion)?",
                "",
                "If validation, the planning_context shape check, or self-check fails:",
                "  - Apply additional fixes",
                "  - Re-run both validations",
                "",
                "If both validations pass:",
                "  Your complete response must be exactly: PASS",
                "  Do not add summaries, explanations, or any other text.",
            ],
            "next": "",
        }

    return {"error": f"Invalid step {step}"}


if __name__ == "__main__":
    from skills.lib.workflow.cli import mode_main

    mode_main(
        __file__,
        get_step_guidance,
        "Plan-Design-QR-Fix: Architect fix workflow for QR failures",
        extra_args=[
            (["--state-dir"], {"type": str, "required": True, "help": "State directory path"}),
        ],
    )
