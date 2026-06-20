"""Shared fix-mode prompt blocks (F2).

WHY: QR fix mode used to say "fix these findings", so the fixer patched
ONLY the QR-named instances. The next verify pass then surfaced sibling
instances of the SAME class (temporal comments, fragmented requirements,
mis-scoped comments, off-by-N hunks) -- 3+ fix<->verify iterations per class.

These blocks reframe a fix pass as a whole-CLASS sweep with a self-check
gate, so a class clears in one iteration. Used by all *_qr_fix.py scripts
(plan + exec twins), hence shared.
"""


# Injected into fix step 1: reframe findings as class examples.
CLASS_SWEEP_DIRECTIVE = (
    "WHOLE-CLASS FIX (read first):\n"
    "  The QR findings below are EXAMPLES OF A CLASS, not an exhaustive list.\n"
    "  For each finding, identify its defect CLASS (e.g. temporal-contaminated\n"
    "  comment, comma-fragmented requirement, mis-scoped comment, off-by-N hunk),\n"
    "  then sweep the ENTIRE artifact for every other instance of that class --\n"
    "  including instances QR did not name -- and fix them all in this pass.\n"
    "  Leaving a sibling instance only sends it back on the next verify cycle.\n"
    "\n"
    "  Scope discipline: fix all instances of the FLAGGED classes; do not\n"
    "  refactor unrelated, passing content."
)


def temporal_scan_gate(state_dir: str) -> str:
    """Step-3 self-check gate text: the deterministic temporal scan must pass.

    The fixer MUST run `temporal-scan` and reach ZERO hits before reporting
    PASS. This is the deterministic backstop that closes the temporal class in
    one iteration instead of relying on the fixer's self-judgement (F2).
    """
    return (
        "TEMPORAL SELF-CHECK GATE (mandatory, deterministic):\n"
        "  Run the scanner and drive it to ZERO hits:\n"
        f"    python3 -m skills.planner.cli.plan --state-dir {state_dir} temporal-scan\n"
        "  Each <hit> names a field, line, class, and signal. Fix every hit --\n"
        "  they are instances of the temporal-contamination class you must clear\n"
        "  entirely. Re-run until the scan reports PASS (exit 0).\n"
        "  You MUST NOT report PASS while the scan still reports any hit."
    )
