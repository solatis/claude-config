#!/usr/bin/env python3
"""arxiv-to-md orchestrator: Parse input, dispatch sub-agents, rename outputs.

Two invocation modes:
  MODE 1: Direct conversion (default)
    - User provides arXiv IDs directly or via discovery
    - Orchestrator constructs filename from paper title + date

  MODE 2: PDF folder sync
    - User specifies source PDF folder + destination markdown folder
    - Orchestrator matches PDFs to existing .md files, identifies gaps
    - Destination filename derived from PDF filename

3-step workflow:
  1. Discover/Parse - Detect mode, find arXiv IDs, dispatch sub-agents
  2. Wait          - Wait for all sub-agents to complete
  3. Finalize      - Copy outputs to target location (filename construction varies by mode)
"""

import argparse
import sys

from skills.lib.paths import get_skills_working_dir
from skills.lib.workflow.prompts import format_step, template_dispatch

_SKILLS_DIR = get_skills_working_dir()


# ============================================================================
# CONFIGURATION
# ============================================================================

MODULE_PATH = "skills.arxiv_to_md.main"
SUBAGENT_MODULE_PATH = "skills.arxiv_to_md.sub_agent"


# ============================================================================
# MESSAGE TEMPLATES
# ============================================================================

# --- STEP 1: DISCOVER --------------------------------------------------------

DISCOVER_INSTRUCTIONS = (
    "MODE DETECTION:\n"
    "Determine which mode based on user input:\n"
    "\n"
    "MODE 1 (default): Direct conversion\n"
    "  Trigger: User provides arXiv IDs directly, or asks to convert papers\n"
    "  Filename: Orchestrator constructs from paper title + date\n"
    "\n"
    "MODE 2: PDF folder sync\n"
    "  Trigger: User specifies source PDF folder AND destination markdown folder\n"
    "  Filename: Derived from PDF filename (orchestrator provides to sub-agent)\n"
    "\n"
    "============================================================\n"
    "\n"
    "MODE 1 DISCOVERY:\n"
    "Before asking the user for arXiv IDs, check for:\n"
    "  - CLAUDE.md in current directory (may list arXiv IDs)\n"
    "  - README.md or similar docs with arXiv links/IDs\n"
    "  - .bib files with arXiv entries\n"
    "If IDs found, confirm with user: 'Found arXiv ID(s) X, Y. Convert these?'\n"
    "\n"
    "PARSE USER INPUT:\n"
    "If user provides input directly, parse for arXiv IDs:\n"
    "  - Format: YYMM.NNNNN (e.g., 2503.05179)\n"
    "  - Or full URL: https://arxiv.org/abs/YYMM.NNNNN\n"
    "  - May be multiple IDs (comma-separated, space-separated, or multiple URLs)\n"
    "\n"
    "MODE 1 DISPATCH:\n"
)

MODE1_TEMPLATE = (
    "Convert this arXiv paper to markdown.\n"
    "\n"
    "arXiv ID: $ARXIV_ID\n"
    "\n"
    f"Start: <invoke working-dir=\"{_SKILLS_DIR}\" cmd=\"python3 -m skills.arxiv_to_md.sub_agent --step 1 --arxiv-id $ARXIV_ID\" />\n"
    "\n"
    "<expected_output>\n"
    "Sub-agent responds with ONLY:\n"
    "\n"
    "On success:\n"
    "FILE: <path-to-markdown>\n"
    "TITLE: <paper title>\n"
    "DATE: <YYYY-MM-DD>\n"
    "\n"
    "On failure:\n"
    "FAIL: <reason>\n"
    "</expected_output>"
)

MODE2_DISCOVERY_INSTRUCTIONS = (
    "\n"
    "============================================================\n"
    "\n"
    "MODE 2 DISCOVERY (PDF folder sync):\n"
    "\n"
    "FORBIDDEN - NEVER read PDF files. Resolve arXiv IDs by searching online for paper title.\n"
    "\n"
    "CRITICAL - CHECK EXISTING FILES FIRST:\n"
    "\n"
    "Most files WILL already exist. Skipping is the common case.\n"
    "Before dispatching ANY sub-agent, check if output already exists.\n"
    "\n"
    "If a PDF already has a matching .md file, STOP. Do NOT dispatch.\n"
    "Skip that PDF entirely.\n"
    "\n"
    "FILE NAMING CONVENTION:\n"
    "  PDFs:     YYYY-MM-DD <title>.pdf\n"
    "  Markdown: YYYY-MM-DD <title>.md\n"
    "  Example:  2025-01-08 Pruning the Unsurprising.pdf\n"
    "\n"
    "1. SCAN DESTINATION FOLDER for existing markdown FIRST:\n"
    "   - List all *.md files in destination folder\n"
    "\n"
    "2. SCAN SOURCE FOLDER for PDFs:\n"
    "   - List all *.pdf files in source folder\n"
    "   - Extract base filename (without .pdf extension)\n"
    "\n"
    "3. For EACH PDF, check if matching .md exists:\n"
    "   Matching logic: same YYYY-MM-DD prefix + similar title\n"
    "   - '2025-01-08 Pruning the Unsurprising.pdf' matches '2025-01-08 Pruning the Unsurprising.md'\n"
    "   If match exists -> SKIP this PDF (do not dispatch)\n"
    "\n"
    "4. RESOLVE ARXIV IDs from unmatched PDFs:\n"
    "   - Extract paper title from PDF filename (after YYYY-MM-DD prefix)\n"
    "   - Use WebSearch to find arXiv ID for that paper title\n"
    "   - DO NOT read the PDF file\n"
    "\n"
    "5. DETERMINE DESTINATION FILENAMES:\n"
    "   For each unmatched PDF with resolved arXiv ID:\n"
    "   - dest_file = '<dest_folder>/<pdf_basename>.md'\n"
    "   - Example: source/2025-01-08 Pruning the Unsurprising.pdf\n"
    "             -> dest/2025-01-08 Pruning the Unsurprising.md\n"
    "\n"
    "MODE 2 DISPATCH:\n"
)

MODE2_TEMPLATE = (
    "Convert this arXiv paper to markdown.\n"
    "\n"
    "arXiv ID: $ARXIV_ID\n"
    "Destination: $DEST_FILE\n"
    "\n"
    f"Start: <invoke working-dir=\"{_SKILLS_DIR}\" cmd=\"python3 -m skills.arxiv_to_md.sub_agent --step 1 --arxiv-id $ARXIV_ID --dest-file '$DEST_FILE'\" />\n"
    "\n"
    "<expected_output>\n"
    "Sub-agent responds with ONLY:\n"
    "\n"
    "On success:\n"
    "FILE: <path-to-markdown>\n"
    "\n"
    "On failure:\n"
    "FAIL: <reason>\n"
    "</expected_output>"
)

# --- STEP 2: WAIT ------------------------------------------------------------

WAIT_INSTRUCTIONS = (
    "WAIT for all sub-agents to complete.\n"
    "\n"
    "Collect results from each sub-agent:\n"
    "\n"
    "MODE 1 response format:\n"
    "  - FILE: <path>   -> successful conversion\n"
    "    TITLE: <title> -> paper title (for filename)\n"
    "    DATE: <date>   -> submission date YYYY-MM-DD (for filename)\n"
    "  - FAIL: <reason> -> conversion failed\n"
    "\n"
    "MODE 2 response format:\n"
    "  - FILE: <path>   -> successful conversion (no TITLE/DATE)\n"
    "    dest_file: already known from dispatch\n"
    "  - FAIL: <reason> -> conversion failed\n"
    "\n"
    "Build results summary:\n"
    "```\n"
    "mode: 1 or 2\n"
    "results:\n"
    "  - arxiv_id: 2503.05179\n"
    "    status: success\n"
    "    temp_path: /tmp/arxiv_2503.05179/cleaned.md\n"
    "    title: 'Pruning the Unsurprising'  # MODE 1 only\n"
    "    date: 2025-03-08                   # MODE 1 only\n"
    "    dest_file: /path/to/dest.md       # MODE 2 only\n"
    "  - arxiv_id: 2401.12345\n"
    "    status: failed\n"
    "    reason: PDF-only submission\n"
    "```"
)

# --- STEP 3: FINALIZE --------------------------------------------------------

FINALIZE_INSTRUCTIONS = (
    "For each SUCCESSFUL conversion:\n"
    "\n"
    "MODE 1 (dest_file NOT provided - construct filename from metadata):\n"
    "\n"
    "1. CONSTRUCT FILENAME from metadata:\n"
    "\n"
    "   Format: YYYY-MM-DD Title - Subtitle.md\n"
    "\n"
    "   Transformation steps:\n"
    "   a) Start with DATE from sub-agent (already YYYY-MM-DD)\n"
    "   b) Take TITLE from sub-agent\n"
    "   c) Replace ? ; : with ' - ' (space-dash-space)\n"
    "      'Foo: Bar Baz' -> 'Foo - Bar Baz'\n"
    "      'What? Why; How:' -> 'What - Why - How -'\n"
    "   d) Remove characters unsafe for filenames: / \\ < > | \" *\n"
    "   e) Collapse multiple spaces to single space\n"
    "   f) Trim leading/trailing whitespace\n"
    "   g) Concatenate: '<date> <title>.md'\n"
    "\n"
    "   Example:\n"
    "     title: 'Pruning the Unsurprising: Efficient LLM Reasoning via First-Token Surprisal'\n"
    "     date: 2026-01-08\n"
    "     result: '2026-01-08 Pruning the Unsurprising - Efficient LLM Reasoning via First-Token Surprisal.md'\n"
    "\n"
    "   FALLBACK: If title/date missing, use <arxiv_id>.md\n"
    "\n"
    "2. Copy the cleaned.md to target:\n"
    "   ```bash\n"
    "   cp /tmp/arxiv_<id>/cleaned.md './<constructed_filename>'\n"
    "   ```\n"
    "   Note: Quote the filename - it contains spaces.\n"
    "\n"
    "============================================================\n"
    "\n"
    "MODE 2 (dest_file WAS provided - copy to pre-determined destination):\n"
    "\n"
    "1. Copy the cleaned.md to dest_file:\n"
    "   ```bash\n"
    "   cp /tmp/arxiv_<id>/cleaned.md '<dest_file>'\n"
    "   ```\n"
    "\n"
    "   The dest_file was determined in step 1 and passed to sub-agent.\n"
    "   No filename construction needed.\n"
    "\n"
    "============================================================\n"
    "\n"
    "VERIFICATION (both modes):\n"
    "  - Use Read tool to confirm file exists and has content\n"
    "\n"
    "PRESENT FINAL SUMMARY to user:\n"
    "```\n"
    "Processed M PDFs: N converted, K skipped (already exist), F failed\n"
    "\n"
    "Skipped (already exist):\n"
    "  2025-01-08 Pruning the Unsurprising -> already exists\n"
    "\n"
    "Converted:\n"
    "  [OK] 2025-01-10 New Paper Title -> ./2025-01-10 New Paper Title.md\n"
    "\n"
    "Failed:\n"
    "  [FAIL] 2024-12-15 Some Paper -> PDF-only submission (no TeX source)\n"
    "```"
)


# ============================================================================
# MESSAGE BUILDERS
# ============================================================================


def build_mode1_dispatch() -> str:
    """Build MODE 1 dispatch instructions."""
    return template_dispatch(
        agent_type="general-purpose",
        template=MODE1_TEMPLATE,
        targets=[{"ARXIV_ID": "EXAMPLE"}],
        command=f'python3 -m {SUBAGENT_MODULE_PATH} --step 1 --arxiv-id $ARXIV_ID',
        model="opus",
        instruction="Launch one sub-agent per arXiv ID.\nUse a SINGLE message with multiple Task tool calls.\n\nThese markdown files become the scientific basis for downstream work.\nCost of error amplifies: subpar markdown -> subpar knowledge.",
    )


def build_mode2_dispatch() -> str:
    """Build MODE 2 dispatch instructions."""
    return template_dispatch(
        agent_type="general-purpose",
        template=MODE2_TEMPLATE,
        targets=[{"ARXIV_ID": "EXAMPLE", "DEST_FILE": "EXAMPLE"}],
        command=f'python3 -m {SUBAGENT_MODULE_PATH} --step 1 --arxiv-id $ARXIV_ID --dest-file \'$DEST_FILE\'',
        model="opus",
        instruction="Launch one sub-agent per arXiv ID.\nUse a SINGLE message with multiple Task tool calls.\n\nThese markdown files become the scientific basis for downstream work.\nCost of error amplifies: subpar markdown -> subpar knowledge.",
    )


def build_discover_body() -> str:
    """Build step 1 body with both dispatch modes."""
    return (
        DISCOVER_INSTRUCTIONS
        + build_mode1_dispatch() + "\n"
        + MODE2_DISCOVERY_INSTRUCTIONS
        + build_mode2_dispatch()
    )


def build_next_command(step: int) -> str | None:
    """Build invoke command for next step."""
    if step == 1:
        return f'python3 -m {MODULE_PATH} --step 2'
    elif step == 2:
        return f'python3 -m {MODULE_PATH} --step 3'
    elif step == 3:
        return None
    return None


# ============================================================================
# STEP DEFINITIONS
# ============================================================================

STATIC_STEPS = {
    2: ("Wait for Completion", WAIT_INSTRUCTIONS),
    3: ("Finalize", FINALIZE_INSTRUCTIONS),
}


def _format_step_1() -> tuple[str, str]:
    """Step 1: Discover and Dispatch - dynamic body generation."""
    return ("Discover and Dispatch", build_discover_body())


DYNAMIC_STEPS = {
    1: _format_step_1,
}


# ============================================================================
# OUTPUT FORMATTING
# ============================================================================


def format_output(step: int) -> str:
    """Format output for the given step."""
    if step in STATIC_STEPS:
        title, instructions = STATIC_STEPS[step]
    elif step in DYNAMIC_STEPS:
        formatter = DYNAMIC_STEPS[step]
        title, instructions = formatter()
    else:
        return f"ERROR: Invalid step {step}"

    next_cmd = build_next_command(step)
    return format_step(instructions, next_cmd or "", title=f"ARXIV-TO-MD - {title}")


# ============================================================================
# ENTRY POINT
# ============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="arxiv-to-md orchestrator",
        epilog="Steps: discover (1) -> wait (2) -> finalize (3)",
    )
    parser.add_argument("--step", type=int, required=True, help="Current step (1-3)")
    args = parser.parse_args()

    if args.step < 1 or args.step > 3:
        sys.exit(f"ERROR: --step must be 1-3, got {args.step}")

    output = format_output(args.step)
    print(output)


if __name__ == "__main__":
    main()
