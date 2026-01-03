# intake-bugs-analysis

Automated bug analysis skill for Intake team using AI-powered pattern discovery.

## Files

| File                        | What                                          | When to read                                          |
| --------------------------- | --------------------------------------------- | ----------------------------------------------------- |
| `SKILL.md`                  | Skill definition and invocation trigger       | Understanding when skill activates                    |
| `README.md`                 | User-facing skill documentation               | Explaining skill to users                             |
| `NOTION_OUTPUT_TEMPLATE.md` | Notion-formatted output template              | Generating final Notion-ready comparison report       |

## Subdirectories

| Directory  | What                                    | When to read                                          |
| ---------- | --------------------------------------- | ----------------------------------------------------- |
| `scripts/` | Python analysis pipeline implementation | Debugging pipeline, understanding script interactions |

---

## Instructions for Claude

> **Workflow overview**: See `SKILL.md` for the 5-step invocation workflow. This file provides detailed guidance for each step.

When this skill is invoked:

## 1. Ask for Period (Required)

Immediately ask the user:

```
What period should I analyze?
```

**Valid formats:**
- `December 2025` (month + year)
- `December 15, 2025` (specific date)
- `December 1-15, 2025` (date range)

Store this in a variable for use in the final report.

## 2. Verify Data Setup

Check if these exist:
- `bug-analysis/data/bug_list.csv`
- `bug-analysis/data/exports/` (with HTML files)

If missing, provide clear setup instructions:

**For CSV**:
```
Please export your bug list from Notion as CSV and save it to:
bug-analysis/data/bug_list.csv

Required columns: Name, ID, Type, Assignee(s), Created by, Created time
```

**For HTML exports**:
```
Please export bugs from Notion:
1. Filter your bug database (by team and period)
2. Click "..." menu → Export
3. Format: HTML
4. Include subpages: Yes
5. Extract the ZIP to: bug-analysis/data/exports/
```

## 3. Run the Pipeline

**Note**: The scripts call `claude` CLI as a subprocess, which can be slow when running from within Claude Code. Some bugs may timeout.

**Recommended approach**:

```bash
cd bug-analysis/scripts
python3 run_full_analysis.py --period "{user_provided_period}" --timeout 120
```

The `--timeout` parameter (default: 120 seconds) controls how long to wait for each Claude CLI call.

**Expected behavior**:
- Most bugs complete successfully
- 1-2 bugs may timeout and need retry
- If bugs timeout, just re-run - the script auto-resumes and only processes missing bugs

## 4. Monitor Progress

**Note**: The analysis runs in the background and takes 2-3 minutes for ~50 bugs. Lack of immediate output is normal.

**How to monitor progress correctly**:

1. **Set realistic expectations**:
   - 50 bugs × 2-3 seconds each = ~2-3 minutes minimum
   - Background tasks don't show real-time output
   - Wait at least 30 seconds before first check

2. **Check actual progress** (not just task status):
   ```bash
   # Count completed analyses - do this every 30-60 seconds
   ls bug-analysis/data/results/individual/*.md | wc -l
   ```

   Show the user: "Progress: 15/49 bugs analyzed (31%)..."

3. **Trust the process**:
   - If the test run worked (first 2-3 bugs), the full run will work
   - Don't start multiple competing tasks
   - Don't assume it's stuck just because there's no output

4. **Read output files directly** (if needed to debug):
   ```bash
   tail -20 /tmp/claude/.../task_id.output
   ```

5. **Timeline to show user**:
   - "Analysis started - this will take ~2-3 minutes for 49 bugs"
   - After 30s: "Progress: X/49 bugs analyzed..."
   - After 60s: "Progress: Y/49 bugs analyzed..."
   - Continue until complete

**Patience rules**:
- Check progress every 30-60 seconds (not more frequently)
- Wait for at least 30 seconds of no output before investigating
- Let the current task complete before starting another
- Run only one analysis task at a time

## 5. Present Results

**PRIMARY OUTPUT**: Generate a Notion-formatted comparison document using `NOTION_OUTPUT_TEMPLATE.md`.

### Generate Notion-Ready Output

1. **Read the template**: Use `NOTION_OUTPUT_TEMPLATE.md` in this skill directory as the format guide

2. **Replace template placeholders**:
   - `{period}`: User-provided period (e.g., "December 2025")
   - `{date}`: Today's date (e.g., "January 3, 2025")
   - `{N}`: Bug counts from analysis
   - `{%}`: Calculated percentages

3. **Populate sections with data from**:
   - Executive summary: Extract from `pattern_analysis.md`
   - Pattern categories: All discovered categories with examples
   - Priority recommendations: Top 5 actions by impact
   - Key insights: Technical and process discoveries
   - Comparison: Compare with any previous manual analysis if available
   - All bugs: Complete list of analyzed bug IDs

4. **Save to**: `bug-analysis/NOTION_COMPARISON.md`

5. **Display to user**:
   - Executive Summary (full section)
   - Top 3 Pattern Categories (name, count, pattern, recommended fix)
   - Top 3 Priority Recommendations
   - Location of full file

6. **Tell the user**:
   ```
   I've generated a Notion-ready analysis at: bug-analysis/NOTION_COMPARISON.md

   This is formatted for copy-paste into your Bugs Initiative:
   https://www.notion.so/pivotapp/Bugs-initiative-28b1a2c7a208805497c1fe9b30f4aec1

   Additional files:
   - Individual bug analyses: bug-analysis/data/results/individual/
   - Raw pattern report: bug-analysis/data/results/summary/pattern_analysis.md
   ```

## 6. Next Steps

Suggest:
```
Next steps:
1. Review the full pattern analysis report
2. Share top priorities with your team
3. Create tickets for the recommended fixes
4. Schedule follow-up analysis next month to track improvement
```

## Error Handling

### BeautifulSoup4 not installed
Try in order:
1. `pip install beautifulsoup4`
2. If permission error: `pip install --user beautifulsoup4`
3. If externally-managed error: `pip install --user --break-system-packages beautifulsoup4`

### Some bugs timeout during analysis
This is expected when calling `claude` CLI from within Claude Code:
- The script auto-resumes, so just run it again
- Already-analyzed bugs are skipped automatically
- Only the failed bugs will be re-processed
- Usually 1-2 retries completes all bugs

```bash
# Just re-run the pipeline - it auto-resumes
python3 run_full_analysis.py --period "{period}" --timeout 180
```

### No bugs matched
- Verify HTML files are in `exports/` directory
- Check bug IDs in CSV match those in HTML filenames
- Run matching script separately to debug

### Analysis fails for specific bugs
- Script will continue with other bugs
- Failed bugs are logged
- User can investigate HTML file for that bug manually

## Advanced Usage

If user wants more control, they can:
- Run scripts individually (show them the commands)
- Analyze a subset first (`--limit 10`)
- Re-analyze specific bugs (`--no-resume`)
- Change output directories

## Important Notes

- The script auto-resumes - won't re-analyze bugs that already have results
- Pattern discovery is bottom-up - categories come from the actual data
- This is designed for Intake team but works for any team's bugs
- Results feed directly into the Bugs Initiative planning
