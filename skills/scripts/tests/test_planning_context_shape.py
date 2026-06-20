"""F6 regression: planning_context shape validates with self-correctable errors.

PLANNER-HARNESS-FIX-ROADMAP.md F6: the architect emitted planning_context in a
richer shape than the schema (constraints as dicts not strings;
rejected_alternatives missing required rejection_reason/decision_ref) -> raw
pydantic errors that blocked a downstream --step N until hand-coerced. The
validator runs on the RAW dict and returns targeted, self-correctable messages;
a CLI command surfaces them inside the architect step.
"""

import json
import subprocess
import sys
from pathlib import Path

from skills.planner.shared.schema import validate_planning_context


def test_valid_shape_has_no_errors():
    pc = {
        "constraints": ["MUST run on Python 3.10+", "SHOULD avoid new deps"],
        "rejected_alternatives": [
            {"id": "RA-1", "alternative": "use webhooks",
             "rejection_reason": "30% delivery failure", "decision_ref": "DL-001"},
        ],
        "decisions": [],
    }
    assert validate_planning_context(pc) == []


def test_constraints_as_dicts_are_flagged():
    pc = {"constraints": [{"text": "MUST x"}, "ok string"], "rejected_alternatives": []}
    errs = validate_planning_context(pc)
    assert any("constraints[0]" in e and "string" in e for e in errs)
    # The valid string entry is not flagged.
    assert not any("constraints[1]" in e for e in errs)


def test_rejected_alternative_missing_fields_flagged():
    pc = {
        "constraints": [],
        "rejected_alternatives": [
            {"id": "RA-1", "alternative": "polling"},  # no rejection_reason / decision_ref
        ],
    }
    errs = validate_planning_context(pc)
    assert any("rejection_reason" in e for e in errs)
    assert any("decision_ref" in e for e in errs)


def test_non_object_planning_context():
    assert validate_planning_context([]) == ["planning_context must be a JSON object"]


def test_constraints_not_a_list():
    errs = validate_planning_context({"constraints": "MUST x", "rejected_alternatives": []})
    assert any("must be a list of strings" in e for e in errs)


def _plan_cli(state_dir: Path, *args):
    scripts_root = Path(__file__).resolve().parents[1]
    return subprocess.run(
        [sys.executable, "-m", "skills.planner.cli.plan",
         "--state-dir", str(state_dir), *args],
        cwd=str(scripts_root), capture_output=True, text=True,
    )


def test_cli_reports_errors_and_exits_nonzero(tmp_path):
    (tmp_path / "plan.json").write_text(json.dumps({
        "overview": {"problem": "p", "approach": "a"},
        "planning_context": {
            "constraints": [{"bad": "dict"}],
            "rejected_alternatives": [{"id": "RA-1", "alternative": "x"}],
        },
        "milestones": [],
    }))
    r = _plan_cli(tmp_path, "validate-planning-context")
    assert r.returncode == 1, r.stdout + r.stderr
    assert "planning_context_errors" in r.stdout
    assert "rejection_reason" in r.stdout


def test_cli_passes_on_valid_shape(tmp_path):
    (tmp_path / "plan.json").write_text(json.dumps({
        "overview": {"problem": "p", "approach": "a"},
        "planning_context": {
            "constraints": ["MUST keep API stable"],
            "rejected_alternatives": [
                {"id": "RA-1", "alternative": "rewrite",
                 "rejection_reason": "too risky", "decision_ref": "DL-002"}
            ],
        },
        "milestones": [],
    }))
    r = _plan_cli(tmp_path, "validate-planning-context")
    assert r.returncode == 0, r.stdout + r.stderr


def test_architect_fix_step_wires_validator():
    from skills.planner.architect import plan_design_qr_fix
    g = plan_design_qr_fix.get_step_guidance(3, None, state_dir="/sd")
    body = "\n".join(str(a) for a in g["actions"])
    assert "validate-planning-context" in body
