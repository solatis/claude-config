# Troubleshooting & Setup

## Data Setup

**HTML exports** - Export bugs from Notion:
1. Filter bug database by team and period
2. Click "..." menu → Export → HTML → Include subpages: Yes
3. Extract ZIP to `inputs/exports/`

**Bug list CSV** - Export from Notion database view:
- https://www.notion.so/pivotapp/1491a2c7a2088047aaa6ec67f005a0db?v=1511a2c7a20880568e63000c072f4a7a
- Save to `inputs/bug_list.csv`
- Required columns: Name, ID, Type, Assignee(s), Created by, Created time

## BeautifulSoup4 not installed

Try in order:
1. `pip install beautifulsoup4`
2. If permission error: `pip install --user beautifulsoup4`
3. If externally-managed error: `pip install --user --break-system-packages beautifulsoup4`

## Claude CLI not found

```bash
npm install -g @anthropic-ai/claude-code
```

## Bugs timeout during analysis

Expected when calling `claude` CLI from within Claude Code. The script auto-resumes:

```bash
# Just re-run - already-analyzed bugs are skipped
# {period} format: "December 2025", "December 15, 2025", or "December 1-15, 2025"
python3 ~/.claude/skills/intake-bugs-analysis/scripts/run_full_analysis.py --period "{period}" --timeout 180
```

## No bugs matched

1. Verify HTML files exist in `inputs/exports/`
2. Check bug IDs in CSV match HTML filenames
3. Debug with: `python3 ~/.claude/skills/intake-bugs-analysis/scripts/match_bugs_to_html.py`

## Analysis fails for specific bugs

- Script continues with remaining bugs
- Failed bugs are logged
- Investigate the HTML file manually if needed

## Running steps individually

For debugging or testing a subset (run from `logs/bug-analysis/`):

```bash
# Step 1: Match only
python3 ~/.claude/skills/intake-bugs-analysis/scripts/match_bugs_to_html.py

# Step 2: Analyze (with limit)
python3 ~/.claude/skills/intake-bugs-analysis/scripts/analyze_bugs.py --limit 10

# Step 3: Patterns only
python3 ~/.claude/skills/intake-bugs-analysis/scripts/categorize_patterns.py --period "December 2025"
```

## Pipeline options

| Option | Description |
|--------|-------------|
| `--limit N` | Analyze first N bugs only |
| `--timeout N` | Seconds per Claude CLI call (default: 120) |
| `--skip-matching` | Skip step 1 if already done |
| `--skip-analysis` | Skip step 2, go straight to patterns |
| `--no-resume` | Force re-analyze all bugs |
