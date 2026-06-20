"""Unified gate output builder for planner and executor workflows.

Single implementation eliminates ~150 lines of duplicated gate logic.
Both planner.py and executor.py call this with their MODULE_PATH.
"""

from dataclasses import dataclass

from skills.lib.workflow.prompts.step import format_step
from skills.planner.shared.builders import (
    format_gate_result,
    format_forbidden,
    PEDANTIC_ENFORCEMENT,
)
from skills.planner.shared.qr.types import QRState, AgentRole


@dataclass
class GateResult:
    """Return type for build_gate_output.

    Why dataclass over plain str: callers distinguish terminal passes
    (workflow done, run translate) from non-terminal passes (proceed to
    next phase). terminal_pass carries pass_step=None without requiring
    callers to re-derive it.
    """
    output: str
    terminal_pass: bool


def _build_escalation_gate(
    module_path: str,
    qr_name: str,
    parts: list,
    escalations: list,
    work_step: int,
    pass_step: int | None,
    fix_target,
    state_dir: str,
    phase: str | None) -> GateResult:
    """F5: render a single human-decision gate for MUST items past the cap.

    The orchestrator has fixed the same MUST item `cap` times without it
    passing. Rather than loop again, present the operator with exactly two
    resolutions: keep fixing, or override-accept with a recorded rationale.
    """
    parts.append("LOOP CONVERGENCE GUARD (F5): a MUST item has failed the fix")
    parts.append("cycle past the per-item cap. Do NOT re-loop silently.")
    parts.append("")
    parts.append("Items requiring a decision:")
    for it in escalations:
        parts.append(
            f"  - {it.get('id', '?')} [{it.get('severity', 'MUST')}], "
            f"failed {it.get('fail_count', 0)}x: {it.get('finding') or it.get('check', '')}"
        )
    parts.append("")
    parts.append("Surface this to the user via AskUserQuestion with two options:")
    parts.append("  1. KEEP FIXING -- try another fix iteration on these items.")
    parts.append("  2. OVERRIDE-ACCEPT -- accept with a recorded rationale and proceed.")
    parts.append("")
    keep_cmd = f"python3 -m {module_path} --step {work_step} --state-dir {state_dir}"
    proceed_cmd = (
        f"python3 -m {module_path} --step {pass_step} --state-dir {state_dir}"
        if pass_step is not None else ""
    )
    parts.append("If KEEP FIXING:")
    parts.append(f"  {keep_cmd}")
    parts.append("")
    parts.append("If OVERRIDE-ACCEPT (record the rationale on each item first):")
    phase_arg = phase or "<phase>"
    for it in escalations:
        parts.append(
            f"  python3 -m skills.planner.cli.qr --state-dir {state_dir} "
            f"--qr-phase {phase_arg} accept-item {it.get('id', '?')} "
            "--reason '<why accepting>'"
        )
    parts.append(f"  then: {proceed_cmd or '(terminal -- workflow complete)'}")

    body = "\n".join(parts)
    title = f"{qr_name} Gate - Human Decision Required"
    # Non-terminal: a human chooses the next command; no deterministic next.
    return GateResult(output=format_step(body, title=title), terminal_pass=False)


def build_gate_output(
    module_path: str,
    script_name: str,
    qr_name: str,
    qr: QRState,
    step: int,
    work_step: int,
    pass_step: int | None,
    pass_message: str,
    fix_target: AgentRole | None,
    state_dir: str,
    escalations: list | None = None,
    phase: str | None = None) -> GateResult:
    """Build complete gate step output for QR gates.

    Gates route to either:
    - pass_step: QR passed, proceed to next workflow phase
    - work_step: QR failed, loop back to fix issues

    F5: when `escalations` is non-empty and QR did not pass, a MUST item has
    failed past the per-item convergence cap. Instead of silently re-looping,
    the gate surfaces ONE explicit human decision.
    """
    parts = []
    parts.append(format_gate_result(passed=qr.passed))
    parts.append("")

    if not qr.passed and escalations:
        return _build_escalation_gate(
            module_path, qr_name, parts, escalations,
            work_step, pass_step, fix_target, state_dir, phase,
        )

    if qr.passed:
        parts.append(pass_message)
        parts.append("")
        parts.append(format_forbidden(
            "Asking the user whether to proceed - the workflow is deterministic",
            "Offering alternatives to the next step - all steps are mandatory",
            "Interpreting 'proceed' as optional - EXECUTE immediately",
        ))
    else:
        parts.append(PEDANTIC_ENFORCEMENT)
        parts.append("")
        target_name = fix_target.value if fix_target else "developer"
        parts.append(
            f"NEXT ACTION:\n"
            f"  Invoke the next step command.\n"
            f"  The next step will dispatch {target_name} with fix guidance."
        )
        parts.append("")
        parts.append(format_forbidden(
            "Fixing issues directly from this gate step",
            "Spawning agents directly from this gate step",
            "Using Edit/Write tools yourself",
            "Proceeding without invoking the next step",
            "Interpreting 'minor issues' as skippable",
            "Claiming 'diminishing returns' or 'comprehensive enough'",
            "Proceeding to next phase without QR PASS",
        ))

    body = "\n".join(parts)
    title = f"{qr_name} Gate"
    terminal_pass = qr.passed and pass_step is None

    if terminal_pass:
        return GateResult(output=format_step(body, title=title), terminal_pass=True)

    if qr.passed:
        next_cmd = f"python3 -m {module_path} --step {pass_step}"
        if state_dir:
            next_cmd += f" --state-dir {state_dir}"
    else:
        next_cmd = f"python3 -m {module_path} --step {work_step} --state-dir {state_dir}"

    return GateResult(
        output=format_step(body, next_cmd, title=title),
        terminal_pass=False,
    )
