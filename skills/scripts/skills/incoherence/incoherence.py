#!/usr/bin/env python3
"""
Incoherence Detector - Step-based incoherence detection workflow

DETECTION PHASE (Steps 1-12):
    Steps 1-3 (Parent): Survey, dimension selection, exploration dispatch
    Steps 4-7 (Sub-Agent): Broad sweep, coverage check, gap-fill, format findings
    Step 8 (Parent): Synthesis & candidate selection
    Step 9 (Parent): Deep-dive dispatch
    Steps 10-11 (Sub-Agent): Deep-dive exploration and formatting
    Step 12 (Parent): Verdict analysis and grouping

INTERACTIVE RESOLUTION PHASE (Steps 13-15):
    Step 13 (Parent): Prepare resolution batches from groups
    Step 14 (Parent): Present batch via AskUserQuestion
                      - Group batches: ask group question ONLY first
                      - Non-group or MODE=individual: ask per-issue questions
    Step 15 (Parent): Loop controller
                      - If unified chosen: record for all, next batch
                      - If individual chosen: loop to step 14 with MODE=individual
                      - If all batches done: proceed to application

APPLICATION PHASE (Steps 16-21):
    Step 16 (Parent): Analyze targets and select agent types
    Step 17 (Parent): Dispatch current wave of agents
    Steps 18-19 (Sub-Agent): Apply resolution, format result
    Step 20 (Parent): Collect wave results, check for next wave
    Step 21 (Parent): Present final report to user

Resolution is interactive - user answers AskUserQuestion prompts inline.
No manual file editing required.
"""

import argparse

from skills.lib.paths import get_skills_working_dir
from skills.lib.workflow.core import (
    Arg,
    StepDef,
    Workflow,
)

_SKILLS_DIR = get_skills_working_dir()
from skills.lib.workflow.ast import W, XMLRenderer, render
from skills.lib.workflow.ast.nodes import (
    TextNode, StepHeaderNode, CurrentActionNode, InvokeAfterNode,
)
from skills.lib.workflow.ast.renderer import (
    render_step_header, render_current_action, render_invoke_after,
)

MODULE_PATH = "skills.incoherence.incoherence"

DIMENSION_CATALOG = """
ABSTRACT DIMENSION CATALOG
==========================

Choose dimensions from this catalog based on Step 1 info sources.

CATEGORY A: SPECIFICATION VS BEHAVIOR
  - README/docs claim X, but code does Y
  - API documentation vs actual API behavior
  - Examples in docs that don't actually work
  Source pairs: Documentation <-> Code implementation

CATEGORY B: INTERFACE CONTRACT INTEGRITY
  - Type definitions vs actual runtime values
  - Schema definitions vs validation behavior
  - Function signatures vs docstrings
  Source pairs: Type/Schema definitions <-> Runtime behavior

CATEGORY C: CROSS-REFERENCE CONSISTENCY
  - Same concept described differently in different docs
  - Numeric constants/limits stated inconsistently
  - Intra-document contradictions
  Source pairs: Document <-> Document

CATEGORY D: TEMPORAL CONSISTENCY (Staleness)
  - Outdated comments referencing removed code
  - TODO/FIXME comments for completed work
  - References to renamed/moved files
  Source pairs: Historical references <-> Current state

CATEGORY E: ERROR HANDLING CONSISTENCY
  - Documented error codes vs actual error responses
  - Exception handling docs vs throw/catch behavior
  Source pairs: Error documentation <-> Error implementation

CATEGORY F: CONFIGURATION & ENVIRONMENT
  - Documented env vars vs actual env var usage
  - Default values in docs vs defaults in code
  Source pairs: Config documentation <-> Config handling code

CATEGORY G: AMBIGUITY & UNDERSPECIFICATION
  - Vague statements that could be interpreted multiple ways
  - Missing thresholds, limits, or parameters
  - Implicit assumptions not stated explicitly
  Detection method: Ask "could two people read this differently?"

CATEGORY H: POLICY & CONVENTION COMPLIANCE
  - Architectural decisions (ADRs) violated by implementation
  - Style guide rules not followed in code
  - "We don't do X" statements violated in codebase
  Source pairs: Policy documents <-> Implementation patterns

CATEGORY I: COMPLETENESS & DOCUMENTATION GAPS
  - Public API endpoints with no documentation
  - Functions/classes with no docstrings
  - Magic values/constants without explanation
  Detection method: Find code constructs, check if docs exist

CATEGORY J: COMPOSITIONAL CONSISTENCY
  - Claims individually valid but jointly impossible
  - Numeric constraints that contradict when combined
  - Configuration values that create impossible states
  - Timing/resource constraints that cannot all be satisfied
  Detection method: Gather related claims, compute implications, check for contradiction
  Example: timeout=30s, retries=10, max_duration=60s → 30×10=300≠60

CATEGORY K: IMPLICIT CONTRACT INTEGRITY
  - Names/identifiers promise behavior the code doesn't deliver
  - Function named validateX() that doesn't actually validate
  - Error messages that misrepresent the actual error
  - Module/package names that don't match contents
  - Log messages that lie about what happened
  Detection method: Parse names semantically, infer promise, compare to behavior
  Note: LLMs are particularly susceptible to being misled by names

CATEGORY L: DANGLING SPECIFICATION REFERENCES
  - Entity A references entity B, but B is never defined anywhere
  - FK references table that has no schema (e.g., api_keys.tenant_id but no tenants table)
  - UI/API mentions endpoints or types that are not specified
  - Schema field references enum or type with no definition
  Detection method:
    1. Extract DEFINED entities (tables, APIs, types, enums) with locations
    2. Extract REFERENCED entities (FKs, type usages, API calls) with locations
    3. Report: referenced but not defined = dangling reference
  Source pairs: Any specification -> Cross-file entity registry
  Note: Distinct from I (code-without-docs). L is SPEC-without-SPEC.

CATEGORY M: INCOMPLETE SPECIFICATION DEFINITIONS
  - Entity is defined but missing components required for implementation
  - Table schema documented but missing fields that other docs reference
  - API endpoint defined but missing request/response schema
  - Proto/schema has fields but lacks types others expect
  Detection method:
    1. For each defined entity, extract CLAIMED components
    2. Cross-reference with EXPECTED components from consuming docs
    3. Report: expected but not claimed = incomplete definition
  Source pairs: Definition document <-> Consumer documents
  Example: rules table shows (id, name, enabled) but API doc expects 'expression' field

SELECTION RULES:
- Select ALL categories relevant to Step 1 info sources
- Typical selection is 5-8 dimensions
- G, H, I, K are especially relevant for LLM-assisted coding
- J requires cross-referencing multiple claims (more expensive)
- L, M are critical for design-phase docs and specs-to-be-implemented
  Select when docs describe systems that need to be built
"""




def format_incoherence_output(step, phase, agent_type, guidance):
    """Format output using AST builder API."""
    parts = []
    title = f"INCOHERENCE [{phase}] [{agent_type}]"
    parts.append(render_step_header(StepHeaderNode(
        title=title,
        script="incoherence",
        step=str(step),
    )))
    parts.append("")

    if step == 1:
        parts.append("""<xml_format_mandate>
CRITICAL: All script outputs use XML format. You MUST:
1. Execute the action in <current_action>
2. When complete, invoke the exact command in <invoke_after>
3. DO NOT modify commands. DO NOT skip steps.
</xml_format_mandate>""")
        parts.append("")

    parts.append(render_current_action(CurrentActionNode(guidance["actions"])))
    parts.append("")

    next_text = guidance.get("next", "")
    if step >= total or "COMPLETE" in next_text.upper():
        parts.append("WORKFLOW COMPLETE - Present report to user.")
    else:
        next_cmd = f'python3 -m skills.incoherence.incoherence --step-number {step + 1}'
        parts.append(render_invoke_after(InvokeAfterNode(cmd=next_cmd)))

    return "\n".join(parts)


STEPS = {
    1: {
        "title": "CODEBASE SURVEY",
        "actions": [
            "CODEBASE SURVEY",
            "",
            "Gather MINIMAL context (README first 50 lines, project index file, dir listing).",
            "Do NOT read detailed docs, source code, configs, or tests.",
            "",
            "Identify: codebase type, primary language, doc locations, info source types",
            "(README, API docs, comments, types, configs, schemas, ADRs, style guides, tests)",
        ],
        "next": "Invoke step 2 with survey results in --thoughts"
    },
    2: {
        "title": "DIMENSION SELECTION",
        "actions": [
            "DIMENSION SELECTION",
            "",
            "Select from catalog (A-M) based on Step 1 info sources.",
            "Do NOT read files or create domain-specific dimensions.",
            "",
            DIMENSION_CATALOG,
            "",
            "Output: Selected dimensions with one-line rationale each.",
        ],
        "next": "Invoke step 3 with selected dimensions in --thoughts"
    },
    3: {
        "title": "EXPLORATION DISPATCH",
        "actions": [
            "EXPLORATION DISPATCH",
            "",
            "Launch one haiku Explore agent per dimension (ALL in SINGLE message).",
            "",
            "AGENT PROMPT:",
            f"  DIMENSION: {{letter}} - {{name}}. DESCRIPTION: {{from_catalog}}",
            f'  Start: <invoke working-dir="{_SKILLS_DIR}" cmd="python3 -m {MODULE_PATH} --step-number 4 --thoughts \\"Dimension: {{{{letter}}}}\\"" />',
        ],
        "next": "After all agents complete, invoke step 8 with combined findings"
    },
    4: {
        "title": "BROAD SWEEP [SUB-AGENT]",
        "actions": [
            "BROAD SWEEP [SUB-AGENT]",
            "",
            "Cast WIDE NET. Prioritize recall over precision. Your dimension is in --thoughts.",
            "",
            "SEARCH: docs/, README, src/, configs, schemas, types, tests.",
            "",
            "FOR L/M DIMENSIONS: Build entity registry first:",
            "  - DEFINED: tables, endpoints, types (entity_name, file:line, components)",
            "  - REFERENCED: FKs, type usages, API calls (entity_name, file:line)",
            "  - Cross-ref: referenced-not-defined=L, defined-but-incomplete=M",
            "",
            "PER FINDING: Location A, Location B, conflict, confidence (low OK).",
            "Bias: Report more. Track searched locations.",
        ],
        "next": "Invoke step 5 with your findings and searched locations in --thoughts"
    },
    5: {
        "title": "COVERAGE CHECK [SUB-AGENT]",
        "actions": [
            "COVERAGE CHECK [SUB-AGENT]",
            "",
            "Identify GAPS: unexplored dirs, skipped file types, unchecked modules.",
            "Diversity check: all findings same dir/type? Check both docs AND code.",
            "",
            "Output: At least 3 gaps + specific files/patterns to search next.",
        ],
        "next": "Invoke step 6 with identified gaps in --thoughts"
    },
    6: {
        "title": "GAP-FILL EXPLORATION [SUB-AGENT]",
        "actions": [
            "GAP-FILL EXPLORATION [SUB-AGENT]",
            "",
            "Search at least 3 new locations from gap list.",
            "Try: tests, examples, scripts/, negations ('not', 'deprecated'), TODOs/FIXMEs.",
            "",
            "Record new findings: Location A, Location B, conflict, confidence.",
        ],
        "next": "Invoke step 7 with all findings (original + new) in --thoughts"
    },
    7: {
        "title": "FORMAT EXPLORATION FINDINGS [SUB-AGENT]",
        "actions": [
            "FORMAT EXPLORATION FINDINGS [SUB-AGENT]",
            "",
            "Output format:",
            "  DIMENSION {letter} | TOTAL: N | AREAS SEARCHED: [list]",
            "  FINDING 1: A=[file:line] B=[file:line] Conflict=[desc] Confidence=[h/m/l]",
            "  ...",
            "",
            "Include ALL findings. Deduplication happens in step 8.",
        ],
        "next": "Output formatted results. Sub-agent task complete."
    },
    8: {
        "title": "SYNTHESIZE CANDIDATES",
        "actions": [
            "SYNTHESIZE CANDIDATES",
            "",
            "1. Score each (0-10): Impact + Confidence + Specificity + Fixability",
            "2. Output: C1, C2... with location, summary, score, dimension",
            "",
            "Pass ALL candidates (no limits). Deduplication after Sonnet verification.",
        ],
        "next": "Invoke step 9 with all candidates in --thoughts"
    },
    9: {
        "title": "DEEP-DIVE DISPATCH",
        "actions": [
            "DEEP-DIVE DISPATCH",
            "",
            "Launch sonnet agents (subagent_type='general-purpose', model='sonnet').",
            "Launch ALL in SINGLE message (no self-limiting).",
            "",
            "AGENT PROMPT:",
            f"  CANDIDATE: {{id}} at {{location}} | DIMENSION: {{letter}} - {{name}}",
            f"  Claimed: {{summary}}",
            f"  Workflow: step 10 (explore) -> step 11 (format)",
            f'  Start: <invoke working-dir="{_SKILLS_DIR}" cmd="python3 -m {MODULE_PATH} --step-number 10 --thoughts \\"Verifying: {{{{id}}}}\\"" />',
        ],
        "next": "After all agents complete, invoke step 12 with all verdicts"
    },
    10: {
        "title": "DEEP-DIVE EXPLORATION [SUB-AGENT]",
        "actions": [
            "DEEP-DIVE EXPLORATION [SUB-AGENT]",
            "",
            "1. Read both sources with 100+ lines context, extract exact quotes",
            "2. Analyze by dimension:",
            "   - A,B,C,E,F,J,K (contradiction): genuinely conflicting? -> TRUE_INCOHERENCE",
            "   - G (ambiguity): two readers interpret differently? -> SIGNIFICANT_AMBIGUITY",
            "   - H (policy): orphaned ref -> DOC_GAP, active violation -> TRUE_INCOHERENCE",
            "   - I (completeness): missing needed info? -> DOCUMENTATION_GAP",
            "   - L,M (omission): undefined/incomplete entity? -> SPECIFICATION_GAP",
            "",
            "3. Verdict: TRUE_INCOHERENCE | SIGNIFICANT_AMBIGUITY | DOCUMENTATION_GAP |",
            "   SPECIFICATION_GAP | FALSE_POSITIVE",
        ],
        "next": "When done exploring, invoke step 11 with findings in --thoughts"
    },
    11: {
        "title": "FORMAT RESULTS [SUB-AGENT]",
        "actions": [
            "FORMAT RESULTS [SUB-AGENT]",
            "",
            "Output format:",
            "  CANDIDATE: {id} | VERDICT: {verdict} | SEVERITY: {c/h/m/l}",
            "  SOURCE A: {file}:{line} \"{quote}\" Claims: {claim}",
            "  SOURCE B: {file}:{line} \"{quote}\" Claims: {claim}",
            "  ANALYSIS: {why conflict} | RECOMMENDATION: {fix}",
        ],
        "next": "Output formatted result. Sub-agent task complete."
    },
    12: {
        "title": "VERDICT ANALYSIS",
        "actions": [
            "VERDICT ANALYSIS",
            "",
            "1. Tally by verdict type and severity",
            "2. Quality check: each non-FALSE_POSITIVE has exact quotes",
            "3. Deduplicate: merge identical source pairs, keep richer analysis",
            "4. Group related issues:",
            "   - SHARED ROOT CAUSE: same file, same outdated doc, same config",
            "   - SHARED THEME: same dimension, same concept, same fix type",
            "   Output: G1, G2... with member issues, relationship, unified resolution",
        ],
        "next": "Invoke step 13 with confirmed findings and groups"
    },
    13: {
        "title": "PREPARE RESOLUTION BATCHES",
        "actions": [
            "PREPARE RESOLUTION BATCHES",
            "",
            "Batch rules (priority order, max 4 per batch):",
            "1. Group-based: issues sharing G1/G2/... together",
            "2. File-based: ungrouped issues affecting same file",
            "3. Singletons: remaining unrelated issues",
            "",
            "Per batch output: Issues, theme/file, group suggestion (if applicable)",
            "",
            "Per issue output:",
            "  ISSUE {id}: {title} | Severity | Dimension | Group",
            "  Source A: {file}:{line} \"{quote max 10 lines}\" Claims: ...",
            "  Source B: {file}:{line} \"{quote max 10 lines}\" Claims: ...",
            "  Analysis: {conflict} | Suggestions: 1. {action} 2. {alt action}",
            "",
            "Suggestions must use ACTUAL values (e.g., 'Update to 60s' not 'match code').",
        ],
        "next": "Invoke step 14 with batch definitions and issue data in --thoughts"
    },
    14: {
        "title": "PRESENT RESOLUTION BATCH",
        "actions": [
            "PRESENT RESOLUTION BATCH",
            "",
            "Use AskUserQuestion. Check --thoughts for 'MODE: individual' flag.",
            "Edge cases: empty batch=skip, single-member group=individual, quotes>10 lines=truncate.",
            "",
            "GROUP BATCH (2+ members, no MODE flag): ask group question only",
            "  header: 'G{n}', options: unified_suggestion | 'Resolve individually' | 'Skip all'",
            "",
            "NON-GROUP or MODE=individual: ask per-issue questions",
            "  header: 'I{n}', include: file:line, quotes, claims, analysis",
            "  options: suggestion_1 | suggestion_2 | 'Skip'",
            "",
            "Suggestions must use ACTUAL values (e.g., 'Update to 60s' not 'match code').",
        ],
        "next": "After AskUserQuestion returns, invoke step 15 with responses"
    },
    15: {
        "title": "RESOLUTION LOOP CONTROLLER",
        "actions": [
            "RESOLUTION LOOP CONTROLLER",
            "",
            "Early exit: if ALL resolutions are NO_RESOLUTION, output 'No issues selected' and stop.",
            "",
            "Process response:",
            "  G{n} response: unified -> record for all; 'individually' -> step 14 MODE=individual;",
            "                 'skip all' -> NO_RESOLUTION for all; 'other' -> record custom for all",
            "  I{n} responses: record each resolution or NO_RESOLUTION",
            "",
            "Loop decision:",
            "  1. 'Resolve individually' -> step 14 with MODE=individual",
            "  2. More batches -> step 14 with next batch",
            "  3. All complete -> step 16 with all resolutions",
            "",
            "Include in --thoughts: collected resolutions, remaining batches, MODE flag if applicable.",
        ],
        "next": (
            "If 'Resolve individually' selected: invoke step 14 with MODE=individual\n"
            "If more batches remain: invoke step 14 with next batch\n"
            "If all batches complete: invoke step 16 with all resolutions"
        )
    },
    16: {
        "title": "PLAN DISPATCH",
        "actions": [
            "PLAN DISPATCH",
            "",
            "From --thoughts: read resolutions, skip NO_RESOLUTION.",
            "",
            "1. Target files: use Source A/B as hints, resolution may specify",
            "2. Agent types: .md/.rst/.txt -> technical-writer, code/config -> developer",
            "3. Group by file: multiple issues same file -> one agent",
            "4. Waves: different files parallel, conflicts sequential",
            "",
            "Output: FILE GROUPS (file, issues, agent) + DISPATCH PLAN (waves)",
        ],
        "next": "Invoke step 17 with dispatch plan in --thoughts"
    },
    17: {
        "title": "RECONCILE DISPATCH",
        "actions": [
            "RECONCILE DISPATCH",
            "",
            "Launch agents for current wave (Wave 1 first time, next wave after step 20).",
            "Agent types: developer (code/config) or technical-writer (docs).",
            "",
            "AGENT PROMPT:",
            f"  TARGET: {{file}} | ISSUES: {{ids}}",
            f"  Per issue: type, severity, sources, analysis, resolution_text",
            f"  Workflow: step 18 (apply) -> step 19 (format)",
            f'  Start: <invoke working-dir="{_SKILLS_DIR}" cmd="python3 -m {MODULE_PATH} --step-number 18 --thoughts \\"FILE: {{{{file}}}}\\"" />',
            "",
            "Launch ALL wave agents in SINGLE message.",
        ],
        "next": "After all wave agents complete, invoke step 20 with results"
    },
    18: {
        "title": "RECONCILE APPLY [SUB-AGENT]",
        "actions": [
            "RECONCILE APPLY [SUB-AGENT]",
            "",
            "For each resolution: locate target, apply change, verify it addresses the issue.",
            "Batched: apply in order, watch for conflicts.",
            "Bias: apply the resolution, interpret charitably, skip rarely.",
        ],
        "next": "When done, invoke step 19 with results in --thoughts"
    },
    19: {
        "title": "RECONCILE FORMAT [SUB-AGENT]",
        "actions": [
            "RECONCILE FORMAT [SUB-AGENT]",
            "",
            "Per issue: ISSUE: {id} | STATUS: RESOLVED|SKIPPED | FILE: {path}",
            "  If RESOLVED: CHANGE: {brief description}",
            "  If SKIPPED: REASON: {why}",
        ],
        "next": "Output formatted result(s). Sub-agent task complete."
    },
    20: {
        "title": "RECONCILE COLLECT",
        "actions": [
            "RECONCILE COLLECT",
            "",
            "Collect wave results: per agent, issues handled, status, change/reason.",
            "Check dispatch plan: more waves -> step 17, all complete -> step 21.",
        ],
        "next": "If more waves: invoke step 17. Otherwise: invoke step 21."
    },
    21: {
        "title": "PRESENT REPORT",
        "actions": [
            "PRESENT REPORT",
            "",
            "Output inline (no file):",
            "  Summary: detected N, resolved M, skipped K",
            "  Table: ID | Severity | Status | Summary (~40 chars)",
            "",
            "List ALL issues. RESOLVED or SKIPPED with reason.",
        ],
        "next": "WORKFLOW COMPLETE."
    },
}


def generic_step_handler(step_info, **kwargs):
    """Generic handler for standard steps."""
    return {"actions": step_info.get("actions", []), "next": step_info.get("next", "")}


STEP_HANDLERS = {i: generic_step_handler for i in range(1, 22)}


def get_step_guidance(step_number, total_steps):
    step_info = STEPS.get(step_number, {})
    handler = STEP_HANDLERS.get(step_number, generic_step_handler)
    return handler(step_info, total_steps=total_steps)


WORKFLOW = Workflow(
    "incoherence",
    StepDef(
        id="survey",
        title="Codebase Survey",
        actions=get_step_guidance(1, 21)["actions"],
    ),
    StepDef(
        id="dimension_selection",
        title="Dimension Selection",
        actions=get_step_guidance(2, 21)["actions"],
    ),
    StepDef(
        id="exploration_dispatch",
        title="Exploration Dispatch",
        actions=get_step_guidance(3, 21)["actions"],
    ),
    StepDef(
        id="broad_sweep",
        title="Broad Sweep [SUB-AGENT]",
        actions=get_step_guidance(4, 21)["actions"],
    ),
    StepDef(
        id="coverage_check",
        title="Coverage Check [SUB-AGENT]",
        actions=get_step_guidance(5, 21)["actions"],
    ),
    StepDef(
        id="gap_fill",
        title="Gap-Fill Exploration [SUB-AGENT]",
        actions=get_step_guidance(6, 21)["actions"],
    ),
    StepDef(
        id="format_exploration",
        title="Format Exploration Findings [SUB-AGENT]",
        actions=get_step_guidance(7, 21)["actions"],
    ),
    StepDef(
        id="synthesize_candidates",
        title="Synthesize Candidates",
        actions=get_step_guidance(8, 21)["actions"],
    ),
    StepDef(
        id="deep_dive_dispatch",
        title="Deep-Dive Dispatch",
        actions=get_step_guidance(9, 21)["actions"],
    ),
    StepDef(
        id="deep_dive_exploration",
        title="Deep-Dive Exploration [SUB-AGENT]",
        actions=get_step_guidance(10, 21)["actions"],
    ),
    StepDef(
        id="format_results",
        title="Format Results [SUB-AGENT]",
        actions=get_step_guidance(11, 21)["actions"],
    ),
    StepDef(
        id="verdict_analysis",
        title="Verdict Analysis",
        actions=get_step_guidance(12, 21)["actions"],
    ),
    StepDef(
        id="prepare_resolution_batches",
        title="Prepare Resolution Batches",
        actions=get_step_guidance(13, 21)["actions"],
    ),
    StepDef(
        id="present_batch",
        title="Present Resolution Batch",
        actions=get_step_guidance(14, 21)["actions"],
    ),
    StepDef(
        id="resolution_loop",
        title="Resolution Loop Controller",
        actions=get_step_guidance(15, 21)["actions"],
    ),
    StepDef(
        id="plan_dispatch",
        title="Plan Dispatch",
        actions=get_step_guidance(16, 21)["actions"],
    ),
    StepDef(
        id="reconcile_dispatch",
        title="Reconcile Dispatch",
        actions=get_step_guidance(17, 21)["actions"],
    ),
    StepDef(
        id="reconcile_apply",
        title="Reconcile Apply [SUB-AGENT]",
        actions=get_step_guidance(18, 21)["actions"],
    ),
    StepDef(
        id="reconcile_format",
        title="Reconcile Format [SUB-AGENT]",
        actions=get_step_guidance(19, 21)["actions"],
    ),
    StepDef(
        id="reconcile_collect",
        title="Reconcile Collect",
        actions=get_step_guidance(20, 21)["actions"],
    ),
    StepDef(
        id="present_report",
        title="Present Report",
        actions=get_step_guidance(21, 21)["actions"],
    ),
    description="Multi-phase incoherence detection and resolution workflow",
    validate=False,
)


def main(
    step_number: int = None):
    """Entry point with parameter annotations for testing framework.

    Note: Parameters have defaults because actual values come from argparse.
    The annotations are metadata for the testing framework.
    """
    parser = argparse.ArgumentParser(description="Incoherence Detector")
    parser.add_argument("--step-number", type=int, required=True)
    args = parser.parse_args()

    guidance = get_step_guidance(args.step_number, WORKFLOW.total_steps)

    # Determine agent type and phase
    # Detection sub-agents: 4-7 (exploration), 10-11 (deep-dive)
    if args.step_number in [4, 5, 6, 7, 10, 11]:
        agent_type = "SUB-AGENT"
        phase = "DETECTION"
    # Application sub-agents: 18-19 (apply resolution)
    elif args.step_number in [18, 19]:
        agent_type = "SUB-AGENT"
        phase = "APPLICATION"
    # Detection parent: 1-12
    elif args.step_number <= 12:
        agent_type = "PARENT"
        phase = "DETECTION"
    # Resolution parent: 13-15
    elif args.step_number <= 15:
        agent_type = "PARENT"
        phase = "RESOLUTION"
    # Application parent: 16-22
    else:
        agent_type = "PARENT"
        phase = "APPLICATION"

    output = format_incoherence_output(
        args.step_number, phase, agent_type, guidance
    )
    print(output)


if __name__ == "__main__":
    main()
