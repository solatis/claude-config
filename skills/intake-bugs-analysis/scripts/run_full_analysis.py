#!/usr/bin/env python3
"""
Complete bug analysis pipeline - runs all steps end-to-end.

This script orchestrates the entire bug analysis process:
1. Match bugs to HTML files
2. Analyze individual bugs with Claude
3. Identify patterns and generate summary report
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_command(script_name, args=None):
    """Run a Python script and handle errors."""
    cmd = ["python3", str(script_name)]
    if args:
        cmd.extend(args)

    print(f"\n{'=' * 80}")
    print(f"Running: {' '.join(cmd)}")
    print(f"{'=' * 80}\n")

    try:
        result = subprocess.run(cmd, check=True)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Error running {script_name}: {e}")
        return False
    except KeyboardInterrupt:
        print(f"\n⚠️  Interrupted by user")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Run complete bug analysis pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full pipeline with defaults
  python3 run_full_analysis.py

  # Run with custom period name
  python3 run_full_analysis.py --period "December 2025"

  # Skip matching if already done
  python3 run_full_analysis.py --skip-matching

  # Only analyze first 10 bugs (for testing)
  python3 run_full_analysis.py --limit 10
        """,
    )

    parser.add_argument(
        "--csv-path",
        default="../data/bug_list.csv",
        help="Path to bug list CSV file",
    )
    parser.add_argument(
        "--html-dir",
        default="../data/exports",
        help="Directory containing HTML exports",
    )
    parser.add_argument(
        "--period",
        default=None,
        help="Period name for the report (e.g., 'December 2025')",
    )
    parser.add_argument(
        "--skip-matching",
        action="store_true",
        help="Skip bug-to-HTML matching (if already done)",
    )
    parser.add_argument(
        "--skip-analysis",
        action="store_true",
        help="Skip individual bug analysis (go straight to patterns)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit analysis to first N bugs (for testing)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Claude CLI timeout in seconds (default: 120)",
    )

    args = parser.parse_args()

    print("🚀 Bug Analysis Pipeline")
    print("=" * 80)

    scripts_dir = Path(__file__).parent

    # Step 1: Match bugs to HTML files
    if not args.skip_matching:
        print("\n📝 Step 1: Matching bugs to HTML files...")
        match_args = [
            "--csv-path",
            args.csv_path,
            "--html-dir",
            args.html_dir,
        ]
        if not run_command(scripts_dir / "match_bugs_to_html.py", match_args):
            print("\n❌ Matching failed. Aborting pipeline.")
            sys.exit(1)
    else:
        print("\n⏭️  Skipping Step 1: Bug matching")

    # Step 2: Analyze individual bugs
    if not args.skip_analysis:
        print("\n🤖 Step 2: Analyzing individual bugs with Claude...")
        analysis_args = [
            "--csv-path",
            "../data/bug_list_matched.csv",
            "--html-dir",
            args.html_dir,
            "--timeout",
            str(args.timeout),
        ]
        if args.limit:
            analysis_args.extend(["--end-at", str(args.limit), "--no-resume"])

        if not run_command(scripts_dir / "analyze_bugs.py", analysis_args):
            print("\n❌ Bug analysis failed. Aborting pipeline.")
            sys.exit(1)
    else:
        print("\n⏭️  Skipping Step 2: Individual bug analysis")

    # Step 3: Pattern analysis
    print("\n🔍 Step 3: Analyzing patterns and generating report...")
    pattern_args = []
    if args.period:
        pattern_args.extend(["--period", args.period])

    if not run_command(scripts_dir / "categorize_patterns.py", pattern_args):
        print("\n⚠️  Pattern analysis failed, but individual analyses are complete.")
        print("You can run categorize_patterns.py separately.")
        sys.exit(1)

    # Success!
    print("\n" + "=" * 80)
    print("✅ Pipeline complete!")
    print("=" * 80)
    print("\n📂 Results:")
    print("  - Individual analyses: ../data/results/individual/")
    print("  - Pattern summary: ../data/results/summary/pattern_analysis.md")
    print("\n💡 Next steps:")
    print("  1. Review the pattern analysis report")
    print("  2. Share findings with your team")
    print("  3. Create action items for top priorities")


if __name__ == "__main__":
    main()
