#!/usr/bin/env python3
"""
Interactive Sequential Planner - Unified 13-step planning workflow.

Steps 1-5:  Planning (context, testing strategy, approaches, assumptions, milestones)
Steps 6-13: Review (QR gates, developer diffs, TW scrub)

Flow:
  1. Context Discovery
  2. Testing Strategy Discovery
  3. Approach Generation
  4. Assumption Surfacing
  5. Approach Selection & Milestones
  6. QR-Completeness -> 7. Gate
  8. Developer Fills Diffs
  9. QR-Code -> 10. Gate
  11. TW Documentation Scrub
  12. QR-Docs -> 13. Gate -> Plan Approved
"""

import argparse
import sys

from skills.lib.workflow.types import QRState, GateConfig
from skills.lib.workflow.formatters import (
    format_step_output,
    format_gate_step,
    format_invoke_after,
    format_step_header,
    format_current_action,
    format_subagent_dispatch,
    format_state_banner,
    format_post_qr_routing,
    format_orchestrator_constraint,
    format_qr_banner,
)
from skills.lib.workflow.cli import add_qr_args
from skills.planner.shared.resources import get_mode_script_path, get_resource


# Module path for -m invocation
MODULE_PATH = "skills.planner.planner"


PLANNING_VERIFICATION = """\
# Planning Verification Checklist

Complete in priority order before writing the plan.

## PHASE 1: CRITICAL (BLOCKING)

### VERIFY 1: Decision Log Completeness

TW sources ALL code comments from Decision Log. Missing entries mean
undocumented code.

- Every architectural choice has multi-step reasoning? INSUFFICIENT: 'Polling |
  Webhooks are unreliable' SUFFICIENT: 'Polling | 30% webhook failure -> need
  fallback anyway -> simpler as primary'
- Every micro-decision documented? (timeouts, thresholds, concurrency choices,
  data structure selections)
- Rejected alternatives listed with concrete reasons?
- Known risks have mitigations with file:line anchors for any behavioral claims?

### VERIFY 2: Code Intent Presence

STOP CHECK: For EACH implementation milestone:

- Does it contain a Code Intent section describing WHAT to change?
- If NO and milestone creates/modifies source files: STOP. Add Code Intent
  before proceeding.

Implementation milestones WITHOUT Code Intent cannot be approved. Only
documentation milestones (100% .md/.rst files) may skip Code Intent.

### VERIFY 3: Invisible Knowledge Capture (BLOCKING)

ALL architecture decisions, tradeoffs, invariants, and rationale that a future
reader could NOT infer from reading code alone MUST be documented in the plan's
Invisible Knowledge section.

MISSING INVISIBLE KNOWLEDGE IS A BLOCKING ISSUE.

Check for:

- Why was this approach chosen over alternatives?
- What tradeoffs were made and why?
- What invariants must be maintained?
- What assumptions underlie this design?
- What would a future maintainer need to know?

If the plan makes ANY decision that requires explanation beyond what code
comments can convey, it MUST be in Invisible Knowledge.

## PHASE 2: FORMAT

### VERIFY 4: Code Intent Clarity

For EACH implementation milestone:

- File paths exact (src/auth/handler.py not 'auth files')?
- Code Intent describes WHAT to change (functions, structs, behavior)?
- Key decisions reference Decision Log entries?
- NO diff blocks present (Developer fills those after plan is written)?

Code Intent should be clear enough for Developer to produce diffs without
ambiguity. If intent is vague, clarify it now.

### VERIFY 5: Milestone Specification

For EACH milestone:

- File paths exact?
- Requirements are specific behaviors, not 'handle X'?
- Acceptance criteria are testable pass/fail assertions?
- Tests section with type, backing, scenarios? (or explicit skip reason)
- Uncertainty flags added where applicable?

## PHASE 3: DOCUMENTATION

### VERIFY 6: Documentation Milestone

- Documentation milestone exists?
- CLAUDE.md format verification:
  - Tabular index format with WHAT/WHEN columns?
  - ~200 token budget (no prose sections)?
  - NO 'Key Invariants', 'Dependencies', 'Constraints' sections?
  - Overview is ONE sentence only?
- README.md included if Invisible Knowledge has content?
- Invisible Knowledge maps to README.md, not CLAUDE.md?
- Stub directories (only .gitkeep) excluded from CLAUDE.md requirement?

### VERIFY 7: Comment Hygiene

Comments will be transcribed VERBATIM. Write in TIMELESS PRESENT.

CONTAMINATED: '// Added mutex to fix race condition' CLEAN: '// Mutex serializes
cache access from concurrent requests'

CONTAMINATED: '// After the retry loop' CLEAN: (delete -- diff context encodes
location)

### VERIFY 8: Assumption Audit Complete

- Step 2 assumption audit completed (all categories)?
- Step 3 decision classification table written?
- Step 4 file classification table written?
- No 'assumption' rows remain unresolved?
- User responses recorded with 'user-specified' backing?

If any step was skipped: STOP. Go back and complete it.
"""


def get_plan_format() -> str:
    """Read the plan format template from resources."""
    return get_resource("plan-format.md")


# Unified step definitions (1-13)
STEPS = {
    # Planning steps (1-5)
    1: {
        "title": "Context Discovery",
        "is_dispatch": True,
        "dispatch_agent": "Explore",
        "mode_script": "explore.py",
        "mode_total_steps": 5,
        "context_vars": {
            "TASK": "the user's task/request being planned",
            "DECISION_CRITERIA": "what planning decisions will consume this output",
        },
        "actions": [
            "READ .claude/conventions: structural.md, diff-format.md, temporal.md",
            "",
            "DELEGATE exploration to Explore sub-agent with decision context.",
            "",
            "The sub-agent will follow a 5-step workflow:",
            "  1. Exploration Planning - parse task into investigation targets",
            "  2. Execute Exploration - gather findings with decision-relevant depth",
            "  3. Gap Analysis - check coverage against decision criteria",
            "  4. Fill Gaps - additional exploration for uncovered criteria",
            "  5. Format Output - compress into structured XML",
        ],
        "post_dispatch": [
            "The sub-agent MUST invoke explore.py and follow its guidance.",
            "",
            "Expected output: Structured XML with sections:",
            "  <approach_inputs> - for Step 3 (Approach Generation)",
            "  <assumption_inputs> - for Step 4 (Assumption Surfacing)",
            "  <milestone_inputs> - for Step 5 (Milestone Planning)",
        ],
    },
    2: {
        "title": "Testing Strategy Discovery",
        "actions": [
            "DISCOVER existing testing strategy from:",
            "  - User conversation hints",
            "  - Project CLAUDE.md / README.md",
            "  - conventions/structural.md domain='testing-strategy'",
            "",
            "PROPOSE test approach for EACH type:",
            "",
            "For UNIT tests:",
            "  Use AskUserQuestion:",
            "    'For unit tests, use property-based (quickcheck) approach?'",
            "    Options: [Yes - few tests cover many variables] [No - example-based] [Skip - no unit tests]",
            "",
            "For INTEGRATION tests:",
            "  Use AskUserQuestion:",
            "    'For integration tests, use real dependencies?'",
            "    Options: [Yes - testcontainers/real deps] [No - mocks] [Skip - no integration tests]",
            "",
            "For E2E tests:",
            "  Use AskUserQuestion:",
            "    'For e2e tests, use generated datasets?'",
            "    Options: [Yes - deterministic generated data] [No - fixtures] [Skip - no e2e tests]",
            "",
            "Record confirmed strategy in Decision Log with 'user-specified' backing.",
        ],
    },
    3: {
        "title": "Approach Generation",
        "actions": [
            "GENERATE 2-3 approach options:",
            "  - Include 'minimal change' option",
            "  - Include 'idiomatic/modern' option",
            "  - Document advantage/disadvantage for each",
            "",
            "TARGET TECH RESEARCH (if new tech/migration):",
            "  - What is canonical usage of target tech?",
            "  - Does it have different abstractions?",
            "",
            "TEST REQUIREMENTS:",
            "  - Check project docs for test requirements",
            "  - If silent, default-conventions domain='testing' applies",
        ],
    },
    4: {
        "title": "Assumption Surfacing",
        "actions": [
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
            "    Use AskUserQuestion BEFORE proceeding",
            "    Record choice in Decision Log with 'user-specified' backing",
        ],
    },
    5: {
        "title": "Approach Selection & Milestones",
        "include_verification": True,
        "include_plan_format": True,
        "actions": [
            "EVALUATE approaches: P(success), failure mode, backtrack cost",
            "",
            "SELECT and record in Decision Log with MULTI-STEP chain:",
            "  BAD:  'Polling | Webhooks unreliable'",
            "  GOOD: 'Polling | 30% webhook failure -> need fallback anyway'",
            "",
            "MILESTONES (each deployable increment):",
            "  - Files: exact paths (each file in ONE milestone only)",
            "  - Requirements: specific behaviors",
            "  - Acceptance: testable pass/fail criteria",
            "  - Code Intent: WHAT to change (Developer converts to diffs in step 7)",
            "  - Tests: type, backing, scenarios",
            "",
            "PARALLELIZATION:",
            "  Vertical slices (parallel) > Horizontal layers (sequential)",
            "  BAD: M1=models, M2=services, M3=controllers (sequential)",
            "  GOOD: M1=auth stack, M2=users stack, M3=posts stack (parallel)",
            "  If file overlap: extract to M0 (foundation) or consolidate",
            "  Draw dependency diagram showing parallel waves",
            "",
            "RISKS: | Risk | Mitigation | Anchor (file:line if behavioral claim) |",
            "",
            "Write plan with Code Intent (no diffs yet).",
            "Developer fills diffs in step 8.",
        ],
    },
    # Review steps (6-13)
    6: {
        "title": "QR-Completeness",
        "is_qr": True,
        "qr_name": "QR-COMPLETENESS",
        "is_dispatch": True,
        "dispatch_agent": "quality-reviewer",
        "mode_script": "qr/plan-completeness.py",
        "mode_total_steps": 6,
        "context_vars": {"PLAN_FILE": "path to the plan being reviewed"},
        "post_dispatch": [
            "The sub-agent MUST invoke the script and follow its guidance.",
            "",
            "Expected output: PASS or ISSUES",
        ],
        "post_qr_routing": {"self_fix": True},
    },
    # Step 7 is gate - handled by GATES dict
    8: {
        "title": "Developer Fills Diffs",
        "is_work": True,
        "work_agent": "developer",
        "is_dispatch": True,
        "dispatch_agent": "developer",
        "mode_script": "dev/fill-diffs.py",
        "mode_total_steps": 4,
        "context_vars": {"PLAN_FILE": "path to the plan being reviewed"},
        "post_dispatch": [
            "The sub-agent MUST invoke the script and follow its guidance.",
            "Developer edits plan file IN-PLACE.",
        ],
    },
    9: {
        "title": "QR-Code",
        "is_qr": True,
        "qr_name": "QR-CODE",
        "is_dispatch": True,
        "dispatch_agent": "quality-reviewer",
        "mode_script": "qr/plan-code.py",
        "mode_total_steps": 7,
        "context_vars": {"PLAN_FILE": "path to the plan being reviewed"},
        "post_dispatch": [
            "The sub-agent MUST invoke the script and follow its guidance.",
            "",
            "Expected output: PASS or ISSUES",
        ],
        "post_qr_routing": {"self_fix": False, "fix_target": "developer"},
    },
    # Step 10 is gate - handled by GATES dict
    11: {
        "title": "TW Documentation Scrub",
        "is_work": True,
        "work_agent": "technical-writer",
        "is_dispatch": True,
        "dispatch_agent": "technical-writer",
        "mode_script": "tw/plan-scrub.py",
        "mode_total_steps": 6,
        "context_vars": {"PLAN_FILE": "path to the plan being reviewed"},
        "post_dispatch": [
            "The sub-agent MUST invoke the script and follow its guidance.",
            "TW edits plan file IN-PLACE.",
            "",
            "Expected output: COMPLETE or BLOCKED",
        ],
    },
    12: {
        "title": "QR-Docs",
        "is_qr": True,
        "qr_name": "QR-DOCS",
        "is_dispatch": True,
        "dispatch_agent": "quality-reviewer",
        "mode_script": "qr/plan-docs.py",
        "mode_total_steps": 5,
        "context_vars": {"PLAN_FILE": "path to the plan being reviewed"},
        "post_dispatch": [
            "The sub-agent MUST invoke the script and follow its guidance.",
            "",
            "Expected output: PASS or ISSUES",
        ],
        "post_qr_routing": {"self_fix": False, "fix_target": "technical-writer"},
    },
    # Step 13 is gate - handled by GATES dict
}


# Gate configurations (steps 7, 10, 13)
GATES = {
    7: GateConfig(
        qr_name="QR-COMPLETENESS",
        work_step=5,  # Route to plan writing step, not QR step
        pass_step=8,
        pass_message="Proceed to step 8 (Developer Fills Diffs).",
        self_fix=True,
    ),
    10: GateConfig(
        qr_name="QR-CODE",
        work_step=8,
        pass_step=11,
        pass_message="Proceed to step 11 (TW Documentation Scrub).",
        self_fix=False,
        fix_target="developer",
    ),
    13: GateConfig(
        qr_name="QR-DOCS",
        work_step=11,
        pass_step=None,
        pass_message="PLAN APPROVED. Ready for /plan-execution.",
        self_fix=False,
        fix_target="technical-writer",
    ),
}


def format_gate(step: int, qr: QRState) -> str:
    """Format gate step output using XML format."""
    gate = GATES[step]
    return format_gate_step(
        script="planner",
        step=step,
        total=13,
        gate=gate,
        qr=qr,
        cmd_template=f"python3 -m {MODULE_PATH}",
    )


def get_step_guidance(step: int, total_steps: int,
                      qr_iteration: int = 1, qr_fail: bool = False,
                      qr_status: str = None) -> dict | str:
    """Returns guidance for a step."""

    # Construct QRState from parameters
    qr = QRState(iteration=qr_iteration, failed=qr_fail, status=qr_status)

    # Gate steps (7, 10, 13) use shared gate function
    if step in (7, 10, 13):
        if not qr_status:
            return {"error": f"--qr-status required for gate step {step}"}
        return format_gate(step, qr)

    info = STEPS.get(step)
    if not info:
        return {"error": f"Invalid step {step}"}

    # Build actions
    actions = list(info.get("actions", []))

    # Add verification checklist for step 4
    if info.get("include_verification"):
        actions.append("")
        actions.append(PLANNING_VERIFICATION)

    # Add plan format for step 5
    if info.get("include_plan_format"):
        plan_format = get_plan_format()
        actions.extend([
            "",
            "Write plan using this format:",
            "",
            plan_format,
        ])

    # Handle planning step 5 in fix mode (main agent fixes plan structure)
    if step == 5 and qr.failed:
        banner = format_state_banner("PLAN-FIX", qr.iteration, "fix")
        fix_actions = [banner, ""] + [
            "FIX MODE: QR-COMPLETENESS found plan structure issues.",
            "",
            "Review the QR findings in your context.",
            "Fix the identified issues in the plan file directly.",
            "",
            "Common issues:",
            "  - Missing Decision Log entries",
            "  - Incomplete Code Intent sections",
            "  - Missing Invisible Knowledge",
            "  - Incomplete milestone specifications",
            "",
            "Use Edit tool to fix the plan file.",
            "After fixing, proceed to QR-Completeness for fresh verification.",
        ]
        # After fix, proceed to step 6 (QR-Completeness) for fresh review
        return {
            "title": f"{info['title']} - Fix Mode",
            "actions": fix_actions,
            "next": f"python3 -m {MODULE_PATH} --step 6 --total-steps {total_steps}",
        }

    # Add QR banner for QR steps
    if info.get("is_qr"):
        qr_name = info.get("qr_name", "QR")
        actions.insert(0, format_qr_banner(qr_name, qr))
        actions.insert(1, "")

    # Generate dispatch block for dispatch steps
    if info.get("is_dispatch"):
        mode_script = get_mode_script_path(info["mode_script"])
        mode_total_steps = info.get("mode_total_steps", 5)
        dispatch_agent = info.get("dispatch_agent", "agent")
        context_vars = info.get("context_vars", {})

        # Add orchestrator constraint before dispatch
        actions.append(format_orchestrator_constraint())
        actions.append("")

        # Build invoke command with QR flags when in fix mode
        invoke_cmd = f"python3 -m {mode_script} --step 1 --total-steps {mode_total_steps}"
        if qr.failed:
            invoke_cmd += f" --qr-fail --qr-iteration {qr.iteration}"

        dispatch_block = format_subagent_dispatch(
            agent=dispatch_agent,
            context_vars=context_vars,
            invoke_cmd=invoke_cmd,
            free_form=False,
            qr_fix_mode=qr.failed,
        )
        actions.append(dispatch_block)
        actions.append("")

        # Add post-dispatch instructions
        post_dispatch = info.get("post_dispatch", [])
        actions.extend(post_dispatch)

        # Add post-QR routing block for QR steps
        post_qr_config = info.get("post_qr_routing")
        if post_qr_config:
            routing_block = format_post_qr_routing(
                self_fix=post_qr_config.get("self_fix", False),
                fix_target=post_qr_config.get("fix_target", "developer"),
            )
            actions.append(routing_block)

    # Determine next step
    next_step = step + 1

    # QR steps (6, 9, 12) use branching (if_pass/if_fail)
    if step in (6, 9, 12):
        base_cmd = f"python3 -m {MODULE_PATH} --step {next_step} --total-steps {total_steps}"
        return {
            "title": info["title"],
            "actions": actions,
            "if_pass": f"{base_cmd} --qr-status pass",
            "if_fail": f"{base_cmd} --qr-status fail",
        }
    else:
        # Non-QR steps use simple next command
        next_cmd = f"python3 -m {MODULE_PATH} --step {next_step} --total-steps {total_steps}"
        return {
            "title": info["title"],
            "actions": actions,
            "next": next_cmd,
        }


def format_output(step: int, total_steps: int,
                  qr_iteration: int, qr_fail: bool, qr_status: str) -> str:
    """Format output for display using XML format."""
    guidance = get_step_guidance(step, total_steps, qr_iteration, qr_fail, qr_status)

    # Gate steps return string directly (already XML formatted)
    if isinstance(guidance, str):
        return guidance

    # Handle error case
    if "error" in guidance:
        return f"Error: {guidance['error']}"

    # Use format_step_output for consistent XML formatting
    return format_step_output(
        script="planner",
        step=step,
        total=total_steps,
        title=guidance["title"],
        actions=guidance["actions"],
        next_command=guidance.get("next"),
        if_pass=guidance.get("if_pass"),
        if_fail=guidance.get("if_fail"),
        is_step_one=(step == 1),
    )


def main():
    parser = argparse.ArgumentParser(
        description="Interactive Sequential Planner (13-step unified workflow)",
        epilog="Steps 1-5: planning | Steps 6-13: review with QR gates",
    )

    parser.add_argument("--step", type=int, required=True)
    parser.add_argument("--total-steps", type=int, required=True)
    add_qr_args(parser)

    args = parser.parse_args()

    if args.step < 1 or args.total_steps < 1:
        print("Error: step and total-steps must be >= 1", file=sys.stderr)
        sys.exit(1)

    if args.total_steps < 13:
        print("Error: workflow requires at least 13 steps", file=sys.stderr)
        sys.exit(1)

    # Gate steps require --qr-status
    if args.step in (7, 10, 13) and not args.qr_status:
        print(f"Error: --qr-status required for gate step {args.step}", file=sys.stderr)
        sys.exit(1)

    print(format_output(args.step, args.total_steps,
                        args.qr_iteration, args.qr_fail, args.qr_status))


if __name__ == "__main__":
    main()
