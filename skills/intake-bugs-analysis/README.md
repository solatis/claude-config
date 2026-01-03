# Intake Bugs Analysis Skill

Automated analysis of bugs reported by the Ops team to identify patterns and reduce no-code bugs.

## What It Does

This skill orchestrates a complete bug analysis workflow:

1. **Matches** bugs from your CSV to their Notion HTML exports
2. **Analyzes** each bug with Claude AI to extract root cause, key findings, and resolution type
3. **Discovers patterns** bottom-up from the analyses to identify recurring issues
4. **Generates reports** with categorized bugs and priority recommendations

## Why Use This

Part of the **Bugs Initiative** to reduce the high volume of bugs affecting team velocity:

- **~50% of Intake bugs** are "no-code bugs" (resolved without code changes)
- These bugs can be prevented through better documentation, UX improvements, or Ops tools
- Pattern analysis identifies the most impactful improvements to make

## Results

### Before
- Manual bug-by-bug investigation
- No systematic pattern identification
- Unknown which improvements would have most impact

### After
- Automated analysis of all bugs in minutes
- Data-driven pattern discovery
- Clear priority list of fixes by impact

## Usage

Simply invoke the skill:
```
Use the intake-bugs-analysis skill on my December bugs
```

The skill will:
1. Ask you for the analysis period
2. Verify your data setup
3. Run the complete pipeline
4. Show you the results

## Output Example

**Individual bug analysis**:
```markdown
## PIVOT-23629: Vendor VAT validation bug

**Root Cause**: PATCH endpoint missing uniqueness validation that POST had

**Key Findings**:
- Validation worked on creation but not updates
- Users could bypass by creating then updating
- Not a regression - was never implemented

**Resolution**: Code fix - Added validation to PATCH endpoint

**Status**: Done
**PR**: https://github.com/pivotapp-ai/pivot/pull/19262
```

**Pattern summary**:
```markdown
## Top Categories

### 1. Workflow Condition Mismatches (12 bugs - 24%)
**Pattern**: Mutually exclusive conditions or outdated workflow logic
**Recommended fixes**:
- Add audit logs for workflow condition changes
- Display warning when conditions are outdated
- Add "last updated" timestamp to groups

### 2. Async Import Failures (8 bugs - 16%)
**Pattern**: Silent failures in vendor/data import processes
**Recommended fixes**:
- Implement error notification system
- Add retry mechanism
- Create import status dashboard for Ops
```

## When to Use

- **Monthly/quarterly**: Analyze bugs from the period
- **Before planning**: Identify what to prioritize fixing
- **After major changes**: Verify if bug patterns improved

## Prerequisites

Set up a workspace directory (e.g., `~/bug-analysis-workspace/`) with:
- `data/exports/`: HTML files exported from Notion
- `data/bug_list.csv`: Bug list from Notion

If you don't have these, the skill will guide you through setup.
