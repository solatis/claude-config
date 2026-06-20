"""Centralized routing logic for work phases.

Definition locality: router pattern logic lives in ONE place.
5 router scripts become thin wrappers that call route_work_phase().

This works by:
1. WORK_PHASES registry defines all work phase routing
2. detect_qr_state() checks for QR failures
3. route_work_phase() returns dispatch target
4. Router scripts call this function instead of duplicating logic

Invariants:
- Each work phase has exactly one entry in WORK_PHASES
- execute/fix scripts are valid Python module paths
- has_failures=True -> dispatch to qr_fix script
- has_failures=False -> dispatch to execute script
"""

from __future__ import annotations

from .qr.utils import (
    load_qr_state,
    query_items,
    by_status,
    by_blocking_severity,
    classify_item_convergence,
)


# Work phase routing registry - ALL work phases in ONE place
#
# Keys: phase key used by router scripts
# Values: dict with:
#   execute: Python module for first-time execution
#   qr_fix: Python module for post-QR fix workflow
#   qr_phase: QR phase name for state detection

WORK_PHASES: dict[str, dict] = {
    "plan-design": {
        "execute": "skills.planner.architect.plan_design_execute",
        "qr_fix": "skills.planner.architect.plan_design_qr_fix",
        "qr_phase": "plan-design",
    },
    "plan-code": {
        "execute": "skills.planner.developer.plan_code_execute",
        "qr_fix": "skills.planner.developer.plan_code_qr_fix",
        "qr_phase": "plan-code",
    },
    "plan-docs": {
        "execute": "skills.planner.technical_writer.plan_docs_execute",
        "qr_fix": "skills.planner.technical_writer.plan_docs_qr_fix",
        "qr_phase": "plan-docs",
    },
    "impl-code": {
        "execute": "skills.planner.developer.exec_implement_execute",
        "qr_fix": "skills.planner.developer.exec_implement_qr_fix",
        "qr_phase": "impl-code",
    },
    "impl-docs": {
        "execute": "skills.planner.technical_writer.exec_docs_execute",
        "qr_fix": "skills.planner.technical_writer.exec_docs_qr_fix",
        "qr_phase": "impl-docs",
    },
}


def detect_qr_state(state_dir: str, phase: str) -> tuple[bool, list[dict]]:
    """Detect QR state for routing decision.

    Severity-aware: only FAIL items at blocking severity for the current
    iteration count as failures. A phase with only below-threshold FAIL
    items routes to execute (not fix).

    Args:
        state_dir: Path to state directory
        phase: QR phase name (e.g., "plan-design")

    Returns:
        (has_failures, failed_items) where:
        - has_failures: True if blocking FAIL items exist
        - failed_items: List of blocking failed item dicts (empty if none)
    """
    qr_state = load_qr_state(state_dir, phase)
    if not qr_state:
        return (False, [])
    iteration = qr_state.get("iteration", 1)
    blocking_failures = query_items(qr_state, by_status("FAIL"), by_blocking_severity(iteration))
    # F5: items that converged out of the loop (already accepted, or SHOULD/COULD
    # past the per-item cap) no longer route to fix mode -- otherwise one stubborn
    # item loops forever. MUST items past the cap still block (the gate escalates).
    blocking_failures = [
        it for it in blocking_failures
        if classify_item_convergence(it) not in ("accepted", "auto_accept")
    ]
    return (len(blocking_failures) > 0, blocking_failures)


def route_work_phase(state_dir: str, phase_key: str) -> dict:
    """Determine dispatch target and build dispatch output.

    Centralized routing logic - router scripts call this function
    instead of duplicating the detect/route pattern.

    This works by:
    1. Look up phase config from WORK_PHASES registry
    2. detect_qr_state() checks for qr-{phase}.json and FAIL items
    3. has_failures=True -> dispatch to qr_fix script
    4. has_failures=False -> dispatch to execute script

    Args:
        state_dir: Path to state directory
        phase_key: Work phase key (e.g., "plan-design", "impl-code")

    Returns:
        Dict with:
        - target_module: Python module path to dispatch to
        - has_failures: Whether QR failures exist
        - failed_count: Number of failed items (0 if none)
        - qr_phase: QR phase name for reference

    Raises:
        ValueError: If phase_key is unknown
    """
    if phase_key not in WORK_PHASES:
        valid = ", ".join(sorted(WORK_PHASES.keys()))
        raise ValueError(f"Unknown work phase: {phase_key}. Valid phases: {valid}")

    config = WORK_PHASES[phase_key]
    has_failures, failed_items = detect_qr_state(state_dir, config["qr_phase"])

    target = config["qr_fix"] if has_failures else config["execute"]

    return {
        "target_module": target,
        "has_failures": has_failures,
        "failed_count": len(failed_items),
        "qr_phase": config["qr_phase"],
    }


def get_work_phase_config(phase_key: str) -> dict:
    """Get configuration for a work phase.

    Args:
        phase_key: Work phase key

    Returns:
        Phase configuration dict

    Raises:
        ValueError: If phase_key is unknown
    """
    if phase_key not in WORK_PHASES:
        valid = ", ".join(sorted(WORK_PHASES.keys()))
        raise ValueError(f"Unknown work phase: {phase_key}. Valid phases: {valid}")
    return WORK_PHASES[phase_key]


def get_all_work_phases() -> list[str]:
    """Return list of all work phase keys."""
    return list(WORK_PHASES.keys())
