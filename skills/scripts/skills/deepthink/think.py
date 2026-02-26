#!/usr/bin/env python3
"""
DeepThink Skill - Structured reasoning for open-ended analytical questions.

Fourteen-step workflow (1-14):
  1. Context Clarification  - Remove bias from input (S2A)
  2. Abstraction            - Domain, first principles, key concepts
  3. Characterization       - Question type, answer structure, mode determination
  4. Analogical Recall      - Direct/cross-domain analogies, anti-patterns
  5. Planning               - Sub-questions, success criteria
  6. Sub-Agent Design       - Generate sub-agent task definitions (Full only)
  7. Design Critique        - Coverage, overlap, appropriateness (Full only)
  8. Design Revision        - Revise based on critique (Full only)
  9. Dispatch               - Launch sub-agents in parallel (Full only)
  10. Quality Gate          - Filter low-quality outputs (Full only)
  11. Aggregation           - Agreement/disagreement maps (Full only)
  12. Initial Synthesis     - First-pass integration
  13. Iterative Refinement  - Verification loop until confident
  14. Formatting & Output   - Format and present final answer

Two modes: Full (all steps) and Quick (skips 6-11).
"""

import argparse
import sys

from skills.lib.workflow.prompts import format_step, roster_dispatch


# ============================================================================
# CONFIGURATION
# ============================================================================

MODULE_PATH = "skills.deepthink.think"
SUBAGENT_MODULE_PATH = "skills.deepthink.subagent"
MAX_ITERATIONS = 5


# ============================================================================
# MESSAGE TEMPLATES
# ============================================================================

# --- STEP 1: CONTEXT_CLARIFICATION ------------------------------------------

CONTEXT_CLARIFICATION_INSTRUCTIONS = (
    "You are an expert analytical reasoner tasked with systematic deep analysis.\n"
    "\n"
    "PART 0 - CONTEXT SUFFICIENCY:\n"
    "  Before analyzing, assess whether you have sufficient context:\n"
    "\n"
    "  A. EXISTING CONTEXT: What relevant information is already in this conversation?\n"
    "     (prior codebase analysis, problem discoveries, architecture understanding)\n"
    "\n"
    "  B. SUFFICIENCY JUDGMENT: For this question, is existing context:\n"
    "     - SUFFICIENT: Can reason directly from available information\n"
    "     - PARTIAL: Have some context but need targeted exploration\n"
    "     - INSUFFICIENT: Need exploration before meaningful reasoning\n"
    "\n"
    "  C. IF NOT SUFFICIENT: Before proceeding to Part A, explore:\n"
    "     - Use Read/Glob/Grep tools to gather necessary context\n"
    "     - Focus on specific files/patterns relevant to the question\n"
    "     - Stop exploring when you have enough to reason -- avoid over-exploration\n"
    "     - Document what you found in a brief EXPLORATION SUMMARY\n"
    "\n"
    "  If context is SUFFICIENT, proceed directly to Part A.\n"
    "\n"
    "Extract objective, relevant content from the user's question.\n"
    "\n"
    "Read the question again before proceeding.\n"
    "\n"
    "Separate it from framing, opinion, or irrelevant information.\n"
    "\n"
    "PART A - CLARIFIED QUESTION:\n"
    "  Restate the core question in neutral, objective terms.\n"
    "  Remove leading language, embedded opinions, or assumptions.\n"
    "  If multiple sub-questions exist, list them clearly.\n"
    "\n"
    "PART B - EXTRACTED CONTEXT:\n"
    "  List factual context from input relevant to answering.\n"
    "  Exclude opinions, preferences, or irrelevant details.\n"
    "\n"
    "PART C - NOTED BIASES:\n"
    "  Identify framing effects, leading language, or embedded assumptions.\n"
    "  Note these so subsequent steps can guard against them.\n"
    "  If none detected, state 'No significant biases detected.'\n"
    "\n"
    "OUTPUT FORMAT:\n"
    "```\n"
    "CLARIFIED QUESTION:\n"
    "[neutral restatement]\n"
    "\n"
    "EXTRACTED CONTEXT:\n"
    "- [fact 1]\n"
    "- [fact 2]\n"
    "\n"
    "NOTED BIASES:\n"
    "- [bias 1] or 'No significant biases detected.'\n"
    "```\n"
    "\n"
    "The CLARIFIED QUESTION will be used as the working question for all subsequent steps."
)

# --- STEP 2: ABSTRACTION ----------------------------------------------------

ABSTRACTION_INSTRUCTIONS = (
    "Before diving into specifics, step back and identify high-level context.\n"
    "Work through this thoroughly. Avoid shortcuts. Show reasoning step by step.\n"
    "\n"
    "PART A - DOMAIN:\n"
    "  What field or domain does this question primarily belong to?\n"
    "  Are there adjacent domains that might offer relevant perspectives?\n"
    "\n"
    "PART B - FIRST PRINCIPLES:\n"
    "  What fundamental principles should guide any answer?\n"
    "  What would an expert consider non-negotiable constraints or truths?\n"
    "\n"
    "PART C - KEY CONCEPTS:\n"
    "  What core concepts must be understood to answer well?\n"
    "  Define any terms that might be ambiguous or contested.\n"
    "\n"
    "PART D - WHAT MAKES THIS HARD:\n"
    "  Why isn't the answer obvious? What makes this genuinely difficult?\n"
    "  Is it contested? Under-specified? Trade-off-laden? Novel?\n"
    "\n"
    "OUTPUT FORMAT:\n"
    "```\n"
    "DOMAIN: [primary domain]\n"
    "ADJACENT DOMAINS: [list]\n"
    "\n"
    "FIRST PRINCIPLES:\n"
    "- [principle 1]\n"
    "- [principle 2]\n"
    "\n"
    "KEY CONCEPTS:\n"
    "- [concept]: [definition if ambiguous]\n"
    "\n"
    "DIFFICULTY ANALYSIS:\n"
    "[why this is hard]\n"
    "\n"
    "ASSUMPTIONS:\n"
    "- [statement] | TYPE: [BLOCKING/MATERIAL/DEFAULT] | VERIFIED: [yes/no/needs-user]\n"
    "```\n"
    "\n"
    "PART E - ASSUMPTIONS:\n"
    "  Identify assumptions about problem scope, interpretation, or constraints.\n"
    "  For EACH assumption:\n"
    "\n"
    "  1. STATEMENT: What is being assumed\n"
    "  2. TYPE: Classify using this decision tree:\n"
    "     - Is analysis MEANINGLESS without resolving this? -> BLOCKING\n"
    "     - Would the CONCLUSION change significantly if wrong? -> MATERIAL\n"
    "     - Is this a REASONABLE DEFAULT most users would accept? -> DEFAULT\n"
    "\n"
    "  3. VERIFICATION: Can tools confirm this?\n"
    "     If verifiable: Use Read/Glob/Grep NOW. Document result.\n"
    "     If not verifiable: Note 'needs user input'\n"
    "\n"
    "  <assumption_examples>\n"
    "  BLOCKING: 'Which codebase?' (cannot proceed without answer)\n"
    "  MATERIAL: 'Assuming Python 3.9+' (affects implementation choices)\n"
    "  DEFAULT:  'Standard library conventions' (reasonable, override later)\n"
    "  </assumption_examples>\n"
    "\n"
    "  <blocking_action>\n"
    "  If ANY assumption is BLOCKING and unverifiable:\n"
    "  Use AskUserQuestion IMMEDIATELY with:\n"
    "    - question: Clear question about the blocking assumption\n"
    "    - header: Short label (max 12 chars)\n"
    "    - options: 2-4 choices (likely default first with '(Recommended)')\n"
    "  DO NOT proceed to Step 3 until resolved.\n"
    "  </blocking_action>\n"
    "\n"
    "  Accumulate MATERIAL assumptions for checkpoint in Step 5.\n"
    "  State DEFAULT assumptions explicitly but proceed."
)

# --- STEP 3: CHARACTERIZATION -----------------------------------------------

CHARACTERIZATION_INSTRUCTIONS = (
    "Classify this question to determine appropriate analysis approach.\n"
    "\n"
    "PART A - QUESTION TYPE:\n"
    "  Classify as one of:\n"
    "  - TAXONOMY/CLASSIFICATION: Seeking a way to organize or categorize\n"
    "  - TRADE-OFF ANALYSIS: Seeking to understand competing concerns\n"
    "  - DEFINITIONAL: Seeking to clarify meaning or boundaries\n"
    "  - EVALUATIVE: Seeking judgment on quality, correctness, fitness\n"
    "  - EXPLORATORY: Seeking to understand a space of possibilities\n"
    "\n"
    "PART B - ANSWER STRUCTURE:\n"
    "  Based on question type, what structure should the final answer take?\n"
    "  (e.g., 'proposed taxonomy with rationale' or 'decision framework')\n"
    "\n"
    "PART C - EVALUATION CRITERIA:\n"
    "  How should we judge whether an answer is good?\n"
    "  What distinguishes excellent from mediocre?\n"
    "  List 3-5 specific criteria.\n"
    "\n"
    "PART D - MODE DETERMINATION:\n"
    "  Should this use FULL mode (with sub-agents) or QUICK mode (direct synthesis)?\n"
    "\n"
    "  Use QUICK mode if ALL true:\n"
    "  - Relatively narrow scope\n"
    "  - Single analytical perspective likely sufficient\n"
    "  - No significant trade-offs between competing values\n"
    "  - High confidence in what a good answer looks like\n"
    "\n"
    "  Otherwise, use FULL mode.\n"
    "\n"
    "OUTPUT FORMAT:\n"
    "```\n"
    "QUESTION TYPE: [type]\n"
    "\n"
    "ANSWER STRUCTURE: [description]\n"
    "\n"
    "EVALUATION CRITERIA:\n"
    "1. [criterion 1]\n"
    "2. [criterion 2]\n"
    "...\n"
    "\n"
    "MODE: [FULL | QUICK]\n"
    "RATIONALE: [why this mode]\n"
    "```"
)

# --- STEP 4: ANALOGICAL_RECALL ----------------------------------------------

ANALOGICAL_RECALL_INSTRUCTIONS = (
    "Recall similar problems that might inform this analysis.\n"
    "Work through thoroughly. Consider multiple analogies before selecting.\n"
    "\n"
    "PART A - DIRECT ANALOGIES:\n"
    "  What similar problems in the same domain have been addressed?\n"
    "  How were they approached? What worked and what didn't?\n"
    "\n"
    "PART B - CROSS-DOMAIN ANALOGIES:\n"
    "  What problems in OTHER domains share structural similarity?\n"
    "  What can we learn from how those were solved?\n"
    "\n"
    "PART C - ANTI-PATTERNS:\n"
    "  What are known bad approaches to problems like this?\n"
    "  What mistakes do people commonly make?\n"
    "\n"
    "PART D - ANALOGICAL INSIGHTS:\n"
    "  What specific insights from these analogies should inform our approach?\n"
    "  Which analogies are most relevant and why?\n"
    "\n"
    "OUTPUT FORMAT:\n"
    "```\n"
    "DIRECT ANALOGIES:\n"
    "- [analogy 1]: [lesson]\n"
    "\n"
    "CROSS-DOMAIN ANALOGIES:\n"
    "- [domain]: [problem]: [insight]\n"
    "\n"
    "ANTI-PATTERNS:\n"
    "- [bad approach]: [why it fails]\n"
    "\n"
    "KEY INSIGHTS:\n"
    "- [insight to apply]\n"
    "```"
)

# --- STEP 5: PLANNING -------------------------------------------------------

PLANNING_INSTRUCTIONS = (
    "Devise a plan for analyzing this question.\n"
    "\n"
    "PART A - SUB-QUESTIONS:\n"
    "  Break into sub-questions that collectively address the main question.\n"
    "  Each sub-question should be:\n"
    "  - Specific enough to analyze\n"
    "  - Distinct from other sub-questions\n"
    "  - Necessary (not just nice-to-have)\n"
    "\n"
    "PART B - SUCCESS CRITERIA:\n"
    "  What would a successful analysis look like?\n"
    "  How will we know when we've done enough exploration?\n"
    "\n"
    "PART C - SYNTHESIS CRITERIA:\n"
    "  When multiple perspectives provide different answers, how resolve?\n"
    "  What principles should guide synthesis?\n"
    "\n"
    "PART D - ANTICIPATED CHALLENGES:\n"
    "  What aspects will be hardest to address?\n"
    "  Where do you expect disagreement or uncertainty?\n"
    "\n"
    "OUTPUT FORMAT:\n"
    "```\n"
    "SUB-QUESTIONS:\n"
    "1. [question 1]\n"
    "2. [question 2]\n"
    "...\n"
    "\n"
    "SUCCESS CRITERIA:\n"
    "- [criterion]\n"
    "\n"
    "SYNTHESIS CRITERIA:\n"
    "- [principle for resolving disagreement]\n"
    "\n"
    "ANTICIPATED CHALLENGES:\n"
    "- [challenge]\n"
    "\n"
    "ASSUMPTION CHECKPOINT:\n"
    "Verified: [tool-confirmed assumptions]\n"
    "User-confirmed: [AskUserQuestion responses]\n"
    "Defaults: [stated assumptions, no explicit confirmation]\n"
    "```\n"
    "\n"
    "PART E - ASSUMPTION CHECKPOINT:\n"
    "  Before analysis, resolve accumulated assumptions from Steps 1-5.\n"
    "\n"
    "  VERIFICATION PASS:\n"
    "  For each MATERIAL assumption:\n"
    "  1. Attempt tool-based verification:\n"
    "     - Codebase: Glob/Grep/Read for evidence\n"
    "     - Documentation: README, config files, existing implementations\n"
    "     - Conversation: Re-scan for user statements that resolve it\n"
    "  2. Document: ASSUMPTION | METHOD | RESULT (verified/refuted/inconclusive)\n"
    "\n"
    "  <verification_example>\n"
    "  ASSUMPTION: 'Target is Python 3.9+'\n"
    "  METHOD: Read pyproject.toml\n"
    "  RESULT: Verified - python = '^3.9'\n"
    "  </verification_example>\n"
    "\n"
    "  UNRESOLVED MATERIAL ASSUMPTIONS:\n"
    "  If MATERIAL assumptions remain unverified after tool verification:\n"
    "\n"
    "  <material_batch_action>\n"
    "  Batch into AskUserQuestion (max 4 questions):\n"
    "    questions: [\n"
    "      {\n"
    "        question: 'What is [specific assumption]?',\n"
    "        header: '[short label]',\n"
    "        options: [\n"
    "          {label: '[default] (Recommended)', description: '[why reasonable]'},\n"
    "          {label: '[alternative]', description: '[when to choose]'}\n"
    "        ],\n"
    "        multiSelect: false\n"
    "      }\n"
    "    ]\n"
    "  Wait for response before proceeding.\n"
    "  If >4 unresolved: prioritize by impact, carry rest as stated defaults.\n"
    "  </material_batch_action>\n"
    "\n"
    "  CARRYING FORWARD:\n"
    "  List all assumptions entering analysis phase:\n"
    "  - VERIFIED: [tool-confirmed]\n"
    "  - USER-CONFIRMED: [from AskUserQuestion]\n"
    "  - DEFAULTS: [stated, no explicit confirmation needed]"
)

# --- STEP 6: SUBAGENT_DESIGN ------------------------------------------------

SUBAGENT_DESIGN_INSTRUCTIONS = (
    "Design sub-agents to explore this question from different angles.\n"
    "\n"
    "HOW SUB-AGENTS WORK:\n"
    "  - All launch simultaneously (parallel execution)\n"
    "  - Each receives the same inputs: original question + shared context\n"
    "  - Each produces independent output returned to you for aggregation\n"
    "  - Sub-agents cannot see or build on each other's work\n"
    "\n"
    "Your task: design WHAT each sub-agent analyzes, knowing they work in isolation.\n"
    "\n"
    "You have complete freedom in how you divide the analytical work.\n"
    "\n"
    "DIVISION STRATEGIES:\n"
    "\n"
    "You may divide analytical work using any of these (or combinations):\n"
    "\n"
    "  By Perspective/Lens\n"
    "    Different epistemological viewpoints examining the same problem.\n"
    "    A skeptic examines assuming the obvious answer is wrong;\n"
    "    an optimist examines assuming success is achievable.\n"
    "\n"
    "  By Role/Stakeholder\n"
    "    Who has skin in the game? Different priorities and constraints.\n"
    "\n"
    "  By Dimension/Facet\n"
    "    Multiple orthogonal aspects that can be analyzed independently.\n"
    "\n"
    "  By Methodology/Approach\n"
    "    Different analytical frameworks applied to the same question.\n"
    "\n"
    "  By Scope/Scale\n"
    "    Micro, meso, macro. Problems look different at different scales.\n"
    "\n"
    "  By Time Horizon\n"
    "    Short-term vs long-term. Tactical vs strategic.\n"
    "\n"
    "  By Hypothesis\n"
    "    Assign sub-agents to steelman competing hypotheses.\n"
    "\n"
    "  By Facet\n"
    "    Identify independent aspects analyzable without depending on\n"
    "    each other's conclusions.\n"
    "\n"
    "You may combine strategies.\n"
    "\n"
    "For each sub-agent, specify:\n"
    "  1. NAME: Short descriptive name\n"
    "  2. DIVISION STRATEGY: Which strategy this represents\n"
    "  3. TASK DESCRIPTION: What specifically to analyze\n"
    "  4. ASSIGNED SUB-QUESTIONS: Which sub-questions to address\n"
    "  5. UNIQUE VALUE: Why this will produce insights others won't\n"
    "\n"
    "OUTPUT FORMAT:\n"
    "```\n"
    "SUB-AGENT 1:\n"
    "- Name: [name]\n"
    "- Strategy: [strategy]\n"
    "- Task: [description]\n"
    "- Sub-Questions: [list]\n"
    "- Unique Value: [why this matters]\n"
    "\n"
    "SUB-AGENT 2:\n"
    "[etc.]\n"
    "\n"
    "DIVISION RATIONALE:\n"
    "[why this particular division]\n"
    "```"
)

# --- STEP 7: DESIGN_CRITIQUE ------------------------------------------------

DESIGN_CRITIQUE_INSTRUCTIONS = (
    "Critically evaluate the sub-agent design from Step 6.\n"
    "\n"
    "PART A - COVERAGE:\n"
    "  Do sub-agents collectively cover all sub-questions from Step 5?\n"
    "  Are there important angles NO sub-agent will address?\n"
    "  List any gaps.\n"
    "\n"
    "PART B - OVERLAP:\n"
    "  Do any sub-agents duplicate work unnecessarily?\n"
    "  Is there productive tension vs wasteful redundancy?\n"
    "  List any problematic overlaps.\n"
    "\n"
    "PART C - APPROPRIATENESS:\n"
    "  Is division strategy well-suited to this question?\n"
    "  Would a different strategy yield better insights?\n"
    "  Are task descriptions clear enough to execute?\n"
    "\n"
    "PART D - BALANCE:\n"
    "  Are some sub-agents given much harder tasks than others?\n"
    "  Is there risk one sub-agent will dominate synthesis?\n"
    "\n"
    "PART E - SPECIFIC ISSUES:\n"
    "  List specific problems with individual sub-agent definitions.\n"
    "  For each issue, be specific about what's wrong.\n"
    "\n"
    "Be genuinely critical. Goal is to improve, not approve.\n"
    "\n"
    "OUTPUT FORMAT:\n"
    "```\n"
    "COVERAGE:\n"
    "- Gaps: [list or 'none']\n"
    "\n"
    "OVERLAP:\n"
    "- Issues: [list or 'none']\n"
    "\n"
    "APPROPRIATENESS:\n"
    "- Assessment: [evaluation]\n"
    "\n"
    "BALANCE:\n"
    "- Assessment: [evaluation]\n"
    "\n"
    "SPECIFIC ISSUES:\n"
    "- [issue 1]\n"
    "- [issue 2]\n"
    "```"
)

# --- STEP 8: DESIGN_REVISION ------------------------------------------------

DESIGN_REVISION_INSTRUCTIONS = (
    "Revise sub-agent design based on critique from Step 7.\n"
    "\n"
    "For each issue identified, either:\n"
    "  1. Revise the design to address it, OR\n"
    "  2. Explain why the issue should not be addressed\n"
    "\n"
    "OUTPUT FORMAT:\n"
    "```\n"
    "REVISIONS MADE:\n"
    "- [change]: [which critique point it addresses]\n"
    "\n"
    "ISSUES NOT ADDRESSED:\n"
    "- [critique point]: [why not addressing]\n"
    "\n"
    "FINAL SUB-AGENT DEFINITIONS:\n"
    "\n"
    "SUB-AGENT 1:\n"
    "- Name: [name]\n"
    "- Strategy: [strategy]\n"
    "- Task: [description]\n"
    "- Sub-Questions: [list]\n"
    "- Unique Value: [why this matters]\n"
    "\n"
    "[etc.]\n"
    "```\n"
    "\n"
    "These definitions will be used to dispatch sub-agents in Step 9."
)

# --- STEP 9: DISPATCH -------------------------------------------------------

DISPATCH_CONTEXT = (
    "Each sub-agent receives:\n"
    "- CLARIFIED QUESTION from Step 1\n"
    "- DOMAIN and FIRST PRINCIPLES from Step 2\n"
    "- QUESTION TYPE and EVALUATION CRITERIA from Step 3\n"
    "- KEY ANALOGIES from Step 4\n"
    "- Their specific task definition from Step 8\n"
    "\n"
    "AGENT PROMPT STRUCTURE (use for each dispatched sub-agent prompt):\n"
    "\n"
    "Explore this question from the assigned perspective.\n"
    "\n"
    "CLARIFIED QUESTION: [from Step 1]\n"
    "DOMAIN: [from Step 2]\n"
    "FIRST PRINCIPLES: [from Step 2]\n"
    "QUESTION TYPE: [from Step 3]\n"
    "EVALUATION CRITERIA: [from Step 3]\n"
    "KEY ANALOGIES: [from Step 4]\n"
    "\n"
    "YOUR TASK:\n"
    "- Name: [agent name from Step 8]\n"
    "- Strategy: [strategy from Step 8]\n"
    "- Task: [task description from Step 8]\n"
    "- Sub-Questions: [assigned questions from Step 8]"
)

DISPATCH_AGENTS = [
    "[Agent 1: Fill from FINAL SUB-AGENT DEFINITIONS in Step 8]",
    "[Agent 2: Fill from FINAL SUB-AGENT DEFINITIONS in Step 8]",
    "[Agent N: Fill from FINAL SUB-AGENT DEFINITIONS in Step 8]",
]

# --- STEP 10: QUALITY_GATE --------------------------------------------------

QUALITY_GATE_INSTRUCTIONS = (
    "Review each sub-agent's output. Assess whether to include in aggregation.\n"
    "\n"
    "For each sub-agent output, assess:\n"
    "  1. COHERENCE: Is reasoning internally consistent?\n"
    "  2. RELEVANCE: Does it actually address its assigned task?\n"
    "  3. SUBSTANTIVENESS: Genuine insights, not just surface observations?\n"
    "  4. FAILURE MODE COMPLETENESS: Did it identify meaningful weaknesses?\n"
    "\n"
    "RATING SCALE:\n"
    "  - PASS: Include fully in aggregation\n"
    "  - PARTIAL: Include with noted reservations\n"
    "  - FAIL: Exclude from aggregation (with explanation)\n"
    "\n"
    "OUTPUT FORMAT:\n"
    "```\n"
    "SUB-AGENT 1 ([name]):\n"
    "- Coherence: [assessment]\n"
    "- Relevance: [assessment]\n"
    "- Substantiveness: [assessment]\n"
    "- Failure Modes: [assessment]\n"
    "- RATING: [PASS/PARTIAL/FAIL]\n"
    "- Notes: [observations]\n"
    "\n"
    "[repeat for each]\n"
    "\n"
    "SUMMARY:\n"
    "- Passing: [list]\n"
    "- Partial: [list]\n"
    "- Failed: [list]\n"
    "- Coverage assessment: [are critical angles missing due to failures?]\n"
    "```"
)

# --- STEP 11: AGGREGATION ---------------------------------------------------

AGGREGATION_INSTRUCTIONS = (
    "Organize findings from all sub-agents that passed quality gate.\n"
    "\n"
    "PART A - AGREEMENT MAP:\n"
    "  What do multiple sub-agents agree on?\n"
    "  List points of convergence with which sub-agents support each.\n"
    "\n"
    "PART B - DISAGREEMENT MAP:\n"
    "  Where do sub-agents disagree?\n"
    "  For each: point of contention, competing positions, reasoning.\n"
    "\n"
    "PART B2 - CONFLICT RESOLUTION (for synthesis):\n"
    "  For each disagreement, note which position has:\n"
    "  - More sub-agent support (majority)\n"
    "  - Stronger evidence grounding\n"
    "  - Better alignment with first principles from Step 2\n"
    "  Flag unresolvable conflicts explicitly.\n"
    "\n"
    "PART C - UNIQUE CONTRIBUTIONS:\n"
    "  What valuable insights appeared in only ONE sub-agent?\n"
    "  Why might others have missed this?\n"
    "\n"
    "PART D - INTERMEDIATE INSIGHTS:\n"
    "  Review reasoning chains of ALL sub-agents (including PARTIAL).\n"
    "  Extract intermediate observations valuable independent of conclusions.\n"
    "  These inform synthesis even if overall analysis not adopted.\n"
    "\n"
    "PART E - FAILURE MODE CATALOG:\n"
    "  Aggregate all anticipated failure modes identified by sub-agents.\n"
    "  Group by theme.\n"
    "\n"
    "PART F - SUB-QUESTION COVERAGE:\n"
    "  For each sub-question from Step 5, summarize responses.\n"
    "  Flag any with weak or no coverage.\n"
    "\n"
    "Preserve all disagreements exactly as found. Record positions without evaluation.\n"
    "This step is purely organizational.\n"
    "\n"
    "OUTPUT FORMAT:\n"
    "```\n"
    "AGREEMENT MAP:\n"
    "- [point]: supported by [sub-agents]\n"
    "\n"
    "DISAGREEMENT MAP:\n"
    "- [contention]: [position A] vs [position B]\n"
    "\n"
    "UNIQUE CONTRIBUTIONS:\n"
    "- [sub-agent]: [insight]\n"
    "\n"
    "INTERMEDIATE INSIGHTS:\n"
    "- [insight from reasoning, not conclusion]\n"
    "\n"
    "FAILURE MODE CATALOG:\n"
    "- [theme]: [modes]\n"
    "\n"
    "SUB-QUESTION COVERAGE:\n"
    "- Q1: [coverage summary]\n"
    "```"
)

# --- STEP 12: INITIAL_SYNTHESIS ---------------------------------------------

SYNTHESIS_FULL_INSTRUCTIONS = (
    "Integrate aggregated findings into a coherent response.\n"
    "Hint: Prioritize aspects matching the EVALUATION CRITERIA from Step 3.\n"
    "Work through thoroughly. Avoid shortcuts. Show reasoning step by step.\n"
    "\n"
    "SYNTHESIS GUIDELINES:\n"
    "  1. Use evaluation criteria from Step 3 to guide integration\n"
    "  2. Resolve disagreements using synthesis criteria from Step 5\n"
    "  3. Draw on intermediate insights from Step 11, not just conclusions\n"
    "  4. Acknowledge where genuine uncertainty remains\n"
    "  5. Do not artificially harmonize positions that genuinely conflict\n"
    "\n"
    "PART A - CORE ANSWER:\n"
    "  What is your integrated response to the original question?\n"
    "  Structure appropriately for the question type from Step 3.\n"
    "\n"
    "PART B - KEY TRADE-OFFS:\n"
    "  What trade-offs are inherent in this answer?\n"
    "  What did you prioritize, and what did you deprioritize?\n"
    "\n"
    "PART C - DISSENTING VIEWS:\n"
    "  Where did you override a sub-agent's position?\n"
    "  Why not adopted, and what would change your mind?\n"
    "\n"
    "PART D - EVIDENCE GROUNDING:\n"
    "  For each major claim, cite the evidence source:\n"
    "  - From Step 2 (first principles)\n"
    "  - From Step 4 (analogies)\n"
    "  - From Step 11 (sub-agent findings or intermediate insights)\n"
    "  Claims without grounding: flag as UNGROUNDED.\n"
    "\n"
    "PART E - ACKNOWLEDGED LIMITATIONS:\n"
    "  What aspects does this synthesis NOT address well?\n"
    "  What additional information would strengthen the analysis?\n"
    "\n"
    "PART F - CONFIDENCE MARKERS:\n"
    "  Mark claims as:\n"
    "  - HIGH: Strong agreement, multiple sources\n"
    "  - MEDIUM: Reasonable but contested or single source\n"
    "  - LOW: Speculative or limited evidence\n"
    "\n"
    "OUTPUT FORMAT:\n"
    "```\n"
    "CORE ANSWER:\n"
    "[structured response]\n"
    "\n"
    "KEY TRADE-OFFS:\n"
    "- Prioritized: [X] over [Y] because [reason]\n"
    "\n"
    "DISSENTING VIEWS:\n"
    "- [sub-agent]: [position not adopted]: [why]\n"
    "\n"
    "EVIDENCE GROUNDING:\n"
    "- [claim]: [source]\n"
    "- UNGROUNDED: [list any ungrounded claims]\n"
    "\n"
    "LIMITATIONS:\n"
    "- [limitation]\n"
    "\n"
    "CONFIDENCE: [overall assessment]\n"
    "```\n"
    "\n"
    "This synthesis will be evaluated in Step 13. Expect to refine it."
)

SYNTHESIS_QUICK_INSTRUCTIONS = (
    "Based on abstraction (Step 2) and analogies (Step 4), synthesize response.\n"
    "Hint: Prioritize aspects matching the EVALUATION CRITERIA from Step 3.\n"
    "Work through thoroughly. Avoid shortcuts. Show reasoning step by step.\n"
    "\n"
    "PART A - CORE ANSWER:\n"
    "  What is your response to the original question?\n"
    "  Ground in first principles from Step 2 and analogies from Step 4.\n"
    "\n"
    "PART B - EVIDENCE GROUNDING:\n"
    "  For each major claim, cite source:\n"
    "  - First principles (Step 2)\n"
    "  - Analogical reasoning (Step 4)\n"
    "  - Domain knowledge\n"
    "  Claims without grounding: flag as UNGROUNDED.\n"
    "\n"
    "PART C - ACKNOWLEDGED LIMITATIONS:\n"
    "  What aspects does this NOT address well?\n"
    "  Where might alternative perspectives yield different conclusions?\n"
    "\n"
    "PART D - CONFIDENCE MARKERS:\n"
    "  Mark claims as HIGH, MEDIUM, or LOW confidence with brief justification.\n"
    "\n"
    "OUTPUT FORMAT:\n"
    "```\n"
    "CORE ANSWER:\n"
    "[structured response]\n"
    "\n"
    "EVIDENCE GROUNDING:\n"
    "- [claim]: [source]\n"
    "- UNGROUNDED: [list any]\n"
    "\n"
    "LIMITATIONS:\n"
    "- [limitation]\n"
    "\n"
    "CONFIDENCE: [overall assessment]\n"
    "```\n"
    "\n"
    "This synthesis will be evaluated in Step 13."
)

# --- STEP 13: ITERATIVE_REFINEMENT ------------------------------------------

REFINEMENT_INSTRUCTIONS = (
    "ITERATION {iteration} OF {max_iter}\n"
    "\n"
    "RULE 0 (MANDATORY): Follow the invoke_after command. Do NOT skip\n"
    "to step 14 unless confidence is CERTAIN or this is iteration 5.\n"
    "\n"
    "Critically evaluate the current synthesis.\n"
    "Work through thoroughly -- avoid quick 'looks good' assessments.\n"
    "\n"
    "PART A - VERIFICATION QUESTION GENERATION:\n"
    "  Generate 3-5 verification questions that would test correctness.\n"
    "  Use OPEN questions ('What is X?', 'Where does Y occur?'), not yes/no.\n"
    "  Yes/no questions bias toward agreement regardless of correctness.\n"
    "  Focus on:\n"
    "  - Claims marked LOW or MEDIUM confidence\n"
    "  - Any UNGROUNDED claims from Step 12\n"
    "  - Potential blind spots\n"
    "  - Failure modes that could invalidate key proposals\n"
    "  - Edge cases the synthesis might not handle\n"
    "\n"
    "PART B - INDEPENDENT VERIFICATION:\n"
    "  For each verification question, answer based ONLY on:\n"
    "  - First principles from Step 2\n"
    "  - Analogies from Step 4\n"
    "  - Aggregated evidence from Step 11 (if Full mode)\n"
    "\n"
    "  CRITICAL: Do NOT look at the synthesis while answering.\n"
    "  Answer based on evidence, not what the synthesis claims.\n"
    "\n"
    "  EXPLORATION OPTION:\n"
    "  If a verification question cannot be answered with existing evidence:\n"
    "  - Use Read/Glob/Grep to find concrete evidence in the codebase\n"
    "  - This is especially valuable for UNGROUNDED claims from Step 12\n"
    "  - Keep exploration bounded -- answer the specific question, then stop\n"
    "  - Update answer with exploration findings and cite sources\n"
    "\n"
    "PART C - DISCREPANCY IDENTIFICATION:\n"
    "  Compare verification answers against current synthesis.\n"
    "  Where do they differ?\n"
    "  List each discrepancy.\n"
    "\n"
    "PART D - ACTIONABLE FEEDBACK:\n"
    "  For each discrepancy or issue, provide feedback.\n"
    "\n"
    "  Each piece of feedback MUST include all three elements:\n"
    "    1. ELEMENT: Name the specific claim, section, or aspect\n"
    "    2. PROBLEM: State precisely what is wrong or unsupported\n"
    "    3. ACTION: Propose a concrete fix or revision\n"
    "\n"
    "  Feedback missing any element should be discarded as too vague.\n"
    "\n"
    "  GOOD: 'ELEMENT: claim X. PROBLEM: contradicts evidence Y. ACTION: qualify with Z.'\n"
    "  BAD: 'The analysis could be stronger.' (no specific element/problem/action)\n"
    "\n"
    "PART E - SYNTHESIS UPDATE:\n"
    "  Review feedback from ALL previous iterations (if any).\n"
    "  Based on actionable feedback, revise the synthesis.\n"
    "  Avoid repeating mistakes identified in prior iterations.\n"
    "  For each revision, note which feedback item it addresses.\n"
    "\n"
    "PART F - CONFIDENCE ASSESSMENT:\n"
    "  After revisions, assess confidence:\n"
    "  - EXPLORING: Still developing understanding\n"
    "  - LOW: Significant gaps or unresolved issues\n"
    "  - MEDIUM: Reasonable answer but some uncertainty\n"
    "  - HIGH: Strong answer, minor refinements possible\n"
    "  - CERTAIN: As good as it can get with available information\n"
    "\n"
    "  Provide specific justification for confidence level.\n"
    "\n"
    "<iteration_gate>\n"
    "CRITICAL: You MUST follow the invoke_after command exactly.\n"
    "\n"
    "EXIT CONDITIONS (both required to proceed to step 14):\n"
    "  1. Confidence = CERTAIN, OR\n"
    "  2. This is iteration 5 (final iteration)\n"
    "\n"
    "If NEITHER condition is met, STOP.\n"
    "Do NOT proceed to step 14. Continue to the next iteration.\n"
    "</iteration_gate>\n"
    "\n"
    "OUTPUT FORMAT:\n"
    "```\n"
    "VERIFICATION QUESTIONS:\n"
    "1. [question]\n"
    "\n"
    "INDEPENDENT ANSWERS:\n"
    "1. [answer without looking at synthesis]\n"
    "\n"
    "DISCREPANCIES:\n"
    "- [where synthesis differs from verification]\n"
    "\n"
    "ACTIONABLE FEEDBACK:\n"
    "- ELEMENT: [what]. PROBLEM: [why wrong]. ACTION: [fix]\n"
    "\n"
    "REVISED SYNTHESIS:\n"
    "[updated synthesis]\n"
    "\n"
    "CONFIDENCE: [level]\n"
    "JUSTIFICATION: [why this level]\n"
    "```"
)

# --- STEP 14: FORMATTING_OUTPUT ---------------------------------------------

FORMATTING_INSTRUCTIONS = (
    "Refinement complete. Confidence: {confidence}.\n"
    "\n"
    "Present the final answer to the user.\n"
    "\n"
    "FORMATTING REQUIREMENTS:\n"
    "  - Lead with the direct answer to the original question\n"
    "  - Use the answer structure determined in Step 3\n"
    "  - Integrate key trade-offs naturally into the explanation\n"
    "  - Note limitations only where they materially affect the answer\n"
    "  - Omit workflow artifacts (step references, sub-agent names, etc.)\n"
    "\n"
    "CONFIDENCE: {confidence_guidance}\n"
    "\n"
    "OUTPUT: Clean prose response directly addressing the user's question.\n"
    "        No meta-commentary about the analysis process."
)


# ============================================================================
# MESSAGE BUILDERS
# ============================================================================


def build_dispatch_body() -> str:
    """Build DISPATCH instructions with roster_dispatch()."""
    invoke_cmd = f'python3 -m {SUBAGENT_MODULE_PATH} --step 1'

    dispatch_text = roster_dispatch(
        agent_type="analytical reasoning (multi-perspective, evidence-grounded)",
        agents=DISPATCH_AGENTS,
        command=invoke_cmd,
        shared_context=DISPATCH_CONTEXT,
        model="reasoning-capable model suitable for nuanced synthesis",
        instruction="Launch ALL sub-agents from FINAL SUB-AGENT DEFINITIONS (Step 8). Use a SINGLE message with multiple agent dispatch calls.",
    )

    return dispatch_text


def build_next_command(step: int, mode: str, confidence: str, iteration: int) -> str | None:
    """Build invoke command for next step."""
    base = f'python3 -m {MODULE_PATH}'

    if step == 1:
        return f'{base} --step 2'
    elif step == 2:
        return f'{base} --step 3'
    elif step == 3:
        return f'{base} --step 4'
    elif step == 4:
        return f'{base} --step 5'
    elif step == 5:
        return f'If FULL: {base} --step 6 --mode full\nIf QUICK: {base} --step 12 --mode quick'
    elif step == 6:
        return f'{base} --step 7 --mode {mode}'
    elif step == 7:
        return f'{base} --step 8 --mode {mode}'
    elif step == 8:
        return f'{base} --step 9 --mode {mode}'
    elif step == 9:
        return f'{base} --step 10 --mode {mode}'
    elif step == 10:
        return f'{base} --step 11 --mode {mode}'
    elif step == 11:
        return f'{base} --step 12 --mode {mode}'
    elif step == 12:
        return f'{base} --step 13 --confidence <your_confidence> --iteration 1 --mode {mode}'
    elif step == 13:
        if confidence == "certain" or iteration >= MAX_ITERATIONS:
            return f'{base} --step 14 --confidence {confidence} --mode {mode}'
        else:
            return f'{base} --step 13 --confidence <your_confidence> --iteration {iteration + 1} --mode {mode}'
    elif step == 14:
        return None

    return None


# ============================================================================
# STEP DEFINITIONS
# ============================================================================

# Static steps: (title, instructions) tuples for steps with constant content
STATIC_STEPS = {
    1: ("Context Clarification", CONTEXT_CLARIFICATION_INSTRUCTIONS),
    2: ("Abstraction", ABSTRACTION_INSTRUCTIONS),
    3: ("Characterization", CHARACTERIZATION_INSTRUCTIONS),
    4: ("Analogical Recall", ANALOGICAL_RECALL_INSTRUCTIONS),
    5: ("Planning", PLANNING_INSTRUCTIONS),
    6: ("Sub-Agent Design", SUBAGENT_DESIGN_INSTRUCTIONS),
    7: ("Design Critique", DESIGN_CRITIQUE_INSTRUCTIONS),
    8: ("Design Revision", DESIGN_REVISION_INSTRUCTIONS),
    10: ("Quality Gate", QUALITY_GATE_INSTRUCTIONS),
    11: ("Aggregation", AGGREGATION_INSTRUCTIONS),
}


def _format_step_9(mode: str, confidence: str, iteration: int) -> tuple[str, str]:
    """Step 9: Dispatch - builds dispatch body via roster_dispatch()."""
    return ("Dispatch", build_dispatch_body())


def _format_step_12(mode: str, confidence: str, iteration: int) -> tuple[str, str]:
    """Step 12: Initial Synthesis - selects instructions based on mode."""
    body = SYNTHESIS_FULL_INSTRUCTIONS if mode == "full" else SYNTHESIS_QUICK_INSTRUCTIONS
    return ("Initial Synthesis", body)


def _format_step_13(mode: str, confidence: str, iteration: int) -> tuple[str, str]:
    """Step 13: Iterative Refinement - parameterized title and body."""
    suffix = " -> Complete" if confidence == "certain" or iteration >= MAX_ITERATIONS else ""
    title = f"Iterative Refinement (Iteration {iteration}){suffix}"
    body = REFINEMENT_INSTRUCTIONS.format(iteration=iteration, max_iter=MAX_ITERATIONS)
    return (title, body)


def _format_step_14(mode: str, confidence: str, iteration: int) -> tuple[str, str]:
    """Step 14: Formatting & Output - parameterized with confidence guidance."""
    confidence_upper = confidence.upper()
    if confidence == "certain":
        guidance = "HIGH\n  Present with authority. Hedging language unnecessary."
    else:
        guidance = f"{confidence_upper}\n  Flag specific claims with lower confidence.\n  Indicate what additional information would strengthen the analysis."
    body = FORMATTING_INSTRUCTIONS.format(confidence=confidence_upper, confidence_guidance=guidance)
    return ("Formatting & Output", body)


# Dynamic steps: functions that compute (title, instructions) based on parameters
# Functions must be defined BEFORE this dictionary (book pattern)
DYNAMIC_STEPS = {
    9: _format_step_9,
    12: _format_step_12,
    13: _format_step_13,
    14: _format_step_14,
}


# ============================================================================
# OUTPUT FORMATTING
# ============================================================================


def format_output(step: int, mode: str, confidence: str, iteration: int) -> str:
    """Format output for the given step.

    Uses callable dispatch: static steps lookup (title, instructions) from
    STATIC_STEPS dict; dynamic steps call formatter functions from DYNAMIC_STEPS.
    """
    if step in STATIC_STEPS:
        title, instructions = STATIC_STEPS[step]
    elif step in DYNAMIC_STEPS:
        formatter = DYNAMIC_STEPS[step]
        title, instructions = formatter(mode, confidence, iteration)
    else:
        return f"ERROR: Invalid step {step}"

    next_cmd = build_next_command(step, mode, confidence, iteration)
    return format_step(instructions, next_cmd or "", title=f"DEEPTHINK - {title}")


# ============================================================================
# ENTRY POINT
# ============================================================================


def main():
    """Entry point for deepthink workflow."""
    parser = argparse.ArgumentParser(
        description="DeepThink - Structured reasoning for open-ended analytical questions",
        epilog="Steps: 1-14 (Full mode) or 1-5,12-14 (Quick mode)",
    )
    parser.add_argument("--step", type=int, required=True)
    parser.add_argument(
        "--confidence",
        type=str,
        choices=["exploring", "low", "medium", "high", "certain"],
        default="exploring",
        help="Confidence level (for Step 13)",
    )
    parser.add_argument(
        "--iteration",
        type=int,
        default=1,
        help="Current iteration within Step 13 (1-5)",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["quick", "full"],
        default="full",
        help="Analysis mode (set in Step 3)",
    )
    args = parser.parse_args()

    if args.step < 1 or args.step > 14:
        sys.exit("ERROR: --step must be 1-14")

    print(format_output(args.step, args.mode, args.confidence, args.iteration))


if __name__ == "__main__":
    main()
