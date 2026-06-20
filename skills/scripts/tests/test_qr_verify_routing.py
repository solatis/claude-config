"""Unit tests for QR verify step routing logic.

Tests the dynamic step calculation: total_steps = 1 + (2 * num_items) + 1
Step 1 is CONTEXT, steps 2..2N+1 alternate ANALYZE/CONFIRM, final step is SUMMARY.
"""

import pytest


def get_step_type(step: int, num_items: int) -> tuple[str, int | None]:
    """Standalone copy of _get_step_type for testing without VerifyBase."""
    if step == 1:
        return ("CONTEXT", None)
    final_step = 2 + (2 * num_items)
    if step == final_step:
        return ("SUMMARY", None)
    item_offset = step - 2
    item_index = item_offset // 2
    phase = item_offset % 2
    return ("ANALYZE" if phase == 0 else "CONFIRM", item_index)


def get_total_steps(num_items: int) -> int:
    """Calculate total steps for N items: 1 + (2 * N) + 1."""
    return 2 + (2 * num_items)


class TestStepRouting:
    """Test step routing for various item counts."""

    def test_step_routing_1_item(self):
        """Verify step routing for single item."""
        assert get_step_type(1, 1) == ("CONTEXT", None)
        assert get_step_type(2, 1) == ("ANALYZE", 0)
        assert get_step_type(3, 1) == ("CONFIRM", 0)
        assert get_step_type(4, 1) == ("SUMMARY", None)
        assert get_total_steps(1) == 4

    def test_step_routing_2_items(self):
        """Verify step routing for 2 items."""
        assert get_step_type(1, 2) == ("CONTEXT", None)
        assert get_step_type(2, 2) == ("ANALYZE", 0)
        assert get_step_type(3, 2) == ("CONFIRM", 0)
        assert get_step_type(4, 2) == ("ANALYZE", 1)
        assert get_step_type(5, 2) == ("CONFIRM", 1)
        assert get_step_type(6, 2) == ("SUMMARY", None)
        assert get_total_steps(2) == 6

    def test_step_routing_3_items(self):
        """Verify step routing for 3 items produces correct sequence."""
        assert get_step_type(1, 3) == ("CONTEXT", None)
        assert get_step_type(2, 3) == ("ANALYZE", 0)
        assert get_step_type(3, 3) == ("CONFIRM", 0)
        assert get_step_type(4, 3) == ("ANALYZE", 1)
        assert get_step_type(5, 3) == ("CONFIRM", 1)
        assert get_step_type(6, 3) == ("ANALYZE", 2)
        assert get_step_type(7, 3) == ("CONFIRM", 2)
        assert get_step_type(8, 3) == ("SUMMARY", None)
        assert get_total_steps(3) == 8

    def test_step_routing_5_items(self):
        """Verify step routing for 5 items."""
        assert get_step_type(1, 5) == ("CONTEXT", None)
        # Items 0-4
        for i in range(5):
            analyze_step = 2 + (i * 2)
            confirm_step = 3 + (i * 2)
            assert get_step_type(analyze_step, 5) == ("ANALYZE", i)
            assert get_step_type(confirm_step, 5) == ("CONFIRM", i)
        assert get_step_type(12, 5) == ("SUMMARY", None)
        assert get_total_steps(5) == 12

    def test_total_steps_formula(self):
        """Verify formula: total_steps = 1 + (2 * num_items) + 1 = 2 + 2*N."""
        for n in range(1, 11):
            expected = 2 + (2 * n)
            assert get_total_steps(n) == expected, f"Failed for n={n}"


class TestStepTypeInvariants:
    """Test invariants of step routing."""

    def test_step_1_always_context(self):
        """Step 1 is always CONTEXT regardless of item count."""
        for n in range(1, 20):
            assert get_step_type(1, n) == ("CONTEXT", None)

    def test_final_step_always_summary(self):
        """Final step is always SUMMARY."""
        for n in range(1, 20):
            final = get_total_steps(n)
            assert get_step_type(final, n) == ("SUMMARY", None)

    def test_analyze_before_confirm(self):
        """For each item, ANALYZE comes before CONFIRM."""
        for n in range(1, 10):
            for item_idx in range(n):
                analyze_step = 2 + (item_idx * 2)
                confirm_step = 3 + (item_idx * 2)
                assert get_step_type(analyze_step, n) == ("ANALYZE", item_idx)
                assert get_step_type(confirm_step, n) == ("CONFIRM", item_idx)

    def test_item_indices_sequential(self):
        """Item indices are sequential from 0 to N-1."""
        for n in range(1, 10):
            seen_indices = set()
            for step in range(2, get_total_steps(n)):
                step_type, idx = get_step_type(step, n)
                if idx is not None:
                    seen_indices.add(idx)
            assert seen_indices == set(range(n)), f"Failed for n={n}"

    def test_no_gaps_in_steps(self):
        """All steps from 1 to total are valid (no gaps)."""
        for n in range(1, 10):
            total = get_total_steps(n)
            for step in range(1, total + 1):
                step_type, _ = get_step_type(step, n)
                assert step_type in ("CONTEXT", "ANALYZE", "CONFIRM", "SUMMARY")


class TestPlanPhaseIntentFidelity:
    """F3: plan-phase verifiers judge intent fidelity, not applied/byte-exact
    state. A correct plan diff with approximate offsets must pass; only a diff
    that mis-describes the change fails.
    """

    def _guidance(self, check: str) -> str:
        from skills.planner.quality_reviewer.plan_code_qr_verify import PlanCodeVerify
        item = {"id": "QR-1", "scope": "code_change:CC-M-001-001", "check": check}
        return "\n".join(PlanCodeVerify().get_verification_guidance(item, "/sd"))

    def test_intent_fidelity_note_is_present(self):
        body = self._guidance("diff format rule 0")
        assert "PLAN-PHASE SCOPE" in body
        assert "ADVISORY" in body or "advisory" in body

    def test_diff_format_offsets_are_advisory(self):
        body = self._guidance("diff format rule 0")
        # @@ offsets / git-apply must be explicitly advisory, not a FAIL trigger.
        assert "ADVISORY" in body
        assert "@@ line numbers" in body
        # The old implementation-grade RULE 2 must be gone.
        assert "Function context in @@ header must be accurate" not in body
        assert "@@ line has valid line numbers" not in body

    def test_context_line_check_targets_current_file(self):
        body = self._guidance("context lines")
        assert "CURRENT file" in body
        # Old false-FAIL framing removed.
        assert "context drift" not in body
        # Must explicitly forbid failing on missing post-change state.
        assert "shouldn't be" in body or "should -- not migrated" in body or "post-change" in body

    def test_decompose_prompts_frame_intent_fidelity(self):
        from skills.planner.quality_reviewer.plan_code_qr_decompose import (
            STEP_1_ABSORB, STEP_2_CONCERNS,
        )
        assert "INTENT FIDELITY" in STEP_1_ABSORB
        assert "git apply" in STEP_1_ABSORB
        # Concerns must list offset/apply-cleanliness as NON-failures.
        assert "advisory in a plan" in STEP_2_CONCERNS
        assert "exec/impl phase" in STEP_2_CONCERNS

    def test_design_and_docs_verify_have_no_byte_exact_checks(self):
        """The design/docs verify twins must not carry git-apply / offset
        checks (those never belonged there)."""
        from skills.planner.quality_reviewer.plan_design_qr_verify import PlanDesignVerify
        from skills.planner.quality_reviewer.plan_docs_qr_verify import PlanDocsVerify
        for cls, check in [(PlanDesignVerify, "decision_log"), (PlanDocsVerify, "temporal")]:
            body = "\n".join(cls().get_verification_guidance(
                {"id": "X", "scope": "*", "check": check}, "/sd"))
            assert "git apply" not in body.lower()
            assert "@@ line has valid line numbers" not in body
