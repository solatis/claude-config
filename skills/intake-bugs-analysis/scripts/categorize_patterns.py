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
        prompt = f"""<bug_analyses>
{combined_text}
</bug_analyses>

You have {len(analyses)} bug analyses above. Identify recurring patterns by ROOT CAUSE (not symptoms).

<step_1_scan>
First, scan all bugs and note the root causes mentioned. Look for the PRIMARY root cause - the fix that would have prevented the bug:
- Similar technical causes (validation gaps, async failures, workflow issues)
- Similar resolution types (code fix vs manual fix vs not-a-bug)
- Same system areas
When a bug has multiple causes, ask: What single fix would have prevented this?
</step_1_scan>

<category_guidance>
Categories must be DISTINCT. Example:
- WRONG: "Feature Flag Issues" and "Multi-Tenancy Issues" - both describe tenant config problems
- RIGHT: "Tenant Configuration" (covers both) OR split by mechanism: "Missing Flag Checks" vs "Missing Query Scoping"
</category_guidance>

<step_2_categorize>
Group bugs into 4-8 MUTUALLY EXCLUSIVE categories:
- Each bug belongs to exactly ONE category (no double-counting)
- When a bug has multiple issues, assign to the PRIMARY root cause
- At least 2 bugs per category (patterns need repetition)
- Categories must have distinct, non-overlapping definitions

Before marking any bug as uncategorized, try broadening the category definition. Only truly unique bugs belong in "Uncategorized".
</step_2_categorize>

<output_format>
# Pattern Analysis

## Categories Identified

### 1. [Category Name] ([X] bugs - [Y]%)
**Pattern**: [1-2 sentence description of the common root cause]
**Bug IDs**: PIVOT-1234, PIVOT-5678, ...
**Evidence** (quote from analyses):
> "[Specific quote from one bug showing this pattern]"
**Common characteristics**:
- [Characteristic 1]
- [Characteristic 2]
**Recommended fixes**:
- [Specific, actionable fix 1]
- [Specific, actionable fix 2]

(Repeat for each category, ordered by bug count descending)

## Priority Recommendations

Rank by impact (bugs addressed × effort required):

1. **[P0] [Action]**: Addresses [X] bugs from Category [N] ([Y]%) - [1 sentence why]
2. **[P1] [Action]**: Addresses [X] bugs from Category [N] ([Y]%) - [1 sentence why]
3. **[P2] [Action]**: Addresses [X] bugs from Category [N] ([Y]%) - [1 sentence why]

## Key Insights

- [Technical insight about the codebase]
- [Process insight about how bugs are reported/resolved]
- [Trend or surprising finding]

## Verification

Total bugs categorized: [X] / {len(analyses)}
Sum of category counts: [X] (must equal total above - if higher, bugs are double-counted)
Categories with 3+ bugs: [list]
Uncategorized: [X] bugs
</output_format>

Output the analysis now. Use actual bug IDs from the data above."""

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
        """Generate the final report."""
        report = []

        # Header
        report.append(f"# Bug Pattern Analysis - {self.period}\n")
        report.append(f"**Generated**: {self.get_timestamp()}\n")
        report.append(f"**Total bugs analyzed**: {stats['total']}\n")
        report.append("")

        # Executive Summary
        report.append("## Executive Summary\n")
        report.append(f"- **Total bugs analyzed**: {stats['total']}")
        report.append(
            f"- **Code fixes required**: {stats['code_fixes']} ({stats['code_fixes'] * 100 // stats['total'] if stats['total'] > 0 else 0}%)"
        )
        report.append(
            f"- **Manual fixes**: {stats['manual_fixes']} ({stats['manual_fixes'] * 100 // stats['total'] if stats['total'] > 0 else 0}%)"
        )
        report.append(
            f"- **Not bugs**: {stats['not_bugs']} ({stats['not_bugs'] * 100 // stats['total'] if stats['total'] > 0 else 0}%)"
        )
        report.append(f"- **Other**: {stats['other']}")
        report.append("")

        no_code = stats['manual_fixes'] + stats['not_bugs']
        if stats['total'] > 0:
            report.append(
                f"**No-code bugs**: {no_code} ({no_code * 100 // stats['total']}%) - bugs resolved without code changes\n"
            )

        # Claude's pattern analysis
        if pattern_analysis:
            report.append("---\n")
            report.append(pattern_analysis)
            report.append("")
        else:
            report.append("## Pattern Analysis\n")
            report.append(
                "*Pattern analysis could not be generated. See individual bug analyses.*\n"
            )

        # Bug List
        report.append("\n---\n")
        report.append("## All Bugs Analyzed\n")
        for analysis in analyses:
            bug_id = analysis["bug_id"]
            # Extract title from first line
            first_line = analysis["content"].split("\n")[0]
            title = first_line.replace("##", "").strip()
            report.append(f"- {title}")
        report.append("")

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
