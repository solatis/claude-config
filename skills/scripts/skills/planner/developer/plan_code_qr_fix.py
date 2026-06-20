#!/usr/bin/env python3
"""Plan code QR fix - targeted repair workflow.

3-step workflow for developer sub-agent in fix mode:
  1. Load QR failures and understand issues
  2. Apply targeted fixes to code_changes in plan.json
  3. Validate fixes locally

This is the FIX script for post-QR repair.
For first-time creation, see plan_code_execute.py.
Router (plan_code.py) dispatches to appropriate script.

Fix scripts separate from execute scripts:
- Execute: first-time creation (blank slate)
- Fix: targeted repair (QR failures guide changes)
- Separation prevents fix logic from polluting execute logic
- Fix scripts are shorter, focused on QR findings
"""

from skills.planner.shared.constraints import format_state_banner
from skills.lib.conventions import get_convention
from skills.planner.shared.resources import validate_state_dir_requirement, get_context_path, render_context_file
from skills.planner.shared.fix_mode import CLASS_SWEEP_DIRECTIVE, temporal_scan_gate
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
    MODULE_PATH = module_path or "skills.planner.developer.plan_code_qr_fix"
    state_dir = kwargs.get("state_dir", "")
    PHASE = "plan-code"

    if step == 1:
        validate_state_dir_requirement(step, state_dir)

        qr_iteration = get_qr_iteration(state_dir, PHASE)

        # Load failed items from qr-{phase}.json
        qr_state = load_qr_state(state_dir, PHASE)
        failed_items_block = format_failed_items_for_fix(qr_state) if qr_state else ""

        banner = format_state_banner("DEV-FILL-DIFFS", qr_iteration, "fix")
        diff_convention = get_convention("diff-format.md")

        # Load context for semantic validation reference
        context_file = get_context_path(state_dir) if state_dir else None
        context_display = render_context_file(context_file) if context_file else ""

        return {
            "title": STEPS[1],
            "actions": [
                banner,
                "",
                f"FIX MODE - QR Iteration {qr_iteration}",
                "",
                "QR-CODE found issues requiring fixes.",
                "",
                failed_items_block if failed_items_block else "Read QR report from: STATE_DIR/qr-plan-code.json",
                "",
                CLASS_SWEEP_DIRECTIVE,
                "",
                "PLANNING CONTEXT (reference for semantic validation):",
                "",
                context_display,
                "",
                "FIX CATEGORIES:",
                "  QR findings fall into two categories with different fix approaches:",
                "",
                "  1. PLAN ISSUES - Finding references a CC-M-XXX-XXX (code_change ID)",
                "     -> Fix by updating the diff in plan.json via CLI commands",
                "",
                "  2. CODEBASE ISSUES - Finding references an existing file not in plan.json",
                "     -> Fix by editing the actual file directly using Edit tool",
                "",
                "For EACH failed item:",
                "  1. Read the 'finding' field to understand the issue",
                "  2. Determine category: plan issue (CC-M ref) or codebase issue (file path)",
                "  3. Note the fix approach for step 2",
                "",
                "DIFF FORMAT REFERENCE:",
                "",
                diff_convention,
                "",
                "CONTEXT PRESERVATION:",
                "  - Do NOT remove valid code_changes",
                "  - Do NOT change diffs outside the flagged classes",
            ],
            "next": f"python3 -m {MODULE_PATH} --step 2 --state-dir {state_dir}",
        }

    elif step == 2:
        return {
            "title": STEPS[2],
            "actions": [
                "APPLY targeted fixes based on category identified in step 1.",
                "",
                "FOR PLAN ISSUES (CC-M-XXX-XXX references):",
                "  Update code_changes in plan.json via CLI commands.",
                "",
                "SINGLE COMMAND EXAMPLE:",
                "",
                "  Context line mismatch:",
                "    - Read actual file content",
                "    - Update diff with correct context lines",
                "    - Update via CLI with --version (get version from list-changes):",
                "      python3 -m skills.planner.cli.plan --state-dir $STATE_DIR set-change \\",
                "        --id CC-M-001-001 --version 1 --milestone M-001 \\",
                "        --diff $'--- a/path/to/file.py\\n+++ b/path/to/file.py\\n...'",
                "",
                "BATCH MODE (preferred - reduces process invocations):",
                "",
                "  python3 -m skills.planner.cli.plan --state-dir $STATE_DIR batch '[",
                "    {\"method\": \"set-change\", \"params\": {\"id\": \"CC-M-001-001\", \"version\": 1, \"milestone\": \"M-001\", \"diff\": \"--- a/src/a.py\\n+++ b/src/a.py\\n...\"}, \"id\": 1},",
                "    {\"method\": \"set-change\", \"params\": {\"id\": \"CC-M-001-002\", \"version\": 1, \"milestone\": \"M-001\", \"diff\": \"--- a/src/b.py\\n+++ b/src/b.py\\n...\"}, \"id\": 2}",
                "  ]'",
                "",
                "COMMON FIX PATTERNS:",
                "",
                "  Missing/incorrect file paths:",
                "    - Verify target file exists",
                "    - Use exact path in diff header",
                "",
                "  RULE 0/1/2 violations:",
                "    - RULE 0: File path must be exact and correct",
                "    - RULE 1: Context lines must match codebase",
                "    - RULE 2: Function context in @@ header must be accurate",
                "",
                "  Diff format errors:",
                "    - Ensure proper --- a/ and +++ b/ headers",
                "    - Ensure @@ line has correct line numbers",
                "    - Ensure context/add/remove prefixes are correct",
                "",
                "FOR CODEBASE ISSUES (existing files not in plan.json):",
                "  Edit the actual file directly using Edit tool.",
                "  These are issues in existing code that the plan depends on.",
                "",
                "CONSTRAINT: Fix EVERY instance of the flagged classes across all",
                "code_changes (not just the named findings). Don't refactor unrelated,",
                "passing items.",
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
                f"  python3 -m skills.planner.cli.plan validate --phase plan-code --state-dir {state_dir}",
                "",
                temporal_scan_gate(state_dir),
                "",
                "SELF-CHECK each fixed item:",
                "  For each FAIL item you addressed:",
                "    - Does the fix address the specific finding?",
                "    - Did you sweep ALL code_changes for siblings of that class,",
                "      or only patch the named instance?",
                "    - Does the fix introduce new issues?",
                "    - Are context lines correct (verify against actual file)?",
                "",
                "If validation, the temporal scan, or self-check fails:",
                "  - Apply additional fixes",
                "  - Re-run validation and the temporal scan",
                "",
                "If validation passes AND the temporal scan reports zero hits:",
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
        "Plan-Code-QR-Fix: Developer fix workflow for QR failures",
        extra_args=[
            (["--state-dir"], {"type": str, "required": True, "help": "State directory path"}),
        ],
    )
