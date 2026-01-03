---
name: intake-bugs-analysis
description: Automated bug analysis for Intake team - matches bugs to exports, runs AI analysis with Claude, and discovers patterns to reduce no-code bugs
---

# Intake Bugs Analysis

Analyzes bugs reported by the Operations team to identify patterns, root causes, and actionable improvements. Part of the Bugs Initiative to reduce no-code bugs (50% of Intake bugs).

## Invocation

When this skill activates:

1. **Verify prerequisites exist**:
   - Check `data/exports/` contains HTML files
   - Check `bug_list.csv` exists
   - If missing, guide user to set up data first (see Data Setup)

2. **Ask the user for the analysis period**
   - **Valid formats:**
     - `December 2025` (month + year)
     - `December 15, 2025` (specific date)
     - `December 1-15, 2025` (date range)

3. **Confirm data directory** (default: `bug-analysis/data`)

4. **Display summary before running**:
   - Total bugs found in CSV
   - HTML files matched
   - Estimated time (2-3 seconds per bug)

5. **Run the complete pipeline**:

```bash
python3 scripts/run_full_analysis.py --period "{user_provided_period}" --timeout 120
```

## Workflow

The skill runs three steps automatically:

### Step 1: Match Bugs to HTML Exports
- Reads bug list CSV
- Matches each bug ID to its exported HTML file
- Creates `bug_list_matched.csv`

### Step 2: Analyze Individual Bugs
- Extracts data from each HTML file (status, PR, comments, tech investigation)
- Calls Claude CLI for AI analysis
- Generates structured summaries (Root Cause, Key Findings, Resolution)
- Saves one markdown file per bug
- **Auto-resumes**: Skips already-analyzed bugs

### Step 3: Discover Patterns
- Reads all individual analyses
- Uses Claude to discover categories bottom-up
- Identifies recurring patterns
- Generates aggregated summary with priority recommendations

## User Interaction

Before running the pipeline (see Invocation step 4), display:
- Total bugs to analyze
- Estimated time (2-3 seconds per bug)
- Output locations

Show progress as the analysis runs. The pipeline outputs status updates automatically.

## Output

### Individual Analyses
`results/individual/PIVOT-{ID}.md`:
```markdown
## PIVOT-12345: Bug title

**Root Cause**: What caused the bug

**Key Findings**:
- Discovery 1
- Discovery 2
- Discovery 3

**Resolution**: Code fix/Manual fix/Not a bug - explanation

**Status**: Done
**PR**: https://github.com/...
```

### Pattern Analysis
`results/summary/pattern_analysis.md`:
- Executive summary (code fixes vs no-code)
- Categories with bug counts and percentages
- Priority recommendations
- Key insights

## When to Use Step-by-Step Control

Use individual scripts ONLY when:
- **Debugging**: A step failed and you need to retry just that step
- **Testing**: User wants to analyze a small subset first (`--limit 10`)
- **Partial runs**: Running pattern analysis on existing individual analyses

For normal operation, always use the main pipeline command.

```bash
# Step 1: Match
python3 scripts/match_bugs_to_html.py

# Step 2: Analyze (with options)
python3 scripts/analyze_bugs.py --limit 10  # Test on 10 bugs first

# Step 3: Patterns
python3 scripts/categorize_patterns.py --period "December 2025"
```

## Prerequisites

- Python 3.8+
- Claude CLI: `npm install -g @anthropic-ai/claude-code`
- BeautifulSoup4:
  1. Try: `pip install beautifulsoup4`
  2. If permission error: `pip install --user beautifulsoup4`
  3. If externally-managed error: `pip install --user --break-system-packages beautifulsoup4`

## Data Setup

Verify these files exist before running the pipeline:

1. **HTML exports** in `data/exports/`:
   - Export bugs from Notion as HTML
   - Each bug should be a separate `.html` file

2. **Bug list CSV** (`bug_list.csv`):
   - Export from Notion database view
   - Required columns: Name, ID, Type, Assignee(s), Created by, Created time

**If files are missing**: Guide user through Notion export process. Do NOT proceed until data is ready.

## Error Handling

- If BeautifulSoup4 not installed: Provide install command
- If HTML files missing: Guide user to export from Notion
- If CSV missing: Explain required format
- If Claude CLI fails: Check installation and API access

## Notes

- Auto-resume prevents duplicate analysis
- Pattern discovery uses actual bug data (no predefined categories)
- Full documentation: `/doc/bug-analysis-process.md`
