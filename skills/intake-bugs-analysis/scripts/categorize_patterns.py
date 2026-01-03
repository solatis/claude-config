#!/usr/bin/env python3
"""
Analyze patterns across bugs and generate summary report.

This script reads individual bug analyses and uses Claude to identify
recurring patterns, categorize bugs, and generate actionable recommendations.
"""

import argparse
import subprocess
import sys
from collections import Counter
from pathlib import Path


class PatternAnalyzer:
    def __init__(self, input_dir, output_path, period="Unknown Period"):
        self.input_dir = Path(input_dir)
        self.output_path = Path(output_path)
        self.period = period

    def read_analyses(self):
        """Read all individual bug analyses."""
        if not self.input_dir.exists():
            print(f"Error: Input directory not found: {self.input_dir}")
            sys.exit(1)

        analyses = []
        for file in sorted(self.input_dir.glob("*.md")):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    content = f.read()
                    analyses.append(
                        {"bug_id": file.stem, "file": file.name, "content": content}
                    )
            except Exception as e:
                print(f"Warning: Could not read {file.name}: {e}")

        return analyses

    def extract_basic_stats(self, analyses):
        """Extract basic statistics from analyses."""
        total = len(analyses)
        code_fixes = 0
        manual_fixes = 0
        not_bugs = 0
        other = 0

        for analysis in analyses:
            content_lower = analysis["content"].lower()
            if "resolution**: code fix" in content_lower or "resolution: code fix" in content_lower:
                code_fixes += 1
            elif "resolution**: manual fix" in content_lower or "resolution: manual fix" in content_lower:
                manual_fixes += 1
            elif "resolution**: not a bug" in content_lower or "resolution: not a bug" in content_lower:
                not_bugs += 1
            else:
                other += 1

        return {
            "total": total,
            "code_fixes": code_fixes,
            "manual_fixes": manual_fixes,
            "not_bugs": not_bugs,
            "other": other,
        }

    def categorize_with_claude(self, analyses):
        """Use Claude to categorize bugs and identify patterns."""
        # Prepare condensed data for Claude
        bug_summaries = []
        for analysis in analyses:
            lines = analysis["content"].split("\n")
            # Extract the key parts (typically first 15-20 lines have the summary)
            summary = "\n".join(lines[:20])
            bug_summaries.append(f"### {analysis['bug_id']}\n{summary}\n")

        combined_text = "\n".join(bug_summaries)

        # Document Positioning: Data first, instructions last
        # Hybrid approach: Feature area PRIMARY (Ops-readable) + Root cause SECONDARY (cross-cutting patterns)
        prompt = f"""<bug_analyses>
{combined_text}
</bug_analyses>

You have {len(analyses)} bug analyses above. Categorize using a HYBRID approach.

<step_1_feature_area>
Scan all bugs and categorize each by PRIMARY feature area:
- Workflow (approvers, conditions, steps, delegation, workflow logic)
- Vendor / Vendor Onboarding (vendor portal, onboarding forms, vendor data)
- Notifications (email, Slack notifications, comments sync)
- Integrations (Slack events, ERP sync, external services)
- Forms / Models (form builder, model publishing, field configuration)
- Permissions / Access (user permissions, visibility, login)
- Data / API (field mapping, API responses, data display)
- Validation / Errors (missing validation, error handling, 500 errors)
</step_1_feature_area>

<step_2_root_cause>
For each bug, ALSO note its root cause type (for cross-cutting patterns later):
- Validation gap (missing or inconsistent validation)
- Configuration error (wrong settings, feature flags, user setup)
- Async/timing issue (race conditions, state sync, webhook failures)
- Data mapping error (field not returned, wrong format, DTO mismatch)
- External service failure (Slack, ERP, third-party outage)
- User error / Not a bug (working as designed, misunderstanding)
</step_2_root_cause>

<step_3_categorize>
Group bugs into MUTUALLY EXCLUSIVE feature categories:
- Each bug belongs to exactly ONE feature category (no double-counting)
- When a bug touches multiple areas, assign to PRIMARY feature where fix belongs
- Merge small categories (<2 bugs) into related ones
</step_3_categorize>

<example type="wrong">
Output shows only root-cause categories:
### 1. Missing Backend Validation (9 bugs)
### 2. External Integration Failures (7 bugs)
Problem: Hides which FEATURES are affected. Ops can't find their bugs.
</example>

<example type="right">
PART 1 shows feature areas (for Ops):
### Workflow (11 bugs)
### Vendor Onboarding (8 bugs)

PART 2 shows cross-cutting patterns (for Engineering):
### Validation Gaps (9 bugs across Workflow, Vendor, Forms)
Single fix: Shared validation service prevents 18% of bugs

Benefit: Ops find bugs by feature, Engineers find systemic fixes.
</example>

<output_format>
(All ### headers become H3 toggle sections in Notion. NO separators between sections.)

### 1. Workflow

- **No approver / Wrong approver in workflow**
    - [PIVOT-ID] Brief description of the specific issue
        → [Fix Type] Suggested action item

- **Skipped steps / Extra steps in workflow**
    - [PIVOT-ID] Brief description

🔧 Potential fixes:
- [ ] Action item 1
- [ ] Action item 2

### 2. Vendor Onboarding

(Same structure: sub-headers grouping similar bugs, bullets with PIVOT-IDs, fix suggestions, then 🔧 Potential fixes)

(Continue numbering: ### 3. ..., ### 4. ..., etc. for each feature area, ordered by bug count descending)

### Cross-Cutting Patterns

Root causes spanning multiple feature areas:

**[Root Cause Name]** ([X] bugs across [Y] features)
- Pattern: [1-2 sentence description]
- Bug IDs: PIVOT-1234, PIVOT-5678...
- Single fix: [specific technical recommendation]

(List each pattern with 3+ bugs that spans 2+ features)

### 💪 Most valuable actions identified

- [ ] **[Fix Type]** Action description (addresses X bugs from Categories Y, Z)
    - Why: [1-sentence justification]
- [ ] **[Fix Type]** Action description (addresses X bugs)
- [ ] **[Fix Type]** Action description (addresses X bugs)
- [ ] **[Fix Type]** Action description (addresses X bugs)
- [ ] **[Fix Type]** Action description (addresses X bugs)

### Verification

**Bug counts:**
- Workflow: X
- Vendor Onboarding: X
- (all categories matching ### headers above)
- **Total: {len(analyses)}**

**Cross-cutting patterns:** [list each with feature span]

✅ Sum = {len(analyses)}, no double-counting
</output_format>

<fix_types>
Use these fix type tags:
- [Audit] - Add audit logs or monitoring
- [Product] - Product/UX improvement
- [Documentation] - Docs or Dust agent
- [Error message] - Better error handling
- [Super Admin] - Super Admin tooling
- [Code] - Code fix required
- [Validation] - Add validation checks
</fix_types>

Output the categorized analysis now. Use actual bug IDs and brief descriptions from the data above."""

        try:
            print("  🤖 Analyzing patterns with Claude (this may take a minute)...")
            result = subprocess.run(
                ["claude", "-p", prompt],
                capture_output=True,
                text=True,
                timeout=180,  # 3 minute timeout for pattern analysis
            )

            if result.returncode == 0:
                return result.stdout.strip()
            else:
                print(f"Error calling Claude: {result.stderr}")
                return None

        except subprocess.TimeoutExpired:
            print("Error: Claude CLI timed out")
            return None
        except FileNotFoundError:
            print(
                "Error: Claude CLI not found. Install with: npm install -g @anthropic-ai/claude-code"
            )
            return None
        except Exception as e:
            print(f"Error: {str(e)}")
            return None

    def generate_report(self, analyses, stats, pattern_analysis):
        """Generate Notion-ready report in Bugs Initiative format."""
        report = []

        # Header - Bugs Initiative format
        report.append(f"## **Intake | Automated Analysis | {self.period}**\n")
        report.append(f"Analysis by Claude Code on {self.get_timestamp()}\n")
        report.append(f"**Method**: Automated AI analysis of {stats['total']} bugs\n")
        report.append("")

        # Executive Summary
        report.append("### Executive Summary\n")
        report.append(f"- **Total bugs analyzed**: {stats['total']}")

        code_pct = stats['code_fixes'] * 100 // stats['total'] if stats['total'] > 0 else 0
        manual_pct = stats['manual_fixes'] * 100 // stats['total'] if stats['total'] > 0 else 0
        not_bug_pct = stats['not_bugs'] * 100 // stats['total'] if stats['total'] > 0 else 0

        report.append(f"- **Code fixes required**: {stats['code_fixes']} ({code_pct}%)")
        report.append(f"- **Manual fixes**: {stats['manual_fixes']} ({manual_pct}%)")
        report.append(f"- **Not bugs**: {stats['not_bugs']} ({not_bug_pct}%)")
        if stats['other'] > 0:
            report.append(f"- **Other/Pending**: {stats['other']}")
        report.append("")

        no_code = stats['manual_fixes'] + stats['not_bugs']
        if stats['total'] > 0:
            no_code_pct = no_code * 100 // stats['total']
            report.append(
                f"**No-code bugs**: {no_code} ({no_code_pct}%) - bugs resolved without code changes\n"
            )

        # Claude's hybrid pattern analysis (no separator - keeps toggle-friendly)
        if pattern_analysis:
            report.append(pattern_analysis)
            report.append("")
        else:
            report.append("## Pattern Analysis\n")
            report.append(
                "*Pattern analysis could not be generated.*\n"
            )

        return "\n".join(report)

    def get_timestamp(self):
        """Get current timestamp."""
        from datetime import datetime

        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def run(self):
        """Run the pattern analysis."""
        print(f"Reading bug analyses from: {self.input_dir}")

        # Read analyses
        analyses = self.read_analyses()
        print(f"Found {len(analyses)} bug analyses")

        if not analyses:
            print("No analyses found. Run analyze_bugs.py first.")
            return

        # Extract basic stats
        print("\n📊 Calculating statistics...")
        stats = self.extract_basic_stats(analyses)

        print(f"  Total: {stats['total']}")
        print(f"  Code fixes: {stats['code_fixes']}")
        print(f"  Manual fixes: {stats['manual_fixes']}")
        print(f"  Not bugs: {stats['not_bugs']}")
        print(f"  Other: {stats['other']}")

        # Categorize with Claude
        print("\n🔍 Identifying patterns...")
        pattern_analysis = self.categorize_with_claude(analyses)

        # Generate report
        print("\n📝 Generating report...")
        report = self.generate_report(analyses, stats, pattern_analysis)

        # Save report
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_path, "w", encoding="utf-8") as f:
            f.write(report)

        print(f"\n✅ Report saved to: {self.output_path}")
        print(f"   Absolute path: {self.output_path.absolute()}")


def main():
    parser = argparse.ArgumentParser(
        description="Analyze patterns across bug analyses"
    )
    parser.add_argument(
        "--input-dir",
        default="outputs/individual",
        help="Directory containing individual bug analyses",
    )
    parser.add_argument(
        "--output",
        default="outputs/summary/pattern_analysis.md",
        help="Output file for pattern analysis report",
    )
    parser.add_argument(
        "--period",
        default=None,
        help="Period name for the report (e.g., 'December 2025')",
    )

    args = parser.parse_args()

    # Auto-detect period if not specified
    period = args.period
    if not period:
        # Try to infer from directory name or current month
        from datetime import datetime

        period = datetime.now().strftime("%B %Y")

    analyzer = PatternAnalyzer(
        input_dir=args.input_dir, output_path=args.output, period=period
    )

    analyzer.run()


if __name__ == "__main__":
    main()
