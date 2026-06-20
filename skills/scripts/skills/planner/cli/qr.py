"""CLI for atomic QR state mutation with file locking.

Usage: python3 -m skills.planner.cli.qr --state-dir <dir> --qr-phase <phase> <command> [args]

Commands:
  update-item <id> --status <PASS|FAIL> [--finding <text>] [--severity <MUST|SHOULD|COULD>]

Parallel verify agents write to the same qr-{phase}.json file simultaneously.
Without coordination, race conditions corrupt the file:
  Agent A reads {items: [todo, todo]}
  Agent B reads {items: [todo, todo]}
  Agent A writes {items: [pass, todo]}  <- lost update
  Agent B writes {items: [todo, pass]}

This CLI serializes access via file locking and prevents corruption.

This works by:
1. fcntl.flock(LOCK_EX) blocks until exclusive lock acquired
2. Read qr-{phase}.json inside critical section
3. Mutate single item in memory
4. Write to tempfile, os.rename() for atomicity
5. Release lock on file descriptor close

Invariants:
- Lock holder is sole writer; readers may see stale data but never partial writes
- os.rename() is atomic on POSIX; no reader sees half-written JSON
- PASS is terminal; PASS->FAIL transition errors immediately
- FAIL requires --finding; prevents silent status changes
"""

from __future__ import annotations

import fcntl
import json
import os
import sys
import tempfile
from pathlib import Path

from .output import EntityResult, print_entity_result
from . import qr_commands
from .dispatch import discover_methods, batch as batch_dispatch, list_methods


# Valid status values (match QAItemStatus enum)
VALID_STATUSES = frozenset({"PASS", "FAIL"})

# Valid severity values (per conventions/severity.md)
VALID_SEVERITIES = frozenset({"MUST", "SHOULD", "COULD"})

# Terminal statuses that cannot be changed
TERMINAL_STATUSES = frozenset({"PASS"})

# Statuses that require finding
REQUIRES_FINDING = frozenset({"FAIL"})

# Statuses that forbid finding
FORBIDS_FINDING = frozenset({"PASS"})


def error_exit(msg: str, code: int = 1):
    """Print error in XML format and exit."""
    print(f"""<qr_cli_error>
  <message>{msg}</message>
</qr_cli_error>""")
    sys.exit(code)


def get_qr_path(state_dir: str, phase: str) -> Path:
    """Get path to qr-{phase}.json file."""
    return Path(state_dir) / f"qr-{phase}.json"


def load_qr_state_locked(fd) -> dict:
    """Load QR state from file descriptor (assumes lock held)."""
    fd.seek(0)
    content = fd.read()
    if not content:
        return {"phase": "", "items": []}
    return json.loads(content)


def save_qr_state_atomic(state_dir: str, phase: str, qr_state: dict):
    """Write QR state atomically via tempfile + rename.

    tempfile in same directory ensures same filesystem (rename can't cross mounts).
    os.rename() is atomic on POSIX filesystems.
    """
    qr_path = get_qr_path(state_dir, phase)

    # Create tempfile in same directory as target
    fd, tmp_path = tempfile.mkstemp(
        dir=state_dir,
        prefix=f"qr-{phase}.",
        suffix=".tmp"
    )
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(qr_state, f, indent=2)
        # Atomic rename
        os.rename(tmp_path, qr_path)
    except Exception:
        # Clean up on failure
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def find_item(qr_state: dict, item_id: str) -> tuple[int, dict | None]:
    """Find item by ID. Returns (index, item) or (-1, None) if not found."""
    for i, item in enumerate(qr_state.get("items", [])):
        if item.get("id") == item_id:
            return i, item
    return -1, None


def validate_transition(current_status: str, new_status: str, item_id: str):
    """Validate status transition is allowed.

    State transitions:
    - TODO -> PASS: verification succeeded
    - TODO -> FAIL: verification found issue
    - FAIL -> PASS: fix applied and re-verified
    - FAIL -> FAIL: re-verification still finds issues (findings update)
    - PASS -> *: forbidden; if previously passed, can't unpass
    """
    if current_status in TERMINAL_STATUSES:
        error_exit(
            f"Item {item_id} has terminal status {current_status}. "
            f"Cannot transition to {new_status}."
        )


def cmd_update_item(state_dir: str, phase: str, args: list[str]):
    """Update a single QR item status.

    This is the core operation for parallel verify agents.
    Uses file locking to prevent concurrent write corruption.
    """
    if not args:
        error_exit("Usage: update-item <id> --status <PASS|FAIL> [--finding <text>] [--severity <MUST|SHOULD|COULD>]")

    item_id = args[0]
    status = None
    finding = None
    severity = None

    i = 1
    while i < len(args):
        if args[i] == "--status" and i + 1 < len(args):
            status = args[i + 1].upper()
            i += 2
        elif args[i] == "--finding" and i + 1 < len(args):
            finding = args[i + 1]
            i += 2
        elif args[i] == "--severity" and i + 1 < len(args):
            severity = args[i + 1].upper()
            if severity not in VALID_SEVERITIES:
                error_exit(f"Invalid severity: {severity}. Must be MUST, SHOULD, or COULD")
            i += 2
        else:
            i += 1

    # Validate status
    if not status:
        error_exit("--status required (PASS or FAIL)")

    if status not in VALID_STATUSES:
        error_exit(f"Invalid status: {status}. Must be PASS or FAIL.")

    # Validate finding requirements
    if status in REQUIRES_FINDING and not finding:
        error_exit(f"Status {status} requires --finding to explain what failed.")

    if status in FORBIDS_FINDING and finding:
        error_exit(f"Status {status} forbids --finding. PASS means no issues found.")

    qr_path = get_qr_path(state_dir, phase)
    if not qr_path.exists():
        error_exit(f"QR state file not found: {qr_path}")

    # File locking for concurrent access
    # fcntl.flock() with LOCK_EX blocks until exclusive lock acquired
    # Lock is released automatically when file descriptor is closed
    with open(qr_path, "r+") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)

        qr_state = load_qr_state_locked(f)

        idx, item = find_item(qr_state, item_id)
        if idx < 0:
            error_exit(f"Item {item_id} not found in qr-{phase}.json")

        current_status = item.get("status", "TODO")
        validate_transition(current_status, status, item_id)

        # Version increments on status change
        item["version"] = item.get("version", 1) + 1
        item["status"] = status
        # F5: track per-item fix<->verify fail count so the convergence guard
        # can stop an item looping more than the cap. Increment only on FAIL.
        if status == "FAIL":
            item["fail_count"] = item.get("fail_count", 0) + 1
        if finding:
            item["finding"] = finding
        elif "finding" in item and status == "PASS":
            # Clear finding on PASS (e.g., FAIL->PASS transition)
            del item["finding"]
        if severity:
            item["severity"] = severity

        qr_state["items"][idx] = item

        # Atomic write
        save_qr_state_atomic(state_dir, phase, qr_state)

        # Lock released when f closes

    # Structured output matching plan.py format
    print_entity_result(EntityResult(
        id=item_id,
        version=item["version"],
        operation="updated"
    ))


def cmd_get_item(state_dir: str, phase: str, args: list[str]):
    """Get a single QR item by ID. For debugging/inspection."""
    if not args:
        error_exit("Usage: get-item <id>")

    item_id = args[0]
    qr_path = get_qr_path(state_dir, phase)

    if not qr_path.exists():
        error_exit(f"QR state file not found: {qr_path}")

    with open(qr_path) as f:
        qr_state = json.load(f)

    _, item = find_item(qr_state, item_id)
    if item is None:
        error_exit(f"Item {item_id} not found")

    print(json.dumps(item, indent=2))


def cmd_list_items(state_dir: str, phase: str, args: list[str]):
    """List all QR items with their status."""
    status_filter = None

    i = 0
    while i < len(args):
        if args[i] == "--status" and i + 1 < len(args):
            status_filter = args[i + 1].upper()
            i += 2
        else:
            i += 1

    qr_path = get_qr_path(state_dir, phase)
    if not qr_path.exists():
        error_exit(f"QR state file not found: {qr_path}")

    with open(qr_path) as f:
        qr_state = json.load(f)

    for item in qr_state.get("items", []):
        item_status = item.get("status", "TODO")
        if status_filter and item_status != status_filter:
            continue
        finding_str = f" | {item.get('finding', '')}" if item.get("finding") else ""
        print(f"{item.get('id')}\t{item_status}{finding_str}")


def cmd_summary(state_dir: str, phase: str, args: list[str]):
    """Print summary of QR state (counts by status)."""
    qr_path = get_qr_path(state_dir, phase)
    if not qr_path.exists():
        error_exit(f"QR state file not found: {qr_path}")

    with open(qr_path) as f:
        qr_state = json.load(f)

    counts = {"TODO": 0, "PASS": 0, "FAIL": 0}
    for item in qr_state.get("items", []):
        status = item.get("status", "TODO")
        counts[status] = counts.get(status, 0) + 1

    total = sum(counts.values())
    print(f"Phase: {phase}")
    print(f"Total: {total}")
    for status, count in sorted(counts.items()):
        print(f"  {status}: {count}")


def cmd_assign_group(state_dir: str, phase: str, args: list[str]):
    """Assign QR item to a group.

    Usage: assign-group <item_id> --group-id <group_id>

    Atomic update with file locking. Group assignment is idempotent.
    Does not increment version (grouping is metadata, not verification).
    """
    if not args:
        error_exit("Usage: assign-group <item_id> --group-id <group_id>")

    item_id = args[0]
    group_id = None

    i = 1
    while i < len(args):
        if args[i] == "--group-id" and i + 1 < len(args):
            group_id = args[i + 1]
            i += 2
        else:
            i += 1

    if not group_id:
        error_exit("--group-id required")

    qr_path = get_qr_path(state_dir, phase)
    if not qr_path.exists():
        error_exit(f"QR state file not found: {qr_path}")

    valid_prefixes = ('umbrella', 'parent-', 'component-', 'concern-', 'affinity-')
    if not (group_id == 'umbrella' or any(group_id.startswith(p) for p in valid_prefixes[1:])):
        error_exit(f"Invalid group_id '{group_id}'. Must be 'umbrella' or start with: parent-, component-, concern-, affinity-")

    with open(qr_path, "r+") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        qr_state = load_qr_state_locked(f)

        idx, item = find_item(qr_state, item_id)
        if idx < 0:
            error_exit(f"Item {item_id} not found in qr-{phase}.json")

        item["group_id"] = group_id
        qr_state["items"][idx] = item
        save_qr_state_atomic(state_dir, phase, qr_state)

    print_entity_result(EntityResult(
        id=item_id,
        version=item.get("version", 1),
        operation="updated"
    ))


def cmd_accept_item(state_dir: str, phase: str, args: list[str]):
    """Override-accept a FAIL item with a recorded rationale (F5).

    Used to resolve the loop-convergence escalation gate: a MUST item that has
    failed past the per-item cap is accepted (accepted=True + acceptance_reason)
    so it stops blocking the workflow, with the human's reason on record.
    """
    if not args:
        error_exit("Usage: accept-item <id> --reason <text>")

    item_id = args[0]
    reason = None
    i = 1
    while i < len(args):
        if args[i] == "--reason" and i + 1 < len(args):
            reason = args[i + 1]
            i += 2
        else:
            i += 1

    if not reason:
        error_exit("--reason required: record why this item is accepted despite failing")

    qr_path = get_qr_path(state_dir, phase)
    if not qr_path.exists():
        error_exit(f"QR state file not found: {qr_path}")

    with open(qr_path, "r+") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        qr_state = load_qr_state_locked(f)
        idx, item = find_item(qr_state, item_id)
        if idx < 0:
            error_exit(f"Item {item_id} not found in qr-{phase}.json")
        item["accepted"] = True
        item["acceptance_reason"] = reason
        item["version"] = item.get("version", 1) + 1
        qr_state["items"][idx] = item
        save_qr_state_atomic(state_dir, phase, qr_state)

    print_entity_result(EntityResult(
        id=item_id,
        version=item["version"],
        operation="accepted"
    ))


COMMANDS = {
    "update-item": cmd_update_item,
    "get-item": cmd_get_item,
    "list-items": cmd_list_items,
    "summary": cmd_summary,
    "assign-group": cmd_assign_group,
    "accept-item": cmd_accept_item,
}


def cli(args: list[str] = None):
    """Main CLI entrypoint."""
    if args is None:
        args = sys.argv[1:]

    if not args:
        print("Usage: python3 -m skills.planner.cli.qr --state-dir <dir> --qr-phase <phase> <command> [args]")
        print("")
        print("Global options:")
        print("  --state-dir <dir>   State directory (required)")
        print("  --qr-phase <phase>  QR phase name (required)")
        print("")
        print("Commands:")
        print("  update-item <id> --status <PASS|FAIL> [--finding <text>]")
        print("  get-item <id>")
        print("  list-items [--status <status>]")
        print("  summary")
        sys.exit(0)

    # Parse global options
    state_dir = None
    phase = None
    remaining_args = []

    i = 0
    while i < len(args):
        if args[i] == "--state-dir" and i + 1 < len(args):
            state_dir = args[i + 1]
            i += 2
        elif args[i] == "--qr-phase" and i + 1 < len(args):
            phase = args[i + 1]
            i += 2
        else:
            remaining_args.append(args[i])
            i += 1

    if not state_dir:
        error_exit("--state-dir required")
    if not phase:
        error_exit("--qr-phase required")

    if not remaining_args:
        error_exit("Command required")

    cmd = remaining_args[0]
    cmd_args = remaining_args[1:]

    # Handle batch command
    if cmd == "batch":
        methods = discover_methods(qr_commands)
        ctx = qr_commands.QRContext(state_dir=Path(state_dir), phase=phase)

        if cmd_args:
            requests = json.loads(cmd_args[0])
        else:
            requests = json.load(sys.stdin)

        results = batch_dispatch(methods, requests, ctx)
        print(json.dumps(results, indent=2))
        return

    # Handle list-methods command
    if cmd == "list-methods":
        methods = discover_methods(qr_commands)
        print(json.dumps(list_methods(methods), indent=2))
        return

    if cmd not in COMMANDS:
        error_exit(f"Unknown command: {cmd}")

    COMMANDS[cmd](state_dir, phase, cmd_args)


def main():
    cli()


if __name__ == "__main__":
    main()
