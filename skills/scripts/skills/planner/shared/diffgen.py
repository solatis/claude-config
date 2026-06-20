"""Deterministic unified-diff generation from snippets (F4).

WHY: code changes used to be stored as hand-authored unified diffs, so the
LLM had to compute `@@ -A,B +C,D` line arithmetic by hand -- a recurring
source of off-by-1/2 hunk errors (PLANNER-HARNESS-FIX-ROADMAP.md F4, a
sub-case of the F2 whack-a-mole it can never fully win).

Here the LLM supplies only (file, old_snippet, new_snippet); difflib computes
the hunk headers. When the current file content is available the diff is
anchored to real line numbers; otherwise it is snippet-relative (offsets are
advisory at plan time per F3). Either way the LLM never writes a `@@` line, so
the off-by-N class is structurally impossible.
"""

import difflib


def build_unified_diff(
    file: str,
    old_snippet: str,
    new_snippet: str,
    file_text: str | None = None,
) -> str:
    """Compute a unified diff for replacing old_snippet with new_snippet.

    Args:
        file: target file path (used for the a/ b/ headers).
        old_snippet: the exact current text to be replaced (may be "" for a
            pure insertion at top of file).
        new_snippet: the replacement text.
        file_text: full current file content, if available. When given and
            old_snippet occurs in it, the diff is anchored to real line
            numbers; otherwise the diff is snippet-relative.

    Returns:
        Unified diff text with tool-computed @@ headers (trailing newline).
        Empty string when old_snippet == new_snippet (no change).
    """
    if old_snippet == new_snippet:
        return ""

    if file_text is not None and old_snippet and old_snippet in file_text:
        # Anchored: diff the whole file against itself with the snippet swapped,
        # so difflib emits real, correct line numbers and surrounding context.
        new_text = file_text.replace(old_snippet, new_snippet, 1)
        a = file_text.splitlines()
        b = new_text.splitlines()
    else:
        # Snippet-relative: offsets start at line 1 of the snippet (advisory).
        a = old_snippet.splitlines()
        b = new_snippet.splitlines()

    diff = difflib.unified_diff(
        a, b,
        fromfile=f"a/{file}",
        tofile=f"b/{file}",
        lineterm="",
        n=3,
    )
    body = "\n".join(diff)
    return body + "\n" if body else ""
