"""QR workflow constants and routing configuration.

Moved from lib/workflow/constants.py to planner/shared/qr/constants.py.
Extended with routing configuration (moved from qr/utils.py).
"""

QR_ITERATION_LIMIT = 5
QR_ITERATION_DEFAULT = 1

# F5: per-item fix<->verify convergence cap. After this many FAILs on the SAME
# item, the loop must converge or surface one decision instead of re-looping:
#   - MUST item past the cap  -> escalate to a single human-decision gate
#   - SHOULD/COULD past the cap -> auto-accept with rationale, proceed
# Default 2 = two fix attempts per item before forcing resolution.
QR_CONVERGENCE_CAP = 2


def get_convergence_cap() -> int:
    """Return the per-item fix<->verify fail cap (F5)."""
    return QR_CONVERGENCE_CAP

# Routing: (workflow, phase) -> (route_step, module_path, total_steps)
# Updated for 14-step planner (was 11) and 10-step executor (was 9)
QR_ROUTING = {
    ("planner", "plan-design"): (6, "skills.planner.orchestrator.planner", 14),
    ("planner", "plan-code"): (10, "skills.planner.orchestrator.planner", 14),
    ("planner", "plan-docs"): (14, "skills.planner.orchestrator.planner", 14),
    ("executor", "impl-code"): (5, "skills.planner.orchestrator.executor", 10),
    ("executor", "impl-docs"): (9, "skills.planner.orchestrator.executor", 10),
}

# CLI argument defaults - single source of truth
CLI_DEFAULTS = {
    "qr_iteration": 1,
    "qr_status": None,
    "mode": None,
    "state_dir": None,
}


def get_routing_info(workflow: str, phase: str) -> tuple[int, str, int]:
    """Get routing info for a QR workflow/phase combination.

    Returns: (gate_step, module_path, total_steps)
    Raises: ValueError if unknown combination
    """
    key = (workflow, phase)
    if key not in QR_ROUTING:
        raise ValueError(f"Unknown QR routing: workflow={workflow}, phase={phase}")
    return QR_ROUTING[key]


def get_cli_default(arg_name: str):
    """Get default value for CLI argument.

    WHY: kwargs.get("qr_iteration", 1) was repeated in 10+ files.
    Using this function ensures all defaults stay synchronized.
    """
    return CLI_DEFAULTS.get(arg_name)


def get_qa_state_file(phase: str) -> str:
    """Get QA state file for a specific phase."""
    return f"qr-{phase}.json"


def get_blocking_severities(iteration: int) -> frozenset[str]:
    """Return severities that block at given iteration.

    Progressive de-escalation narrows blocking scope as iterations
    increase, accepting lower-severity issues rather than looping
    indefinitely:
        iteration 1-2: MUST + SHOULD + COULD
        iteration 3:   MUST + SHOULD
        iteration 4+:  MUST only

    Threshold rationale per conventions/severity.md:
    - Iterations 1-2 give full coverage (all severities verified).
    - Iteration 3 drops COULD (cosmetic/auto-fixable). Two fix
      attempts is sufficient for low-impact items.
    - Iteration 4 drops SHOULD (structural debt). Only MUST
      (knowledge loss risks) justifies blocking a plan indefinitely.

    Args:
        iteration: QR loop iteration count (1-indexed)

    Returns:
        Frozenset of severity strings that block at this iteration
    """
    if iteration >= 4:
        return frozenset({"MUST"})
    if iteration >= 3:
        return frozenset({"MUST", "SHOULD"})
    return frozenset({"MUST", "SHOULD", "COULD"})


def get_iteration_guidance_message(iteration: int) -> str:
    """Get user-facing message about current iteration state."""
    blocking = get_blocking_severities(iteration)
    # Severity priority order, not alphabetical
    severity_order = ["MUST", "SHOULD", "COULD"]
    levels = ", ".join(s for s in severity_order if s in blocking)
    return f"Iteration {iteration}: blocking on {levels}."
