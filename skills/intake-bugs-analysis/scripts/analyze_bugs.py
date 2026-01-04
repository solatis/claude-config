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
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from bs4 import BeautifulSoup

NOTION_DB_URL = "https://www.notion.so/pivotapp/1491a2c7a2088047aaa6ec67f005a0db"


def fetch_pr_metadata(pr_url):
    """Fetch PR metadata using gh CLI."""
    if not pr_url:
        return None

    try:
        result = subprocess.run(
            ["gh", "pr", "view", pr_url, "--json", "title,state,additions,deletions,reviewDecision"],
            timeout=10,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
        return None
    except Exception:
        return None


def notion_link(bug_id):
    """Format bug ID as Notion search hyperlink."""
    return f"[{bug_id}]({NOTION_DB_URL}?q={bug_id})"


class BugAnalyzer:
    def __init__(self, csv_path, html_dir, output_dir, claude_timeout=60, workers=4):
        self.csv_path = Path(csv_path)
        self.html_dir = Path(html_dir)
        self.output_dir = Path(output_dir)
        self.claude_timeout = claude_timeout
        self.workers = workers
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

        # Extract PR link or reference
        pr_link = None
        pr_reference = None
        for th in soup.find_all("th"):
            header_text = th.get_text()
            if "Pull Request" in header_text or "Github" in header_text:
                pr_td = th.find_next("td")
                if pr_td:
                    # Try to find a link first
                    pr_a = pr_td.find("a")
                    if pr_a and pr_a.get("href"):
                        pr_link = pr_a.get("href")
                        break
                    # Fallback: extract plain text (branch name)
                    text = pr_td.get_text(strip=True)
                    if text and text.lower() not in ("none", "n/a", "-", ""):
                        pr_reference = text
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
            "pr_reference": pr_reference,
            "tech_investigation": tech_investigation,
            "bug_description": bug_description,
            "comments": comments,
        }

    def analyze_with_claude(self, bug_id, bug_title, data, pr_meta):
        """Use Claude CLI to generate bug summary."""
        # Determine availability of optional fields
        has_description = bool(data["bug_description"])
        has_tech_investigation = bool(data["tech_investigation"])
        has_comments = bool(data["comments"])
        has_pr = bool(pr_meta)
        has_pr_reference = bool(data.get("pr_reference"))

        # Document Positioning: Data first, instructions last
        prompt = f"""You are a senior software engineer performing bug triage for a B2B SaaS procurement platform. Your task is to analyze bug reports and provide structured root cause analysis.

<bug_data>
<bug_id>{bug_id}</bug_id>
<title>{bug_title}</title>
<status>{data["status"]}</status>
<pr_link>{data["pr_link"] if data["pr_link"] else "None"}</pr_link>
<pr_reference>{data["pr_reference"] if data["pr_reference"] else "None"}</pr_reference>

<bug_description available="{"yes" if has_description else "no"}">
{data["bug_description"] if has_description else "Not provided"}
</bug_description>

<tech_investigation available="{"yes" if has_tech_investigation else "no"}">
{data["tech_investigation"] if has_tech_investigation else "Not provided"}
</tech_investigation>

<comments available="{"yes" if has_comments else "no"}">
{chr(10).join([f"- {c['user']}: {c['text']}" for c in data["comments"]]) if has_comments else "No comments"}
</comments>

<pr_metadata available="{"yes" if has_pr else ("partial" if has_pr_reference else "no")}">
{f"Title: {pr_meta['title']}, State: {pr_meta['state']}, Changes: +{pr_meta['additions']}/-{pr_meta['deletions']}, Review: {pr_meta.get('reviewDecision', 'PENDING')}" if has_pr else (f"Branch reference: {data['pr_reference']} (code fix exists)" if has_pr_reference else "No PR linked")}
</pr_metadata>
</bug_data>

<data_handling>
When fields are marked available="no", base analysis on remaining data. Do not invent missing information.
</data_handling>

Analyze the bug above and provide a concise summary.

<format>
**Root Cause**: [1-2 sentence technical explanation of what caused the bug]

**Key Findings**:
- [Finding 1]
- [Finding 2]

**Resolution**: [Category] - [brief explanation]
</format>

Key Findings: 2-5 bullet points, each under 15 words. Focus on facts, not interpretation.

<resolution_decision_tree>
Determine resolution by checking Status FIRST, then resolution evidence:

IF Status is NOT "Done":
  → "Pending" - Bug still under investigation. Stop here.
  (This bug will be excluded from pattern analysis)

IF Status = "Done":
  Check for resolution evidence (ALL of: PR linked, fix described in comments, OR clear conclusion in investigation):

  - Evidence shows code was deployed → "Code fix" - [describe the code change]
  - Evidence shows Ops fixed without code (data correction, config change, user guidance) → "Manual fix" - [describe the manual resolution]
  - Evidence shows not a bug (working as intended, user error, duplicate, cannot reproduce) → "Not a bug" - [explain why]
  - NO evidence of how it was resolved (no PR AND no fix in comments AND investigation incomplete) → "Resolution Undocumented" - [note what's missing]
  (This bug requires manual review)

Use the FIRST matching category.
</resolution_decision_tree>

<ambiguity_handling>
SCOPE: This section applies to ambiguous ROOT CAUSES within a known resolution category.

For bugs where resolution IS known (Code fix, Manual fix, Not a bug) but root cause is unclear:
- Use pattern: "Insufficient data - [best hypothesis based on available evidence]"
- State what evidence supports the hypothesis
- Note what additional information would confirm the root cause

IMPORTANT: This does NOT apply when the RESOLUTION ITSELF is unknown.
If Status=Done but no resolution evidence exists → use "Resolution Undocumented" instead.

Do NOT fabricate details. It is acceptable to acknowledge uncertainty.
</ambiguity_handling>

<example type="good">
**Root Cause**: PATCH endpoint missing uniqueness validation that POST endpoint had, allowing duplicate VAT numbers on update.

**Key Findings**:
- Validation existed on creation but not updates
- 3 vendors affected with duplicate VAT numbers
- No regression - never implemented for PATCH

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

<example type="pending_vs_undocumented">
Same bug data, different Status:

Status: In Progress, No PR, Investigation incomplete
→ **Resolution**: Pending - Investigation ongoing

Status: Done, No PR, Investigation incomplete
→ **Resolution**: Resolution Undocumented - Closed without fix evidence

Key difference: "Pending" = ticket still open. "Resolution Undocumented" = ticket closed but process gap.
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

        print(f"🔄 [{index + 1}/{total}] {bug_id}: {bug_title[:50]}...")

        if html_file == "NOT_FOUND":
            print(f"⚠️  [{index + 1}/{total}] {bug_id}: HTML not found")
            return False

        html_path = self.html_dir / html_file
        if not html_path.exists():
            print(f"⚠️  [{index + 1}/{total}] {bug_id}: HTML missing")
            return False

        # Extract data
        try:
            data = self.extract_bug_data(html_path)
        except Exception as e:
            print(f"❌ [{index + 1}/{total}] {bug_id}: Extract error - {e}")
            return False

        # Fetch PR metadata
        pr_meta = fetch_pr_metadata(data.get("pr_link"))

        # Analyze with Claude
        summary = self.analyze_with_claude(bug_id, bug_title, data, pr_meta)

        if summary.startswith("Error"):
            print(f"❌ [{index + 1}/{total}] {bug_id}: {summary}")
            return False

        # Save result
        output_file = self.output_dir / f"{bug_id}.md"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(f"## {notion_link(bug_id)}: {bug_title}\n\n")
            f.write(f"{summary}\n\n")
            f.write(f"**Status**: {data['status']}\n")
            if data["pr_link"]:
                pr_number = data['pr_link'].split('/')[-1]
                f.write(f"**PR**: [#{pr_number}]({data['pr_link']})\n")
            elif data.get("pr_reference"):
                f.write(f"**PR Reference**: {data['pr_reference']}\n")
            f.write("\n---\n")

        print(f"✅ [{index + 1}/{total}] {bug_id}: Done")
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

        # Analyze bugs in parallel
        print(f"\nStarting analysis with {self.workers} parallel workers...")
        print("=" * 80)

        successful = 0
        failed = 0
        total = len(bugs_to_analyze)

        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            # Submit all tasks
            future_to_bug = {
                executor.submit(self.analyze_bug, bug, i, total): bug
                for i, bug in enumerate(bugs_to_analyze)
            }

            # Collect results as they complete
            for future in as_completed(future_to_bug):
                try:
                    success = future.result()
                    if success:
                        successful += 1
                    else:
                        failed += 1
                except Exception as e:
                    print(f"  ❌ Worker error: {e}")
                    failed += 1

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
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of parallel workers (default: 4)",
    )

    args = parser.parse_args()

    analyzer = BugAnalyzer(
        csv_path=args.csv_path,
        html_dir=args.html_dir,
        output_dir=args.output_dir,
        claude_timeout=args.timeout,
        workers=args.workers,
    )

    analyzer.run(
        start_from=args.start_from,
        end_at=args.end_at,
        resume=not args.no_resume,
    )


if __name__ == "__main__":
    main()
