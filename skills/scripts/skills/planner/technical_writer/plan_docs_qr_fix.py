#!/usr/bin/env python3
"""Plan docs QR fix - targeted repair workflow.

3-step workflow for technical-writer sub-agent in fix mode:
  1. Load QR failures and understand issues
  2. Apply targeted fixes to documentation in plan.json
  3. Validate fixes locally

Scope: Documentation quality only -- fixing issues in documentation fields.
TW can fix:
- Temporal contamination in documentation strings
- Missing WHY comments (add inline_comments/function_blocks)
- Invalid decision_refs (correct or add missing refs)
- Structural completeness gaps (populate empty documentation{} fields)
- README content gaps (add to readme_entries[])

TW cannot fix (escalate if QR flags these -- they are out of scope):
- Code correctness issues (compilation, exports, types)
- Diff format issues (context lines, syntax)
- Logic errors in planned code

This is the FIX script for post-QR repair.
For first-time creation, see plan_docs_execute.py.
Router (plan_docs.py) dispatches to appropriate script.
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
    MODULE_PATH = module_path or "skills.planner.technical_writer.plan_docs_qr_fix"
    state_dir = kwargs.get("state_dir", "")
    PHASE = "plan-docs"

    if step == 1:
        validate_state_dir_requirement(step, state_dir)

        qr_iteration = get_qr_iteration(state_dir, PHASE)

        # Load failed items from qr-{phase}.json
        qr_state = load_qr_state(state_dir, PHASE)
        failed_items_block = format_failed_items_for_fix(qr_state) if qr_state else ""

        banner = format_state_banner("TW-PLAN-SCRUB", qr_iteration, "fix")

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
                "QR-DOCS found issues in your documentation.",
                "",
                failed_items_block if failed_items_block else "Read QR report from: STATE_DIR/qr-plan-docs.json",
                "",
                CLASS_SWEEP_DIRECTIVE,
                "",
                "PLANNING CONTEXT (reference for semantic validation):",
                "",
                context_display,
                "",
                "For EACH failed item:",
                "  1. Read the 'finding' field to understand the issue",
                "  2. Identify what in plan.json documentation needs to change",
                "  3. Note the fix approach for step 2",
                "",
                "FIXABLE ISSUE TYPES (address these):",
                "  - Temporal contamination in comments",
                "  - Missing WHY comments (add inline_comments/function_blocks)",
                "  - Invalid decision_refs (correct the reference)",
                "  - Structural completeness gaps (populate documentation{} fields)",
                "  - README content gaps (add to readme_entries[])",
                "",
                "OUT OF SCOPE (if QR flagged these, mark as PASS with note):",
                "  - Code correctness (compilation, exports, types) -- plan-code's job",
                "  - Diff format issues -- plan-code's job",
                "  - Whether files exist on disk -- this is a plan, not implementation",
                "  If an item is out of scope, update its status to PASS with finding:",
                "    'Out of scope for plan-docs phase (code correctness)'",
                "",
                "CONTEXT PRESERVATION:",
                "  - Do NOT remove valid documentation",
                "  - Do NOT change sections outside the flagged classes",
            ],
            "next": f"python3 -m {MODULE_PATH} --step 2 --state-dir {state_dir}",
        }

    elif step == 2:
        temporal_resource = get_convention("temporal.md")
        return {
            "title": STEPS[2],
            "actions": [
                "APPLY targeted fixes using CLI commands.",
                "",
                "SINGLE COMMAND EXAMPLES:",
                "",
                "Missing or invalid doc_diff:",
                "  - Rewrite doc_diff to fix issues",
                "  - Use set-doc-diff to update:",
                "    python3 -m skills.planner.cli.plan --state-dir $STATE_DIR set-doc-diff \\",
                "      --change CC-M-001-001 --version 1 --content-file /tmp/fixed.diff",
                "",
                "Temporal contamination in doc_diff:",
                "  - Rewrite doc_diff content to remove change-relative language",
                "  - Update via set-doc-diff:",
                "    python3 -m skills.planner.cli.plan --state-dir $STATE_DIR set-doc-diff \\",
                "      --change CC-M-001-001 --version 2 --content-file /tmp/fixed.diff",
                "",
                "Missing decision references:",
                "  - Find Decision Log entry (DL-XXX) that explains the choice",
                "  - Add reference to doc_diff content: (ref: DL-XXX)",
                "",
                "Missing documentation-only changes (READMEs):",
                "  - Create via create-doc-change:",
                "    python3 -m skills.planner.cli.plan --state-dir $STATE_DIR create-doc-change \\",
                "      --milestone M-001 --file path/README.md --content-file /tmp/readme.diff",
                "",
                "BATCH MODE (preferred - reduces process invocations):",
                "",
                "  python3 -m skills.planner.cli.plan --state-dir $STATE_DIR batch '[",
                "    {\"method\": \"set-doc-diff\", \"params\": {\"change\": \"CC-M-001-001\", \"version\": 1, \"content_file\": \"/tmp/fixed1.diff\"}, \"id\": 1},",
                "    {\"method\": \"set-doc-diff\", \"params\": {\"change\": \"CC-M-001-002\", \"version\": 1, \"content_file\": \"/tmp/fixed2.diff\"}, \"id\": 2}",
                "  ]'",
                "",
                "TEMPORAL REFERENCE:",
                temporal_resource,
                "",
                "CONSTRAINT: Fix EVERY instance of the flagged classes across all",
                "doc_diffs (not just the named findings). For temporal contamination,",
                "sweep the whole doc surface -- the scan in step 3 enforces zero hits.",
                "Don't refactor unrelated, passing items.",
            ],
            "next": f"python3 -m {MODULE_PATH} --step 3 --state-dir {state_dir}",
        }

    elif step == 3:
        return {
            "title": STEPS[3],
            "actions": [
                "VALIDATE your fixes before returning to orchestrator.",
                "",
                "Run documentation validation:",
                f"  python3 -m skills.planner.cli.plan validate --phase plan-docs --state-dir {state_dir}",
                "",
                temporal_scan_gate(state_dir),
                "",
                "SELF-CHECK each fixed item:",
                "  For each FAIL item you addressed:",
                "    - Does the fix address the specific finding?",
                "    - Did you sweep the WHOLE doc surface for siblings of that",
                "      class, or only patch the named instance?",
                "    - Does the fix introduce new temporal contamination?",
                "    - Are decision_refs valid?",
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
        "Plan-Docs-QR-Fix: Technical writer fix workflow for QR failures",
        extra_args=[
            (["--state-dir"], {"type": str, "required": True, "help": "State directory path"}),
        ],
    )
