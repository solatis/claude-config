#!/usr/bin/env python3
"""Plan code execution - first-time code filling workflow.

4-step workflow for developer sub-agent:
  1. Task Description (context display, CLI commands overview)
  2. Read Target Files (read codebase, understand patterns)
  3. Create Unified Diffs (diff format reference, create diffs)
  4. Validate and Output (CLI validation, output format)

This is the EXECUTE script for first-time code filling.
For QR fix mode, see plan_code_qr_fix.py.
Router (plan_code.py) dispatches to appropriate script.
"""

from skills.planner.shared.constraints import format_state_banner
from skills.lib.conventions import get_convention
from skills.planner.shared.resources import (
    STATE_DIR_ARG_REQUIRED,
    get_context_path,
    render_context_file,
    validate_state_dir_requirement,
)


STEPS = {
    1: "Task Description",
    2: "Read Target Files",
    3: "Create Unified Diffs",
    4: "Validate and Output",
}


DEVELOPER_AWARENESS = """
QR-Code checks: naming, structure, patterns, repetition, documentation.
Avoid: god functions >50 lines, duplicate logic, temporal contamination.
Decision Log provides WHY context.
"""


def get_step_guidance(
    step: int, module_path: str = None, **kwargs) -> dict:
    """Return guidance for the given step."""
    MODULE_PATH = module_path or "skills.planner.developer.plan_code_execute"
    state_dir = kwargs.get("state_dir", "")

    if step == 1:
        validate_state_dir_requirement(step, state_dir)
        context_file = get_context_path(state_dir)
        context_display = render_context_file(context_file)
        banner = format_state_banner("DEV-FILL-DIFFS", 1, "work")

        return {
            "title": STEPS[1],
            "actions": [
                "PLANNING CONTEXT (from orchestrator):",
                "",
                context_display,
                "",
                banner,
                "",
                DEVELOPER_AWARENESS,
                "",
                "MODE: PLANNING (not implementing)",
                "You are a Plan Author, not a code implementer.",
                "Your output is DIFF TEXT in files, not code changes to the codebase.",
                "",
                "TASK: Convert Code Intent to Code Changes in plan.json.",
                "",
                "JSON-IR ARCHITECTURE:",
                "  plan.json contains code_intents[] populated by Architect.",
                "  Your job: create code_changes[] entries linked via intent_ref.",
                "  Use CLI commands - DO NOT edit plan.json directly.",
                "",
                "WORKFLOW OVERVIEW:",
                "  1. Read plan.json to understand code_intents",
                "  2. Read target files from codebase (READ-ONLY)",
                "  3. Pass diff content directly via --diff flag",
                "  4. Run CLI to register changes",
                "",
                "FORBIDDEN: Edit tool. You are planning, not implementing.",
                "",
                "CLI COMMANDS (single invocation):",
                "  python3 -m skills.planner.cli.plan --state-dir $STATE_DIR list-milestones",
                "  python3 -m skills.planner.cli.plan --state-dir $STATE_DIR list-intents M-001",
                "  python3 -m skills.planner.cli.plan --state-dir $STATE_DIR set-change \\",
                "    --milestone M-001 --intent-ref CI-M-001-001 --file path.py --diff $'...'",
                "",
                "BATCH MODE (preferred for multiple changes):",
                "",
                "  python3 -m skills.planner.cli.plan --state-dir $STATE_DIR batch '[",
                "    {\"method\": \"set-change\", \"params\": {\"milestone\": \"M-001\", \"intent_ref\": \"CI-M-001-001\", \"file\": \"src/a.py\", \"diff\": \"...\"}, \"id\": 1},",
                "    {\"method\": \"set-change\", \"params\": {\"milestone\": \"M-001\", \"intent_ref\": \"CI-M-001-002\", \"file\": \"src/b.py\", \"diff\": \"...\"}, \"id\": 2}",
                "  ]'",
                "",
                "Read plan.json now. List milestones and code_intents.",
            ],
            "next": f"python3 -m {MODULE_PATH} --step 2 --state-dir {state_dir}",
        }

    elif step == 2:
        state_dir_arg = f" --state-dir {state_dir}" if state_dir else ""
        return {
            "title": STEPS[2],
            "actions": [
                "For EACH code_intent in plan.json:",
                "",
                "1. READ TARGET FILES from codebase (for reference only):",
                "   - Read file specified in code_intent.file",
                "   - Read adjacent files for pattern reference",
                "   - Note context lines for diff anchoring",
                "   - DO NOT MODIFY these files. Extract patterns for diffs only.",
                "",
                "2. UNDERSTAND CONTEXT:",
                "   - Existing patterns and conventions",
                "   - Where new code should be inserted",
                "   - What context lines to use for anchoring",
                "",
                "3. NOTE for each intent:",
                "   - Current file structure",
                "   - Insertion points for new code",
                "   - Context lines (2-3 lines before/after changes)",
                "",
                "SKIP PATTERN: If milestone only touches .md/.rst/.txt files,",
                "mark as documentation-only (no code_changes needed).",
            ],
            "next": f"python3 -m {MODULE_PATH} --step 3{state_dir_arg}",
        }

    elif step == 3:
        state_dir_arg = f" --state-dir {state_dir}" if state_dir else ""
        diff_resource = get_convention("diff-format.md")
        return {
            "title": STEPS[3],
            "actions": [
                "AUTHORITATIVE REFERENCE FOR DIFF FORMAT:",
                "",
                "=" * 60,
                diff_resource,
                "=" * 60,
                "",
                "For EACH code_intent, store the change via CLI.",
                "",
                "PREFERRED: SNIPPETS (the tool computes @@ headers -- you never",
                "hand-author line numbers, so off-by-N hunks are impossible):",
                "",
                "  1. Copy the EXACT current text to replace into --old-snippet",
                "     (verbatim from the file you read in step 2; use \"\" for a pure",
                "     insertion at the top of the file).",
                "  2. Put the replacement text in --new-snippet.",
                "  3. The tool reads the file, runs difflib, and stores a valid",
                "     unified diff with correct line numbers.",
                "",
                "  python3 -m skills.planner.cli.plan --state-dir $STATE_DIR set-change \\",
                "    --milestone M-001 --intent-ref CI-M-001-001 \\",
                "    --file path/to/file.py \\",
                "    --old-snippet $'    context_line_before()\\n    context_line_after()' \\",
                "    --new-snippet $'    context_line_before()\\n    # WHY (Decision Log)\\n    new_code()\\n    context_line_after()'",
                "",
                "STOP CHECK: If you are about to use Edit on a source file, STOP.",
                "That means you are implementing, not planning. Return to step 1.",
                "",
                "FALLBACK: --diff (only if you cannot supply snippets). You then own",
                "the @@ arithmetic, which is the historical off-by-N source -- avoid.",
                "  @@ line numbers are advisory at plan time (a tool recomputes them",
                "  at apply); never block on offset arithmetic.",
                "",
                "REQUIREMENTS:",
                "  - File path: exact path to target file",
                "  - old_snippet: copied verbatim from the current file (so it anchors)",
                "  - Comments: explain WHY, source from Planning Context",
                "",
                "CRITICAL: Each code_change MUST have valid intent_ref.",
                "  CLI validates: intent_ref must exist in code_intents[].",
            ],
            "next": f"python3 -m {MODULE_PATH} --step 4{state_dir_arg}",
        }

    elif step == 4:
        return {
            "title": STEPS[4],
            "actions": [
                "VALIDATE plan.json using CLI:",
                "",
                "  python3 -m skills.planner.cli.plan validate --phase plan-code",
                "",
                "This validates:",
                "  - Every code_intent has matching code_change with valid intent_ref",
                "  - All decision_refs in why_comments point to existing decisions",
                "  - Context lines match actual file content",
                "",
                "VALIDATION CHECKLIST (verify before completing):",
                "",
                "  [ ] Every code_intent has code_change with matching intent_ref",
                "  [ ] File paths are exact (not 'auth files' but 'src/auth/handler.py')",
                "  [ ] Context lines exist in target files (verify patterns match)",
                "  [ ] 2-3 context lines for reliable anchoring",
                "  [ ] Comments explain WHY, not WHAT",
                "  [ ] No location directives in comments",
                "",
                "---",
                "",
                "OUTPUT FORMAT (MINIMAL - orchestrator reads plan.json directly):",
                "",
                "TOKEN BUDGET: MAX 200 tokens for return message.",
                "DO NOT include diff content in return. plan.json has the changes.",
                "",
                "If all code_changes added successfully:",
                "  'COMPLETE: Code changes added for [N] intents.'",
                "  'Milestones with changes: [list]'",
                "",
                "If issues found:",
                "  <escalation>",
                "    <type>BLOCKED</type>",
                "    <context>[Intent ID]</context>",
                "    <issue>[What prevented change creation]</issue>",
                "    <needed>[What's needed to proceed]</needed>",
                "  </escalation>",
                "",
                "When complete, output: PASS",
            ],
            "next": "",
        }

    return {"error": f"Invalid step {step}"}


if __name__ == "__main__":
    from skills.lib.workflow.cli import mode_main

    mode_main(
        __file__,
        get_step_guidance,
        "Plan-Code-Execute: Developer code filling workflow",
        extra_args=[STATE_DIR_ARG_REQUIRED],
    )
