#!/usr/bin/env python3
"""
Shared utilities for intake-bugs-analysis skill.

Contains constants and helper functions used by analyze_bugs.py and categorize_patterns.py.
"""

import re

NOTION_DB_URL = "https://www.notion.so/pivotapp/1491a2c7a2088047aaa6ec67f005a0db"


def notion_link(bug_id):
    """Format bug ID as Notion search hyperlink."""
    return f"[{bug_id}]({NOTION_DB_URL}?q={bug_id})"


def add_notion_links(text):
    """Replace PIVOT-##### patterns with Notion search hyperlinks."""
    return re.sub(
        r'\b(PIVOT-\d+)\b',
        lambda m: f"[{m.group(1)}]({NOTION_DB_URL}?q={m.group(1)})",
        text
    )


def extract_bug_title(content):
    """Extract bug title from analysis markdown.

    Format: "## [PIVOT-ID](url): Title"

    Uses "):" delimiter to correctly identify end of markdown link.
    ":" alone would match URL colons prematurely.
    """
    first_line = content.split("\n")[0]
    if "):" in first_line:
        return first_line.split("):", 1)[1].strip()
    return "Unknown"


def has_resolution(content, resolution_type):
    """Check if analysis contains specified resolution type.

    Handles both `**Resolution**:` and `Resolution:` formats.
    Claude markdown output inconsistently bolds headers depending on prompt response structure.
    Dual check prevents false negatives when detecting resolution type.
    """
    content_lower = content.lower()
    pattern = resolution_type.lower()
    return f"resolution**: {pattern}" in content_lower or f"resolution: {pattern}" in content_lower


def filter_analyses_by_status(analyses):
    """Separate analyses into pending, undocumented, and resolved.

    Returns tuple for unpacking: pending_ids, undocumented, resolved = filter_analyses_by_status(data)
    """
    pending_bug_ids = [a["bug_id"] for a in analyses if has_resolution(a["content"], "pending")]
    undocumented_analyses = [a for a in analyses if has_resolution(a["content"], "resolution undocumented")]
    resolved_analyses = [a for a in analyses if not has_resolution(a["content"], "pending") and not has_resolution(a["content"], "resolution undocumented")]

    return pending_bug_ids, undocumented_analyses, resolved_analyses
