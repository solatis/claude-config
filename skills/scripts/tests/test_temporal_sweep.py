"""F2 regression: fix-mode clears the whole temporal class in one pass.

PLANNER-HARNESS-FIX-ROADMAP.md F2: the QR fix loop used to patch only the
findings QR named, so sibling instances of the same class re-surfaced on the
next verify pass (3+ iterations). These tests guard the two mechanisms that
close the class in one iteration:

  1. A deterministic scanner (scan_text/scan_plan_docs) that finds EVERY
     instance of the temporal class, not just the named ones.
  2. The class-sweep directive injected into every *_qr_fix.py prompt.
  3. The `temporal-scan` CLI gate that exits non-zero while any hit remains,
     so the fixer cannot report PASS with siblings still present.
"""

import json
import subprocess
import sys
from pathlib import Path

from skills.planner.shared.temporal_detection import (
    scan_text,
    scan_plan_docs,
    format_scan_report,
)


def test_scan_text_finds_all_class_instances():
    # Three sibling instances of the temporal class on separate lines.
    text = (
        "# Added retry handler\n"
        "x = 1  # timeless, fine\n"
        "# Previously used webhooks\n"
        "# TODO: wire metrics\n"
    )
    hits = scan_text(text)
    classes = {h.question_id for h in hits}
    assert "CHANGE_RELATIVE" in classes      # "Added"
    assert "BASELINE_REFERENCE" in classes   # "Previously"
    assert "PLANNING_ARTIFACT" in classes    # "TODO"
    # The clean line produced no hit.
    assert all(h.line_no != 2 for h in hits)


def test_scan_text_word_boundary_no_false_fire():
    # "Willing"/"Insertion" must not match the "Will"/"Insert" signals.
    assert scan_text("She is willing and the insertion point is set") == []


def test_scan_text_clean_is_zero():
    assert scan_text("Validates the token and returns the user.") == []


def _plan_with_temporal_docs():
    return {
        "milestones": [
            {
                "id": "M-001",
                "code_changes": [
                    {"id": "CC-M-001-001",
                     "doc_diff": "+ # Added caching layer\n+ # Replaces the old path",
                     "comments": "TODO: revisit",
                     "diff": "--- a/x.py\n+++ b/x.py\n@@\n+# Now uses pooling\n unchanged Previously line"},
                ],
                "documentation": {
                    "module_comment": "Will hold the registry",
                    "inline_comments": [{"location": "f:1", "comment": "Instead of the legacy hook"}],
                    "function_blocks": [],
                    "docstrings": [],
                },
            }
        ]
    }


def test_scan_plan_docs_sweeps_every_field():
    hits = scan_plan_docs(_plan_with_temporal_docs())
    fields = {h.field for h in hits}
    assert "CC-M-001-001.doc_diff" in fields
    assert "CC-M-001-001.comments" in fields
    assert "CC-M-001-001.diff(+)" in fields
    assert "M-001.module_comment" in fields
    assert "M-001.inline_comments" in fields
    # The unchanged (context) diff line with "Previously" must NOT count --
    # only added (+) lines are ours.
    assert all("unchanged" not in h.text for h in hits)


def test_scan_plan_docs_excludes_decision_reasoning():
    # planning_context reasoning legitimately says "chose"/"deliberately" and
    # must never be scanned -- doing so would false-fire and defeat the gate.
    plan = {
        "planning_context": {
            "decisions": [{"id": "DL-1", "decision": "Use polling",
                           "reasoning_chain": "We deliberately chose polling instead of webhooks"}],
        },
        "milestones": [],
    }
    assert scan_plan_docs(plan) == []


def test_format_scan_report_pass_and_fail():
    assert "PASS" in format_scan_report([])
    rep = format_scan_report(scan_plan_docs(_plan_with_temporal_docs()))
    assert "<temporal_scan" in rep and "hit" in rep


def _run_cli(state_dir: Path, *args):
    scripts_root = Path(__file__).resolve().parents[1]
    return subprocess.run(
        [sys.executable, "-m", "skills.planner.cli.plan",
         "--state-dir", str(state_dir), *args],
        cwd=str(scripts_root), capture_output=True, text=True,
    )


def test_temporal_scan_cli_gate(tmp_path):
    """The gate exits 1 while hits remain, 0 once swept clean -- this is what
    forbids the fixer from reporting PASS with siblings still present.
    """
    state_dir = tmp_path
    plan_path = state_dir / "plan.json"

    # Dirty: multiple sibling instances -> non-zero exit.
    plan_path.write_text(json.dumps(_plan_with_temporal_docs()))
    dirty = _run_cli(state_dir, "temporal-scan")
    assert dirty.returncode == 1, dirty.stdout + dirty.stderr
    assert "temporal_scan" in dirty.stdout

    # Clean: zero hits -> exit 0, PASS.
    clean_plan = {
        "milestones": [
            {"id": "M-001",
             "code_changes": [{"id": "CC-M-001-001",
                               "doc_diff": "+ # Caches lookups by key",
                               "comments": "", "diff": ""}],
             "documentation": {"module_comment": "Holds the registry",
                               "inline_comments": [], "function_blocks": [], "docstrings": []}}
        ]
    }
    plan_path.write_text(json.dumps(clean_plan))
    clean = _run_cli(state_dir, "temporal-scan")
    assert clean.returncode == 0, clean.stdout + clean.stderr
    assert "PASS" in clean.stdout


def test_all_fix_scripts_carry_class_sweep_directive(tmp_path):
    """Every *_qr_fix.py fix prompt must reframe findings as a class to sweep,
    not a closed list -- the core F2 behavior change.
    """
    from skills.planner.architect import plan_design_qr_fix
    from skills.planner.developer import plan_code_qr_fix, exec_implement_qr_fix
    from skills.planner.technical_writer import plan_docs_qr_fix, exec_docs_qr_fix

    # plan-phase scripts render context.json in step 1; provide one.
    (tmp_path / "context.json").write_text("{}")
    sd = str(tmp_path)

    mods = [plan_design_qr_fix, plan_code_qr_fix, plan_docs_qr_fix,
            exec_implement_qr_fix, exec_docs_qr_fix]
    for mod in mods:
        g = mod.get_step_guidance(1, None, state_dir=sd)
        body = "\n".join(str(a) for a in g["actions"])
        assert "WHOLE-CLASS FIX" in body, f"{mod.__name__} missing class-sweep directive"


def test_plan_phase_fix_scripts_wire_temporal_gate(tmp_path):
    """The plan-phase comment-bearing fix scripts must wire the deterministic
    temporal-scan gate into their step-3 self-check.
    """
    from skills.planner.developer import plan_code_qr_fix
    from skills.planner.technical_writer import plan_docs_qr_fix

    sd = str(tmp_path)
    for mod in (plan_code_qr_fix, plan_docs_qr_fix):
        g = mod.get_step_guidance(3, None, state_dir=sd)
        body = "\n".join(str(a) for a in g["actions"])
        assert "temporal-scan" in body, f"{mod.__name__} step 3 missing temporal-scan gate"
