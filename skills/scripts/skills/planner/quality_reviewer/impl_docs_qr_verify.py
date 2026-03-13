#!/usr/bin/env python3
"""QR verification for impl-docs phase.

Single-item verification mode for parallel QR dispatch.
Each verify agent receives --qr-item and validates ONE check.

Modes:
- --qr-item: Single item verification (for parallel dispatch)
- Default (legacy): Sequential 4-step full verification (deprecated)

For decomposition (generating items), see impl_docs_qr_decompose.py.
"""

from skills.planner.shared.qr.utils import (
    get_qr_iteration,
    has_qr_failures,
    format_qr_result,
)
from skills.planner.shared.schema import get_qa_state_schema_example
from .qr_verify_base import VerifyBase


PHASE = "impl-docs"
WORKFLOW = "executor"


class ImplDocsVerify(VerifyBase):
    """QR verification for impl-docs phase."""

    PHASE = "impl-docs"

    def get_verification_guidance(self, item: dict, state_dir: str) -> list[str]:
        """Impl-docs-specific verification instructions."""
        scope = item.get("scope", "*")
        check = item.get("check", "")

        guidance = []

        if scope == "*":
            guidance.extend([
                "MACRO CHECK - Verify across all documentation:",
                "",
                f"  Read plan.json for IK and modified files:",
                f"    cat {state_dir}/plan.json | jq '{{ik: .invisible_knowledge, milestones: .milestones[].files}}'",
                "",
                "  Read project index file and README.md files in modified directories.",
                "",
            ])
        elif scope.startswith("directory:"):
            directory = scope.split(":", 1)[1]
            guidance.extend([
                f"DIRECTORY CHECK - Focus on {directory}:",
                "",
                f"  Read project index file: cat {directory}/project index file",
                f"  Read README.md: cat {directory}/README.md (if exists)",
                "",
            ])
        else:
            guidance.extend([
                f"SCOPED CHECK - Scope: {scope}",
                "",
                "  Read the relevant documentation files.",
                "",
            ])

        # Add check-specific guidance
        if "claude.md" in check.lower() and "tabular" in check.lower():
            guidance.extend([
                "CLAUDE.MD FORMAT CHECK:",
                "  Must use tabular index format:",
                "  | File | Contents (WHAT) | Read When (WHEN) |",
                "  | ---- | --------------- | ---------------- |",
                "  - FAIL if prose instead of table",
                "  - FAIL if overview >1 sentence",
                "",
            ])
        elif "forbidden section" in check.lower():
            guidance.extend([
                "FORBIDDEN SECTIONS CHECK:",
                "  project index file must NOT have:",
                "  - 'Key Invariants' section",
                "  - 'Dependencies' section",
                "  - 'Constraints' section",
                "  These belong in README.md, not project index file.",
                "",
            ])
        elif "overview" in check.lower() and "one sentence" in check.lower():
            guidance.extend([
                "OVERVIEW LENGTH CHECK:",
                "  project index file overview must be ONE sentence max.",
                "  Count sentences in Overview section.",
                "",
            ])
        elif "temporal" in check.lower():
            guidance.extend([
                "TEMPORAL CONTAMINATION CHECK:",
                "  Scan comments in modified files for:",
                "  - CHANGE_RELATIVE: 'Added', 'Replaced', 'Changed'",
                "  - BASELINE_REFERENCE: 'instead of', 'previously'",
                "",
            ])
        elif "ik" in check.lower() and "proximity" in check.lower():
            guidance.extend([
                "IK PROXIMITY CHECK:",
                "  Each Invisible Knowledge item must be documented",
                "  in README.md in the SAME directory as affected code.",
                "  - FAIL if IK is in separate doc/ directory",
                "  - FAIL if IK references external wiki without local summary",
                "",
            ])
        elif "readme" in check.lower() and "created" in check.lower():
            guidance.extend([
                "README.MD CREATION CHECK:",
                "  If invisible_knowledge has content:",
                "  - README.md should exist in relevant directories",
                "  - README.md should contain IK items",
                "",
            ])
        elif "self-contained" in check.lower():
            guidance.extend([
                "SELF-CONTAINED CHECK:",
                "  README.md must not rely on external sources:",
                "  - No 'see wiki for details'",
                "  - No 'refer to doc/ directory'",
                "  External knowledge must be summarized locally.",
                "",
            ])
        elif "marker" in check.lower():
            guidance.extend([
                "INTENT MARKER VALIDATION:",
                "  Valid format: ':MARKER: [what]; [why]'",
                "  - Must have semicolon",
                "  - Must have non-empty why after semicolon",
                "",
            ])

        return guidance


def get_step_guidance(step: int, module_path: str = None, **kwargs) -> dict:
    """Gateway normalizes input and delegates to base class."""
    module_path = module_path or "skills.planner.quality_reviewer.impl_docs_qr_verify"
    qr_item = kwargs.get("qr_item")
    state_dir = kwargs.get("state_dir", "")

    if qr_item:
        # Normalize to list (backwards compat if single string passed)
        items = qr_item if isinstance(qr_item, list) else [qr_item]
        kwargs["qr_item"] = items
        verifier = ImplDocsVerify()
        return verifier.get_step_guidance(step, module_path, **kwargs)

    return {
        "title": "Error: No Items",
        "actions": ["--qr-item required. Use: --qr-item a --qr-item b"],
        "next": "",
    }


if __name__ == "__main__":
    from skills.lib.workflow.cli import mode_main
    mode_main(
        __file__,
        get_step_guidance,
        "QR-Impl-Docs: Post-implementation documentation quality review workflow",
        extra_args=[
            (["--state-dir"], {"type": str, "help": "State directory path"}),
            (["--qr-item"], {"action": "append", "help": "Item ID (repeatable)"}),
        ],
    )
