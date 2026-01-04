#!/usr/bin/env python3
"""
Analyze patterns across bugs and generate summary report.

This script reads individual bug analyses and uses Claude to identify
recurring patterns, categorize bugs, and generate actionable recommendations.
"""

import argparse
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

NOTION_DB_URL = "https://www.notion.so/pivotapp/1491a2c7a2088047aaa6ec67f005a0db"


def add_notion_links(text):
    """Replace PIVOT-##### patterns with Notion search hyperlinks."""
    return re.sub(
        r'\b(PIVOT-\d+)\b',
        lambda m: f"[{m.group(1)}]({NOTION_DB_URL}?q={m.group(1)})",
        text
    )


def validate_output(text, expected_count):
    """Validate Claude's output for cross-references, duplicates, and count.

    Returns list of error strings (empty if valid).
    """
    errors = []

    # Extract PIVOT-IDs from "Most Valuable Actions" section
    actions_section = re.search(
        r'### 💪 Most Valuable Actions\n(.*?)(?=### Bug Index|$)',
        text, re.DOTALL
    )
    action_ids = set(re.findall(r'PIVOT-\d+', actions_section.group(1))) if actions_section else set()

    # Extract PIVOT-IDs from "Bug Index" section, grouped by category
    index_section = re.search(r'### Bug Index by Feature\n(.*?)$', text, re.DOTALL)
    index_text = index_section.group(1) if index_section else ""

    # Parse categories: **Category (N)**
    category_pattern = r'\*\*([^*]+)\s*\((\d+)\)\*\*\n(.*?)(?=\*\*[^*]+\s*\(\d+\)\*\*|$)'
    categories = re.findall(category_pattern, index_text, re.DOTALL)

    all_index_ids = set()
    category_ids = {}  # category -> set of IDs

    for cat_name, count, cat_content in categories:
        cat_name = cat_name.strip()
        ids = set(re.findall(r'PIVOT-\d+', cat_content))
        category_ids[cat_name] = ids
        all_index_ids.update(ids)

    # Check 1: Cross-reference - all action IDs must be in index
    missing_from_index = action_ids - all_index_ids
    if missing_from_index:
        errors.append(f"Cross-reference: {len(missing_from_index)} bug(s) in Actions but missing from Index: {', '.join(sorted(missing_from_index))}")

    # Check 2: No duplicates across categories
    seen = set()
    duplicates = set()
    for cat_name, ids in category_ids.items():
        for bug_id in ids:
            if bug_id in seen:
                duplicates.add(bug_id)
            seen.add(bug_id)

    if duplicates:
        errors.append(f"Duplicates: {len(duplicates)} bug(s) appear in multiple categories: {', '.join(sorted(duplicates))}")

    # Check 3: Count matches expected
    actual_count = len(all_index_ids)
    if actual_count != expected_count:
        errors.append(f"Count mismatch: Bug Index has {actual_count} bugs, expected {expected_count}")

    return errors


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
        undocumented = 0
        other = 0

        for analysis in analyses:
            content_lower = analysis["content"].lower()
            if "resolution**: code fix" in content_lower or "resolution: code fix" in content_lower:
                code_fixes += 1
            elif "resolution**: manual fix" in content_lower or "resolution: manual fix" in content_lower:
                manual_fixes += 1
            elif "resolution**: not a bug" in content_lower or "resolution: not a bug" in content_lower:
                not_bugs += 1
            elif "resolution**: resolution undocumented" in content_lower or "resolution: resolution undocumented" in content_lower:
                undocumented += 1
            else:
                other += 1

        return {
            "total": total,
            "code_fixes": code_fixes,
            "manual_fixes": manual_fixes,
            "not_bugs": not_bugs,
            "undocumented": undocumented,
            "other": other,
        }

    def categorize_with_claude(self, analyses):
        """Use Claude to categorize bugs and identify patterns."""
        # Separate pending, undocumented, and resolved bugs
        pending_bugs = []
        undocumented_bugs = []
        resolved_analyses = []

        for analysis in analyses:
            content_lower = analysis["content"].lower()
            if "resolution**: pending" in content_lower or "resolution: pending" in content_lower:
                pending_bugs.append(analysis["bug_id"])
            elif "resolution**: resolution undocumented" in content_lower or "resolution: resolution undocumented" in content_lower:
                undocumented_bugs.append(analysis)  # Keep full analysis for title extraction
            else:
                resolved_analyses.append(analysis)

        # Prepare condensed data for Claude (resolved bugs only)
        bug_summaries = []
        for analysis in resolved_analyses:
            lines = analysis["content"].split("\n")
            # Extract the key parts (typically first 15-20 lines have the summary)
            summary = "\n".join(lines[:20])
            bug_summaries.append(f"### {analysis['bug_id']}\n{summary}\n")

        combined_text = "\n".join(bug_summaries)

        # Build analysis scope section for pending bugs
        pending_section = ""
        if pending_bugs:
            pending_section = f"""<analysis_scope>
**Excluded from categorization** ({len(pending_bugs)} pending bugs):
{', '.join(pending_bugs)}

These bugs are still under investigation. They have individual analyses but are excluded from pattern categorization since root causes are not yet determined.
</analysis_scope>

"""

        # Build manual review section for undocumented bugs
        undocumented_section = ""
        if undocumented_bugs:
            # Extract title from first line of each analysis (format: "## [PIVOT-ID](url): Title")
            def extract_title(content):
                first_line = content.split("\n")[0]
                if ":" in first_line:
                    return first_line.split(":", 1)[1].strip()
                return "Unknown"

            bug_list = "\n".join([f"- {b['bug_id']}: {extract_title(b['content'])}" for b in undocumented_bugs])
            undocumented_section = f"""<manual_review_required>
**{len(undocumented_bugs)} bug(s) closed without documented resolution:**
{bug_list}

These should be manually reviewed to understand why due process was not followed.
</manual_review_required>

"""

        # Document Positioning: Data first, instructions last
        # Hybrid approach: Feature area PRIMARY (Ops-readable) + Root cause SECONDARY (cross-cutting patterns)
        prompt = f"""You are a technical lead analyzing bug trends to inform quarterly planning and reduce operational toil. Your goal is to identify patterns that, if addressed, would prevent multiple future bugs.

{pending_section}{undocumented_section}<bug_analyses>
{combined_text}
</bug_analyses>

You have {len(resolved_analyses)} resolved bug analyses above{f" (excludes {len(pending_bugs)} pending)" if pending_bugs else ""}{f" (excludes {len(undocumented_bugs)} requiring manual review)" if undocumented_bugs else ""}.

<internal_analysis>
Silently perform these steps. Do NOT output this analysis.

1. Categorize each bug by PRIMARY feature area:
   Workflow | Vendor | Notifications | Integrations | Forms | Permissions | Data/API

2. Tag each bug with root cause type:
   Validation gap | Configuration error | Async/timing | Data mapping | External service | User error

3. Group into mutually exclusive categories.

4. Identify cross-cutting patterns: root causes appearing in 2+ feature areas with 3+ bugs total.

5. Synthesize top 5 actions that address the most bugs across categories.
</internal_analysis>

<verification_checkpoint>
Before outputting, verify these invariants:
1. CROSS-REFERENCE: Every PIVOT-ID in "Most Valuable Actions" appears in "Bug Index"
2. NO DUPLICATES: Each PIVOT-ID appears in exactly ONE Bug Index category
3. COUNT CHECK: Sum of bugs across all categories equals {len(resolved_analyses)}

If any check fails:
- Cross-reference fail: Add missing bug to appropriate Bug Index category
- Duplicate fail: Remove bug from all but one category (keep most relevant)
- Count fail: Find missing/extra bugs and fix

Do NOT include this verification in your output.
</verification_checkpoint>

<example type="wrong">
Output with duplicate content:
### 1. Workflow
- PIVOT-22670: Wrong approver assigned → [Validation] Add condition check
🔧 Potential fixes:
- [ ] Add validation check
### Cross-Cutting Patterns
**Validation Gaps** (12 bugs): PIVOT-22670, PIVOT-22399...
### Most valuable actions
- [ ] **[Validation]** Add condition check (PIVOT-22670...)
Problem: Same bug (PIVOT-22670) and fix appear 3 times. Output too long and redundant.
</example>

<example type="right">
### 💪 Most Valuable Actions
- [ ] **[Validation]** Shared validation service
    - Why: 27% of bugs stem from inconsistent validation across endpoints
    - Bugs (12): PIVOT-22399, PIVOT-22670, PIVOT-23629...
### Bug Index by Feature
**Workflow (11)**: PIVOT-22670, PIVOT-22649, PIVOT-22772, PIVOT-22778...
**Vendor (9)**: PIVOT-22399, PIVOT-23629, PIVOT-23524...
Benefit: Actions summarize fixes for Engineering. Index provides navigation for Ops. No duplication.
</example>

<example type="wrong">
Duplicate bug across categories:
**Workflow (11)**: PIVOT-22670, PIVOT-23343...
**Vendor Onboarding (5)**: PIVOT-23343, PIVOT-22431...
Problem: PIVOT-23343 appears in both Workflow AND Vendor Onboarding. Each bug must appear in exactly one category.
</example>

<example type="right">
**Workflow (11)**: PIVOT-22670, PIVOT-22649...
**Vendor Onboarding (5)**: PIVOT-23343, PIVOT-22431...
Fix: PIVOT-23343 appears only in Vendor Onboarding (its primary feature area).
</example>

<output_format>
Output exactly these two sections: Most Valuable Actions and Bug Index by Feature. No separators (---).

### 💪 Most Valuable Actions

Top 5 actions by impact (bugs addressed). Each action references the specific bugs it would fix.

- [ ] **[Fix Type]** Action description
    - Why: 1-sentence justification linking to root cause pattern
    - Bugs (X): PIVOT-ID1, PIVOT-ID2...

(Provide exactly 5 actions in this format, ranked by bug count)

### Bug Index by Feature

Grouped by feature area, sorted by bug count descending. Each bug has description and suggested fix for auditability.

**Workflow (N)**
- PIVOT-ID1 *short description of issue*
    → [Fix Type] suggested action
- PIVOT-ID2 *short description*
    → [Fix Type] suggested action

**Vendor (N)**
- PIVOT-ID1 *short description*
    → [Fix Type] suggested action

(Continue for each feature area: Integrations, Forms, Permissions, Data/API)

Omit empty categories. Total bug count must equal {len(resolved_analyses)}.
</output_format>

<fix_types>
Fix types describe WHAT ACTION TO TAKE. Choose the most specific:
- [Validation] - Add input validation or business rule checks
- [Error message] - Improve error text to help users self-resolve
- [Audit] - Add monitoring/logging to detect issues earlier
- [Documentation] - Update docs or create guidance
- [Product] - UX/workflow improvement to prevent user confusion
- [Super Admin] - Add admin tooling for Ops to fix data issues
- [Code] - General code change (use only when no specific tag fits)
</fix_types>

Output the analysis now. Use actual bug IDs from the data above."""

        try:
            print("  🤖 Analyzing patterns with Claude (this may take a minute)...")

            def call_claude(p):
                r = subprocess.run(
                    ["claude", "-p", p],
                    capture_output=True,
                    text=True,
                    timeout=180,
                )
                return r.stdout.strip() if r.returncode == 0 else None

            # First attempt
            output = call_claude(prompt)
            if not output:
                print("  ❌ Error: Claude returned no output")
                return None

            # Validate output
            errors = validate_output(output, len(resolved_analyses))

            if errors:
                # Warn user about validation failure
                print(f"  ⚠️  Validation failed: {'; '.join(errors)}")
                print("  🔄 Re-prompting with error feedback...")

                # Build retry prompt with error feedback
                retry_prompt = f"""{prompt}

<validation_errors>
Your previous output had these errors:
{chr(10).join(f'- {e}' for e in errors)}

Fix these issues in your response. Ensure:
1. Every bug in "Most Valuable Actions" appears in "Bug Index"
2. Each bug appears in exactly ONE Bug Index category
3. Total bug count equals {len(resolved_analyses)}
</validation_errors>"""

                # Retry
                output = call_claude(retry_prompt)
                if output:
                    retry_errors = validate_output(output, len(resolved_analyses))
                    if retry_errors:
                        print(f"  ⚠️  Validation still failed after retry: {'; '.join(retry_errors)}")
                        # Continue with output anyway

            return output

        except subprocess.TimeoutExpired:
            print("  ❌ Error: Claude CLI timed out")
            return None
        except FileNotFoundError:
            print(
                "  ❌ Error: Claude CLI not found. Install with: npm install -g @anthropic-ai/claude-code"
            )
            return None
        except Exception as e:
            print(f"  ❌ Error: {str(e)}")
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
        undoc_pct = stats.get('undocumented', 0) * 100 // stats['total'] if stats['total'] > 0 else 0

        report.append(f"- **Code fixes required**: {stats['code_fixes']} ({code_pct}%)")
        report.append(f"- **Manual fixes**: {stats['manual_fixes']} ({manual_pct}%)")
        report.append(f"- **Not bugs**: {stats['not_bugs']} ({not_bug_pct}%)")
        if stats.get('undocumented', 0) > 0:
            report.append(f"- **Resolution undocumented**: {stats['undocumented']} ({undoc_pct}%) - requires manual review")
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
            report.append(add_notion_links(pattern_analysis))
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
