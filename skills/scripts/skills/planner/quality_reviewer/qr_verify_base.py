"""Base class for QR verify scripts.

Definition locality + INTENT.md compliance:
- INTENT.md requires separate files per phase
- Base class provides shared logic (item loading, CLI invocation, output format)
- Subclasses override phase-specific verification logic

Dynamic step workflow based on item count:
- Formula: total_steps = 1 + (2 * num_items) + 1
- Step 1: CONTEXT (load shared state)
- Steps 2..2N+1: ANALYZE/CONFIRM pairs per item
- Final step: SUMMARY (aggregate results)

This works by:
1. Receive --qr-item a --qr-item b from orchestrator dispatch (argparse action="append")
2. Calculate total steps from item count
3. Route step number to (CONTEXT, ANALYZE, CONFIRM, SUMMARY)
4. ANALYZE: explore codebase, form preliminary conclusion
5. CONFIRM: verify confidence, invoke cli/qr.py to record result
6. SUMMARY: aggregate pass/fail, output single word

Invariants:
- Verify agent mutates only assigned items
- PASS means check succeeded; no finding
- FAIL means check failed; finding explains what
- cli/qr.py handles file locking; script doesn't touch JSON
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from skills.planner.shared.qr.phases import get_phase_config
from skills.planner.shared.qr.utils import load_qr_state, get_qr_item, format_qr_item_for_verification
from skills.planner.shared.resources import get_context_path, render_context_file


# CLI module for atomic QR updates
CLI_MODULE = "skills.planner.cli.qr"


# Plan-phase verifiers judge a PLAN, not an applied implementation (F3).
# A correct plan describes intended changes against the CURRENT working tree:
# nobody `git apply`s its hunks and the tree is intentionally un-migrated.
# Verifying it like implementation code produced false FAILs ("params still
# synchronous", "@@ offsets not git-apply-clean"). Plan-phase checks must judge
# INTENT FIDELITY -- does the diff correctly DESCRIBE the change against the
# current file -- and treat line-number arithmetic as advisory. Byte-exact /
# git-apply-clean checks belong to the exec/impl phase, where diffs are applied.
PLAN_INTENT_FIDELITY_NOTE = [
    "PLAN-PHASE SCOPE (intent fidelity, not applied state):",
    "  - This is a PLAN. The working tree is intentionally NOT migrated yet,",
    "    so do NOT FAIL because the file 'still' shows the pre-change state --",
    "    that is expected. Judge whether the diff correctly DESCRIBES the",
    "    intended change against the CURRENT file content.",
    "  - @@ line numbers are ADVISORY here. NEVER FAIL on offset arithmetic or",
    "    git-apply-cleanliness; that is the exec/impl phase's job.",
    "  - FAIL only when the diff MIS-describes the change: wrong file, wrong",
    "    transform, or context lines that do not exist in the current file.",
    "",
]


class VerifyBase(ABC):
    """Base class for QR verify scripts.

    Subclasses must:
    1. Set PHASE class attribute
    2. Override get_verification_guidance() with phase-specific verification instructions
    """

    PHASE: str = None  # Override in subclass

    def __init__(self):
        if not self.PHASE:
            raise ValueError("Subclass must set PHASE class attribute")
        self.config = get_phase_config(self.PHASE)

    @abstractmethod
    def get_verification_guidance(self, item: dict, state_dir: str) -> list[str]:
        """Return phase-specific verification instructions.

        Override in subclass with specific checks for this phase.

        Args:
            item: QR item dict with id, scope, check, status
            state_dir: Path to state directory

        Returns:
            List of instruction strings for the verification step
        """
        raise NotImplementedError

    def _get_step_type(self, step: int, num_items: int) -> tuple[str, int | None]:
        """Map step number to step type and item index.

        Step 1 is CONTEXT (load shared state).
        Steps 2 through 2N+1 alternate ANALYZE/CONFIRM per item.
        Final step is SUMMARY (aggregate results).

        Pure function: step number and item count determine step type and index.
        """
        if step == 1:
            return ("CONTEXT", None)
        final_step = 2 + (2 * num_items)
        if step == final_step:
            return ("SUMMARY", None)
        # Steps 2..final_step-1 are item steps
        item_offset = step - 2  # 0-indexed from step 2
        item_index = item_offset // 2
        phase = item_offset % 2  # 0=ANALYZE, 1=CONFIRM
        return ("ANALYZE" if phase == 0 else "CONFIRM", item_index)

    def _get_total_steps(self, num_items: int) -> int:
        """Calculate total steps for N items: 1 + (2 * N) + 1."""
        return 2 + (2 * num_items)

    def get_step_guidance(self, step: int, module_path: str, **kwargs) -> dict:
        """Route to appropriate step handler based on step number and item count."""
        # action="append" returns list or None if not provided
        items = kwargs.get("qr_item") or []
        state_dir = kwargs.get("state_dir", "")

        if not items:
            return {
                "title": "Error",
                "actions": ["--qr-item required (repeatable: --qr-item a --qr-item b)"],
                "next": "",
            }
        if not state_dir:
            return {
                "title": "Error",
                "actions": ["--state-dir required"],
                "next": "",
            }

        num_items = len(items)
        total_steps = self._get_total_steps(num_items)
        step_type, item_idx = self._get_step_type(step, num_items)

        if step_type == "CONTEXT":
            return self._step_context(state_dir, module_path, items, total_steps)
        elif step_type == "ANALYZE":
            return self._step_analyze(state_dir, module_path, items, item_idx, total_steps)
        elif step_type == "CONFIRM":
            return self._step_confirm(state_dir, module_path, items, item_idx, total_steps)
        elif step_type == "SUMMARY":
            return self._step_summary(state_dir, module_path, items, total_steps)
        else:
            return {"error": f"Unknown step type for step {step}"}

    def _step_context(self, state_dir: str, module_path: str, item_ids: list[str], total_steps: int) -> dict:
        """Step 1: Load conventions, phase rules, context.json, plan.json. List all items."""
        state_dir_arg = f" --state-dir {state_dir}"
        item_flags = " ".join(f"--qr-item {id}" for id in item_ids)

        context_file = get_context_path(state_dir)
        context_display = render_context_file(context_file) if context_file else ""

        qr_state = load_qr_state(state_dir, self.PHASE)
        if not qr_state:
            return {
                "title": f"QR Verify Step 1/{total_steps}: Context ({self.PHASE})",
                "actions": [f"ERROR: Could not load qr-{self.PHASE}.json from {state_dir}"],
                "next": "",
            }

        # Load all items and display with severity
        items = []
        for item_id in item_ids:
            item = get_qr_item(qr_state, item_id)
            if not item:
                return {
                    "title": f"QR Verify Step 1/{total_steps}: Context ({self.PHASE})",
                    "actions": [f"ERROR: Item {item_id} not found in qr-{self.PHASE}.json"],
                    "next": "",
                }
            items.append(item)

        item_summary = []
        for item in items:
            severity = item.get("severity", "SHOULD")
            item_summary.append(f"  {item['id']} [{severity}]: {item.get('check', '')[:60]}")

        return {
            "title": f"QR Verify Step 1/{total_steps}: Context ({self.PHASE})",
            "actions": [
                f"PHASE: {self.PHASE}",
                f"ITEMS TO VERIFY: {len(items)}",
                "",
                *item_summary,
                "",
                "PLANNING CONTEXT (reference for semantic validation):",
                "",
                context_display,
                "",
                "UNDERSTAND the checks you need to perform.",
                "Note the scope: '*' means macro check, 'file:path:lines' means specific location.",
                "Severity indicates blocking behavior: MUST blocks all iterations, SHOULD blocks 1-4.",
            ],
            "next": f"python3 -m {module_path} --step 2{state_dir_arg} {item_flags}",
        }

    def _step_analyze(self, state_dir: str, module_path: str, item_ids: list[str], item_idx: int, total_steps: int) -> dict:
        """ANALYZE step: Explore codebase if needed, analyze item, form preliminary conclusion."""
        state_dir_arg = f" --state-dir {state_dir}"
        item_flags = " ".join(f"--qr-item {id}" for id in item_ids)
        current_step = 2 + (item_idx * 2)  # ANALYZE is first of the pair

        item_id = item_ids[item_idx]
        qr_state = load_qr_state(state_dir, self.PHASE)
        if not qr_state:
            return {
                "title": f"QR Verify Step {current_step}/{total_steps}: Analyze ({self.PHASE})",
                "actions": [f"ERROR: Could not load qr-{self.PHASE}.json"],
                "next": "",
            }

        item = get_qr_item(qr_state, item_id)
        if not item:
            return {
                "title": f"QR Verify Step {current_step}/{total_steps}: Analyze ({self.PHASE})",
                "actions": [f"ERROR: Item {item_id} not found"],
                "next": "",
            }

        item_display = format_qr_item_for_verification(item)
        severity = item.get("severity", "SHOULD")
        guidance = self.get_verification_guidance(item, state_dir)

        return {
            "title": f"QR Verify Step {current_step}/{total_steps}: Analyze {item_id} ({self.PHASE})",
            "actions": [
                f"ANALYZING: {item_id} (item {item_idx + 1} of {len(item_ids)})",
                f"SEVERITY: {severity}",
                "",
                item_display,
                "",
                "VERIFICATION GUIDANCE:",
                *guidance,
                "",
                "TASK:",
                "1. Read relevant files/sections based on scope",
                "2. Apply the verification check",
                "3. Form preliminary conclusion: PASS or FAIL?",
                "4. If FAIL, note specific evidence",
                "",
                "DO NOT update qr state yet. Proceed to CONFIRM step.",
            ],
            "next": f"python3 -m {module_path} --step {current_step + 1}{state_dir_arg} {item_flags}",
        }

    def _step_confirm(self, state_dir: str, module_path: str, item_ids: list[str], item_idx: int, total_steps: int) -> dict:
        """CONFIRM step: Verify confidence, record result via cli/qr.py."""
        state_dir_arg = f" --state-dir {state_dir}"
        item_flags = " ".join(f"--qr-item {id}" for id in item_ids)
        current_step = 2 + (item_idx * 2) + 1  # CONFIRM is second of the pair

        item_id = item_ids[item_idx]
        qr_state = load_qr_state(state_dir, self.PHASE)
        item = get_qr_item(qr_state, item_id) if qr_state else None
        severity = item.get("severity", "SHOULD") if item else "SHOULD"

        # Determine next step
        next_step = current_step + 1
        if item_idx + 1 < len(item_ids):
            # More items to process
            next_action = f"python3 -m {module_path} --step {next_step}{state_dir_arg} {item_flags}"
        else:
            # This was the last item, proceed to SUMMARY
            next_action = f"python3 -m {module_path} --step {next_step}{state_dir_arg} {item_flags}"

        return {
            "title": f"QR Verify Step {current_step}/{total_steps}: Confirm {item_id} ({self.PHASE})",
            "actions": [
                f"CONFIRMING: {item_id} (item {item_idx + 1} of {len(item_ids)})",
                f"SEVERITY: {severity}",
                "",
                "CONFIDENCE CHECK:",
                "- Are you confident in your conclusion?",
                "- Did you verify against actual code/plan content?",
                "- Is your evidence specific and verifiable?",
                "",
                "RECORD RESULT via CLI:",
                "",
                "If PASS:",
                f"  python3 -m {CLI_MODULE} --state-dir {state_dir} --qr-phase {self.PHASE} \\",
                f"    update-item {item_id} --status PASS",
                "",
                "If FAIL:",
                f"  python3 -m {CLI_MODULE} --state-dir {state_dir} --qr-phase {self.PHASE} \\",
                f"    update-item {item_id} --status FAIL --finding '<one-line explanation>'",
                "",
                "Execute ONE of the above commands, then proceed.",
            ],
            "next": next_action,
        }

    def _step_summary(self, state_dir: str, module_path: str, item_ids: list[str], total_steps: int) -> dict:
        """SUMMARY step: Count results, output single word PASS or FAIL."""
        return {
            "title": f"QR Verify Step {total_steps}/{total_steps}: Summary ({self.PHASE})",
            "actions": [
                f"VERIFICATION COMPLETE: {len(item_ids)} items processed",
                "",
                "=" * 60,
                "FINAL OUTPUT FORMAT - READ THIS CAREFULLY",
                "=" * 60,
                "",
                "After processing all items, output EXACTLY ONE WORD:",
                "",
                "    PASS",
                "",
                "  or",
                "",
                "    FAIL",
                "",
                "RULES:",
                "- Your ENTIRE response after the CLI commands is ONE WORD",
                "- No markdown headers (## or **)",
                "- No 'VERDICT:' prefix",
                "- No explanation or reasoning",
                "- No prose of any kind",
                "- The finding/explanation goes in the --finding flag, NOT in your output",
                "",
                "WRONG outputs (DO NOT DO THIS):",
                "  '## VERDICT: FAIL'",
                "  '**FAIL**: The check failed because...'",
                "  'FAIL: M-002 lists buffer_test.go...'",
                "  'FAIL\\n\\nThe analysis shows...'",
                "",
                "CORRECT outputs (DO THIS):",
                "  'PASS'",
                "  'FAIL'",
                "",
                "If ANY item fails -> output: FAIL",
                "If ALL items pass -> output: PASS",
            ],
            "next": "",
        }
