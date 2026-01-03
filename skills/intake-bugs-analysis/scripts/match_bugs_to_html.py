#!/usr/bin/env python3
"""
Match bugs from CSV to their exported HTML files.

This script reads a CSV list of bugs and matches each bug ID to its
corresponding HTML file exported from Notion.
"""

import argparse
import csv
import os
import sys
from pathlib import Path


def find_html_files(html_dir):
    """Find all HTML files in the directory, excluding 'Untitled' files."""
    html_path = Path(html_dir)
    if not html_path.exists():
        print(f"Error: HTML directory not found: {html_dir}")
        sys.exit(1)

    all_files = list(html_path.glob("*.html"))
    html_files = [f for f in all_files if not f.name.startswith("Untitled")]

    print(f"Found {len(html_files)} HTML files (excluding Untitled)")
    return html_files


def match_bug_to_html(bug_id, html_files, html_dir):
    """
    Match a bug ID to its HTML file.

    Strategy:
    1. Primary: Look for bug ID in <td> tags or early in file (first 5000 chars)
    2. Fallback: Search anywhere in the file
    """
    best_match = None

    for html_file in html_files:
        try:
            with open(html_file, "r", encoding="utf-8") as f:
                content = f.read()

            # Primary match: bug ID in properties table
            if f"<td>{bug_id}</td>" in content or f">{bug_id}<" in content[:5000]:
                return html_file.name

            # Fallback: bug ID appears anywhere
            if bug_id in content and not best_match:
                best_match = html_file.name

        except Exception as e:
            print(f"Warning: Error reading {html_file.name}: {e}")
            continue

    return best_match


def main():
    parser = argparse.ArgumentParser(
        description="Match bugs from CSV to exported HTML files"
    )
    parser.add_argument(
        "--csv-path",
        default="inputs/bug_list.csv",
        help="Path to bug list CSV file",
    )
    parser.add_argument(
        "--html-dir",
        default="inputs/exports",
        help="Directory containing HTML exports",
    )
    parser.add_argument(
        "--output",
        default="inputs/bug_list_matched.csv",
        help="Output CSV file with HTML file mappings",
    )

    args = parser.parse_args()

    # Read CSV
    csv_path = Path(args.csv_path)
    if not csv_path.exists():
        print(f"Error: CSV file not found: {args.csv_path}")
        print(f"\nExpected path: {csv_path.absolute()}")
        sys.exit(1)

    print(f"Reading bugs from: {args.csv_path}")
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        bugs = list(reader)

    print(f"Total bugs in CSV: {len(bugs)}")

    # Find HTML files
    html_files = find_html_files(args.html_dir)

    # Match bugs to HTML files
    print("\nMatching bugs to HTML files...")
    matched = 0
    unmatched_bugs = []

    for bug in bugs:
        bug_id = bug.get("ID", "")
        if not bug_id:
            print(f"Warning: Bug without ID found: {bug.get('Name', 'Unknown')[:50]}")
            continue

        html_file = match_bug_to_html(
            bug_id, html_files, Path(args.html_dir)
        )

        if html_file:
            bug["HTML_File"] = html_file
            matched += 1
        else:
            bug["HTML_File"] = "NOT_FOUND"
            unmatched_bugs.append(
                {"bug_id": bug_id, "bug_title": bug.get("Name", "Unknown")}
            )

    # Report results
    print(f"\nResults:")
    print(f"  Matched: {matched}")
    print(f"  Unmatched: {len(unmatched_bugs)}")

    if unmatched_bugs:
        print("\nUnmatched bugs:")
        for bug in unmatched_bugs:
            print(f"  {bug['bug_id']}: {bug['bug_title'][:70]}...")

    # Write output CSV
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = list(bugs[0].keys())
    if "HTML_File" not in fieldnames:
        fieldnames.append("HTML_File")

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(bugs)

    print(f"\nOutput written to: {args.output}")
    print(f"Absolute path: {output_path.absolute()}")


if __name__ == "__main__":
    main()
