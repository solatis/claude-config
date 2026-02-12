#!/usr/bin/env python3
"""
Plan Executor - Execute approved plans through delegation.

Ten-step workflow with parallel QR verification:
  1. Execution Planning - analyze plan, build wave list, create state_dir
  2. Implementation - dispatch developers (wave-aware parallel)
  3. Code QR Decompose - generate verification items
  4. Code QR Verify - parallel verification of items
  5. Code QR Gate - route pass/fail
  6. Documentation - TW pass
  7. Doc QR Decompose - generate verification items
  8. Doc QR Verify - parallel verification of items
  9. Doc QR Gate - route pass/fail
  10. Retrospective - present summary

QR Block Pattern (matching planner's 4-step pattern per phase):
  N   work        developer/TW agents     Implementation or documentation
  N+1 decompose   1 QR agent              qr-{phase}.json
  N+2 verify      N QR agents (parallel)  Each: PASS or FAIL
  N+3 route       0 agents (orchestrator) Loop to N or proceed to N+4
"""

import argparse
import json
import sys
import tempfile
from pathlib import Path

from skills.lib.workflow.types import AgentRole
from skills.lib.workflow.prompts import subagent_dispatch, template_dispatch
from skills.lib.workflow.prompts.step import format_step
from skills.planner.shared.qr.cli import add_qr_args
from skills.planner.shared.qr.types import QRState, QRStatus, LoopState
from skills.planner.shared.qr.utils import (
    qr_file_exists,
    increment_qr_iteration,
    load_qr_state,
    query_items,
    by_status,
    by_blocking_severity,
)
from skills.planner.shared.qr.phases import get_phase_config
from skills.planner.shared.gates import build_gate_output
from skills.planner.shared.resources import get_mode_script_path
from skills.planner.shared.builders import (
    THINKING_EFFICIENCY,
    format_forbidden,
)
from skills.planner.shared.constraints import (
    ORCHESTRATOR_CONSTRAINT,
    format_state_banner,
)


# Module path for -m invocation
MODULE_PATH = "skills.planner.orchestrator.executor"


def _format_qr_item_flags(item_ids: list[str]) -> str:
    """Format item IDs as repeated --qr-item flags."""
    return " ".join(f"--qr-item {id}" for id in item_ids)


# =============================================================================
# Step 1: Execution Planning
# =============================================================================

def format_step_1(state_dir: str, reconciliation_check: bool) -> str:
    """Create state_dir, analyze plan, build wave list."""
    actions = [
        THINKING_EFFICIENCY,
        "",
        "Plan file: $PLAN_FILE (substitute from context)",
        "",
        "ANALYZE plan:",
        "  - Count milestones and parse dependency diagram",
        "  - Group milestones into WAVES for execution",
        "  - Set up TodoWrite tracking",
        "",
        "WAVE ANALYSIS:",
        "  Parse the plan's 'Milestone Dependencies' diagram.",
        "  Group into waves: milestones at same depth = one wave.",
        "",
        "  Example diagram:",
        "    M0 (foundation)",
        "     |",
        "     +---> M1 (auth)     \\",
        "     |                    } Wave 2 (parallel)",
        "     +---> M2 (users)    /",
        "     |",
        "     +---> M3 (posts) ----> M4 (feed)",
        "            Wave 3          Wave 4",
        "",
        "  Output format:",
        "    Wave 1: [0]       (foundation, sequential)",
        "    Wave 2: [1, 2]    (parallel)",
        "    Wave 3: [3]       (sequential)",
        "    Wave 4: [4]       (sequential)",
        "",
        "STATE SETUP:",
        f"  State directory created: {state_dir}",
        f"  Write plan context to: {state_dir}/plan.json",
        "",
        "  After analyzing the plan, use the Write tool to create plan.json:",
        "  {",
        '    "schema_version": 2,',
        '    "plan_file": "<path to plan file>",',
        '    "milestones": [',
        '      {"id": "M-001", "name": "...", "acceptance_criteria": ["..."], "files": ["..."]}',
        "    ],",
        '    "waves": [[0], [1, 2], [3]]',
        "  }",
        "",
        "WORKFLOW:",
        "  This step is ANALYSIS + STATE SETUP. Do NOT delegate yet.",
        "  Record wave groupings for step 2 (Implementation).",
    ]

    if reconciliation_check:
        actions.extend([
            "",
            "RECONCILIATION CHECK REQUESTED:",
            "  Before implementing, verify which milestones are already satisfied.",
            "  For each milestone, check if acceptance criteria are met in current code.",
            "  Mark satisfied milestones as complete; execute only remaining ones.",
        ])

    body = "\n".join(actions)
    next_cmd = f"python3 -m {MODULE_PATH} --step 2 --state-dir {state_dir}"

    return format_step(body, next_cmd, title="Execution Planning")


# =============================================================================
# Step 2: Implementation
# =============================================================================

def format_step_2(qr: QRState, state_dir: str) -> str:
    """Wave-aware implementation dispatch."""
    if qr.state == LoopState.RETRY:
        title = "Implementation - Fix Mode"
        actions = [
            format_state_banner("IMPLEMENTATION FIX", qr.iteration, "fix"),
            "",
            "FIX MODE: Code QR found issues.",
            "",
            ORCHESTRATOR_CONSTRAINT,
            "",
        ]

        mode_script = get_mode_script_path("developer/exec_implement.py")
        invoke_cmd = f"python3 -m {mode_script} --step 1 --state-dir {state_dir}"

        actions.append(subagent_dispatch(
            agent_type="developer",
            command=invoke_cmd,
        ))
        actions.append("")
        actions.append("Developer reads QR report and fixes issues in <milestone> blocks.")
        actions.append("After developer completes, re-run Code QR for fresh verification.")
    else:
        title = "Implementation"
        actions = [
            "Execute ALL milestones using wave-aware parallel dispatch.",
            "",
            "WAVE-AWARE EXECUTION:",
            "  - Milestones within same wave: dispatch in PARALLEL",
            "    (Multiple Task calls in single response)",
            "  - Waves execute SEQUENTIALLY",
            "    (Wait for wave N to complete before starting wave N+1)",
            "",
            "Use waves identified in step 1.",
            "",
            ORCHESTRATOR_CONSTRAINT,
            "",
            "FOR EACH WAVE:",
            "  1. Dispatch developer agents for ALL milestones in wave:",
            "     Task(developer): Milestone N",
            "     Task(developer): Milestone M  (if parallel)",
            "",
            "  2. Each prompt must include:",
            "     - Plan file: $PLAN_FILE",
            "     - Milestone: [number and name]",
            "     - Files: [exact paths to create/modify]",
            "     - Acceptance criteria: [from plan]",
            "",
            "  3. Wait for ALL agents in wave to complete",
            "",
            "  4. Run tests: pytest / tsc / go test -race",
            "     Pass criteria: 100% tests pass, zero warnings",
            "",
            "  5. Proceed to next wave (repeat 1-4)",
            "",
            "After ALL waves complete, proceed to Code QR.",
            "",
            "ERROR HANDLING (you NEVER fix code yourself):",
            "  Clear problem + solution: Task(developer) immediately",
            "  Difficult/unclear problem: Task(debugger) to diagnose first",
            "  Uncertain how to proceed: AskUserQuestion with options",
        ]

    body = "\n".join(actions)
    next_cmd = f"python3 -m {MODULE_PATH} --step 3 --state-dir {state_dir}"

    return format_step(body, next_cmd, title=title)


# =============================================================================
# Steps 3, 7: QR Decompose
# =============================================================================

def format_qr_decompose(step: int, phase: str, state_dir: str, qr: QRState) -> str:
    """Dispatch QR decomposition agent for a phase."""
    config = get_phase_config(phase)
    decompose_script = config["decompose_script"]

    title_map = {3: "Code QR Decompose", 7: "Doc QR Decompose"}
    title = title_map.get(step, f"QR Decompose ({phase})")

    # Skip if already decomposed
    if qr_file_exists(state_dir, phase):
        next_step = step + 1
        body = "\n".join([
            f"QR items for {phase} already defined.",
            "Proceeding to verification of existing items.",
        ])
        next_cmd = f"python3 -m {MODULE_PATH} --step {next_step} --state-dir {state_dir}"
        return format_step(body, next_cmd, title=f"{title} - Skipped")

    actions = [
        format_state_banner(f"QR-{phase.upper()}-DECOMPOSE", qr.iteration, "decompose"),
        "",
        ORCHESTRATOR_CONSTRAINT,
        "",
    ]

    invoke_cmd = f"python3 -m {decompose_script} --step 1 --state-dir {state_dir}"
    actions.append(subagent_dispatch(
        agent_type="quality-reviewer",
        command=invoke_cmd,
    ))
    actions.append("")
    actions.append(f"Expected output: qr-{phase}.json written to STATE_DIR")
    actions.append("Orchestrator generates verification dispatch from this file.")

    body = "\n".join(actions)
    next_step = step + 1
    next_cmd = f"python3 -m {MODULE_PATH} --step {next_step} --state-dir {state_dir}"

    return format_step(body, next_cmd, title=title)


# =============================================================================
# Steps 4, 8: QR Verify (parallel)
# =============================================================================

def format_qr_verify(step: int, phase: str, state_dir: str, qr: QRState) -> str:
    """Dispatch parallel QR verification agents."""
    config = get_phase_config(phase)
    verify_script = config["verify_script"]

    title_map = {4: "Code QR Verify", 8: "Doc QR Verify"}
    title = title_map.get(step, f"QR Verify ({phase})")

    qr_state = load_qr_state(state_dir, phase)
    if not qr_state or "items" not in qr_state:
        decompose_step = step - 1
        body = f"Error: qr-{phase}.json not found or malformed. Routing back to decompose step."
        retry_cmd = f"python3 -m {MODULE_PATH} --step {decompose_step} --state-dir {state_dir}"
        return format_step(body, retry_cmd, title=title)

    iteration = qr_state.get("iteration", 1)
    if qr.state == LoopState.RETRY:
        new_iter = increment_qr_iteration(state_dir, phase)
        if new_iter is not None:
            iteration = new_iter

    # Dispatch only items at blocking severity for current iteration
    items = query_items(qr_state, by_status("TODO", "FAIL"), by_blocking_severity(iteration))
    if not items:
        next_step = step + 1
        body = "All items already verified. Proceeding with pass."
        if_pass = f"python3 -m {MODULE_PATH} --step {next_step} --state-dir {state_dir} --qr-status pass"
        return format_step(body, title=title, if_pass=if_pass, if_fail=if_pass)

    # Group items by group_id for batch verification
    groups = {}
    for item in items:
        gid = item.get("group_id") or item["id"]
        groups.setdefault(gid, []).append(item)

    targets = [
        {
            "group_id": gid,
            "item_ids": ",".join(i["id"] for i in group_items),
            "qr_item_flags": _format_qr_item_flags([i["id"] for i in group_items]),
            "item_count": str(len(group_items)),
            "checks_summary": "; ".join(i.get("check", "")[:40] for i in group_items[:3]),
        }
        for gid, group_items in groups.items()
    ]

    tmpl = f"""Verify QR group: $group_id ($item_count items)
Items: $item_ids
Checks: $checks_summary

Start: python3 -m {verify_script} --step 1 --state-dir {state_dir} $qr_item_flags"""

    command = f"python3 -m {verify_script} --step 1 --state-dir {state_dir} $qr_item_flags"

    dispatch_text = template_dispatch(
        agent_type="quality-reviewer",
        template=tmpl,
        targets=targets,
        command=command,
        instruction=f"Verify {len(groups)} groups ({len(items)} items) in parallel.",
    )

    actions = [
        ORCHESTRATOR_CONSTRAINT,
        "",
        "=== PHASE 1: DISPATCH (delegate to sub-agents) ===",
        "",
        f"VERIFY: {len(items)} items",
        "",
        dispatch_text,
        "",
        "=== PHASE 2: AGGREGATE (your action after all agents return) ===",
        "",
        f"After ALL {len(groups)} agents return, tally results mechanically:",
        f"  ALL agents returned PASS  ->  invoke next step with --qr-status pass",
        f"  ANY agent returned FAIL   ->  invoke next step with --qr-status fail",
        "",
        format_forbidden(
            "Interpreting results beyond PASS/FAIL tallying",
            "Claiming 'diminishing returns' or 'comprehensive enough'",
            "Skipping the next step command",
            "Proceeding to a later step without QR PASS",
        ),
    ]

    body = "\n".join(actions)
    next_step = step + 1
    base_cmd = f"python3 -m {MODULE_PATH} --step {next_step} --state-dir {state_dir}"

    return format_step(body, title=title,
                       if_pass=f"{base_cmd} --qr-status pass",
                       if_fail=f"{base_cmd} --qr-status fail")


# =============================================================================
# Steps 5, 9: QR Gate (route pass/fail)
# =============================================================================

def format_qr_gate(step: int, phase: str, state_dir: str, qr: QRState) -> str:
    """Route based on QR results: pass → next phase, fail → fix loop."""
    gate_config = {
        5: ("Code QR", 2, 6, "Code quality verified. Proceed to documentation.", AgentRole.DEVELOPER),
        9: ("Doc QR", 6, 10, "Documentation verified. Proceed to retrospective.", AgentRole.TECHNICAL_WRITER),
    }

    qr_name, work_step, pass_step, pass_message, fix_target = gate_config[step]

    result = build_gate_output(
        module_path=MODULE_PATH,
        script_name="executor",
        qr_name=qr_name,
        qr=qr,
        step=step,
        work_step=work_step,
        pass_step=pass_step,
        pass_message=pass_message,
        fix_target=fix_target,
        state_dir=state_dir,
    )

    return result.output


# =============================================================================
# Step 6: Documentation
# =============================================================================

def format_step_6(qr: QRState, state_dir: str) -> str:
    """Dispatch technical writer for documentation."""
    mode_script = get_mode_script_path("technical_writer/exec_docs.py")

    if qr.state == LoopState.RETRY:
        title = "Documentation - Fix Mode"
        actions = [
            format_state_banner("DOCUMENTATION FIX", qr.iteration, "fix"),
            "",
            "FIX MODE: Doc QR found issues.",
            "",
            ORCHESTRATOR_CONSTRAINT,
            "",
        ]

        invoke_cmd = f"python3 -m {mode_script} --step 1 --state-dir {state_dir}"
        actions.append(subagent_dispatch(
            agent_type="technical-writer",
            command=invoke_cmd,
        ))
    else:
        title = "Documentation"
        actions = [
            ORCHESTRATOR_CONSTRAINT,
            "",
        ]

        invoke_cmd = f"python3 -m {mode_script} --step 1 --state-dir {state_dir}"
        actions.append(subagent_dispatch(
            agent_type="technical-writer",
            command=invoke_cmd,
        ))

    body = "\n".join(actions)
    next_cmd = f"python3 -m {MODULE_PATH} --step 7 --state-dir {state_dir}"

    return format_step(body, next_cmd, title=title)


# =============================================================================
# Step 10: Retrospective
# =============================================================================

def format_step_10() -> str:
    """Present execution retrospective."""
    actions = [
        "PRESENT retrospective to user (do not write to file):",
        "",
        "EXECUTION RETROSPECTIVE",
        "=======================",
        "Plan: [path]",
        "Status: COMPLETED | BLOCKED | ABORTED",
        "",
        "Milestone Outcomes: | Milestone | Status | Notes |",
        "Reconciliation Summary: [if run]",
        "Plan Accuracy Issues: [if any]",
        "Deviations from Plan: [if any]",
        "Quality Review Summary: [counts by category]",
        "Feedback for Future Plans: [actionable suggestions]",
    ]

    body = "\n".join(actions)
    return format_step(body, title="Retrospective")


# =============================================================================
# Step Dispatch
# =============================================================================

def format_output(step: int, state_dir: str,
                  qr_iteration: int, qr_fail: bool, qr_status: str,
                  reconciliation_check: bool) -> str:
    """Format output for display."""
    from skills.planner.shared.constants import EXECUTOR_TOTAL_STEPS

    # Construct QRState
    status = QRStatus(qr_status) if qr_status else None
    state = LoopState.RETRY if qr_fail else LoopState.INITIAL
    qr = QRState(iteration=qr_iteration, state=state, status=status)

    # Derive fix mode from QR state files (like planner does)
    phase_for_step = {2: "impl-code", 6: "impl-docs"}
    if step in phase_for_step and state_dir and not qr_fail:
        from skills.planner.shared.qr.utils import has_qr_failures
        phase = phase_for_step[step]
        if has_qr_failures(state_dir, phase):
            qr = QRState(iteration=qr_iteration, state=LoopState.RETRY, status=status)

    if step == 1:
        return format_step_1(state_dir, reconciliation_check)
    elif step == 2:
        return format_step_2(qr, state_dir)
    elif step == 3:
        return format_qr_decompose(3, "impl-code", state_dir, qr)
    elif step == 4:
        return format_qr_verify(4, "impl-code", state_dir, qr)
    elif step == 5:
        if not qr_status:
            return "Error: --qr-status required for step 5 (Code QR Gate)"
        return format_qr_gate(5, "impl-code", state_dir, qr)
    elif step == 6:
        return format_step_6(qr, state_dir)
    elif step == 7:
        return format_qr_decompose(7, "impl-docs", state_dir, qr)
    elif step == 8:
        return format_qr_verify(8, "impl-docs", state_dir, qr)
    elif step == 9:
        if not qr_status:
            return "Error: --qr-status required for step 9 (Doc QR Gate)"
        return format_qr_gate(9, "impl-docs", state_dir, qr)
    elif step == 10:
        return format_step_10()
    else:
        return f"Error: invalid step {step} (valid: 1-10)"


def main():
    parser = argparse.ArgumentParser(
        description="Plan Executor - Execute approved plans (10-step workflow)",
        epilog="Steps: plan -> implement -> code QR (decompose/verify/gate) -> docs -> doc QR (decompose/verify/gate) -> retrospective",
    )

    parser.add_argument("--step", type=int, required=True)
    parser.add_argument("--state-dir", type=str, default=None,
                        help="State directory path (created in step 1)")
    add_qr_args(parser)
    parser.add_argument("--qr-iteration", type=int, default=1)
    parser.add_argument("--qr-fail", action="store_true")
    parser.add_argument("--reconciliation-check", action="store_true")

    args = parser.parse_args()

    if args.step < 1 or args.step > 10:
        sys.exit("Error: step must be 1-10")

    # Create state_dir for step 1 if not provided
    state_dir = args.state_dir
    if args.step == 1 and not state_dir:
        state_dir = tempfile.mkdtemp(prefix="executor-")
        # Write minimal plan skeleton
        plan_path = Path(state_dir) / "plan.json"
        plan_path.write_text(json.dumps({
            "schema_version": 2,
            "overview": {"problem": "", "approach": ""},
            "planning_context": {
                "decisions": [],
                "rejected_alternatives": [],
                "constraints": [],
                "risks": [],
            },
            "invisible_knowledge": {
                "system": "",
                "invariants": [],
                "tradeoffs": [],
            },
            "milestones": [],
            "waves": [],
        }, indent=2))

    # Validate state_dir for steps 2+
    if args.step > 1 and not state_dir:
        sys.exit(f"Error: --state-dir required for step {args.step}")

    print(format_output(args.step, state_dir,
                        args.qr_iteration, args.qr_fail, args.qr_status,
                        args.reconciliation_check))


if __name__ == "__main__":
    main()
