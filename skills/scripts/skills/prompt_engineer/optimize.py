#!/usr/bin/env python3
"""
Prompt Engineer Skill - Scope-adaptive prompt optimization workflow.

Architecture:
  - Four-scope dispatch (single-prompt, ecosystem, greenfield, problem)
  - Shared string constants for reusable fragments
  - Runtime file injection via --categories CLI argument

Scopes:
  - single-prompt: One prompt file, general optimization
  - ecosystem: Multiple related prompts that interact
  - greenfield: No existing prompt, designing from requirements
  - problem: Existing prompt(s) with specific issue to fix

Research grounding:
  - Self-Refine (Madaan 2023): Separate feedback from refinement
  - CoVe (Dhuliawala 2023): Factored verification with OPEN questions
"""

import argparse
import sys
from pathlib import Path

from skills.lib.workflow.prompts import format_step, format_file_content


# ============================================================================
# SHARED PROMPTS
# ============================================================================

TRIAGE_INSTRUCTIONS = (
    "EXAMINE the input, request, AND any relevant prior conversation:\n"
    "  - Problem descriptions stated earlier\n"
    "  - Analysis or diagnosis already performed\n"
    "  - User preferences or constraints mentioned\n"
    "\n"
    "  FILES PROVIDED:\n"
    "    - None: likely GREENFIELD\n"
    "    - Single file with prompt: likely SINGLE-PROMPT\n"
    "    - Multiple related files: likely ECOSYSTEM\n"
    "\n"
    "  REQUEST TYPE:\n"
    "    - General optimization ('improve this'): SINGLE-PROMPT or ECOSYSTEM\n"
    "    - Specific problem ('fix X', 'it does Y wrong'): PROBLEM\n"
    "    - Design request ('I want X to do Y'): GREENFIELD\n"
    "\n"
    "DETERMINE SCOPE (use boundary tests as guidance):\n"
    "  SINGLE-PROMPT: One file + 'improve/optimize' request\n"
    "    Boundary: If 2+ files interact -> ECOSYSTEM\n"
    "  ECOSYSTEM: Multiple files with shared terminology or data flow\n"
    "    Boundary: If no interaction between files -> multiple SINGLE-PROMPT\n"
    "  GREENFIELD: No existing prompt + 'create/design/build' request\n"
    "    Boundary: If modifying existing -> SINGLE-PROMPT or PROBLEM\n"
    "  PROBLEM: Existing prompt + specific failure described\n"
    "    Boundary: If no specific failure -> SINGLE-PROMPT or ECOSYSTEM\n"
    "  (boundaries are heuristics; use judgment for edge cases)\n"
    "\n"
    "OUTPUT:\n"
    "  SCOPE: [single-prompt | ecosystem | greenfield | problem]\n"
    "  RATIONALE: [why this scope fits]"
)

REFINE_INSTRUCTIONS = (
    "VERIFY each proposed technique (factored verification):\n"
    "\n"
    "  For each technique you claimed APPLICABLE:\n"
    "  1. Close your proposal. Answer from reference ONLY:\n"
    "     Q: 'What is the EXACT trigger condition for [technique]?'\n"
    "  2. Close the reference. Answer from target prompt ONLY:\n"
    "     Q: 'What text appears at line [N]?'\n"
    "  3. Compare: Does quoted text match quoted trigger?\n"
    "\n"
    "  Cross-check: CLAIMED vs VERIFIED\n"
    "    CONSISTENT -> keep\n"
    "    INCONSISTENT -> revise or remove\n"
    "\n"
    "SPOT-CHECK dismissed techniques:\n"
    "  Pick 3 marked NOT APPLICABLE\n"
    "  Verify triggers truly don't match\n"
    "\n"
    "UPDATE proposals based on verification.\n"
    "\n"
    "REDUNDANCY AND CONFLICT CHECK:\n"
    "  For each ADD proposal, verify against existing techniques from Phase 1:\n"
    "  Q: 'Does an existing technique already serve this purpose?'\n"
    "  If YES and existing is STRONG -> REMOVE proposal (redundant)\n"
    "  If YES and existing is PARTIAL/WEAK -> reclassify as IMPROVE\n"
    "  For each IMPROVE proposal:\n"
    "  Q: 'Does improvement conflict with other existing techniques?'\n"
    "  If YES -> note conflict and adjust or remove\n"
    "\n"
    "META-CONSTRAINT VERIFICATION:\n"
    "  For EACH proposed change:\n"
    "  Q: Does this change modify PROMPT TEXT STRUCTURE or add OUTPUT INSTRUCTIONS?\n"
    "  A: [Classify: quote the change and state which]\n"
    "\n"
    "  PROMPT TEXT STRUCTURE changes include:\n"
    "    - Shortening/compressing existing prompt text\n"
    "    - Removing sections or examples from prompt\n"
    "    - Refactoring code structure (extracting to variables, etc.)\n"
    "\n"
    "  OUTPUT INSTRUCTIONS changes include:\n"
    "    - Adding response format constraints\n"
    "    - Adding per-step word limits\n"
    "    - Adding output structure requirements\n"
    "\n"
    "  If ANY changes modify prompt text structure:\n"
    "    -> VIOLATION of meta-constraint\n"
    "    -> REMOVE these changes\n"
    "    -> REVISE to add output instructions instead\n"
    "\n"
    "CONTEXT-CORRECTNESS VERIFICATION (for greenfield/problem scopes):\n"
    "  If execution context was identified (STANDALONE/SKILL/SUB-AGENT/COMPONENT):\n"
    "\n"
    "  Q: What is the execution context for this prompt?\n"
    "  A: [answer from Step 2/Assess]\n"
    "\n"
    "  Q: Does the draft contain <system> wrapper or identity setup?\n"
    "  A: [quote from draft or 'None']\n"
    "\n"
    "  Q: Should this execution context have <system>/identity?\n"
    "  A: STANDALONE -> yes. SKILL/SUB-AGENT/COMPONENT -> no.\n"
    "\n"
    "  If INCONSISTENT: flag for revision before Approve step."
)

APPROVE_INSTRUCTIONS = (
    "Present using this format:\n"
    "\n"
    "PROPOSED CHANGES\n"
    "================\n"
    "\n"
    "| # | Location | Opportunity | Technique | Risk |\n"
    "|---|----------|-------------|-----------|------|\n"
    "\n"
    "Then each change in detail\n"
    "\n"
    "VERIFICATION SUMMARY:\n"
    "  - Changes verified: N\n"
    "  - Changes revised: M\n"
    "  - Changes removed: K\n"
    "\n"
    "ANTI-PATTERNS CHECKED:\n"
    "  From Anti-Patterns section of each reference read:\n"
    "  - List each by name\n"
    "  - For each: [OK] or [FOUND: description]\n"
    "\n"
    "\n"
    "CRITICAL: STOP. Do NOT proceed to Execute step.\n"
    "Wait for explicit user approval before continuing."
)

CONTEXT_GATHERING = (
    "\n"
    "CONTEXT GATHERING (before category selection):\n"
    "\n"
    "First, gather context from available sources:\n"
    "  - Files already read in this conversation\n"
    "  - Prior analysis or problem descriptions\n"
    "  - Standard patterns you recognize\n"
    "\n"
    "FOR MULTIPLE RELATED PROMPTS:\n"
    "  <system_goal>\n"
    "    What is the HIGH-LEVEL goal of this prompt system?\n"
    "    What end-to-end workflow do these prompts enable?\n"
    "  </system_goal>\n"
    "  Then for EACH prompt, derive its purpose FROM the system goal.\n"
    "\n"
    "FOR A SINGLE PROMPT:\n"
    "  <prompt_purpose>\n"
    "    What problem does this prompt solve?\n"
    "    What inputs/outputs define its contract?\n"
    "    What does success look like?\n"
    "  </prompt_purpose>\n"
    "\n"
    "<observed_issues>\n"
    "  Map current/anticipated issues to categories:\n"
    "  - Reasoning: [skips steps, wrong decomposition, no visible trace]\n"
    "  - Consistency: [different outputs each run]\n"
    "  - Accuracy: [wrong facts, hallucinations]\n"
    "  - Context: [ignores input, distracted by noise]\n"
    "  - Format: [wrong structure, unparseable]\n"
    "  State 'None observed' for categories without issues.\n"
    "</observed_issues>\n"
    "\n"
    "WHEN TO ASK FOR CLARIFICATION:\n"
    "  - If the high-level goal is unclear from available context\n"
    "  - If you're uncertain which issues are actually occurring\n"
    "  - If success criteria are ambiguous\n"
    "  Use AskUserQuestion when genuinely uncertain -- not for standard patterns.\n"
    "  Better to confirm than to optimize the wrong thing."
)

UNDERSTAND_SIMPLE_INSTRUCTIONS = (
    "ARTICULATE what this prompt accomplishes:\n"
    "\n"
    "<purpose>\n"
    "  What is the high-level goal of this prompt?\n"
    "  What inputs does it expect?\n"
    "  What outputs should it produce?\n"
    "  What does SUCCESS look like?\n"
    "</purpose>\n"
    "\n"
    "<existing_techniques>\n"
    "  STEP BACK from the specific text. Identify the OVERALL PROMPTING\n"
    "  STRATEGY before examining individual lines:\n"
    "    What approach does this prompt take? (e.g., role-based, decomposition,\n"
    "    structured output, few-shot, chain-of-thought, verification loop)\n"
    "\n"
    "  Then identify SPECIFIC techniques already in use:\n"
    "  For each, quote the implementing text:\n"
    "    | Technique | Lines | Implementing Text | Quality |\n"
    "    |-----------|-------|-------------------|---------|\n"
    "  Quality ratings:\n"
    "    STRONG: Clear implementation, well-matched to task\n"
    "    PARTIAL: Present but incomplete, missing key elements\n"
    "    WEAK: Attempted but ineffective, wrong variant for context\n"
    "\n"
    "  COHESION between existing techniques:\n"
    "    - Do they reinforce or conflict with each other?\n"
    "    - Are there gaps where a connecting technique is expected?\n"
    "    - Is there redundancy (multiple techniques solving the same problem)?\n"
    "  If only 0-1 techniques found, state: 'Minimal existing technique usage.'\n"
    "</existing_techniques>\n"
    "\n"
    "<boundaries>\n"
    "  If this prompt delegates to sub-agents or other components:\n"
    "  - What is each recipient's bounded responsibility?\n"
    "  - What is the MINIMUM each recipient needs?\n"
    "  - What should NOT be passed to recipients? Why?\n"
    "  If no delegation exists, state: 'No delegation boundaries.'\n"
    "</boundaries>\n"
    + CONTEXT_GATHERING
)

TECHNIQUE_REVIEW = (
    "SYSTEMATIC TECHNIQUE REVIEW (two-phase):\n"
    "\n"
    "  PHASE 1 — EXISTING TECHNIQUE DETECTION:\n"
    "  For each technique in the Technique Selection Guide:\n"
    "  1. QUOTE the mechanism/implementation description from the reference\n"
    "  2. QUOTE text from the target prompt that IMPLEMENTS this (or 'Not present')\n"
    "  3. If present, rate implementation:\n"
    "     STRONG: Matches mechanism well, all key elements present\n"
    "     PARTIAL: Core idea present, missing elements (list what's missing)\n"
    "     WEAK: Attempted but misapplied (explain mismatch)\n"
    "\n"
    "  PHASE 2 — APPLICABLE TECHNIQUE IDENTIFICATION:\n"
    "  For each technique NOT already present (or rated WEAK/PARTIAL):\n"
    "  1. QUOTE the trigger condition from the table\n"
    "  2. QUOTE text from the target prompt that matches the trigger (or 'No match')\n"
    "  3. Verdict: ADD (not present, trigger matches) |\n"
    "             IMPROVE (present but PARTIAL/WEAK) |\n"
    "             NOT APPLICABLE (trigger doesn't match)\n"
    "  - Pay attention to 'Any task' triggers (foundational techniques)\n"
    "\n"
    "  PHASE 1 informs PHASE 2: A technique rated STRONG in Phase 1\n"
    "  is EXCLUDED from Phase 2 proposals (already well-implemented)."
)

TECHNIQUE_REVIEW_ECOSYSTEM = (
    TECHNIQUE_REVIEW + "\n"
    "  - Note techniques that apply to multiple prompts\n"
    "  - Note techniques used INCONSISTENTLY across prompts\n"
    "    (e.g., one prompt uses CoT well, another uses it poorly)"
)

CHANGE_FORMAT = (
    "Format each change:\n"
    "  === CHANGE N: [title] ===\n"
    "  Type: ADD | IMPROVE | ADJUST\n"
    "    ADD: New technique not currently present\n"
    "    IMPROVE: Strengthen existing PARTIAL/WEAK implementation\n"
    "    ADJUST: Modify for cohesion with other techniques\n"
    "  Line: [numbers]\n"
    "  Technique: [name] | Trigger: \"[quoted]\" | Effect: [quoted]\n"
    "  BEFORE: [original]\n"
    "  AFTER: [modified]\n"
    "  TRADEOFF: [downside or None]"
)

FIX_FORMAT = (
    "Format each fix:\n"
    "  === FIX N: [title] ===\n"
    "  Line: [numbers]\n"
    "  Technique: [name] | Trigger: \"[quoted]\" | Effect: [quoted]\n"
    "  BEFORE: [original]\n"
    "  AFTER: [modified]"
)

CHANGE_PRESENTATION = (
    "PRESENT CHANGES MADE:\n"
    "\n"
    "For EACH change applied, show:\n"
    "  === CHANGE N: [title] ===\n"
    "  Location: [file:lines]\n"
    "  BEFORE:\n"
    "  ```\n"
    "  [original text]\n"
    "  ```\n"
    "  AFTER:\n"
    "  ```\n"
    "  [modified text]\n"
    "  ```\n"
    "\n"
    "Then present the complete modified prompt(s)."
)

ANTI_PATTERN_AUDIT = (
    "ANTI-PATTERN FINAL AUDIT against modified prompt:\n"
    "\n"
    "Check each anti-pattern from the reference (including but not limited to):\n"
    "  [ ] Hedging Spiral: Does it encourage hesitation?\n"
    "  [ ] Everything-Is-Critical: Are emphasis markers overused?\n"
    "  [ ] Implicit Category Trap: Are categories explicit?\n"
    "  [ ] Negative Instruction Trap: Are directives affirmative?\n"
    "  [ ] (other anti-patterns from reference as applicable)"
)

ANTI_PATTERN_AUDIT_NONSTANDALONE = (
    ANTI_PATTERN_AUDIT + "\n"
    "\n"
    "CONTEXT-SPECIFIC (non-STANDALONE):\n"
    "  [ ] Context Mismatch: Does it have <system> or identity setup?\n"
    "      If YES -> FAIL: Remove wrapper/identity."
)

CATEGORY_SELECTION_INSTRUCTIONS = (
    "SELECT TECHNIQUE CATEGORIES based on your context gathering.\n"
    "\n"
    "Use your <system_goal> or <prompt_purpose> and <observed_issues>\n"
    "to inform selection. The issue-to-category mapping:\n"
    "  - Reasoning issues -> reasoning/decomposition, reasoning/elicitation\n"
    "  - Consistency issues -> correctness/sampling\n"
    "  - Accuracy issues -> correctness/verification, correctness/refinement\n"
    "  - Context issues -> context/reframing, context/augmentation\n"
    "  - Format issues -> structure\n"
    "\n"
    "If you have unresolved uncertainty about the goal or issues,\n"
    "use AskUserQuestion before proceeding.\n"
    "\n"
    "Available categories:\n"
    "\n"
    "  MANDATORY:\n"
    "    efficiency -- Output compression (applies to ALL prompts)\n"
    "\n"
    "  INCLUDE ALL THAT APPLY (minimum 3 total):\n"
    "\n"
    "    Reasoning quality:\n"
    "      reasoning/decomposition -- Multi-step, compositional problems\n"
    "      reasoning/elicitation -- Model skips steps, no visible trace\n"
    "\n"
    "    Output correctness:\n"
    "      correctness/sampling -- Inconsistent outputs across runs\n"
    "      correctness/verification -- Factual errors, hallucination\n"
    "      correctness/refinement -- Benefits from iteration\n"
    "\n"
    "    Input/context:\n"
    "      context/reframing -- Poorly framed, ambiguous instructions\n"
    "      context/augmentation -- Missing domain knowledge\n"
    "\n"
    "    Output format:\n"
    "      structure -- Needs specific format (code, JSON, tables)\n"
    "\n"
    "SELECTION RULES:\n"
    "  1. Start with efficiency (mandatory)\n"
    "  2. For EACH category, ask: 'Could this help?' not 'Is this the main problem?'\n"
    "  3. Minimum 3 categories total (more is fine)\n"
    "  4. Justify exclusions, not inclusions\n"
    "\n"
    "SELF-REFINEMENT:\n"
    "  For EACH category you DID NOT select:\n"
    "    - State the category\n"
    "    - Quote evidence from the prompt that this category cannot help\n"
    "  If you cannot quote evidence, include the category.\n"
    "\n"
    "OUTPUT FORMAT:\n"
    "  SELECTED: efficiency,reasoning/decomposition,correctness/verification,...\n"
    "  EXCLUDED with evidence:\n"
    "    - context/augmentation: '[quoted text]' shows complete domain context\n"
    "    - structure: '[quoted text]' shows free-form output is acceptable"
)

TECHNIQUE_AUDIT_INSTRUCTIONS = (
    "TECHNIQUE AUDIT TABLE (MANDATORY):\n"
    "\n"
    "For EVERY technique in EVERY injected reference file, create:\n"
    "\n"
    "| Technique | Source | Already Used? | Quality | Recommendation | Evidence |\n"
    "|-----------|--------|---------------|---------|----------------|----------|\n"
    "\n"
    "Column definitions:\n"
    "  Already Used?: YES (quote implementing text) / NO\n"
    "  Quality: STRONG / PARTIAL / WEAK / N/A (if not used)\n"
    "  Recommendation: KEEP (strong, no change) / IMPROVE (partial/weak) /\n"
    "                  ADD (not present, trigger matches) / SKIP (not applicable)\n"
    "  Evidence: For KEEP/IMPROVE: quote implementing text.\n"
    "            For ADD: quote trigger match. For SKIP: why trigger doesn't match.\n"
    "\n"
    "Rules:\n"
    "  - List ALL techniques from ALL injected files (no skipping)\n"
    "  - Check for existing usage BEFORE checking trigger applicability\n"
    "  - KEEP means 'already well-implemented, do not propose changes'\n"
    "\n"
    "This ensures existing techniques are recognized before new ones are proposed."
)


# ============================================================================
# CONFIGURATION
# ============================================================================

MODULE_PATH = "skills.prompt_engineer.optimize"

CATEGORY_TO_FILE = {
    "efficiency": "efficiency.md",
    "structure": "structure.md",
    "context/reframing": "context/reframing.md",
    "context/augmentation": "context/augmentation.md",
    "reasoning/decomposition": "reasoning/decomposition.md",
    "reasoning/elicitation": "reasoning/elicitation.md",
    "correctness/sampling": "correctness/sampling.md",
    "correctness/verification": "correctness/verification.md",
    "correctness/refinement": "correctness/refinement.md",
}

SCOPES = ("single-prompt", "ecosystem", "greenfield", "problem")

SCOPE_TOTAL_STEPS = {
    "single-prompt": 7,
    "ecosystem": 8,
    "greenfield": 7,
    "problem": 7,
}

INJECTION_STEP = {
    "single-prompt": 4,
    "ecosystem": 5,
    "greenfield": 4,
    "problem": 4,
}

# Scope-specific parts of the read guide (fallback when no --categories provided)
READ_GUIDE_VARIANTS = {
    "single-prompt": {
        "heading": "READ BASED ON DIAGNOSED PROBLEM:",
        "efficiency_note": "Output compression techniques apply to all prompts",
        "selection_intro": "THEN select based on problem type identified in Assess:",
        "categories": (
            "\n"
            "  Model can't reason through problem?\n"
            "    -> references/reasoning/decomposition.md (multi-step complexity)\n"
            "    -> references/reasoning/elicitation.md (skips steps, no trace)\n"
            "\n"
            "  Model reasons but gives wrong answers?\n"
            "    -> references/correctness/sampling.md (inconsistent outputs)\n"
            "    -> references/correctness/verification.md (factual errors)\n"
            "    -> references/correctness/refinement.md (needs iteration)\n"
            "\n"
            "  Context issues (noisy, missing info)?\n"
            "    -> references/context/reframing.md (poorly framed)\n"
            "    -> references/context/augmentation.md (missing knowledge)\n"
            "\n"
            "  Need specific output format?\n"
            "    -> references/structure.md (code, JSON, tables)"
        ),
        "footer": (
            "Extract: Technique Selection Guide from each reference read.\n"
            "For each technique: note Trigger Condition and Tradeoffs."
        ),
    },
    "ecosystem": {
        "heading": "READ BASED ON DIAGNOSED PROBLEMS:",
        "efficiency_note": "Output compression techniques apply to all prompts",
        "selection_intro": "FOR EACH PROMPT, select based on its diagnosed problem:",
        "categories": (
            "\n"
            "  Model can't reason through problem?\n"
            "    -> references/reasoning/decomposition.md\n"
            "    -> references/reasoning/elicitation.md\n"
            "\n"
            "  Model reasons but wrong answers?\n"
            "    -> references/correctness/sampling.md\n"
            "    -> references/correctness/verification.md\n"
            "    -> references/correctness/refinement.md\n"
            "\n"
            "  Context issues?\n"
            "    -> references/context/reframing.md\n"
            "    -> references/context/augmentation.md\n"
            "\n"
            "  Need specific format?\n"
            "    -> references/structure.md"
        ),
        "footer": (
            "Extract: Technique Selection Guide from each reference.\n"
            "Note which techniques apply to multiple prompts in ecosystem."
        ),
    },
    "greenfield": {
        "heading": "READ BASED ON REQUIREMENTS:",
        "efficiency_note": "Output compression techniques apply to all prompts",
        "selection_intro": "SELECT based on task requirements from Assess:",
        "categories": (
            "\n"
            "  Task requires multi-step reasoning?\n"
            "    -> references/reasoning/decomposition.md\n"
            "    -> references/reasoning/elicitation.md\n"
            "\n"
            "  Task needs high accuracy/consistency?\n"
            "    -> references/correctness/sampling.md\n"
            "    -> references/correctness/verification.md\n"
            "\n"
            "  Task involves long/noisy context?\n"
            "    -> references/context/reframing.md\n"
            "    -> references/context/augmentation.md\n"
            "\n"
            "  Task needs structured output?\n"
            "    -> references/structure.md"
        ),
        "footer": (
            "Extract: Technique Selection Guide from each reference.\n"
            "Match techniques to requirements and execution context."
        ),
    },
    "problem": {
        "heading": "READ BASED ON DIAGNOSED FAILURE:",
        "efficiency_note": "Output compression often relevant to problem fixes",
        "selection_intro": "SELECT based on problem class from Diagnose step:",
        "categories": (
            "\n"
            "  Reasoning failures (skips steps, wrong decomposition)?\n"
            "    -> references/reasoning/decomposition.md\n"
            "    -> references/reasoning/elicitation.md\n"
            "\n"
            "  Consistency failures (different answers each time)?\n"
            "    -> references/correctness/sampling.md\n"
            "\n"
            "  Accuracy failures (wrong facts, hallucinations)?\n"
            "    -> references/correctness/verification.md\n"
            "\n"
            "  Quality failures (output needs polish)?\n"
            "    -> references/correctness/refinement.md\n"
            "\n"
            "  Context failures (ignores info, distracted)?\n"
            "    -> references/context/reframing.md\n"
            "\n"
            "  Format failures (wrong structure)?\n"
            "    -> references/structure.md"
        ),
        "footer": "Focus on techniques matching the specific failure mode.",
    },
}


# ============================================================================
# MESSAGE TEMPLATES
# ============================================================================

# --- STEP 2: ASSESS ----------------------------------------------------------

ASSESS_SINGLE_INSTRUCTIONS = (
    "PRIOR CONTEXT: Incorporate any relevant analysis, problem descriptions,\n"
    "or preferences from earlier in this conversation.\n"
    "\n"
    "READ the prompt file. Classify complexity:\n"
    "  SIMPLE: <20 lines, single purpose, no conditionals\n"
    "  COMPLEX: multiple sections, conditionals, tool orchestration\n"
    "\n"
    "Document OPERATING CONTEXT:\n"
    "  - Interaction: single-shot or conversational?\n"
    "  - Agent type: tool-use, coding, analysis, general?\n"
    "  - Failure modes: what goes wrong when this fails?"
)

ASSESS_ECOSYSTEM_INSTRUCTIONS = (
    "PRIOR CONTEXT: Incorporate any relevant analysis, problem descriptions,\n"
    "or preferences from earlier in this conversation.\n"
    "\n"
    "READ all prompt-containing files in scope.\n"
    "\n"
    "MAP the ecosystem:\n"
    "  - List each prompt with location (file:lines)\n"
    "  - Identify relationships: orchestrator, subagent, shared-context\n"
    "  - Note terminology that should be consistent across prompts\n"
    "\n"
    "Create interaction table:\n"
    "  | Prompt | File:Lines | Receives From | Sends To | Shared Terms |\n"
    "  |--------|------------|---------------|----------|--------------|\n"
    "\n"
    "For each prompt, identify (at minimum):\n"
    "  - Input sources (which prompts/systems feed it)\n"
    "  - Output consumers (which prompts/systems consume its output)\n"
    "  - Terminology that MUST be consistent across prompts\n"
    "\n"
    "For EACH prompt, document:\n"
    "  - Purpose and role in the ecosystem\n"
    "  - What it receives from / passes to other prompts\n"
    "  - Complexity classification"
)

ASSESS_GREENFIELD_INSTRUCTIONS = (
    "PRIOR CONTEXT: Incorporate any relevant analysis, problem descriptions,\n"
    "or preferences from earlier in this conversation.\n"
    "\n"
    "UNDERSTAND requirements (core questions, not exhaustive):\n"
    "  - What task should the prompt accomplish?\n"
    "  - What inputs will it receive?\n"
    "  - What outputs should it produce?\n"
    "  - What constraints exist? (length, format, tone)\n"
    "\n"
    "DETERMINE execution context (CRITICAL - affects scaffold):\n"
    "  STANDALONE: Full system prompt with complete control\n"
    "    -> Prompt IS the system message, can define identity/role\n"
    "  SKILL: Injected into existing agent (e.g., Claude Code skill)\n"
    "    -> NO <system> wrapper, NO identity setup, task-focused\n"
    "  SUB-AGENT: Task instruction passed to delegated agent\n"
    "    -> Bounded task description, minimal context, NO workflow overview\n"
    "  COMPONENT: Fragment composing with other prompts\n"
    "    -> Interface-focused, expects external orchestration\n"
    "\n"
    "  Ask user if unclear. State context with rationale.\n"
    "\n"
    "INFER architecture (single-turn vs multi-turn):\n"
    "  SINGLE-TURN when: discrete task, one input -> one output\n"
    "  MULTI-TURN when: refinement loops, verification, context accumulation\n"
    "\n"
    "  NEVER suggest subagents or HITL unless user explicitly requests.\n"
    "  State architecture choice with rationale.\n"
    "\n"
    "IDENTIFY edge cases (examples to consider):\n"
    "  - What happens with ambiguous input?\n"
    "  - What errors are expected?\n"
    "  - What should NOT happen?"
)

DIAGNOSE_PROBLEM_INSTRUCTIONS = (
    "PRIOR CONTEXT: Incorporate any relevant analysis, problem descriptions,\n"
    "or preferences from earlier in this conversation.\n"
    "\n"
    "UNDERSTAND the problem:\n"
    "  - What is the observed behavior?\n"
    "  - What is the expected behavior?\n"
    "  - When does it occur? (always / sometimes / conditions)\n"
    "\n"
    "READ relevant prompt(s) if they exist.\n"
    "\n"
    "CLASSIFY the problem (primary categories):\n"
    "  PROMPTING: Can be addressed by technique application\n"
    "  CAPABILITY: Model fundamentally cannot do this\n"
    "  ARCHITECTURE: Needs structural change, not technique\n"
    "  EXTERNAL: Problem is in surrounding code, not prompt\n"
    "  (problem may span multiple categories)\n"
    "\n"
    "If NOT a prompting issue: state clearly and STOP.\n"
    "If prompting issue: identify lines that may contribute."
)

# --- STEP 3: UNDERSTAND ------------------------------------------------------

UNDERSTAND_ECOSYSTEM_INSTRUCTIONS = (
    "ARTICULATE semantic understanding before optimization.\n"
    "\n"
    "<system_understanding>\n"
    "  What is this workflow accomplishing end-to-end?\n"
    "  What enters the system? What does it produce?\n"
    "  What invariants must be maintained across components?\n"
    "</system_understanding>\n"
    "\n"
    "<prompt_understanding>\n"
    "  For EACH prompt, answer:\n"
    "  - What does this prompt ACCOMPLISH (purpose, not description)?\n"
    "  - Why is it positioned HERE in the sequence?\n"
    "  - What would BREAK if this prompt were removed?\n"
    "</prompt_understanding>\n"
    "\n"
    "<handoff_understanding>\n"
    "  For EACH delegation (A -> B), answer:\n"
    "  - What is B's BOUNDED responsibility? (specific task, not 'help')\n"
    "  - What is the MINIMUM information B needs to accomplish that?\n"
    "  - What does B ALREADY KNOW from its own context?\n"
    "  - What must NOT cross this boundary? Why?\n"
    "    (orchestrator internals, workflow steps, other components' state)\n"
    "</handoff_understanding>\n"
    "\n"
    "INVERT THE DEFAULT QUESTION:\n"
    "  Ask 'what is the MINIMUM B needs?' not 'what might help B?'\n"
    "\n"
    "CONTRASTIVE EXAMPLES:\n"
    "\n"
    "<example type='CORRECT'>\n"
    "  SKILL.md: 'Invoke the script. The script IS the workflow.'\n"
    "  WHY: Main agent delegates completely. No internals exposed.\n"
    "</example>\n"
    "<example type='INCORRECT'>\n"
    "  SKILL.md: 'Invoke the script. It has 6 steps: 1. Triage...'\n"
    "  WHY: Main agent doesn't need workflow internals.\n"
    "</example>\n"
    "\n"
    "<example type='CORRECT'>\n"
    "  Sub-agent: 'Execute step 1. <invoke cmd=\"...--step 1\" />'\n"
    "  WHY: Sub-agent needs only its step instructions.\n"
    "</example>\n"
    "<example type='INCORRECT'>\n"
    "  Sub-agent: 'Execute step 1. There are 8 steps: 1. Context...'\n"
    "  WHY: Sub-agent discovers workflow during execution. Overview is noise.\n"
    "</example>\n"
    + CONTEXT_GATHERING
)

UNDERSTAND_GREENFIELD_INSTRUCTIONS = (
    "ARTICULATE semantic understanding of what you're building:\n"
    "\n"
    "<purpose>\n"
    "  What is the high-level goal of this prompt?\n"
    "  What inputs does it expect?\n"
    "  What outputs should it produce?\n"
    "  What does SUCCESS look like?\n"
    "</purpose>\n"
    "\n"
    "<boundaries>\n"
    "  If this prompt will delegate to sub-agents or components:\n"
    "  - What is each recipient's bounded responsibility?\n"
    "  - What is the MINIMUM each recipient needs?\n"
    "  - What should NOT be passed to recipients? Why?\n"
    "  If no delegation planned, state: 'No delegation boundaries.'\n"
    "</boundaries>\n"
    "\n"
    "CONTEXT MISMATCH ANTI-PATTERN (review before Design):\n"
    "\n"
    "<incorrect>\n"
    "  Context: SKILL (Claude Code)\n"
    "  Output: <system>You are a helpful assistant that...</system>\n"
    "  WHY WRONG: Skills are injected into existing conversation.\n"
    "             The agent already has identity. Adding <system> is nonsensical.\n"
    "</incorrect>\n"
    "<correct>\n"
    "  Context: SKILL (Claude Code)\n"
    "  Output: 'When user requests X, invoke script Y. The script handles Z.'\n"
    "  WHY RIGHT: Task-focused, no identity, assumes existing agent context.\n"
    "</correct>\n"
    "\n"
    "<incorrect>\n"
    "  Context: SUB-AGENT\n"
    "  Output: 'You are part of a 6-step workflow. Step 1 does A, step 2...'\n"
    "  WHY WRONG: Sub-agent needs only its task. Workflow overview is noise.\n"
    "</incorrect>\n"
    "<correct>\n"
    "  Context: SUB-AGENT\n"
    "  Output: 'Search for files matching pattern X. Return paths and sizes.'\n"
    "  WHY RIGHT: Bounded task, minimal context, clear output contract.\n"
    "</correct>"
)

# --- STEP 4: PLAN / VERIFY / DESIGN / TARGET --------------------------------

PLAN_SINGLE_INSTRUCTIONS = (
    "BLIND identification of opportunities (quote line evidence):\n"
    "  List as 'Lines X-Y: [issue]'\n"
    "\n"
    + TECHNIQUE_REVIEW + "\n"
    "\n"
    "TECHNIQUE COHESION ANALYSIS (after audit):\n"
    "  Consider ALL techniques (existing + proposed) as a set:\n"
    "  - SYNERGIES: Which techniques reinforce each other?\n"
    "    (Reference Composability Notes in the loaded references)\n"
    "  - CONFLICTS: Which techniques interfere or create contradictions?\n"
    "    (Reference Composability 'Avoid combining' warnings)\n"
    "  - GAPS: Is a connecting technique expected but missing?\n"
    "    (e.g., decomposition without verification, CoT without output format)\n"
    "  If conflicts found: adjust proposals to resolve.\n"
    "  If gaps found: add proposals to fill.\n"
    "\n"
    + CHANGE_FORMAT + "\n"
    "\n"
    "Include TECHNIQUE DISPOSITION summary."
)

VERIFY_UNDERSTANDING_INSTRUCTIONS = (
    "TEST understanding with counterfactual questions (OPEN, not yes/no).\n"
    "\n"
    "For EACH handoff (A -> B):\n"
    "  Q: DESCRIBE what could be REMOVED from this handoff without breaking B.\n"
    "  A: [list specific items currently included but not necessary]\n"
    "\n"
    "  Q: EXPLAIN what would fail and HOW if we added orchestrator internals\n"
    "     (workflow steps, state, other components) to this handoff.\n"
    "  A: [describe mechanism: confusion, coupling, scope creep, etc.]\n"
    "\n"
    "For the ECOSYSTEM:\n"
    "  Q: If component X were removed, WHICH components break and WHY?\n"
    "  A: [trace dependencies based on your understanding]\n"
    "\n"
    "CONSISTENCY CHECK:\n"
    "  Compare answers to <handoff_understanding>.\n"
    "  Revise understanding if inconsistent."
)

DESIGN_GREENFIELD_INSTRUCTIONS = (
    "SELECT applicable techniques for the design:\n"
    "  Based on requirements, architecture, and EXECUTION CONTEXT from Step 2\n"
    "\n"
    "SCAFFOLD based on execution context:\n"
    "\n"
    "  IF STANDALONE:\n"
    "    - Identity/role establishment (<system>You are...)\n"
    "    - Task description\n"
    "    - Input handling\n"
    "    - Output format\n"
    "    - Constraints and rules\n"
    "\n"
    "  IF SKILL (injected into existing agent):\n"
    "    - Invocation trigger (when to activate)\n"
    "    - Task instructions (imperative, action-focused)\n"
    "    - Input/output contract\n"
    "    - Constraints specific to this skill\n"
    "    ASSUME: Agent already has identity. Write task-focused instructions only.\n"
    "\n"
    "  IF SUB-AGENT (delegated task):\n"
    "    - Bounded task description\n"
    "    - Required inputs/outputs\n"
    "    - Success criteria\n"
    "    ASSUME: Sub-agent discovers context during execution. Write bounded task only.\n"
    "\n"
    "  IF COMPONENT (composable fragment):\n"
    "    - Interface specification\n"
    "    - Expected inputs from upstream\n"
    "    - Outputs for downstream\n"
    "    ASSUME: External orchestrator provides context. Write interface only.\n"
    "\n"
    "For each section, match techniques:\n"
    "  === SECTION: [name] ===\n"
    "  Technique: [name] | Trigger: \"[quoted]\"\n"
    "  DRAFT: [proposed content]\n"
    "  RATIONALE: [why this technique here]\n"
    "\n"
    "CONTEXT-CORRECTNESS CHECK (before drafting):\n"
    "\n"
    "<example context='SKILL' type='INCORRECT'>\n"
    "  <system>You are a helpful code review assistant...</system>\n"
    "  WHY WRONG: Skills inject into existing agent. Agent has identity.\n"
    "</example>\n"
    "<example context='SKILL' type='CORRECT'>\n"
    "  When user requests code review, analyze the diff and provide feedback.\n"
    "  Focus on: correctness, style, potential bugs.\n"
    "  WHY RIGHT: Task-focused. No identity. Imperative instructions.\n"
    "</example>\n"
    "\n"
    "<example context='SUB-AGENT' type='INCORRECT'>\n"
    "  You are step 3 of a 6-step workflow. Steps 1-2 have gathered context...\n"
    "  WHY WRONG: Sub-agent needs only its task. Workflow is orchestrator's concern.\n"
    "</example>\n"
    "<example context='SUB-AGENT' type='CORRECT'>\n"
    "  Search for files matching pattern. Return paths and sizes.\n"
    "  WHY RIGHT: Bounded task. Clear contract. No workflow knowledge.\n"
    "</example>\n"
    "\n"
    "WRITE complete prompt draft."
)

TARGET_FIX_PROBLEM_INSTRUCTIONS = (
    "REVERSE LOOKUP - which techniques address this problem class?\n"
    "  Review Technique Selection Guide for matching triggers\n"
    "\n"
    "For each candidate technique:\n"
    "  - QUOTE trigger condition\n"
    "  - Explain how problem matches trigger\n"
    "  - Propose specific change\n"
    "\n"
    + FIX_FORMAT + "\n"
    "  Expected effect: [how this fixes the problem]"
)

# --- STEP 5: REFINE / PLAN --------------------------------------------------

PLAN_ECOSYSTEM_INSTRUCTIONS = (
    "FOR EACH PROMPT - identify opportunities:\n"
    "  List as 'File:Lines X-Y: [issue]'\n"
    "\n"
    "FOR THE ECOSYSTEM - identify cross-prompt issues:\n"
    "  Using your interaction table AND your <handoff_understanding>:\n"
    "  - For each Shared Term: check consistency across listed prompts\n"
    "  - For each Receives From/Sends To pair: check handoff clarity\n"
    "  - For each handoff: is it MINIMAL?\n"
    "    REJECT changes that add information the receiver doesn't need.\n"
    "    REJECT changes that leak orchestrator internals.\n"
    "\n"
    "  HANDOFF MINIMALISM TEST for each proposed change:\n"
    "    Ask: 'Would the receiver need to change if this internal changed?'\n"
    "    NO -> creates coupling without benefit -> EXCLUDE\n"
    "    YES -> necessary information -> INCLUDE\n"
    "  - Conflicting instructions\n"
    "  - Redundant specifications\n"
    "  List as 'ECOSYSTEM: [issue across File1, File2]'\n"
    "\n"
    + TECHNIQUE_REVIEW_ECOSYSTEM + "\n"
    "\n"
    + CHANGE_FORMAT + "\n"
    "Note which changes affect single file vs multiple."
)

# --- STEP 7: EXECUTE / CREATE / APPLY / APPROVE -----------------------------

EXECUTE_SINGLE_INSTRUCTIONS = (
    "Apply each approved change to the prompt file.\n"
    "\n"
    "INTEGRATION CHECKS (verify at minimum):\n"
    "  - Cross-section references correct?\n"
    "  - Terminology consistent?\n"
    "  - Priority markers not overused? (max 2-3 CRITICAL/NEVER)\n"
    "\n"
    + ANTI_PATTERN_AUDIT + "\n"
    "\n"
    + CHANGE_PRESENTATION
)

CREATE_GREENFIELD_INSTRUCTIONS = (
    "CREATE the prompt file(s).\n"
    "\n"
    "INTEGRATION CHECKS (verify at minimum):\n"
    "  - All requirements addressed?\n"
    "  - Edge cases handled?\n"
    "  - Structure follows chosen architecture?\n"
    "\n"
    + ANTI_PATTERN_AUDIT_NONSTANDALONE + "\n"
    "\n"
    + CHANGE_PRESENTATION
)

APPLY_FIX_PROBLEM_INSTRUCTIONS = (
    "Apply targeted fix to the prompt.\n"
    "\n"
    "VERIFY the fix addresses the stated problem:\n"
    "  - Does the change match the diagnosed cause?\n"
    "  - Could it introduce new issues?\n"
    "\n"
    + CHANGE_PRESENTATION
)

# --- STEP 8: EXECUTE (ECOSYSTEM ONLY) ---------------------------------------

EXECUTE_ECOSYSTEM_INSTRUCTIONS = (
    "Apply changes to each file.\n"
    "\n"
    "ECOSYSTEM INTEGRATION CHECKS:\n"
    "  - Terminology aligned across all files?\n"
    "  - Handoffs clear and consistent?\n"
    "  - No conflicting instructions introduced?\n"
    "\n"
    + ANTI_PATTERN_AUDIT + "\n"
    "\n"
    + CHANGE_PRESENTATION
)


# ============================================================================
# MESSAGE BUILDERS
# ============================================================================


def build_read_guide(scope: str) -> str:
    """Build scope-specific read guide from shared template + variant parts."""
    v = READ_GUIDE_VARIANTS[scope]
    return (
        v["heading"] + "\n"
        "\n"
        "All references are in the `references/` subdirectory of the prompt-engineer\n"
        "skill directory. NOTE: *NOT* the prompt_engineer scripts directory, but the\n"
        "prompt-engineer skill directory, which also contains the SKILL.md file.\n"
        "\n"
        "ALWAYS read: references/efficiency.md\n"
        "  -> " + v["efficiency_note"] + "\n"
        "\n"
        + v["selection_intro"] + "\n"
        + v["categories"] + "\n"
        "\n"
        + v["footer"] + "\n"
        "\n"
        "NEVER read papers/**/* - use references/ only."
    )


READ_GUIDES = {s: build_read_guide(s) for s in SCOPES}


def get_references_dir() -> Path:
    """Path to prompt-engineer/references/ directory.

    Traverses from scripts/skills/prompt_engineer/ up to scripts/,
    then into sibling prompt-engineer/references/.
    """
    return Path(__file__).parent.parent.parent.parent / "prompt-engineer" / "references"


def load_and_format_files(categories: list[str]) -> str:
    """Load reference files for categories, return formatted blocks joined by newlines."""
    refs_dir = get_references_dir()
    blocks = []
    for cat in categories:
        if cat not in CATEGORY_TO_FILE:
            valid = ", ".join(sorted(CATEGORY_TO_FILE.keys()))
            sys.exit(f"ERROR: Unknown category '{cat}'. Valid: {valid}")
        rel_path = CATEGORY_TO_FILE[cat]
        full_path = refs_dir / rel_path
        if not full_path.exists():
            sys.exit(f"ERROR: Reference file not found: {full_path}")
        content = full_path.read_text()
        blocks.append(format_file_content(f"references/{rel_path}", content))
    return "\n\n".join(blocks)


def build_next_command(step: int, scope: str | None, categories: list[str] | None) -> str | None:
    """Build CLI command for the next workflow step.

    Three special cases:
    - Step 1 (triage): scope unknown, uses placeholder
    - Step N-1 (pre-injection): appends --categories <SELECTED_CATEGORIES> placeholder
    - Steps with categories: passes --categories through to subsequent steps
    """
    base = f'python3 -m {MODULE_PATH}'

    if step == 1:
        return f'{base} --step 2 --scope <determined-scope>'

    total = SCOPE_TOTAL_STEPS[scope]
    if step >= total:
        return None

    cmd = f'{base} --step {step + 1} --scope {scope}'

    inj_step = INJECTION_STEP.get(scope)
    if inj_step:
        if step == inj_step - 1 and not categories:
            cmd += ' --categories <SELECTED_CATEGORIES>'
        elif categories:
            cmd += f' --categories {",".join(categories)}'

    return cmd


# ============================================================================
# STEP DEFINITIONS
# ============================================================================

SCOPE_STEPS = {
    "single-prompt": {
        1: ("Triage", TRIAGE_INSTRUCTIONS),
        2: ("Assess", ASSESS_SINGLE_INSTRUCTIONS),
        3: ("Understand", UNDERSTAND_SIMPLE_INSTRUCTIONS),
        4: ("Plan", PLAN_SINGLE_INSTRUCTIONS),
        5: ("Refine", REFINE_INSTRUCTIONS),
        6: ("Approve", APPROVE_INSTRUCTIONS),
        7: ("Execute", EXECUTE_SINGLE_INSTRUCTIONS),
    },
    "ecosystem": {
        1: ("Triage", TRIAGE_INSTRUCTIONS),
        2: ("Assess", ASSESS_ECOSYSTEM_INSTRUCTIONS),
        3: ("Understand", UNDERSTAND_ECOSYSTEM_INSTRUCTIONS),
        4: ("Verify Understanding", VERIFY_UNDERSTANDING_INSTRUCTIONS),
        5: ("Plan", PLAN_ECOSYSTEM_INSTRUCTIONS),
        6: ("Refine", REFINE_INSTRUCTIONS),
        7: ("Approve", APPROVE_INSTRUCTIONS),
        8: ("Execute", EXECUTE_ECOSYSTEM_INSTRUCTIONS),
    },
    "greenfield": {
        1: ("Triage", TRIAGE_INSTRUCTIONS),
        2: ("Assess Requirements", ASSESS_GREENFIELD_INSTRUCTIONS),
        3: ("Understand", UNDERSTAND_GREENFIELD_INSTRUCTIONS),
        4: ("Design", DESIGN_GREENFIELD_INSTRUCTIONS),
        5: ("Refine", REFINE_INSTRUCTIONS),
        6: ("Approve", APPROVE_INSTRUCTIONS),
        7: ("Create", CREATE_GREENFIELD_INSTRUCTIONS),
    },
    "problem": {
        1: ("Triage", TRIAGE_INSTRUCTIONS),
        2: ("Diagnose", DIAGNOSE_PROBLEM_INSTRUCTIONS),
        3: ("Understand", UNDERSTAND_SIMPLE_INSTRUCTIONS),
        4: ("Target Fix", TARGET_FIX_PROBLEM_INSTRUCTIONS),
        5: ("Refine", REFINE_INSTRUCTIONS),
        6: ("Approve", APPROVE_INSTRUCTIONS),
        7: ("Apply Fix", APPLY_FIX_PROBLEM_INSTRUCTIONS),
    },
}


# ============================================================================
# OUTPUT FORMATTING
# ============================================================================


def format_output(step: int, scope: str | None, categories: list[str] | None) -> str:
    """Format complete step output for the given step and scope.

    File injection logic lives here (not in step content) because it augments
    the step body based on runtime state (--categories presence and step
    position relative to INJECTION_STEP).
    """
    if step == 1:
        title, body = "Triage", TRIAGE_INSTRUCTIONS
        scope_label = ""
    else:
        if scope not in SCOPE_STEPS:
            return f"ERROR: Unknown scope '{scope}'"
        steps = SCOPE_STEPS[scope]
        if step not in steps:
            return f"ERROR: Invalid step {step} for scope '{scope}'"
        title, body = steps[step]
        scope_label = f"Scope: {scope.upper()}\n\n"

    # File injection: augment body based on injection step position
    if scope and step > 1:
        inj_step = INJECTION_STEP.get(scope)
        if inj_step:
            if step == inj_step - 1 and not categories:
                # Pre-injection step: LLM selects categories for next invocation
                body = f"{body}\n\n{CATEGORY_SELECTION_INSTRUCTIONS}"
            elif step == inj_step:
                if categories:
                    # Injection step with files: embed references + technique audit
                    file_blocks = load_and_format_files(categories)
                    body = (
                        f"TECHNIQUE REFERENCES\n"
                        f"The following reference files have been loaded based on your "
                        f"category selection:\n\n"
                        f"{file_blocks}\n\n"
                        f"{body}\n\n"
                        f"{TECHNIQUE_AUDIT_INSTRUCTIONS}"
                    )
                else:
                    # Injection step without files: read guide fallback
                    body = f"{READ_GUIDES[scope]}\n\n{body}"

    body = scope_label + body
    next_cmd = build_next_command(step, scope, categories)
    return format_step(body, next_cmd or "", title=f"PROMPT ENGINEER - {title}")


# ============================================================================
# ENTRY POINT
# ============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Prompt Engineer - Scope-adaptive prompt optimization",
        epilog="Step 1: triage (determines scope). Steps 2+: scope-specific workflow.",
    )
    parser.add_argument("--step", type=int, required=True)
    parser.add_argument(
        "--scope",
        choices=list(SCOPES),
        default=None,
        help="Required for steps 2+. Run step 1 first to determine scope.",
    )
    parser.add_argument(
        "--categories",
        type=str,
        default=None,
        help="Comma-separated technique categories to inject (e.g., efficiency,reasoning/decomposition)",
    )
    args = parser.parse_args()

    if args.step < 1:
        sys.exit("ERROR: --step must be >= 1")
    if args.step > 1 and args.scope is None:
        sys.exit("ERROR: --scope required for steps 2+. Run step 1 first to determine scope.")
    if args.scope and args.step > SCOPE_TOTAL_STEPS[args.scope]:
        sys.exit(f"ERROR: Step {args.step} exceeds total ({SCOPE_TOTAL_STEPS[args.scope]}) for scope '{args.scope}'")

    categories = None
    if args.categories:
        categories = [c.strip() for c in args.categories.split(",") if c.strip()]

    print(format_output(args.step, args.scope, categories))


if __name__ == "__main__":
    main()
