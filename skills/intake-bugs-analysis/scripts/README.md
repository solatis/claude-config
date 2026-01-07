# Bug Analysis Pipeline

## Overview

Four-stage pipeline that transforms Notion bug exports into pattern-based analysis reports using AI.

## Architecture

### Pipeline Flow

```
1. match_bugs_to_html.py    → Maps bug IDs to exported HTML files
2. analyze_bugs.py          → Extracts and analyzes each bug (calls Claude CLI)
3. categorize_patterns.py   → Discovers patterns across all analyses
4. run_full_analysis.py     → Orchestrates full pipeline with error handling
```

**Data flow:**
- Input: `bug_list.csv` + `exports/*.html`
- Intermediate: `bug_list_matched.csv` + `results/individual/*.md`
- Output: `results/summary/pattern_analysis.md`

### Key Interactions

- **Auto-resume across scripts**: Each script checks for existing output files and skips already-processed bugs. This allows retrying failed bugs without duplicate work.
- **Claude CLI as subprocess**: `analyze_bugs.py` calls `claude` CLI for AI analysis. When invoked from within Claude Code, these subprocess calls can be slow and timeout. Use `--timeout 180` (3 minutes) to prevent failures.
- **Error isolation**: Pipeline continues processing remaining bugs if individual bugs fail. Failed bugs are logged but don't block the full run.

## Design Decisions

**Why separate match/analyze/categorize scripts?**
- Allows debugging each stage independently
- Match results are cached (CSV) for fast re-analysis
- Analysis can be paused/resumed without re-matching
- Pattern discovery can be re-run without re-analyzing bugs

**Why auto-resume instead of force re-run?**
- 50 bugs × 2-3 minutes = significant time investment
- Network/timeout issues are transient - retry should be cheap
- Allows incremental analysis as new bugs are added

**Why Claude CLI subprocess instead of direct API?**
- Skill uses existing Claude Code authentication
- No API key management needed
- Consistent with skill environment philosophy

## Shared Module

**Why shared.py exists:**
The `shared.py` module consolidates bug analysis utilities used by both `analyze_bugs.py` and `categorize_patterns.py`. This grouping reflects the shared domain concept of "bug analysis utilities" rather than generic helpers.

**What it provides:**
- Resolution detection with dual-format handling (bold/non-bold markdown)
- Bug title parsing using "):" delimiter
- Notion link generation and markdown injection
- Analysis filtering by status (pending/undocumented/resolved)

**Design tradeoffs:**
- **Duplication removed vs indirection added**: Eliminates 8 duplicated resolution checks, at cost of import statement in each script
- **Single file vs granular modules**: Simpler imports for 4-script skill; acceptable growth risk given skill scope

## Invariants

- **Matching before analysis**: `analyze_bugs.py` expects `bug_list_matched.csv` to exist
- **HTML file availability**: All bugs in matched CSV must have corresponding HTML files in `exports/`
- **Individual before patterns**: `categorize_patterns.py` requires individual analyses to exist
- **File naming convention**: Individual analyses must be named `PIVOT-{id}.md` for auto-resume to work
