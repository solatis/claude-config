#!/usr/bin/env python3
"""QR decomposition for plan-code phase.

Scope: Code correctness in planned changes.
  - Context line verification (diff context matches codebase)
  - Diff format validation (RULE 0/1/2 compliance)
  - Intent linkage (every code_intent has code_change)
  - WHY comment decision_refs validity
NOT documentation quality (plan-docs's job).

Severity categories (per conventions/severity.md):
  MUST: KNOWLEDGE subset (decision refs, assumption validation)
  SHOULD: STRUCTURE categories (god objects, convention violations)
  COULD: COSMETIC (toolchain-catchable, formatter-fixable)

WHY STRUCTURE allowed: Dev agent can fix code correctness issues.
"""

from skills.planner.quality_reviewer.prompts.decompose import dispatch_step


PHASE = "plan-code"


STEP_1_ABSORB = """\
Read plan.json from STATE_DIR:
  cat $STATE_DIR/plan.json | jq '.'

SCOPE: Code correctness in planned changes -- judged as INTENT FIDELITY.
This is a PLAN: the working tree is intentionally NOT migrated, nobody
`git apply`s these hunks, and @@ offsets are advisory. Verify that each diff
correctly DESCRIBES its change against the CURRENT file; do NOT FAIL because
the file still shows the pre-change state or because line numbers are
approximate. git-apply-cleanliness is the exec/impl phase's job.

Focus on:
  - milestones[].code_intents[] -- what changes are intended
  - milestones[].code_changes[] -- actual diff content
  - code_changes[].diff (context lines must match the CURRENT codebase)
  - code_changes[].why_comments[].decision_ref (refs must exist)

OUT OF SCOPE (already verified in plan-docs phase):
  - Documentation quality (temporal contamination, WHY-not-WHAT)
  - README/CLAUDE.md content
  - Invisible knowledge coverage"""


STEP_2_CONCERNS = """\
Brainstorm concerns specific to CODE CORRECTNESS (intent fidelity):
  - Context lines don't match the CURRENT codebase (diff anchors to nothing)
  - Diff mis-describes the change: wrong file, wrong transform
  - Diff format violations (missing +/- prefixes, wrong file headers)
  - Code_intents without corresponding code_changes
  - Invalid decision_refs in why_comments
  - Type errors, missing imports, API mismatches
  - Convention violations (per project style)

DO NOT raise these as failures (advisory in a plan):
  - @@ line numbers / hunk offsets being approximate
  - The diff not applying git-clean (checked in exec/impl phase)
  - The file 'still' showing the pre-change state (it should -- not migrated)

DO NOT brainstorm documentation concerns (out of scope for this phase)."""


STEP_3_ENUMERATION = """\
For plan-code, enumerate CODE CHANGE ARTIFACTS:

INTENTS:
  - Each milestone's code_intents (ID, description)
  - Intent-to-change mapping (which intents have changes?)

CHANGES:
  - Each code_change (ID, file path, line range)
  - Files touched across all changes
  - Context line locations requiring verification

REFERENCES:
  - decision_refs in why_comments (do they exist in planning_context?)

DO NOT enumerate:
  - documentation{} fields (plan-docs's job)
  - readme_entries (plan-docs's job)"""


STEP_5_GENERATE = """\
SEVERITY ASSIGNMENT (per conventions/severity.md, plan-code scope):

  MUST (blocks all iterations):
    - ASSUMPTION_UNVALIDATED: architectural assumption without citation
    - MARKER_INVALID: intent marker without valid explanation
    - decision_ref references non-existent decision

  SHOULD (iterations 1-4) - STRUCTURE categories:
    - GOD_OBJECT: >15 methods OR >10 deps
    - GOD_FUNCTION: >50 lines OR >3 nesting
    - CONVENTION_VIOLATION: violates documented project convention
    - TESTING_STRATEGY_VIOLATION: tests don't follow confirmed strategy

  COULD (iterations 1-3) - COSMETIC:
    - TOOLCHAIN_CATCHABLE: errors the compiler/linter would flag
    - FORMATTER_FIXABLE: style issues fixable by formatter
    - DEAD_CODE: unused functions, impossible branches

DO NOT use KNOWLEDGE categories for documentation issues --
those are plan-docs's responsibility."""


COMPONENT_EXAMPLES = """\
  - A file being modified
  - A module/package
  - A code_intent cluster"""


CONCERN_EXAMPLES = """\
  - Error handling consistency
  - Type safety across boundaries
  - Testing boundary clarity"""


PHASE_PROMPTS = {
    1: STEP_1_ABSORB,
    2: STEP_2_CONCERNS,
    3: STEP_3_ENUMERATION,
    5: STEP_5_GENERATE,
}

GROUPING_CONFIG = {
    "component_examples": COMPONENT_EXAMPLES,
    "concern_examples": CONCERN_EXAMPLES,
}


def get_step_guidance(step: int, module_path: str = None, **kwargs) -> dict:
    module_path = module_path or "skills.planner.quality_reviewer.plan_code_qr_decompose"
    state_dir = kwargs.get("state_dir", "")
    return dispatch_step(step, PHASE, module_path, PHASE_PROMPTS, GROUPING_CONFIG, state_dir)


if __name__ == "__main__":
    from skills.lib.workflow.cli import mode_main

    mode_main(
        __file__,
        get_step_guidance,
        "QR-Plan-Code-Decompose: Generate verification items for code changes",
        extra_args=[
            (["--state-dir"], {"type": str, "required": True, "help": "State directory path"}),
        ],
    )
