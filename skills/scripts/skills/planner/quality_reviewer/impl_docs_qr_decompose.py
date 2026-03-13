#!/usr/bin/env python3
"""QR decomposition for impl-docs phase.

Scope: Post-implementation documentation.
  - project index file format (tabular index)
  - IK proximity audit (docs adjacent to code)
  - Temporal contamination in comments
  - README.md creation criteria
NOT code quality (verified in impl-code phase).

Severity categories: Same as plan-docs (TW can fix documentation issues).
"""

from skills.planner.quality_reviewer.prompts.decompose import dispatch_step


PHASE = "impl-docs"


STEP_1_ABSORB = """\
Read plan.json from STATE_DIR:
  cat $STATE_DIR/plan.json | jq '.'

Also read documentation files in modified directories:
  - project index file files
  - README.md files
  - Comments in source files

SCOPE: Post-implementation documentation quality.

Focus on:
  - invisible_knowledge section (was it transferred?)
  - Modified directory list (need docs?)
  - project index file format compliance
  - README.md presence where required

OUT OF SCOPE:
  - Code quality (verified in impl-code)
  - Plan structure (verified in plan-design)"""


STEP_2_CONCERNS = """\
Brainstorm concerns specific to POST-IMPL DOCUMENTATION:
  - project index file missing or wrong format (tabular index required)
  - IK not at best location (should be adjacent to code)
  - Temporal contamination in comments
  - README.md missing where required
  - Comments don't explain WHY

DO NOT brainstorm code quality or plan structure concerns."""


STEP_3_ENUMERATION = """\
For impl-docs, enumerate DOCUMENTATION ARTIFACTS:

DIRECTORIES:
  - Each directory with modified files (directory path)
  - project index file exists? Format correct?
  - README.md exists where required?

INVISIBLE KNOWLEDGE:
  - Each invisible_knowledge item (count, topics)
  - Current location vs best location

COMMENTS:
  - Source files with new comments
  - Temporal contamination candidates"""


STEP_5_GENERATE = """\
SEVERITY ASSIGNMENT (per conventions/severity.md, impl-docs scope):

  MUST (blocks all iterations) - KNOWLEDGE categories:
    - IK_TRANSFER_FAILURE: invisible knowledge not at best location
    - TEMPORAL_CONTAMINATION: change-relative language in comments
    - BASELINE_REFERENCE: comment references removed code

  SHOULD (iterations 1-4):
    - project index file format violations
    - README.md missing where scope warrants
    - WHY-not-WHAT violations

  COULD (iterations 1-3):
    - Minor formatting inconsistencies
    - Documentation style variations"""


COMPONENT_EXAMPLES = """\
  - A modified directory
  - A project index file file
  - A README.md file"""


CONCERN_EXAMPLES = """\
  - IK proximity
  - Temporal contamination
  - Format compliance"""


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
    module_path = module_path or "skills.planner.quality_reviewer.impl_docs_qr_decompose"
    state_dir = kwargs.get("state_dir", "")
    return dispatch_step(step, PHASE, module_path, PHASE_PROMPTS, GROUPING_CONFIG, state_dir)


if __name__ == "__main__":
    from skills.lib.workflow.cli import mode_main

    mode_main(
        __file__,
        get_step_guidance,
        "QR-Impl-Docs-Decompose: Generate verification items for post-impl documentation",
        extra_args=[
            (["--state-dir"], {"type": str, "required": True, "help": "State directory path"}),
        ],
    )
