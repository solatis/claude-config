#!/usr/bin/env python3
"""arxiv-to-md sub-agent: Convert a single arXiv paper to markdown.

Arguments:
  --arxiv-id   Required. The arXiv ID to convert (YYMM.NNNNN format).
  --dest-file  Optional. When provided by orchestrator, skip metadata extraction.
               The orchestrator has already determined the destination filename.

6-step workflow:
  1. Fetch     - Download and extract arXiv source; extract metadata if --dest-file not provided
  2. Preprocess - Expand inputs, normalize encoding
  3. Convert   - TeX to markdown via pandoc
  4. Clean     - Inventory sections, remove unwanted
  5. Verify    - Factored verification: source vs output
  6. Validate  - Check output quality, return FILE: (+ TITLE/DATE if no --dest-file) or FAIL:
"""

import argparse
import sys

from skills.lib.paths import get_scripts_dir
from skills.lib.workflow.prompts import format_step


# ============================================================================
# CONFIGURATION
# ============================================================================

MODULE_PATH = "skills.arxiv_to_md.sub_agent"


# ============================================================================
# MESSAGE TEMPLATES
# ============================================================================

# --- STEP 1: FETCH -----------------------------------------------------------

FETCH_INSTRUCTIONS = (
    "Create working directory and download source:\n"
    "  mkdir -p /tmp/arxiv_<id>\n"
    "  curl -L https://arxiv.org/e-print/<id> -o /tmp/arxiv_<id>/source.tar.gz\n"
    "\n"
    "Extract the tarball:\n"
    "  cd /tmp/arxiv_<id> && tar -xzf source.tar.gz\n"
    "\n"
    "Find the main .tex file:\n"
    "  - Use Glob tool to find *.tex files\n"
    "  - Use Read tool to identify which contains \\documentclass\n"
    "  - Common names: main.tex, paper.tex, <arxiv_id>.tex\n"
    "\n"
    "IF NO .tex FILES FOUND (PDF-only submission):\n"
    "  Try older versions - TeX source may exist in earlier revisions.\n"
    "  arXiv IDs support version suffix: <id>v1, <id>v2, etc.\n"
    "\n"
    "  1. Check https://arxiv.org/abs/<id> to find available versions\n"
    "  2. Try downloading older versions in reverse order:\n"
    "     curl -L https://arxiv.org/e-print/<id>v<N-1> -o source.tar.gz\n"
    "  3. Stop when you find a version with .tex source\n"
    "  4. If no version has TeX source, respond: FAIL: PDF-only submission\n"
    "\n"
    "EXTRACT PAPER METADATA (only when --dest-file NOT provided):\n"
    "\n"
    "IF --dest-file was NOT provided:\n"
    "  1. TITLE - Extract from the main .tex file:\n"
    "     - Look for \\title{...} command\n"
    "     - May span multiple lines: \\title{First Line\n"
    "         Second Line}\n"
    "     - Strip LaTeX commands (\\textbf, \\emph, etc.)\n"
    "     - Collapse whitespace to single spaces\n"
    "     - Handle subtitles: if title contains ':' keep it\n"
    "\n"
    "  2. DATE - Fetch submission date from arXiv abstract page:\n"
    "     - Use WebFetch on https://arxiv.org/abs/<id>\n"
    "     - Find the first submission date (not revision date)\n"
    "     - Format: look for 'Submitted' or '[v1]' date\n"
    "     - Convert to YYYY-MM-DD format\n"
    "\n"
    "IF --dest-file WAS provided:\n"
    "  Skip metadata extraction - orchestrator already determined filename.\n"
    "\n"
    "OUTPUT:\n"
    "```\n"
    "source_dir: /tmp/arxiv_<id>\n"
    "main_tex: <filename>.tex\n"
    "version: <vN if not latest>\n"
    "paper_title: <extracted title>      # only if --dest-file not provided\n"
    "submission_date: YYYY-MM-DD         # only if --dest-file not provided\n"
    "```"
)

# --- STEP 2: PREPROCESS ------------------------------------------------------

PREPROCESS_INSTRUCTIONS = (
    "Run TeX preprocessing via Bash tool:\n"
    "\n"
    "```bash\n"
    "python3 << 'EOF'\n"
    "import sys\n"
    f"sys.path.insert(0, {str(get_scripts_dir())!r})\n"
    "from skills.arxiv_to_md.tex_utils import preprocess_tex\n"
    "\n"
    "result = preprocess_tex('<source_dir>/<main_tex>')\n"
    "print(f'Preprocessed: {result}')\n"
    "EOF\n"
    "```\n"
    "\n"
    "This:\n"
    "  - Expands \\input{} and \\include{} statements recursively\n"
    "  - Inlines .bbl bibliography file (if present) for citation resolution\n"
    "  - Normalizes encoding to UTF-8\n"
    "\n"
    "OUTPUT:\n"
    "```\n"
    "preprocessed: <source_dir>/preprocessed.tex\n"
    "```"
)

# --- STEP 3: CONVERT ---------------------------------------------------------

CONVERT_INSTRUCTIONS = (
    "Run conversion via Bash tool:\n"
    "\n"
    "```bash\n"
    "pandoc <source_dir>/preprocessed.tex -f latex -t markdown --wrap=none -o <source_dir>/raw.md\n"
    "```\n"
    "\n"
    "Math formulas ($...$ and $$...$$) are preserved automatically.\n"
    "\n"
    "OUTPUT:\n"
    "```\n"
    "raw_md: <source_dir>/raw.md\n"
    "```"
)

# --- STEP 4: CLEAN -----------------------------------------------------------

CLEAN_INSTRUCTIONS = (
    "Use the Read tool on <source_dir>/raw.md.\n"
    "\n"
    "INVENTORY - Extract all section headings from raw.md:\n"
    "  List every heading (# through ####) in document order.\n"
    "  Tag each as:\n"
    "    [REMOVE] - References, Bibliography, Acknowledgments, Acknowledgements\n"
    "    [KEEP]   - Everything else\n"
    "\n"
    "THEN perform cleaning:\n"
    "\n"
    "REMOVE these sections:\n"
    "  - References / Bibliography\n"
    "    (heading + all content until next heading or EOF)\n"
    "  - Acknowledgements / Acknowledgments\n"
    "    (heading + all content until next heading or EOF)\n"
    "\n"
    "REPLACE image references with placeholders:\n"
    "  - ![alt](path) patterns -> [IMAGE: alt or filename]\n"
    "  - Preserve figure captions in placeholder text\n"
    "\n"
    "PRESERVE everything else:\n"
    "  - Abstract, Introduction, Methods, Results, Conclusion, Discussion\n"
    "  - All math formulas ($ and $$ delimiters)\n"
    "  - Tables with their content and formatting\n"
    "  - Inline citations [1], [2], etc.\n"
    "\n"
    "WRAP remnant LaTeX for LLM comprehension:\n"
    "  - Any unconverted LaTeX (tables, environments) -> wrap in ```latex blocks\n"
    "  - Mathematical equations ($...$, $$...$$) -> wrap in ```latex blocks\n"
    "  - This hints to LLMs how to interpret the content\n"
    "  Example:\n"
    "    Before: The loss is $L = \\sum_i (y_i - \\hat{y}_i)^2$\n"
    "    After:  The loss is ```latex $L = \\sum_i (y_i - \\hat{y}_i)^2$ ```\n"
    "\n"
    "CONVERT pandoc citation markers:\n"
    "  - [@key] patterns -> [key] (strip the @ symbol)\n"
    "  - [@key1; @key2] -> [key1; key2]\n"
    "  - This removes pandoc-specific syntax while preserving citation intent\n"
    "\n"
    "Use the Write tool to save to <source_dir>/cleaned.md.\n"
    "\n"
    "OUTPUT:\n"
    "```\n"
    "sections_inventory:\n"
    "  - [KEEP] Abstract\n"
    "  - [KEEP] Introduction\n"
    "  - [KEEP] Methods\n"
    "  - ... (all sections in order)\n"
    "  - [REMOVE] Acknowledgments\n"
    "  - [REMOVE] References\n"
    "\n"
    "cleaned_md: <source_dir>/cleaned.md\n"
    "sections_removed: [list of heading names]\n"
    "images_replaced: <count>\n"
    "```"
)

# --- STEP 5: VERIFY ----------------------------------------------------------

VERIFY_INSTRUCTIONS = (
    "FACTORED VERIFICATION (source-based checking)\n"
    "\n"
    "For EACH [KEEP] section from step 4 inventory:\n"
    "  1. Open-ended verification question (NOT yes/no):\n"
    "     'What content appears under [Section Name] in cleaned.md?'\n"
    "  2. Compare against raw.md (use Read tool on both files):\n"
    "     - Does the section exist in cleaned.md?\n"
    "     - Is the content substantively present?\n"
    "     - Any unexpected truncation?\n"
    "\n"
    "CRITICAL: Verify against raw.md, NOT from memory.\n"
    "(Factored verification prevents hallucination transfer)\n"
    "\n"
    "OUTPUT:\n"
    "```\n"
    "verification_results:\n"
    "  - Abstract: [PRESENT] first paragraph matches\n"
    "  - Introduction: [PRESENT] N paragraphs preserved\n"
    "  - Methods: [PRESENT] N subsections intact\n"
    "  - ... (each [KEEP] section)\n"
    "\n"
    "content_delta:\n"
    "  raw_word_count: N\n"
    "  cleaned_word_count: M\n"
    "  ratio: M/N (expect 0.70-0.95)\n"
    "\n"
    "COMPLETENESS: [PASS | FAIL: <missing sections>]\n"
    "```\n"
    "\n"
    "If FAIL: Report missing sections and STOP."
)

# --- STEP 6: VALIDATE --------------------------------------------------------

VALIDATE_INSTRUCTIONS = (
    "Use the Read tool on <source_dir>/cleaned.md.\n"
    "\n"
    "Validate:\n"
    "  1. Markdown structure intact (headings render properly)\n"
    "  2. Math delimiters balanced ($ and $$ counts should be even)\n"
    "  3. Section count matches inventory [KEEP] count\n"
    "  4. No raw LaTeX commands visible (\\section, \\begin, etc.)\n"
    "  5. Word count sanity (from step 5):\n"
    "     - ratio < 0.70: content may be missing\n"
    "     - ratio > 0.95: removal may have failed\n"
    "\n"
    "TERMINAL OUTPUT (respond with ONLY one of these):\n"
    "\n"
    "If validation PASSED:\n"
    "  FILE: <source_dir>/cleaned.md\n"
    "  IF --dest-file was NOT provided:\n"
    "    TITLE: <paper_title from step 1>\n"
    "    DATE: <submission_date from step 1>\n"
    "\n"
    "If validation FAILED:\n"
    "  FAIL: <concise reason>\n"
    "\n"
    "The orchestrator parses this response.\n"
    "Include TITLE and DATE only when --dest-file was NOT provided."
)


# ============================================================================
# MESSAGE BUILDERS
# ============================================================================


def build_next_command(step: int, arxiv_id: str, dest_file: str | None) -> str | None:
    """Build invoke command for next step with passthrough args."""
    if step >= 6:
        return None

    cmd_parts = [
        "python3 -m", MODULE_PATH,
        f"--step {step + 1}",
        f"--arxiv-id {arxiv_id}"
    ]
    if dest_file:
        cmd_parts.append(f"--dest-file {dest_file}")

    return " ".join(cmd_parts)


# ============================================================================
# STEP DEFINITIONS
# ============================================================================

STATIC_STEPS = {
    2: ("Preprocess", PREPROCESS_INSTRUCTIONS),
    3: ("Convert", CONVERT_INSTRUCTIONS),
    4: ("Clean", CLEAN_INSTRUCTIONS),
    5: ("Verify Completeness", VERIFY_INSTRUCTIONS),
    6: ("Validate and Report", VALIDATE_INSTRUCTIONS),
}


def _format_step_1(arxiv_id: str, dest_file: str | None) -> tuple[str, str]:
    """Step 1: Fetch - dynamic context prepending."""
    context_lines = [f"arXiv ID: {arxiv_id}"]
    if dest_file:
        context_lines.append(f"Destination: {dest_file}")
    context_lines.append("")

    body = "\n".join(context_lines) + "\n" + FETCH_INSTRUCTIONS
    return ("Fetch", body)


DYNAMIC_STEPS = {
    1: _format_step_1,
}


# ============================================================================
# OUTPUT FORMATTING
# ============================================================================


def format_output(step: int, arxiv_id: str, dest_file: str | None) -> str:
    """Format output for the given step."""
    if step in STATIC_STEPS:
        title, instructions = STATIC_STEPS[step]
    elif step in DYNAMIC_STEPS:
        formatter = DYNAMIC_STEPS[step]
        title, instructions = formatter(arxiv_id, dest_file)
    else:
        return f"ERROR: Invalid step {step}"

    next_cmd = build_next_command(step, arxiv_id, dest_file)
    return format_step(instructions, next_cmd or "", title=f"ARXIV-TO-MD SUB-AGENT - {title}")


# ============================================================================
# ENTRY POINT
# ============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="arxiv-to-md sub-agent: single paper conversion",
        epilog="Steps: fetch (1) -> preprocess (2) -> convert (3) -> clean (4) -> verify (5) -> validate (6)",
    )
    parser.add_argument("--step", type=int, required=True, help="Current step (1-6)")
    parser.add_argument("--arxiv-id", type=str, required=True, help="arXiv ID to convert")
    parser.add_argument(
        "--dest-file",
        type=str,
        help="Destination filename (when orchestrator determines it). Skips metadata extraction.",
    )
    args = parser.parse_args()

    if args.step < 1 or args.step > 6:
        sys.exit(f"ERROR: --step must be 1-6, got {args.step}")

    output = format_output(args.step, args.arxiv_id, args.dest_file)
    print(output)


if __name__ == "__main__":
    main()
