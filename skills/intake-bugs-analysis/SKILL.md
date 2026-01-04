---
name: intake-bugs-analysis
description: Invoke IMMEDIATELY via python script to run Intake bug analysis. Use when asked to "run intake bugs analysis", "analyze intake bugs", or "use intake-bugs-analysis skill". Do NOT activate on general bug discussions.
---

# Intake Bugs Analysis

Analyzes bugs reported by the Operations team to identify patterns, root causes,
and actionable improvements. Part of the Bugs Initiative to reduce no-code bugs.

## Activation

This skill should ONLY activate when the user explicitly requests it:

**Trigger phrases (activate):**
- "run intake bugs analysis"
- "analyze intake bugs"
- "use intake-bugs-analysis skill"
- "run the bug analysis pipeline"

**Do NOT activate on:**
- General bug discussions ("let's analyze this bug")
- Questions about bug patterns ("what patterns do we see?")
- Other bug-related tasks without explicit skill invocation

## Invocation

When this skill activates:

1. **Verify prerequisites exist**:
   - Check `inputs/exports/` contains HTML files
   - Check `inputs/bug_list.csv` exists

   **If files are missing, STOP.** Do NOT:
   - Search for files in Downloads or other directories
   - Extract or unzip any archive files
   - Copy files from the exports folder to create bug_list.csv
   - Create or generate any input files

   Instead, IMMEDIATELY use AskUserQuestion to ask the user to provide the missing files.
   Tell them to see `resources/troubleshooting.md` for instructions on how to export from Notion.
   Wait for the user to confirm files are in place before proceeding.

2. **Ask the user for the analysis period**:
   - `December 2025` (month + year)
   - `December 15, 2025` (specific date)
   - `December 1-15, 2025` (date range)

3. **Set working directory**: `cd logs/bug-analysis`

4. **Display summary and request confirmation**:
   - Total bugs found in CSV
   - HTML files matched
   - Bugs with "Pending" status (will be analyzed but excluded from pattern categorization)
   - Estimated time (~3 seconds per bug)

   **If pending bugs detected**, display:
   ```
   ⚠️ Excluding N bugs still pending investigation:
     - PIVOT-XXXXX: [title]
     - PIVOT-YYYYY: [title]
   These will not be included in pattern analysis. Re-run after resolution.
   ```

   - **Ask: "Proceed with analysis? (yes/no)"**
   - **STOP and wait for user confirmation**
   - If user declines, abort gracefully

   **Note**: Pending bugs are analyzed individually but excluded from the pattern report since their root causes are not yet determined.

5. **Run the pipeline** (only after confirmation):
   ```bash
   python3 ~/.claude/skills/intake-bugs-analysis/scripts/run_full_analysis.py --period "{period}" --timeout 120
   ```

6. **Generate Notion output**:
   - Read `outputs/summary/pattern_analysis.md` for analysis results
   - Read `NOTION_OUTPUT_TEMPLATE.md` for output structure
   - Fill placeholders using data from pattern analysis
   - Save to `NOTION_COMPARISON.md`
   - Display executive summary and top 3 patterns to user

## Workflow

The pipeline runs three steps automatically:

1. **Match**: Maps bug IDs from CSV to HTML export files
2. **Analyze**: Extracts data from HTML, calls Claude CLI for each bug
3. **Patterns**: Discovers categories bottom-up, generates recommendations

Auto-resume: Skips already-analyzed bugs on re-run.

## Output

| File | Contents |
|------|----------|
| `outputs/individual/PIVOT-{ID}.md` | Per-bug analysis (root cause, findings, resolution) |
| `outputs/summary/pattern_analysis.md` | Categories, priorities, insights |
| `NOTION_COMPARISON.md` | Notion-ready report |

## Resources

| Resource | Read when |
|----------|-----------|
| `resources/troubleshooting.md` | Errors, debugging, advanced options |
| `resources/monitoring.md` | Pipeline is running |
