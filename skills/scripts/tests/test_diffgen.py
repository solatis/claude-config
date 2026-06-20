"""F4 regression: code-change @@ headers are tool-computed, never hand-authored.

PLANNER-HARNESS-FIX-ROADMAP.md F4: storing changes as hand-authored unified
diffs forced the LLM to compute `@@ -A,B +C,D` arithmetic, a recurring
off-by-N source. With snippets in and difflib computing headers, the off-by-N
class is structurally impossible. These tests pin that property and the
set-change CLI integration.
"""

import json
import subprocess
import sys
from pathlib import Path

from skills.planner.shared.diffgen import build_unified_diff


def test_no_change_returns_empty():
    assert build_unified_diff("f.py", "x = 1", "x = 1") == ""


def test_snippet_relative_diff_is_valid():
    diff = build_unified_diff("f.py", "a = 1\nb = 2", "a = 1\nb = 3")
    assert "--- a/f.py" in diff
    assert "+++ b/f.py" in diff
    assert "@@" in diff
    assert "-b = 2" in diff
    assert "+b = 3" in diff


def test_anchored_diff_has_real_line_numbers():
    # Snippet sits deep in a larger file; the @@ header must anchor there,
    # computed by difflib -- not by the caller and not snippet-relative (which
    # would start at line 1).
    file_text = "".join(f"l{i}\n" for i in range(1, 13))  # l1..l12
    file_text = file_text.replace("l9\n", "target_old\n")
    diff = build_unified_diff("f.py", "target_old", "target_new", file_text)
    assert "-target_old" in diff
    assert "+target_new" in diff
    hunk = next(l for l in diff.splitlines() if l.startswith("@@"))
    start = int(hunk.split()[1].lstrip("-").split(",")[0])
    # Anchored near line 9 (with 3 lines of context) -> start ~6, not 1.
    assert start > 1, f"expected a file-anchored offset, got {hunk!r}"

    # Contrast: with no file_text the same change is snippet-relative (start 1).
    rel = build_unified_diff("f.py", "target_old", "target_new")
    rel_hunk = next(l for l in rel.splitlines() if l.startswith("@@"))
    assert rel_hunk.split()[1].startswith("-1")


def test_pure_insertion():
    diff = build_unified_diff("f.py", "", "# new header\n")
    assert "+# new header" in diff


def test_set_change_with_snippets_computes_diff(tmp_path):
    scripts_root = Path(__file__).resolve().parents[1]

    # Build a minimal plan with a milestone + intent so set-change validates.
    state_dir = tmp_path / "state"
    state_dir.mkdir()

    def cli(*args, cwd=None):
        return subprocess.run(
            [sys.executable, "-m", "skills.planner.cli.plan",
             "--state-dir", str(state_dir), *args],
            cwd=str(cwd or scripts_root), capture_output=True, text=True,
        )

    assert cli("init", "--task", "fixture").returncode == 0
    assert cli("set-milestone", "--name", "M1", "--files", "f.py").returncode == 0
    # Intent for the change to reference.
    r = cli("set-intent", "--milestone", "M-001", "--file", "f.py",
            "--behavior", "add guard")
    assert r.returncode == 0, r.stderr

    # A real target file; pass its absolute path so the diff anchors to real
    # lines while the CLI still runs from scripts_root (module resolution).
    target = tmp_path / "f.py"
    target.write_text("def g():\n    return 1\n")

    r = cli("set-change", "--milestone", "M-001", "--intent-ref", "CI-M-001-001",
            "--file", str(target),
            "--old-snippet", "    return 1",
            "--new-snippet", "    # guard\n    return 1")
    assert r.returncode == 0, r.stderr + r.stdout

    plan = json.loads((state_dir / "plan.json").read_text())
    cc = plan["milestones"][0]["code_changes"][0]
    # Snippets persisted, and a tool-computed diff with a @@ header present.
    assert cc["old_snippet"] == "    return 1"
    assert "+    # guard" in cc["diff"]
    assert "@@" in cc["diff"]


def test_set_change_rejects_diff_and_snippets_together(tmp_path):
    scripts_root = Path(__file__).resolve().parents[1]
    state_dir = tmp_path / "state"
    state_dir.mkdir()

    def cli(*args):
        return subprocess.run(
            [sys.executable, "-m", "skills.planner.cli.plan",
             "--state-dir", str(state_dir), *args],
            cwd=str(scripts_root), capture_output=True, text=True,
        )

    cli("init", "--task", "fixture")
    cli("set-milestone", "--name", "M1", "--files", "f.py")
    r = cli("set-change", "--milestone", "M-001", "--file", "f.py",
            "--diff", "x", "--old-snippet", "a", "--new-snippet", "b")
    assert r.returncode != 0
    assert "not both" in (r.stdout + r.stderr)
