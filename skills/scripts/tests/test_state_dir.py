"""F1 regression: planner state lives in a persistent dir, never /tmp.

These guard the fix from PLANNER-HARNESS-FIX-ROADMAP.md F1: a session-limit
restart used to wipe /tmp and destroy an in-progress plan one step before the
final write. Step 1 must (a) honor an explicit --state-dir for resume, and
(b) default to a persistent .claude/planner-state/ dir instead of /tmp.
"""

import json
import subprocess
import sys
from pathlib import Path

from skills.planner.shared.resources import (
    create_state_dir,
    default_state_root,
)


def test_default_state_root_is_not_under_tmp():
    root = default_state_root()
    assert "/tmp" not in str(root), f"state root must not live under /tmp: {root}"
    assert root.name == "planner-state"


def test_create_state_dir_honors_explicit(tmp_path):
    explicit = tmp_path / "my-state"
    out = create_state_dir(str(explicit))
    assert Path(out) == explicit
    assert explicit.is_dir()
    # Idempotent: re-running against the same dir returns it unchanged (resume).
    out2 = create_state_dir(str(explicit))
    assert Path(out2) == explicit


def test_create_state_dir_default_is_persistent_not_tmp(monkeypatch, tmp_path):
    # Point the default root at a controlled location and confirm the minted
    # dir lands under it (persistent), never under /tmp.
    fake_root = tmp_path / ".claude" / "planner-state"
    monkeypatch.setattr(
        "skills.planner.shared.resources.default_state_root",
        lambda: fake_root,
    )
    out = create_state_dir(None)
    assert Path(out).is_dir()
    assert str(out).startswith(str(fake_root))
    assert "/tmp/planner-" not in out


def test_create_state_dir_default_is_unique(monkeypatch, tmp_path):
    fake_root = tmp_path / "planner-state"
    monkeypatch.setattr(
        "skills.planner.shared.resources.default_state_root",
        lambda: fake_root,
    )
    a = create_state_dir(None)
    b = create_state_dir(None)
    assert a != b


def _run_step1(state_dir: Path, scripts_root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable, "-m", "skills.planner.orchestrator.planner",
            "--step", "1", "--state-dir", str(state_dir),
        ],
        cwd=str(scripts_root),
        capture_output=True,
        text=True,
    )


def test_step1_honors_state_dir_and_resumes(tmp_path):
    """Step 1 writes plan.json into the given --state-dir, and re-running
    step 1 against the same dir resumes (reuses it) -- the F1 acceptance:
    kill mid-run, re-invoke with same --state-dir, zero loss.
    """
    scripts_root = Path(__file__).resolve().parents[1]
    state_dir = tmp_path / "run-state"

    r1 = _run_step1(state_dir, scripts_root)
    assert r1.returncode == 0, r1.stderr
    plan = state_dir / "plan.json"
    assert plan.is_file(), "step 1 must write plan.json into the explicit state dir"
    assert f"STATE_DIR={state_dir}" in r1.stdout

    # Simulate progress, then a restart: mutate plan.json, re-run step 1 with
    # the SAME dir. The dir (and our marker) must survive -- step 1 honors it
    # rather than minting a new /tmp dir.
    data = json.loads(plan.read_text())
    data["overview"]["problem"] = "resume-marker"
    plan.write_text(json.dumps(data))

    r2 = _run_step1(state_dir, scripts_root)
    assert r2.returncode == 0, r2.stderr
    assert f"STATE_DIR={state_dir}" in r2.stdout
    # The state dir itself is reused (no /tmp dir minted in stdout).
    assert "/tmp/planner-" not in r2.stdout
    # Resume-safe: prior work survives a step-1 re-run (skeleton not clobbered).
    assert json.loads(plan.read_text())["overview"]["problem"] == "resume-marker"
