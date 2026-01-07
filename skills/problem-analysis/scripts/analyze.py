#!/usr/bin/env python3
"""
Problem Analysis Skill - Compact structured reasoning workflow.

Four-phase workflow:
  1. Define   - Problem decomposition + initial solution generation
  2. Explore  - Solution expansion + critique
  3. Verify   - Factored verification (OPEN questions, cross-check)
  4. Synthesize - Trade-off analysis + recommendation

Research grounding:
  - ToT (Yao 2023): decompose into evaluable thoughts
  - CoVe (Dhuliawala 2023): OPEN questions, factored verification (17%->70%)
  - Self-Refine (Madaan 2023): actionable feedback
  - Analogical Prompting (Yasunaga 2024): recall distinct problems

Usage:
    python3 analyze.py --step 1 --total-steps 4
"""

import argparse
import sys


STEPS = {
    1: {
        "title": "Define",
        "brief": "Problem decomposition + initial solutions",
        "actions": [
            "STATE the problem in one sentence: 'I need to decide X'",
            "",
            "LIST CONSTRAINTS:",
            "  HARD: non-negotiable (latency, accuracy, compatibility)",
            "  SOFT: preferences (can trade off)",
            "",
            "SURFACE ASSUMPTIONS (ask yourself):",
            "  'What am I assuming about scale/load?'",
            "  'What am I assuming will NOT change?'",
            "",
            "GENERATE 2-4 DISTINCT solutions:",
            "  Each must differ on a fundamental axis:",
            "    scope, complexity, control, approach",
            "  For each: name, mechanism, key assumptions, claimed benefits",
            "",
            "Do NOT favor any solution yet.",
        ],
    },
    2: {
        "title": "Explore",
        "brief": "Expand solution space + critique",
        "actions": [
            "EXPAND - Push beyond initial solutions:",
            "  - What axes were NOT represented?",
            "  - What's the OPPOSITE of each solution?",
            "  - What would a different domain do?",
            "  - What's the 80/20 'good enough' option?",
            "  - What if we did NOTHING?",
            "  - If inferring from code: Search broadly, identify the dominant pattern",
            "",
            "ADD 1-2 more solutions covering unexplored axes.",
            "",
            "CRITIQUE each solution:",
            "  - What could go wrong? (failure modes)",
            "  - What assumption might be false?",
            "  - Where is complexity hiding?",
            "",
            "SPECIFIC feedback (not vague):",
            "  BAD:  'might have scaling issues'",
            "  GOOD: 'Redis fails at >100K ops/sec; Solution A assumes <50K'",
            "",
            "Mark each: ELIMINATE (fatal flaw) / REFINE (fixable) / ADVANCE",
        ],
    },
    3: {
        "title": "Verify",
        "brief": "Factored verification + cross-check",
        "actions": [
            "FACTORED VERIFICATION (answer WITHOUT looking at solutions):",
            "",
            "Step A - Convert assumptions to OPEN questions:",
            "  BAD:  'Is option A better?' (yes/no = agreement bias)",
            "  GOOD: 'What throughput does option A achieve under load?'",
            "",
            "Step B - Answer each INDEPENDENTLY:",
            "  - Pretend you haven't seen the solutions",
            "  - Answer from first principles",
            "  - Cite reasoning for each answer",
            "",
            "Step C - Categorize:",
            "  VERIFIED / FALSIFIED / UNCERTAIN",
            "",
            "CROSS-CHECK against claims:",
            "  - Which claims SUPPORTED?",
            "  - Which claims CONTRADICTED?",
            "  - Which claims UNTESTED?",
            "",
            "Mark solutions with falsified CORE assumptions as ELIMINATED.",
        ],
    },
    4: {
        "title": "Synthesize",
        "brief": "Trade-off analysis + recommendation",
        "actions": [
            "SURVIVING SOLUTIONS (not eliminated by verification)",
            "",
            "TRADE-OFF MATRIX (verified facts only):",
            "  For each dimension that matters:",
            "    'A achieves X; B achieves Y (verified)'",
            "",
            "DECISION FRAMEWORK:",
            "  'If [constraint] paramount -> A because...'",
            "  'If [priority] matters more -> B because...'",
            "  'If uncertain about [X] -> gather [data] first'",
            "",
            "RECOMMENDATION (if one dominates):",
            "  State which + single strongest reason",
            "  Acknowledge what you're giving up",
        ],
    },
}


def format_output(step: int, total_steps: int) -> str:
    """Format compact output for display."""
    # Extra steps go to Verify (where accuracy improves most)
    if step > 4 and step < total_steps:
        info = STEPS[3]  # Extra verification rounds
    elif step >= total_steps:
        info = STEPS[4]  # Final synthesis
    else:
        info = STEPS.get(step, STEPS[4])

    is_complete = step >= total_steps

    lines = [
        f"PROBLEM ANALYSIS - Step {step}/{total_steps}: {info['title']}",
        f"  {info['brief']}",
        "",
        "DO:",
    ]

    for action in info["actions"]:
        if action:
            lines.append(f"  {action}")
        else:
            lines.append("")

    lines.append("")

    if is_complete:
        lines.append("COMPLETE - Present recommendation to user.")
    else:
        next_step = step + 1
        if next_step > 4 and next_step < total_steps:
            next_info = STEPS[3]
        elif next_step >= total_steps:
            next_info = STEPS[4]
        else:
            next_info = STEPS.get(next_step, STEPS[4])
        lines.append(f"NEXT: Step {next_step} - {next_info['title']}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Problem Analysis - Compact reasoning workflow",
        epilog="Phases: define (1) -> explore (2) -> verify (3) -> synthesize (4)",
    )
    parser.add_argument("--step", type=int, required=True)
    parser.add_argument("--total-steps", type=int, required=True)
    args = parser.parse_args()

    if args.step < 1:
        sys.exit("ERROR: --step must be >= 1")
    if args.total_steps < 4:
        sys.exit("ERROR: --total-steps must be >= 4")
    if args.step > args.total_steps:
        sys.exit("ERROR: --step cannot exceed --total-steps")

    print(format_output(args.step, args.total_steps))


if __name__ == "__main__":
    main()
