#!/usr/bin/env python3
"""Impl code QR fix - targeted repair workflow.

3-step workflow for developer sub-agent in fix mode:
  1. Load QR failures and understand issues
  2. Apply targeted fixes to implementation
  3. Validate fixes locally

This is the FIX script for post-QR repair.
For first-time implementation, see exec_implement_execute.py.
Router (exec_implement.py) dispatches to appropriate script.
"""

from skills.planner.shared.constraints import format_state_banner
from skills.planner.shared.resources import validate_state_dir_requirement
from skills.planner.shared.qr.utils import (
    load_qr_state,
    format_failed_items_for_fix,
    get_qr_iteration,
)


STEPS = {
    1: "Load QR Failures",
    2: "Apply Code Fixes",
    3: "Validate Fixes",
}


def get_step_guidance(
    step: int, module_path: str = None, **kwargs) -> dict:
    """Return guidance for the given step."""
    MODULE_PATH = module_path or "skills.planner.developer.exec_implement_qr_fix"
    state_dir = kwargs.get("state_dir", "")
    PHASE = "impl-code"

    if step == 1:
        validate_state_dir_requirement(step, state_dir)

        qr_iteration = get_qr_iteration(state_dir, PHASE)

        # Load failed items from qr-{phase}.json
        qr_state = load_qr_state(state_dir, PHASE)
        failed_items_block = format_failed_items_for_fix(qr_state) if qr_state else ""

        banner = format_state_banner("IMPLEMENTATION-FIX", qr_iteration, "fix")

        return {
            "title": STEPS[1],
            "actions": [
                banner,
                "",
                f"FIX MODE - QR Iteration {qr_iteration}",
                "",
                "Code QR found issues in implemented code.",
                "",
                failed_items_block if failed_items_block else "Read QR report from: STATE_DIR/qr-impl-code.json",
                "",
                "For EACH failed item:",
                "  1. Read the 'finding' field to understand the issue",
                "  2. Identify what in the codebase needs to change",
                "  3. Note the fix approach for step 2",
                "",
                "COMMON ISSUE TYPES:",
                "  - Acceptance criteria mismatch",
                "  - Temporal contamination in comments",
                "  - Structural issues (god functions, duplicate logic)",
                "  - Missing error handling",
                "",
                "CONTEXT PRESERVATION:",
                "  - Do NOT refactor unrelated code",
                "  - Focus ONLY on addressing the specific failures",
            ],
            "next": f"python3 -m {MODULE_PATH} --step 2 --state-dir {state_dir}",
        }

    elif step == 2:
        return {
            "title": STEPS[2],
            "actions": [
                "APPLY targeted fixes to code.",
                "",
                "For each failed item, fix the identified issue:",
                "",
                "Acceptance criteria mismatch:",
                "  - Re-read the acceptance criteria from plan",
                "  - Modify code to match expected behavior",
                "",
                "Temporal contamination:",
                "  - Rewrite comments to remove change-relative language",
                "  - Use Edit tool on source files",
                "",
                "Structural issues:",
                "  - Extract functions if >50 lines",
                "  - Remove duplicate logic",
                "  - Add missing error handling",
                "",
                "CONSTRAINT: Fix ONLY the failing items. Don't refactor passing code.",
            ],
            "next": f"python3 -m {MODULE_PATH} --step 3 --state-dir {state_dir}",
        }

    elif step == 3:
        return {
            "title": STEPS[3],
            "actions": [
                "VALIDATE your fixes before returning to orchestrator.",
                "",
                "Run tests:",
                "  pytest / tsc / go test -race",
                "",
                "SELF-CHECK each fixed item:",
                "  For each FAIL item you addressed:",
                "    - Does the fix address the specific finding?",
                "    - Does the fix pass tests?",
                "    - Does the fix introduce new issues?",
                "",
                "If tests fail or self-check fails:",
                "  - Apply additional fixes",
                "  - Re-run tests",
                "",
                "If all tests pass:",
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
        "Exec-Implement-QR-Fix: Developer fix workflow for QR failures",
        extra_args=[
            (["--state-dir"], {"type": str, "required": True, "help": "State directory path"}),
        ],
    )
