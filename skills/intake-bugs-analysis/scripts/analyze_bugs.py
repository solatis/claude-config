#!/usr/bin/env python3
"""
Analyze bugs using Claude AI to generate structured summaries.

This script extracts bug data from HTML files and uses Claude CLI
to generate concise root cause analysis for each bug.
"""

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from bs4 import BeautifulSoup


class BugAnalyzer:
    def __init__(self, csv_path, html_dir, output_dir, claude_timeout=60):
        self.csv_path = Path(csv_path)
        self.html_dir = Path(html_dir)
        self.output_dir = Path(output_dir)
        self.claude_timeout = claude_timeout
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def extract_bug_data(self, html_path):
        """Extract investigation data from a bug HTML file."""
        with open(html_path, "r", encoding="utf-8") as f:
            content = f.read()
            soup = BeautifulSoup(content, "html.parser")

        # Extract Status
        status = "Unknown"
        for th in soup.find_all("th"):
            if "Status" in th.get_text():
                status_td = th.find_next("td")
                if status_td:
                    status = status_td.get_text(strip=True)
                    break

        # Extract PR link
        pr_link = None
        for th in soup.find_all("th"):
            if "Pull Request" in th.get_text():
                pr_td = th.find_next("td")
                if pr_td:
                    pr_a = pr_td.find("a")
                    if pr_a and pr_a.get("href"):
                        pr_link = pr_a.get("href")
                        break

        # Extract comments
        comments = []
        summary = soup.find(
            "summary", string=lambda text: text and "Page comments" in text
        )
        if summary:
            details = summary.find_parent("details")
            if details:
                for li in details.find_all("li"):
                    user = "Unknown"
                    user_span = li.find("span", class_="user")
                    if user_span:
                        user_b = user_span.find("b")
                        if user_b:
                            user = user_b.get_text(strip=True)

                    all_divs = li.find_all("div", recursive=False)
                    if len(all_divs) >= 2:
                        comment_text = all_divs[1].get_text(strip=True)
                        if comment_text:
                            comments.append({"user": user, "text": comment_text})

        # Extract tech investigation
        tech_investigation = ""
        for p in soup.find_all("p"):
            if "Tech investigation" in p.get_text():
                next_p = p.find_next("p")
                if next_p:
                    tech_text = next_p.get_text(strip=True)
                    if tech_text and tech_text != "➡️":
                        tech_investigation = tech_text.replace("➡️", "").strip()
                break

        # Extract bug description
        bug_description = ""
        for callout in soup.find_all("figure", class_="callout"):
            if "➡️" in callout.get_text():
                text = callout.get_text(strip=True)
                if len(text) > 100 and "Please indicate above" not in text:
                    bug_description = text.replace("➡️", "").strip()
                    break

        return {
            "status": status,
            "pr_link": pr_link,
            "tech_investigation": tech_investigation,
            "bug_description": bug_description,
            "comments": comments,
        }

    def analyze_with_claude(self, bug_id, bug_title, data):
        """Use Claude CLI to generate bug summary."""
        # Document Positioning: Data first, instructions last
        prompt = f"""<bug_data>
Bug ID: {bug_id}
Title: {bug_title}
Status: {data["status"]}
PR Link: {data["pr_link"] if data["pr_link"] else "None"}

Bug Description:
{data["bug_description"] if data["bug_description"] else "Not provided"}

Tech Investigation:
{data["tech_investigation"] if data["tech_investigation"] else "Not provided"}

Comments:
{chr(10).join([f"- {c['user']}: {c['text']}" for c in data["comments"]]) if data["comments"] else "No comments"}
</bug_data>

Analyze the bug above and provide a concise summary.

<format>
**Root Cause**: [1-2 sentence technical explanation of what caused the bug]

**Key Findings**:
- [Finding 1]
- [Finding 2]

**Resolution**: [Category] - [brief explanation]
</format>

Key Findings: Include 2-5 findings based on complexity.

Resolution categories:
- Code fix: Required code changes (new feature, bug fix, validation)
- Manual fix: Ops resolved without code (data correction, config change)
- Not a bug: Working as intended, user error, or duplicate
- Pending: Still under investigation or blocked

<example type="good">
**Root Cause**: PATCH endpoint missing uniqueness validation that POST endpoint had, allowing duplicate VAT numbers on update.

**Key Findings**:
- Validation existed on creation but not on updates
- 3 vendors affected with duplicate VAT numbers
- No regression - validation was never implemented for PATCH

**Resolution**: Code fix - Added VAT uniqueness validation to PATCH endpoint
</example>

<example type="bad">
**Root Cause**: There was a bug.

**Key Findings**:
- Something was wrong
- It got fixed
- Users were affected

**Resolution**: Other - Fixed it
</example>

Output ONLY the formatted summary. No preamble, no explanation."""

        try:
            result = subprocess.run(
                ["claude", "-p", prompt],
                capture_output=True,
                text=True,
                timeout=self.claude_timeout,
            )

            if result.returncode == 0:
                return result.stdout.strip()
            else:
                return f"Error calling Claude: {result.stderr}"

        except subprocess.TimeoutExpired:
            return "Error: Claude CLI timed out"
        except FileNotFoundError:
            return "Error: Claude CLI not found. Install with: npm install -g @anthropic-ai/claude-code"
        except Exception as e:
            return f"Error: {str(e)}"

    def get_already_analyzed(self):
        """Get set of bug IDs that have already been analyzed."""
        analyzed = set()
        for file in self.output_dir.glob("*.md"):
            # Extract bug ID from filename (e.g., "PIVOT-12345.md")
            bug_id = file.stem
            if bug_id.startswith("PIVOT-"):
                analyzed.add(bug_id)
        return analyzed

    def analyze_bug(self, bug, index, total):
        """Analyze a single bug."""
        bug_id = bug["ID"]
        bug_title = bug["Name"]
        html_file = bug.get("HTML_File", "")

        print(f"\n[{index + 1}/{total}] {bug_id}: {bug_title[:60]}...")

        if html_file == "NOT_FOUND":
            print("  ⚠️  HTML file not found - skipping")
            return False

        html_path = self.html_dir / html_file
        if not html_path.exists():
            print(f"  ⚠️  HTML file does not exist: {html_file}")
            return False

        # Extract data
        print("  📄 Extracting data from HTML...")
        try:
            data = self.extract_bug_data(html_path)
        except Exception as e:
            print(f"  ❌ Error extracting data: {e}")
            return False

        print(
            f"  ℹ️  Status: {data['status']} | PR: {'Yes' if data['pr_link'] else 'No'} | Comments: {len(data['comments'])}"
        )

        # Analyze with Claude
        print("  🤖 Analyzing with Claude...")
        summary = self.analyze_with_claude(bug_id, bug_title, data)

        if summary.startswith("Error"):
            print(f"  ❌ {summary}")
            return False

        # Save result
        output_file = self.output_dir / f"{bug_id}.md"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(f"## {bug_id}: {bug_title}\n\n")
            f.write(f"{summary}\n\n")
            f.write(f"**Status**: {data['status']}\n")
            if data["pr_link"]:
                f.write(f"**PR**: {data['pr_link']}\n")
            f.write("\n---\n")

        print(f"  ✅ Analysis saved to: {output_file.name}")
        return True

    def run(self, start_from=0, end_at=None, resume=True):
        """Run the analysis on all bugs."""
        # Read CSV
        if not self.csv_path.exists():
            print(f"Error: CSV file not found: {self.csv_path}")
            return

        print(f"Reading bugs from: {self.csv_path}")
        with open(self.csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            bugs = list(reader)

        total_bugs = len(bugs)
        print(f"Total bugs: {total_bugs}")

        # Filter bugs to analyze
        if resume:
            already_analyzed = self.get_already_analyzed()
            print(f"Already analyzed: {len(already_analyzed)} bugs")
            bugs_to_analyze = [b for b in bugs if b["ID"] not in already_analyzed]
            print(f"Remaining to analyze: {len(bugs_to_analyze)} bugs")
        else:
            bugs_to_analyze = bugs[start_from:end_at]
            print(f"Analyzing bugs {start_from} to {end_at or total_bugs}")

        if not bugs_to_analyze:
            print("\n✅ All bugs already analyzed!")
            return

        # Analyze bugs
        print("\nStarting analysis...")
        print("=" * 80)

        successful = 0
        failed = 0

        for i, bug in enumerate(bugs_to_analyze):
            success = self.analyze_bug(
                bug, i, len(bugs_to_analyze)
            )

            if success:
                successful += 1
            else:
                failed += 1

            # Small delay between API calls
            if i < len(bugs_to_analyze) - 1:
                time.sleep(1)

        # Summary
        print("\n" + "=" * 80)
        print("\n📊 Analysis Summary:")
        print(f"  ✅ Successful: {successful}")
        print(f"  ❌ Failed: {failed}")
        print(f"  📁 Results in: {self.output_dir}")


def main():
    parser = argparse.ArgumentParser(
        description="Analyze bugs using Claude AI"
    )
    parser.add_argument(
        "--csv-path",
        default="inputs/bug_list_matched.csv",
        help="Path to matched bug list CSV",
    )
    parser.add_argument(
        "--html-dir",
        default="inputs/exports",
        help="Directory containing HTML exports",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/individual",
        help="Output directory for analysis results",
    )
    parser.add_argument(
        "--start-from",
        type=int,
        default=0,
        help="Start analysis from bug number (0-indexed)",
    )
    parser.add_argument(
        "--end-at",
        type=int,
        default=None,
        help="End analysis at bug number (0-indexed)",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Don't resume - analyze all bugs in range",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Claude CLI timeout in seconds",
    )

    args = parser.parse_args()

    analyzer = BugAnalyzer(
        csv_path=args.csv_path,
        html_dir=args.html_dir,
        output_dir=args.output_dir,
        claude_timeout=args.timeout,
    )

    analyzer.run(
        start_from=args.start_from,
        end_at=args.end_at,
        resume=not args.no_resume,
    )


if __name__ == "__main__":
    main()
