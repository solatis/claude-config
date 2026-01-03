---
name: intake-bugs-analysis
description: Automated bug analysis for Intake team - matches bugs to exports, runs AI analysis with Claude, and discovers patterns to reduce no-code bugs
---

# Intake Bugs Analysis

Analyzes bugs reported by the Operations team to identify patterns, root causes,
and actionable improvements. Part of the Bugs Initiative to reduce no-code bugs.

## Invocation

When this skill activates:

1. **Verify prerequisites exist**:
   - Check `inputs/exports/` contains HTML files
   - Check `inputs/bug_list.csv` exists
   - If missing, see `resources/troubleshooting.md`

2. **Ask the user for the analysis period**:
   - `December 2025` (month + year)
   - `December 15, 2025` (specific date)
   - `December 1-15, 2025` (date range)

3. **Set working directory**: `cd logs/bug-analysis`

4. **Display summary before running**:
   - Total bugs found in CSV
   - HTML files matched
   - Estimated time (~3 seconds per bug)

5. **Run the pipeline**:
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
