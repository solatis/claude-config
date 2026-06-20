"""F5 regression: per-item fix<->verify loop-convergence guard.

PLANNER-HARNESS-FIX-ROADMAP.md F5: fix<->verify loops had no per-item cap;
only a human deciding "override / accept advisory" broke them. After K
(default 2) failures on the SAME item, the loop must converge or surface one
decision:
  - MUST item past the cap  -> escalate to a single human-decision gate
  - SHOULD/COULD past the cap -> auto-accept with rationale, proceed
"""

import json
import subprocess
import sys
from pathlib import Path

from skills.planner.shared.qr.utils import (
    classify_item_convergence,
    convergence_partition,
    has_qr_failures,
    get_escalations,
    record_auto_accepts,
)
from skills.planner.shared.qr.constants import get_convergence_cap


def test_cap_default_is_two():
    assert get_convergence_cap() == 2


def test_classify_covers_all_classes():
    assert classify_item_convergence({"severity": "MUST", "fail_count": 1}) == "retry"
    assert classify_item_convergence({"severity": "MUST", "fail_count": 2}) == "escalate"
    assert classify_item_convergence({"severity": "SHOULD", "fail_count": 2}) == "auto_accept"
    assert classify_item_convergence({"severity": "COULD", "fail_count": 9}) == "auto_accept"
    assert classify_item_convergence({"severity": "MUST", "fail_count": 9, "accepted": True}) == "accepted"


def _qr_state(items):
    return {"phase": "plan-code", "iteration": 1, "items": items}


def test_partition_buckets():
    state = _qr_state([
        {"id": "A", "scope": "*", "check": "c", "status": "FAIL", "severity": "MUST", "fail_count": 1},
        {"id": "B", "scope": "*", "check": "c", "status": "FAIL", "severity": "MUST", "fail_count": 2},
        {"id": "C", "scope": "*", "check": "c", "status": "FAIL", "severity": "SHOULD", "fail_count": 3},
        {"id": "D", "scope": "*", "check": "c", "status": "PASS", "severity": "MUST", "fail_count": 0},
    ])
    part = convergence_partition(state)
    assert [i["id"] for i in part["retry"]] == ["A"]
    assert [i["id"] for i in part["escalate"]] == ["B"]
    assert [i["id"] for i in part["auto_accept"]] == ["C"]


def _write_qr(tmp_path, items):
    state = _qr_state(items)
    (tmp_path / "qr-plan-code.json").write_text(json.dumps(state))
    return str(tmp_path)


def test_should_item_past_cap_stops_blocking(tmp_path):
    sd = _write_qr(tmp_path, [
        {"id": "S", "scope": "*", "check": "c", "status": "FAIL", "severity": "SHOULD", "fail_count": 2},
    ])
    # Auto-acceptable -> no blocking failure -> loop proceeds.
    assert has_qr_failures(sd, "plan-code") is False


def test_must_item_past_cap_still_blocks_but_escalates(tmp_path):
    sd = _write_qr(tmp_path, [
        {"id": "M", "scope": "*", "check": "c", "status": "FAIL", "severity": "MUST", "fail_count": 2},
    ])
    assert has_qr_failures(sd, "plan-code") is True
    esc = get_escalations(sd, "plan-code")
    assert [i["id"] for i in esc] == ["M"]


def test_retry_under_cap_still_blocks(tmp_path):
    sd = _write_qr(tmp_path, [
        {"id": "R", "scope": "*", "check": "c", "status": "FAIL", "severity": "SHOULD", "fail_count": 1},
    ])
    assert has_qr_failures(sd, "plan-code") is True


def test_record_auto_accepts_mutates_and_is_idempotent(tmp_path):
    sd = _write_qr(tmp_path, [
        {"id": "S", "scope": "*", "check": "c", "status": "FAIL", "severity": "SHOULD", "fail_count": 2},
        {"id": "M", "scope": "*", "check": "c", "status": "FAIL", "severity": "MUST", "fail_count": 2},
    ])
    accepted = record_auto_accepts(sd, "plan-code")
    assert [i["id"] for i in accepted] == ["S"]

    state = json.loads((tmp_path / "qr-plan-code.json").read_text())
    by_id = {i["id"]: i for i in state["items"]}
    assert by_id["S"]["accepted"] is True
    assert "acceptance_reason" in by_id["S"]
    assert by_id["M"].get("accepted") is not True  # MUST never auto-accepted

    # Idempotent: a second pass finds nothing new to accept.
    assert record_auto_accepts(sd, "plan-code") == []


def test_validate_state_accepts_convergence_fields(tmp_path):
    """The new per-item fields must not break qr-file schema validation."""
    from skills.planner.shared.schema import validate_state
    (tmp_path / "qr-plan-code.json").write_text(json.dumps(_qr_state([
        {"id": "M", "scope": "*", "check": "c", "status": "FAIL",
         "severity": "MUST", "fail_count": 3, "accepted": True, "acceptance_reason": "ok"},
    ])))
    # Minimal plan.json so validate_state has something to load.
    (tmp_path / "plan.json").write_text(json.dumps({
        "overview": {"problem": "p", "approach": "a"}, "milestones": [],
    }))
    validate_state(str(tmp_path))  # must not raise


# --- CLI integration ---------------------------------------------------------

def _qr_cli(state_dir: Path, *args):
    scripts_root = Path(__file__).resolve().parents[1]
    return subprocess.run(
        [sys.executable, "-m", "skills.planner.cli.qr",
         "--state-dir", str(state_dir), "--qr-phase", "plan-code", *args],
        cwd=str(scripts_root), capture_output=True, text=True,
    )


def test_update_item_increments_fail_count(tmp_path):
    _write_qr(tmp_path, [
        {"id": "X", "scope": "*", "check": "c", "status": "TODO", "severity": "MUST"},
    ])
    r = _qr_cli(tmp_path, "update-item", "X", "--status", "FAIL", "--finding", "bad")
    assert r.returncode == 0, r.stderr
    item = json.loads((tmp_path / "qr-plan-code.json").read_text())["items"][0]
    assert item["fail_count"] == 1


def test_accept_item_cli_sets_accepted(tmp_path):
    _write_qr(tmp_path, [
        {"id": "M", "scope": "*", "check": "c", "status": "FAIL", "severity": "MUST", "fail_count": 2},
    ])
    r = _qr_cli(tmp_path, "accept-item", "M", "--reason", "known limitation, tracked")
    assert r.returncode == 0, r.stderr
    item = json.loads((tmp_path / "qr-plan-code.json").read_text())["items"][0]
    assert item["accepted"] is True
    assert item["acceptance_reason"] == "known limitation, tracked"
    # Now non-blocking.
    assert has_qr_failures(str(tmp_path), "plan-code") is False


def test_accept_item_requires_reason(tmp_path):
    _write_qr(tmp_path, [
        {"id": "M", "scope": "*", "check": "c", "status": "FAIL", "severity": "MUST", "fail_count": 2},
    ])
    r = _qr_cli(tmp_path, "accept-item", "M")
    assert r.returncode != 0
    assert "reason" in (r.stdout + r.stderr).lower()


# --- gate escalation ---------------------------------------------------------

def test_gate_renders_human_decision_on_escalation():
    from skills.planner.shared.gates import build_gate_output
    from skills.planner.shared.qr.types import QRState, QRStatus

    qr = QRState(status=QRStatus.FAIL)
    res = build_gate_output(
        module_path="skills.planner.orchestrator.planner",
        script_name="planner",
        qr_name="plan-code-qr-route",
        qr=qr, step=10, work_step=7, pass_step=11,
        pass_message="proceed",
        fix_target=None, state_dir="/sd",
        escalations=[{"id": "M", "severity": "MUST", "fail_count": 2,
                      "check": "x", "finding": "still wrong"}],
        phase="plan-code",
    )
    assert "Human Decision Required" in res.output
    assert "OVERRIDE-ACCEPT" in res.output
    assert "accept-item M" in res.output
    assert res.terminal_pass is False


def test_gate_normal_loop_when_no_escalation():
    from skills.planner.shared.gates import build_gate_output
    from skills.planner.shared.qr.types import QRState, QRStatus

    qr = QRState(status=QRStatus.FAIL)
    res = build_gate_output(
        module_path="skills.planner.orchestrator.planner",
        script_name="planner",
        qr_name="plan-code-qr-route",
        qr=qr, step=10, work_step=7, pass_step=11,
        pass_message="proceed",
        fix_target=None, state_dir="/sd",
        escalations=[], phase="plan-code",
    )
    assert "Human Decision Required" not in res.output
