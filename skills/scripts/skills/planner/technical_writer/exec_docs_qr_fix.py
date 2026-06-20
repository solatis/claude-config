#!/usr/bin/env python3
"""Impl docs QR fix - targeted repair workflow.

3-step workflow for technical-writer sub-agent in fix mode:
  1. Load QR failures and understand issues
  2. Apply targeted fixes to documentation
  3. Validate fixes locally

This is the FIX script for post-QR repair.
For first-time documentation, see exec_docs_execute.py.
Router (exec_docs.py) dispatches to appropriate script.
"""

from skills.planner.shared.constraints import format_state_banner
from skills.lib.conventions import get_convention
from skills.planner.shared.resources import validate_state_dir_requirement
from skills.planner.shared.fix_mode import CLASS_SWEEP_DIRECTIVE
from skills.planner.shared.qr.utils import (
    load_qr_state,
    format_failed_items_for_fix,
    get_qr_iteration,
)


STEPS = {
    1: "Load QR Failures",
    2: "Apply Doc Fixes",
    3: "Validate Fixes",
}


def get_step_guidance(
    step: int, module_path: str = None, **kwargs) -> dict:
    """Return guidance for the given step."""
    MODULE_PATH = module_path or "skills.planner.technical_writer.exec_docs_qr_fix"
    state_dir = kwargs.get("state_dir", "")
    PHASE = "impl-docs"

    if step == 1:
        validate_state_dir_requirement(step, state_dir)

        qr_iteration = get_qr_iteration(state_dir, PHASE)

        # Load failed items from qr-{phase}.json
        qr_state = load_qr_state(state_dir, PHASE)
        failed_items_block = format_failed_items_for_fix(qr_state) if qr_state else ""

        banner = format_state_banner("TW-POST-IMPL", qr_iteration, "fix")

        return {
            "title": STEPS[1],
            "actions": [
                banner,
                "",
                f"FIX MODE - QR Iteration {qr_iteration}",
                "",
                "Doc QR found issues in documentation.",
                "",
                failed_items_block if failed_items_block else "Read QR report from: STATE_DIR/qr-impl-docs.json",
                "",
                CLASS_SWEEP_DIRECTIVE,
                "",
                "For EACH failed item:",
                "  1. Read the 'finding' field to understand the issue and its CLASS",
                "  2. Identify what documentation needs to change -- and every other",
                "     instance of that class across the docs you touched",
                "  3. Note the fix approach for step 2",
                "",
                "COMMON ISSUE TYPES:",
                "  - CLAUDE.md format violations (prose instead of tabular)",
                "  - IK proximity failures (docs not adjacent to code)",
                "  - Temporal contamination in comments",
                "  - Missing README.md when IK present",
                "",
                "CONTEXT PRESERVATION:",
                "  - Do NOT remove valid documentation",
                "  - Fix every instance of the flagged classes; do NOT refactor",
                "    unrelated, passing docs",
            ],
            "next": f"python3 -m {MODULE_PATH} --step 2 --state-dir {state_dir}",
        }

    elif step == 2:
        temporal_resource = get_convention("temporal.md")
        return {
            "title": STEPS[2],
            "actions": [
                "APPLY targeted fixes to documentation.",
                "",
                "COMMON FIXES:",
                "",
                "CLAUDE.md format violations:",
                "  - Rewrite to tabular format",
                "  - Remove forbidden sections",
                "  - Shorten overview to one sentence",
                "",
                "IK proximity failures:",
                "  - Move knowledge to README.md in SAME directory as code",
                "  - Add inline comments at enforcement points",
                "  - Remove references to external doc/ directories",
                "",
                "Temporal contamination:",
                "  - Rewrite comments to remove change-relative language",
                "  - Sweep ALL touched docs/comments for the same pattern, not",
                "    just the flagged line",
                "",
                "Missing README.md:",
                "  - Create README.md with IK content",
                "  - Follow self-contained principle",
                "",
                "TEMPORAL REFERENCE:",
                temporal_resource,
                "",
                "CONSTRAINT: Fix EVERY instance of the flagged classes (not just the",
                "named findings). Don't refactor unrelated, passing docs.",
            ],
            "next": f"python3 -m {MODULE_PATH} --step 3 --state-dir {state_dir}",
        }

    elif step == 3:
        return {
            "title": STEPS[3],
            "actions": [
                "VALIDATE your fixes before returning to orchestrator.",
                "",
                "SELF-CHECK each fixed item:",
                "  For each FAIL item you addressed:",
                "    - Does the fix address the specific finding?",
                "    - Did you sweep all touched docs for siblings of that class,",
                "      or only patch the named instance?",
                "    - CLAUDE.md: Is it now tabular format?",
                "    - IK: Is it now adjacent to relevant code?",
                "    - Comments: Are they free of temporal contamination?",
                "",
                "If self-check fails:",
                "  - Apply additional fixes",
                "",
                "If all checks pass:",
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
        "Exec-Docs-QR-Fix: Technical writer fix workflow for QR failures",
        extra_args=[
            (["--state-dir"], {"type": str, "required": True, "help": "State directory path"}),
        ],
    )
