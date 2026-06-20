"""CLI entrypoint for plan.json manipulation with CAS versioning.

Usage: python3 -m skills.planner.cli.plan --state-dir <dir> <command> [args]

Role-based scope enforcement via PLAN_AGENT_ROLE env var.
All writes are validated and atomic (write to .tmp, rename).
CAS versioning: updates require --version matching current entity version.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar, TYPE_CHECKING

from .output import EntityResult, VersionMismatchError, print_entity_result, exit_with_version_error
from . import plan_commands
from .dispatch import discover_methods, batch as batch_dispatch, list_methods

PYDANTIC_AVAILABLE = False
Plan = None  # Will be set if pydantic available

if TYPE_CHECKING:
    from ..shared.schema import (
        Plan,
        Overview,
        Milestone,
        CodeIntent,
        CodeChange,
        Decision,
        Risk,
        Documentation,
        Docstring,
        FunctionBlock,
        InlineComment,
        ReadmeEntry,
        DiagramGraph,
        DiagramNode,
        DiagramEdge,
    )

try:
    from ..shared.schema import (
        Plan,
        Overview,
        Milestone,
        CodeIntent,
        CodeChange,
        Decision,
        Risk,
        Documentation,
        Docstring,
        FunctionBlock,
        InlineComment,
        ReadmeEntry,
        DiagramGraph,
        DiagramNode,
        DiagramEdge,
    )
    PYDANTIC_AVAILABLE = True
except ImportError:
    pass


# =============================================================================
# Role Enforcement
# =============================================================================


ROLE_PERMISSIONS = {
    "architect": {"init", "set-milestone", "set-intent", "set-decision",
                  "set-diagram", "add-diagram-node", "add-diagram-edge"},
    "developer": {"set-change"},
    "tw": {"set-doc", "set-readme", "set-diagram-render",
           "set-doc-diff", "create-doc-change"},
    "qr": {"validate"},
}


def get_role() -> str:
    return os.environ.get("PLAN_AGENT_ROLE", "")


def check_role(command: str) -> str | None:
    """Check if current role can execute command. Returns error message or None."""
    role = get_role()
    if not role:
        return None  # no role restriction

    allowed = ROLE_PERMISSIONS.get(role, set())
    if command not in allowed:
        return f"Role '{role}' cannot execute '{command}'. Allowed: {', '.join(sorted(allowed))}"
    return None


# =============================================================================
# State Directory Resolution
# =============================================================================


_STATE_DIR: Path | None = None


def get_state_dir() -> Path:
    """Return state directory. Must call set_state_dir() first."""
    if _STATE_DIR is None:
        error_exit("--state-dir required")
    return _STATE_DIR


def set_state_dir(path: str) -> None:
    """Set global state directory."""
    global _STATE_DIR
    _STATE_DIR = Path(path)


def get_plan_path(state_dir: Path) -> Path:
    return state_dir / "plan.json"


# =============================================================================
# I/O Helpers
# =============================================================================


def error_exit(msg: str, code: int = 1):
    """Print error in XML format and exit."""
    print(f"""<validation_error>
  <message>{msg}</message>
</validation_error>""")
    sys.exit(code)


def validation_error(location: str, expected: str, actual: str, action: str):
    """Print detailed validation error."""
    print(f"""<validation_error>
  <location>{location}</location>
  <expected>{expected}</expected>
  <actual>{actual}</actual>
  <action>{action}</action>
</validation_error>""")
    sys.exit(1)


def success(msg: str):
    """Print success message."""
    print(msg)


# =============================================================================
# CAS Versioning Helpers
# =============================================================================


def check_version(entity, provided_version: int | None, entity_id: str) -> None:
    """Validate CAS version for update operations.

    Raises VersionMismatchError if provided_version != entity.version.
    No-op if provided_version is None (create operation).
    """
    if provided_version is None:
        return
    current = getattr(entity, 'version', 1)
    if provided_version != current:
        raise VersionMismatchError(
            entity_id=entity_id,
            expected=provided_version,
            actual=current,
            current_json=entity.model_dump_json(indent=2)
        )


def bump_version(entity) -> None:
    """Increment entity version after successful update."""
    if hasattr(entity, 'version'):
        entity.version += 1


# =============================================================================
# Plan I/O
# =============================================================================


def load_plan(state_dir: Path) -> "Plan":
    """Load and validate plan.json."""
    path = get_plan_path(state_dir)
    if not path.exists():
        error_exit(f"plan.json not found at {path}")
    try:
        data = json.loads(path.read_text())
        return Plan.model_validate(data)
    except json.JSONDecodeError as e:
        error_exit(f"Invalid JSON in plan.json: {e}")
    except Exception as e:
        error_exit(f"Validation error: {e}")


def save_plan(state_dir: Path, plan: "Plan"):
    """Atomic write: write to .tmp then rename."""
    path = get_plan_path(state_dir)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(plan.model_dump_json(indent=2))
    tmp_path.rename(path)
    # Catch schema violations immediately after mutation
    from ..shared.schema import validate_state
    validate_state(str(state_dir))


# =============================================================================
# Command Base Class
# =============================================================================


class Command(ABC):
    """Base class for CLI commands. Subclasses define args and handler together."""

    name: ClassVar[str]           # command name (e.g., "set-intent")
    help: ClassVar[str]           # help text
    role: ClassVar[str | None]    # required role or None for unrestricted

    @classmethod
    @abstractmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        """Add command-specific arguments to parser."""
        pass

    @classmethod
    @abstractmethod
    def run(cls, args: argparse.Namespace) -> None:
        """Execute the command."""
        pass


# =============================================================================
# Commands: Initialization
# =============================================================================


class InitCommand(Command):
    name = "init"
    help = "Initialize new plan.json with task description"
    role = "architect"

    @classmethod
    def add_arguments(cls, p: argparse.ArgumentParser) -> None:
        p.add_argument("--task", required=True, help="Task description")
        p.add_argument("--title", default="Untitled Plan", help="Plan title")

    @classmethod
    def run(cls, args: argparse.Namespace) -> None:
        state_dir = get_state_dir()
        path = get_plan_path(state_dir)

        if path.exists():
            error_exit(f"plan.json already exists at {path}")

        plan = Plan(
            overview=Overview(problem=args.task, approach=""),
        )

        save_plan(state_dir, plan)
        success(f"Initialized plan.json with id={plan.plan_id}")


# =============================================================================
# Commands: Architect Phase (set-milestone, set-intent, set-decision)
# =============================================================================


class SetMilestoneCommand(Command):
    name = "set-milestone"
    help = "Create or update milestone"
    role = "architect"

    @classmethod
    def add_arguments(cls, p: argparse.ArgumentParser) -> None:
        p.add_argument("--id", help="Milestone ID (omit for create)")
        p.add_argument("--version", type=int, help="Current version (required for update)")
        p.add_argument("--name", help="Milestone name (required for create)")
        p.add_argument("--files", help="Comma-separated file paths")
        p.add_argument("--flags", help="Comma-separated flags")
        p.add_argument("--requirements", help="Comma-separated requirements")
        p.add_argument("--acceptance-criteria", help="Comma-separated acceptance criteria")
        p.add_argument("--tests", help="Comma-separated test specs")

    @classmethod
    def run(cls, args: argparse.Namespace) -> None:
        state_dir = get_state_dir()
        plan = load_plan(state_dir)

        files = [f.strip() for f in args.files.split(",")] if args.files else []
        flags = [f.strip() for f in args.flags.split(",")] if args.flags else []
        requirements = [r.strip() for r in args.requirements.split(",")] if args.requirements else []
        acceptance = [a.strip() for a in args.acceptance_criteria.split(",")] if args.acceptance_criteria else []
        tests = [t.strip() for t in args.tests.split(",")] if args.tests else []

        if args.id:
            # UPDATE path
            ms = plan.get_milestone(args.id)
            if not ms:
                ids = [m.id for m in plan.milestones]
                validation_error("milestone.id", "Valid milestone ID", args.id,
                               f"Use existing: {', '.join(ids) or 'none'}")

            try:
                check_version(ms, args.version, args.id)
            except VersionMismatchError as e:
                exit_with_version_error(e)
                return

            # Update only provided fields
            if args.name:
                ms.name = args.name
            if files:
                ms.files = files
            if flags:
                ms.flags = flags
            if requirements:
                ms.requirements = requirements
            if acceptance:
                ms.acceptance_criteria = acceptance
            if tests:
                ms.tests = tests

            bump_version(ms)
            save_plan(state_dir, plan)
            print_entity_result(EntityResult(id=ms.id, version=ms.version, operation="updated"))

        else:
            # CREATE path
            if args.version is not None:
                error_exit("--version only valid for updates (when --id provided)")
            if not args.name:
                error_exit("--name required for create")

            num = len(plan.milestones) + 1
            mid = f"M-{num:03d}"

            ms = Milestone(
                id=mid,
                version=1,
                number=num,
                name=args.name,
                files=files,
                flags=flags,
                requirements=requirements,
                acceptance_criteria=acceptance,
                tests=tests,
            )
            plan.milestones.append(ms)

            save_plan(state_dir, plan)
            print_entity_result(EntityResult(id=mid, version=1, operation="created"))


class SetIntentCommand(Command):
    name = "set-intent"
    help = "Create or update code intent"
    role = "architect"

    @classmethod
    def add_arguments(cls, p: argparse.ArgumentParser) -> None:
        p.add_argument("--id", help="Intent ID (omit for create)")
        p.add_argument("--version", type=int, help="Current version (required for update)")
        p.add_argument("--milestone", required=True, help="Parent milestone ID")
        p.add_argument("--file", help="Target file path (required for create)")
        p.add_argument("--function", help="Target function name")
        p.add_argument("--behavior", help="Behavioral description (required for create)")
        p.add_argument("--decision-refs", help="Comma-separated decision IDs")

    @classmethod
    def run(cls, args: argparse.Namespace) -> None:
        state_dir = get_state_dir()
        plan = load_plan(state_dir)

        ms = plan.get_milestone(args.milestone)
        if not ms:
            ids = [m.id for m in plan.milestones]
            validation_error("milestone", "Valid milestone ID", args.milestone,
                           f"Use existing: {', '.join(ids) or 'none'}")

        decision_refs = [r.strip() for r in args.decision_refs.split(",")] if args.decision_refs else []
        for dref in decision_refs:
            if not plan.get_decision(dref):
                validation_error("decision_refs", "Valid decision ID", dref,
                               f"Use existing: {', '.join(d.id for d in plan.planning_context.decisions)}")

        if args.id:
            # UPDATE path
            _, ci = plan.get_intent(args.id)
            if not ci:
                all_intents = [c.id for m in plan.milestones for c in m.code_intents]
                validation_error("intent.id", "Valid intent ID", args.id,
                               f"Use existing: {', '.join(all_intents) or 'none'}")

            try:
                check_version(ci, args.version, args.id)
            except VersionMismatchError as e:
                exit_with_version_error(e)
                return

            # Update only provided fields
            if args.file:
                ci.file = args.file
            if args.function is not None:
                ci.function = args.function if args.function else None
            if args.behavior:
                ci.behavior = args.behavior
            if decision_refs:
                ci.decision_refs = decision_refs

            bump_version(ci)
            save_plan(state_dir, plan)
            print_entity_result(EntityResult(id=ci.id, version=ci.version, operation="updated"))

        else:
            # CREATE path
            if args.version is not None:
                error_exit("--version only valid for updates (when --id provided)")
            if not args.file or not args.behavior:
                error_exit("--file and --behavior required for create")

            num = len(ms.code_intents) + 1
            cid = f"CI-{ms.id}-{num:03d}"

            ci = CodeIntent(
                id=cid,
                version=1,
                file=args.file,
                function=args.function,
                behavior=args.behavior,
                decision_refs=decision_refs,
            )
            ms.code_intents.append(ci)

            save_plan(state_dir, plan)
            print_entity_result(EntityResult(id=cid, version=1, operation="created"))


class SetDecisionCommand(Command):
    name = "set-decision"
    help = "Create or update decision"
    role = "architect"

    @classmethod
    def add_arguments(cls, p: argparse.ArgumentParser) -> None:
        p.add_argument("--id", help="Decision ID (omit for create)")
        p.add_argument("--version", type=int, help="Current version (required for update)")
        p.add_argument("--decision", help="Decision text (required for create)")
        p.add_argument("--reasoning", help="Reasoning chain (required for create)")

    @classmethod
    def run(cls, args: argparse.Namespace) -> None:
        state_dir = get_state_dir()
        plan = load_plan(state_dir)

        if args.id:
            # UPDATE path
            dl = plan.get_decision(args.id)
            if not dl:
                dids = [d.id for d in plan.planning_context.decisions]
                validation_error("decision.id", "Valid decision ID", args.id,
                               f"Use existing: {', '.join(dids) or 'none'}")

            try:
                check_version(dl, args.version, args.id)
            except VersionMismatchError as e:
                exit_with_version_error(e)
                return

            # Update only provided fields
            if args.decision:
                dl.decision = args.decision
            if args.reasoning:
                dl.reasoning = args.reasoning

            bump_version(dl)
            save_plan(state_dir, plan)
            print_entity_result(EntityResult(id=dl.id, version=dl.version, operation="updated"))

        else:
            # CREATE path
            if args.version is not None:
                error_exit("--version only valid for updates (when --id provided)")
            if not args.decision or not args.reasoning:
                error_exit("--decision and --reasoning required for create")

            num = len(plan.planning_context.decisions) + 1
            did = f"DL-{num:03d}"

            dl = Decision(
                id=did,
                version=1,
                decision=args.decision,
                reasoning=args.reasoning,
            )
            plan.planning_context.decisions.append(dl)

            save_plan(state_dir, plan)
            print_entity_result(EntityResult(id=did, version=1, operation="created"))


class SetDiagramCommand(Command):
    name = "set-diagram"
    help = "Create or update diagram graph"
    role = "architect"

    @classmethod
    def add_arguments(cls, p: argparse.ArgumentParser) -> None:
        p.add_argument("--id", help="Diagram ID (omit for create)")
        p.add_argument("--type", required=True,
                      choices=["architecture", "state", "sequence", "dataflow"])
        p.add_argument("--scope", required=True,
                      help="'overview' | 'invisible_knowledge' | 'milestone:M-XXX'")
        p.add_argument("--title", required=True)

    @classmethod
    def run(cls, args: argparse.Namespace) -> None:
        state_dir = get_state_dir()
        plan = load_plan(state_dir)

        if args.id:
            dg = next((d for d in plan.diagram_graphs if d.id == args.id), None)
            if not dg:
                error_exit(f"Diagram {args.id} not found")
            dg.type = args.type
            dg.scope = args.scope
            dg.title = args.title
            operation = "updated"
        else:
            next_num = len(plan.diagram_graphs) + 1
            new_id = f"DIAG-{next_num:03d}"
            dg = DiagramGraph(
                id=new_id,
                type=args.type,
                scope=args.scope,
                title=args.title
            )
            plan.diagram_graphs.append(dg)
            operation = "created"

        save_plan(state_dir, plan)
        print_entity_result(EntityResult(id=dg.id, version=1, operation=operation))


class AddDiagramNodeCommand(Command):
    name = "add-diagram-node"
    help = "Add node to diagram"
    role = "architect"

    @classmethod
    def add_arguments(cls, p: argparse.ArgumentParser) -> None:
        p.add_argument("--diagram", required=True, help="Diagram ID")
        p.add_argument("--node-id", required=True, help="Node ID within diagram")
        p.add_argument("--label", required=True)
        p.add_argument("--type", help="Node type (free-form)")

    @classmethod
    def run(cls, args: argparse.Namespace) -> None:
        state_dir = get_state_dir()
        plan = load_plan(state_dir)

        dg = next((d for d in plan.diagram_graphs if d.id == args.diagram), None)
        if not dg:
            error_exit(f"Diagram {args.diagram} not found")

        if any(n.id == args.node_id for n in dg.nodes):
            error_exit(f"Node {args.node_id} already exists in {args.diagram}")

        node = DiagramNode(id=args.node_id, label=args.label, type=args.type)
        dg.nodes.append(node)

        save_plan(state_dir, plan)
        success(f"Added node {args.node_id} to {args.diagram}")


class AddDiagramEdgeCommand(Command):
    name = "add-diagram-edge"
    help = "Add edge to diagram"
    role = "architect"

    @classmethod
    def add_arguments(cls, p: argparse.ArgumentParser) -> None:
        p.add_argument("--diagram", required=True, help="Diagram ID")
        p.add_argument("--source", required=True, help="Source node ID")
        p.add_argument("--target", required=True, help="Target node ID")
        p.add_argument("--label", required=True, help="Edge label")
        p.add_argument("--protocol", help="Protocol (free-form)")

    @classmethod
    def run(cls, args: argparse.Namespace) -> None:
        state_dir = get_state_dir()
        plan = load_plan(state_dir)

        dg = next((d for d in plan.diagram_graphs if d.id == args.diagram), None)
        if not dg:
            error_exit(f"Diagram {args.diagram} not found")

        edge = DiagramEdge(
            source=args.source,
            target=args.target,
            label=args.label,
            protocol=args.protocol
        )
        dg.edges.append(edge)

        errors = plan.validate_diagram_edges(args.diagram)
        if errors:
            dg.edges.pop()
            error_exit(errors[0])

        save_plan(state_dir, plan)
        success(f"Added edge {args.source} -> {args.target} to {args.diagram}")


# =============================================================================
# Commands: Developer Phase (set-change)
# =============================================================================


class SetChangeCommand(Command):
    name = "set-change"
    help = "Create or update code change"
    role = "developer"

    @classmethod
    def add_arguments(cls, p: argparse.ArgumentParser) -> None:
        p.add_argument("--id", help="Change ID (omit for create)")
        p.add_argument("--version", type=int, help="Current version (required for update)")
        p.add_argument("--milestone", required=True, help="Parent milestone ID")
        p.add_argument("--intent-ref", help="Intent ID this implements")
        p.add_argument("--file", help="Changed file path (required for create)")
        p.add_argument("--diff", help="Diff content (required for create unless snippets given)")
        p.add_argument("--old-snippet", help="F4: exact current text to replace; @@ headers computed by tool")
        p.add_argument("--new-snippet", help="F4: replacement text; pair with --old-snippet")
        p.add_argument("--comments", help="Change-level comments")

    @staticmethod
    def _diff_from_snippets(file: str, old_snippet: str, new_snippet: str) -> str:
        """F4: compute the unified diff deterministically from snippets.

        Reads the current file from cwd when present so the @@ headers anchor to
        real line numbers; the LLM never authors them.
        """
        from ..shared.diffgen import build_unified_diff
        try:
            file_text = Path(file).read_text()
        except (OSError, ValueError):
            file_text = None  # plan-time: file may not exist / be readable
        return build_unified_diff(file, old_snippet, new_snippet, file_text)

    @classmethod
    def run(cls, args: argparse.Namespace) -> None:
        state_dir = get_state_dir()
        plan = load_plan(state_dir)

        # F4: snippets are the source of truth when provided; tool computes diff.
        use_snippets = args.old_snippet is not None or args.new_snippet is not None
        if use_snippets and (args.old_snippet is None or args.new_snippet is None):
            error_exit("--old-snippet and --new-snippet must be provided together")
        if use_snippets and args.diff:
            error_exit("pass snippets OR --diff, not both (diff is computed from snippets)")

        ms = plan.get_milestone(args.milestone)
        if not ms:
            ids = [m.id for m in plan.milestones]
            validation_error("milestone", "Valid milestone ID", args.milestone,
                           f"Use existing: {', '.join(ids) or 'none'}")

        # Validate intent_ref if provided
        if args.intent_ref:
            _, ci = plan.get_intent(args.intent_ref)
            if not ci:
                all_intents = [c.id for m in plan.milestones for c in m.code_intents]
                validation_error("intent_ref", "Valid intent ID", args.intent_ref,
                               f"Use existing: {', '.join(all_intents) or 'none'}")

        if args.id:
            # UPDATE path
            _, cc = plan.get_change(args.id)
            if not cc:
                all_changes = [c.id for m in plan.milestones for c in m.code_changes]
                validation_error("change.id", "Valid change ID", args.id,
                               f"Use existing: {', '.join(all_changes) or 'none'}")

            try:
                check_version(cc, args.version, args.id)
            except VersionMismatchError as e:
                exit_with_version_error(e)
                return

            # Update only provided fields
            if args.intent_ref is not None:
                cc.intent_ref = args.intent_ref if args.intent_ref else None
            if args.file:
                cc.file = args.file
            if use_snippets:
                cc.old_snippet = args.old_snippet
                cc.new_snippet = args.new_snippet
                cc.diff = cls._diff_from_snippets(cc.file, args.old_snippet, args.new_snippet)
            elif args.diff:
                cc.diff = args.diff
            if args.comments is not None:
                cc.comments = args.comments

            bump_version(cc)
            save_plan(state_dir, plan)
            print_entity_result(EntityResult(id=cc.id, version=cc.version, operation="updated"))

        else:
            # CREATE path
            if args.version is not None:
                error_exit("--version only valid for updates (when --id provided)")
            if not args.file or not (args.diff or use_snippets):
                error_exit("--file and (--diff OR --old-snippet/--new-snippet) required for create")

            if use_snippets:
                diff_content = cls._diff_from_snippets(args.file, args.old_snippet, args.new_snippet)
            else:
                diff_content = args.diff

            num = len(ms.code_changes) + 1
            ccid = f"CC-{ms.id}-{num:03d}"

            cc = CodeChange(
                id=ccid,
                version=1,
                intent_ref=args.intent_ref,
                file=args.file,
                diff=diff_content,
                old_snippet=args.old_snippet or "" if use_snippets else "",
                new_snippet=args.new_snippet or "" if use_snippets else "",
                comments=args.comments or "",
            )
            ms.code_changes.append(cc)

            # Validate refs
            errors = plan.validate_refs()
            if errors:
                error_exit("\n".join(errors))

            save_plan(state_dir, plan)
            print_entity_result(EntityResult(id=ccid, version=1, operation="created"))


# =============================================================================
# Commands: TW Phase (set-doc)
# =============================================================================


class SetDocCommand(Command):
    name = "set-doc"
    help = "Create or update documentation"
    role = "tw"

    @classmethod
    def add_arguments(cls, p: argparse.ArgumentParser) -> None:
        p.add_argument("--milestone", required=True, help="Parent milestone ID")
        p.add_argument("--type", required=True, choices=["module", "docstring", "function_block", "inline"],
                      help="Documentation type")
        p.add_argument("--content-file", required=True, help="Path to content file")
        p.add_argument("--function", help="Function name (for docstring or function_block type)")
        p.add_argument("--location", help="Location spec (for inline type)")
        p.add_argument("--decision-ref", help="Decision ID reference (for function_block/inline type)")
        p.add_argument("--source", help="Source provenance (for function_block/inline type)")

    @classmethod
    def run(cls, args: argparse.Namespace) -> None:
        state_dir = get_state_dir()
        plan = load_plan(state_dir)

        ms = plan.get_milestone(args.milestone)
        if not ms:
            ids = [m.id for m in plan.milestones]
            validation_error("milestone.id", "Valid milestone ID", args.milestone,
                           f"Use existing: {', '.join(ids)}")

        content_path = Path(args.content_file)
        if not content_path.exists():
            error_exit(f"Content file not found: {args.content_file}")

        content = content_path.read_text().strip()

        if args.type == "module":
            ms.documentation.module_comment = content
        elif args.type == "docstring":
            if not args.function:
                error_exit("--function required for docstring type")
            ms.documentation.docstrings.append(Docstring(function=args.function, docstring=content))
        elif args.type == "function_block":
            if not args.function:
                error_exit("--function required for function_block type")
            if args.decision_ref and not plan.get_decision(args.decision_ref):
                dids = [d.id for d in plan.planning_context.decisions]
                validation_error("decision_ref", "Valid decision ID", args.decision_ref,
                               f"Use existing: {', '.join(dids)}")
            ms.documentation.function_blocks.append(
                FunctionBlock(function=args.function, comment=content, decision_ref=args.decision_ref, source=args.source)
            )
        elif args.type == "inline":
            if not args.location:
                error_exit("--location required for inline type")
            if args.decision_ref and not plan.get_decision(args.decision_ref):
                dids = [d.id for d in plan.planning_context.decisions]
                validation_error("decision_ref", "Valid decision ID", args.decision_ref,
                               f"Use existing: {', '.join(dids)}")
            ms.documentation.inline_comments.append(
                InlineComment(location=args.location, comment=content, decision_ref=args.decision_ref, source=args.source)
            )

        save_plan(state_dir, plan)
        success(f"Added {args.type} documentation to {args.milestone}")


class SetReadmeCommand(Command):
    name = "set-readme"
    help = "Create or update plan-level README entry"
    role = "tw"

    @classmethod
    def add_arguments(cls, p: argparse.ArgumentParser) -> None:
        p.add_argument("--path", required=True, help="Directory path for README.md")
        p.add_argument("--content-file", required=True, help="Path to content file")

    @classmethod
    def run(cls, args: argparse.Namespace) -> None:
        state_dir = get_state_dir()
        plan = load_plan(state_dir)

        content_path = Path(args.content_file)
        if not content_path.exists():
            error_exit(f"Content file not found: {args.content_file}")

        content = content_path.read_text().strip()

        # Upsert: one README per directory path
        for i, entry in enumerate(plan.readme_entries):
            if entry.path == args.path:
                plan.readme_entries[i] = ReadmeEntry(path=args.path, content=content)
                save_plan(state_dir, plan)
                success(f"Updated README for {args.path}")
                return

        plan.readme_entries.append(ReadmeEntry(path=args.path, content=content))
        save_plan(state_dir, plan)
        success(f"Created README for {args.path}")


class SetDiagramRenderCommand(Command):
    name = "set-diagram-render"
    help = "Set ASCII render for diagram"
    role = "tw"

    @classmethod
    def add_arguments(cls, p: argparse.ArgumentParser) -> None:
        p.add_argument("--diagram", required=True, help="Diagram ID")
        p.add_argument("--content-file", required=True, help="Path to ASCII content")

    @classmethod
    def run(cls, args: argparse.Namespace) -> None:
        state_dir = get_state_dir()
        plan = load_plan(state_dir)

        dg = next((d for d in plan.diagram_graphs if d.id == args.diagram), None)
        if not dg:
            error_exit(f"Diagram {args.diagram} not found")

        content_path = Path(args.content_file)
        if not content_path.exists():
            error_exit(f"Content file not found: {args.content_file}")

        try:
            dg.ascii_render = content_path.read_text()
        except Exception as e:
            error_exit(f"Failed to read render for diagram {args.diagram}: {e}")

        save_plan(state_dir, plan)
        success(f"Set ASCII render for {args.diagram}")


class SetDocDiffCommand(Command):
    name = "set-doc-diff"
    help = "Set documentation diff for a code change"
    role = "tw"

    @classmethod
    def add_arguments(cls, p: argparse.ArgumentParser) -> None:
        p.add_argument("--change", required=True, help="CodeChange ID (CC-M-XXX-YYY)")
        p.add_argument("--version", type=int, required=True, help="Current version for CAS")
        p.add_argument("--content-file", required=True, help="Path to unified diff file")

    @classmethod
    def run(cls, args: argparse.Namespace) -> None:
        state_dir = get_state_dir()
        plan = load_plan(state_dir)

        _, cc = plan.get_change(args.change)
        if not cc:
            all_changes = [c.id for m in plan.milestones for c in m.code_changes]
            validation_error("change", "Valid change ID", args.change,
                           f"Valid: {', '.join(all_changes) or 'none'}")

        try:
            check_version(cc, args.version, args.change)
        except VersionMismatchError as e:
            exit_with_version_error(e)
            return

        content_path = Path(args.content_file)
        if not content_path.exists():
            error_exit(f"Content file not found: {args.content_file}")

        cc.doc_diff = content_path.read_text()
        bump_version(cc)
        save_plan(state_dir, plan)
        print_entity_result(EntityResult(id=cc.id, version=cc.version, operation="updated"))


class CreateDocChangeCommand(Command):
    name = "create-doc-change"
    help = "Create documentation-only change (README, comments to existing file)"
    role = "tw"

    @classmethod
    def add_arguments(cls, p: argparse.ArgumentParser) -> None:
        p.add_argument("--milestone", required=True, help="Parent milestone ID")
        p.add_argument("--file", required=True, help="File path (e.g., path/README.md)")
        p.add_argument("--content-file", required=True, help="Path to unified diff file")

    @classmethod
    def run(cls, args: argparse.Namespace) -> None:
        state_dir = get_state_dir()
        plan = load_plan(state_dir)

        ms = plan.get_milestone(args.milestone)
        if not ms:
            ids = [m.id for m in plan.milestones]
            validation_error("milestone", "Valid milestone ID", args.milestone,
                           f"Valid: {', '.join(ids) or 'none'}")

        content_path = Path(args.content_file)
        if not content_path.exists():
            error_exit(f"Content file not found: {args.content_file}")

        num = len(ms.code_changes) + 1
        ccid = f"CC-{ms.id}-{num:03d}"

        cc = CodeChange(
            id=ccid,
            version=1,
            intent_ref=None,  # Doc-only, no intent
            file=args.file,
            diff="",  # Empty - doc only
            doc_diff=content_path.read_text(),
            comments="",
        )
        ms.code_changes.append(cc)
        save_plan(state_dir, plan)
        print_entity_result(EntityResult(id=ccid, version=1, operation="created"))


# =============================================================================
# Commands: Translate
# =============================================================================



def translate_to_markdown(plan: "Plan") -> str:
    """Generate Markdown from plan.json."""
    lines = []

    # Overview
    lines.append("# Plan")
    lines.append("")
    lines.append("## Overview")
    lines.append("")
    lines.append(plan.overview.problem)
    lines.append("")
    if plan.overview.approach:
        lines.append(f"**Approach**: {plan.overview.approach}")
        lines.append("")

    overview_diagrams = [d for d in plan.diagram_graphs if d.scope == "overview"]
    for dg in overview_diagrams:
        lines.append(f"### {dg.title}")
        lines.append("")
        if dg.ascii_render:
            lines.append("```")
            lines.append(dg.ascii_render)
            lines.append("```")
        else:
            lines.append(f"[Diagram pending Technical Writer rendering: {dg.id}]")
        lines.append("")

    # Planning Context
    if plan.planning_context.decisions:
        lines.append("## Planning Context")
        lines.append("")
        lines.append("### Decision Log")
        lines.append("")
        lines.append("| ID | Decision | Reasoning Chain |")
        lines.append("|---|---|---|")
        for dl in plan.planning_context.decisions:
            lines.append(f"| {dl.id} | {dl.decision} | {dl.reasoning} |")
        lines.append("")

    if plan.planning_context.rejected_alternatives:
        lines.append("### Rejected Alternatives")
        lines.append("")
        lines.append("| Alternative | Why Rejected |")
        lines.append("|---|---|")
        for ra in plan.planning_context.rejected_alternatives:
            lines.append(f"| {ra.alternative} | {ra.rejection_reason} (ref: {ra.decision_ref}) |")
        lines.append("")

    if plan.planning_context.constraints:
        lines.append("### Constraints")
        lines.append("")
        for c in plan.planning_context.constraints:
            lines.append(f"- {c}")
        lines.append("")

    if plan.planning_context.risks:
        lines.append("### Known Risks")
        lines.append("")
        for r in plan.planning_context.risks:
            lines.append(f"- **{r.risk}**: {r.mitigation}")
        lines.append("")

    # Invisible Knowledge
    ik = plan.invisible_knowledge
    if ik.system or ik.invariants or ik.tradeoffs:
        lines.append("## Invisible Knowledge")
        lines.append("")

        if ik.system:
            lines.append("### System")
            lines.append("")
            lines.append(ik.system)
            lines.append("")

        if ik.invariants:
            lines.append("### Invariants")
            lines.append("")
            for inv in ik.invariants:
                lines.append(f"- {inv}")
            lines.append("")

        if ik.tradeoffs:
            lines.append("### Tradeoffs")
            lines.append("")
            for t in ik.tradeoffs:
                lines.append(f"- {t}")
            lines.append("")

        ik_diagrams = [d for d in plan.diagram_graphs if d.scope == "invisible_knowledge"]
        for dg in ik_diagrams:
            lines.append(f"### {dg.title}")
            lines.append("")
            if dg.ascii_render:
                lines.append("```")
                lines.append(dg.ascii_render)
                lines.append("```")
            else:
                lines.append(f"[Diagram pending Technical Writer rendering: {dg.id}]")
            lines.append("")

    # Milestones
    lines.append("## Milestones")
    lines.append("")

    for ms in plan.milestones:
        lines.append(f"### Milestone {ms.number}: {ms.name}")
        lines.append("")

        ms_diagrams = [d for d in plan.diagram_graphs if d.scope == f"milestone:{ms.id}"]
        for dg in ms_diagrams:
            lines.append(f"**{dg.title}**")
            lines.append("")
            if dg.ascii_render:
                lines.append("```")
                lines.append(dg.ascii_render)
                lines.append("```")
            else:
                lines.append(f"[Diagram pending Technical Writer rendering: {dg.id}]")
            lines.append("")

        if ms.files:
            lines.append(f"**Files**: {', '.join(ms.files)}")
            lines.append("")

        if ms.flags:
            lines.append(f"**Flags**: {', '.join(ms.flags)}")
            lines.append("")

        if ms.requirements:
            lines.append("**Requirements**:")
            lines.append("")
            for req in ms.requirements:
                lines.append(f"- {req}")
            lines.append("")

        if ms.acceptance_criteria:
            lines.append("**Acceptance Criteria**:")
            lines.append("")
            for ac in ms.acceptance_criteria:
                lines.append(f"- {ac}")
            lines.append("")

        if ms.tests:
            lines.append("**Tests**:")
            lines.append("")
            for t in ms.tests:
                lines.append(f"- {t}")
            lines.append("")

        # Code Intent
        if ms.code_intents:
            lines.append("#### Code Intent")
            lines.append("")
            for ci in ms.code_intents:
                func_str = f"::{ci.function}" if ci.function else ""
                refs_str = f" (refs: {', '.join(ci.decision_refs)})" if ci.decision_refs else ""
                lines.append(f"- **{ci.id}** `{ci.file}{func_str}`: {ci.behavior}{refs_str}")
            lines.append("")

        # Code Changes
        if ms.code_changes:
            lines.append("#### Code Changes")
            lines.append("")
            for cc in ms.code_changes:
                ref_str = f" - implements {cc.intent_ref}" if cc.intent_ref else ""
                lines.append(f"**{cc.id}** ({cc.file}){ref_str}")
                lines.append("")

                # Code diff (may be empty for doc-only changes)
                if cc.diff:
                    lines.append("**Code:**")
                    lines.append("")
                    lines.append("```diff")
                    lines.append(cc.diff)
                    lines.append("```")
                    lines.append("")

                # Documentation diff
                if cc.doc_diff:
                    lines.append("**Documentation:**")
                    lines.append("")
                    lines.append("```diff")
                    lines.append(cc.doc_diff)
                    lines.append("```")
                    lines.append("")
                elif cc.diff:
                    lines.append("*[Documentation pending TW]*")
                    lines.append("")

                if cc.comments:
                    lines.append(f"> **Developer notes**: {cc.comments}")
                lines.append("")

        # Documentation
        doc = ms.documentation
        if doc.module_comment or doc.docstrings or doc.function_blocks or doc.inline_comments:
            lines.append("#### Documentation")
            lines.append("")
            if doc.module_comment:
                lines.append("**Module Comment**:")
                lines.append("")
                lines.append(doc.module_comment)
                lines.append("")
            for ds in doc.docstrings:
                lines.append(f"**{ds.function}**:")
                lines.append("")
                lines.append("```")
                lines.append(ds.docstring)
                lines.append("```")
                lines.append("")
            if doc.function_blocks:
                lines.append("**Function Blocks**:")
                lines.append("")
                for fb in doc.function_blocks:
                    ref_str = f" (ref: {fb.decision_ref})" if fb.decision_ref else ""
                    lines.append(f"- `{fb.function}`{ref_str}: {fb.comment}")
                lines.append("")
            if doc.inline_comments:
                lines.append("**Inline Comments**:")
                lines.append("")
                for ic in doc.inline_comments:
                    ref_str = f" (ref: {ic.decision_ref})" if ic.decision_ref else ""
                    lines.append(f"- `{ic.location}`{ref_str}: {ic.comment}")
                lines.append("")

    # README Entries
    if plan.readme_entries:
        lines.append("## README Entries")
        lines.append("")
        for entry in plan.readme_entries:
            lines.append(f"### {entry.path}/README.md")
            lines.append("")
            lines.append(entry.content)
            lines.append("")

    # Waves
    if plan.waves:
        lines.append("## Execution Waves")
        lines.append("")
        for w in plan.waves:
            lines.append(f"- {w.id}: {', '.join(w.milestones)}")
        lines.append("")

    return "\n".join(lines)


# =============================================================================
# Commands: QR Phase (validate)
# =============================================================================


class ValidateCommand(Command):
    name = "validate"
    help = "Validate plan.json for a specific phase"
    role = "qr"

    @classmethod
    def add_arguments(cls, p: argparse.ArgumentParser) -> None:
        p.add_argument("--phase", required=True, choices=["plan-design", "plan-code", "plan-docs"],
                      help="Phase to validate")

    @classmethod
    def run(cls, args: argparse.Namespace) -> None:
        state_dir = get_state_dir()
        plan = load_plan(state_dir)

        errors = []

        # Reference validation (all phases)
        errors.extend(plan.validate_refs())

        # Phase-specific completeness
        errors.extend(plan.validate_completeness(args.phase))

        if errors:
            print("<validation_errors>")
            for err in errors:
                print(f"  <error>{err}</error>")
            print("</validation_errors>")
            sys.exit(1)
        else:
            success(f"Validation passed for phase {args.phase}")


class ValidatePlanningContextCommand(Command):
    name = "validate-planning-context"
    help = "F6: validate planning_context shape with self-correctable errors"
    role = None

    @classmethod
    def add_arguments(cls, p: argparse.ArgumentParser) -> None:
        pass

    @classmethod
    def run(cls, args: argparse.Namespace) -> None:
        # Read RAW plan.json (not load_plan) so a malformed planning_context
        # yields friendly, targeted errors instead of a pydantic traceback --
        # this is the whole point of F6: catch shape drift in the architect
        # step and feed it back for self-correction.
        import json
        from ..shared.schema import validate_planning_context

        state_dir = get_state_dir()
        plan_raw = json.loads(get_plan_path(state_dir).read_text())
        errors = validate_planning_context(plan_raw.get("planning_context", {}))

        if errors:
            print("<planning_context_errors>")
            for err in errors:
                print(f"  <error>{err}</error>")
            print("</planning_context_errors>")
            sys.exit(1)
        success("planning_context shape is valid")


class TemporalScanCommand(Command):
    name = "temporal-scan"
    help = "Deterministic temporal-contamination scan over the doc/comment surface"
    role = None

    @classmethod
    def add_arguments(cls, p: argparse.ArgumentParser) -> None:
        pass

    @classmethod
    def run(cls, args: argparse.Namespace) -> None:
        # F2 post-fix gate: read raw plan.json (not the pydantic model) so the
        # scan stays robust to deprecated/loose doc fields, then drive the
        # whole temporal class to zero hits. Exit 1 on any hit so the fixer
        # cannot report PASS while siblings of a named finding remain.
        import json
        from ..shared.temporal_detection import scan_plan_docs, format_scan_report

        state_dir = get_state_dir()
        plan_raw = json.loads(get_plan_path(state_dir).read_text())
        hits = scan_plan_docs(plan_raw)

        print(format_scan_report(hits))
        if hits:
            sys.exit(1)


# =============================================================================
# Commands: List Helpers (read-only, no role restriction)
# =============================================================================


class ListMilestonesCommand(Command):
    name = "list-milestones"
    help = "List all milestones"
    role = None

    @classmethod
    def add_arguments(cls, p: argparse.ArgumentParser) -> None:
        pass

    @classmethod
    def run(cls, args: argparse.Namespace) -> None:
        state_dir = get_state_dir()
        plan = load_plan(state_dir)
        for ms in plan.milestones:
            print(f"{ms.id}\tv{ms.version}\t{ms.name}")


class ListIntentsCommand(Command):
    name = "list-intents"
    help = "List intents in milestone"
    role = None

    @classmethod
    def add_arguments(cls, p: argparse.ArgumentParser) -> None:
        p.add_argument("milestone_id", help="Milestone ID")

    @classmethod
    def run(cls, args: argparse.Namespace) -> None:
        state_dir = get_state_dir()
        plan = load_plan(state_dir)

        ms = plan.get_milestone(args.milestone_id)
        if not ms:
            ids = [m.id for m in plan.milestones]
            error_exit(f"Milestone {args.milestone_id} not found. Valid IDs: {', '.join(ids)}")

        for ci in ms.code_intents:
            print(f"{ci.id}\tv{ci.version}\t{ci.file}\t{ci.behavior[:50]}...")


class ListChangesCommand(Command):
    name = "list-changes"
    help = "List changes in milestone"
    role = None

    @classmethod
    def add_arguments(cls, p: argparse.ArgumentParser) -> None:
        p.add_argument("milestone_id", help="Milestone ID")

    @classmethod
    def run(cls, args: argparse.Namespace) -> None:
        state_dir = get_state_dir()
        plan = load_plan(state_dir)

        ms = plan.get_milestone(args.milestone_id)
        if not ms:
            ids = [m.id for m in plan.milestones]
            error_exit(f"Milestone {args.milestone_id} not found. Valid IDs: {', '.join(ids)}")

        for cc in ms.code_changes:
            print(f"{cc.id}\tv{cc.version}\t{cc.intent_ref}\t{cc.file}")


class ListDecisionsCommand(Command):
    name = "list-decisions"
    help = "List all decisions"
    role = None

    @classmethod
    def add_arguments(cls, p: argparse.ArgumentParser) -> None:
        pass

    @classmethod
    def run(cls, args: argparse.Namespace) -> None:
        state_dir = get_state_dir()
        plan = load_plan(state_dir)

        for dl in plan.planning_context.decisions:
            print(f"{dl.id}\tv{dl.version}\t{dl.decision[:50]}...")


# =============================================================================
# Command Registry
# =============================================================================


COMMANDS: list[type[Command]] = [
    InitCommand,
    SetMilestoneCommand,
    SetIntentCommand,
    SetDecisionCommand,
    SetDiagramCommand,
    AddDiagramNodeCommand,
    AddDiagramEdgeCommand,
    SetChangeCommand,
    SetDocCommand,
    SetReadmeCommand,
    SetDiagramRenderCommand,
    SetDocDiffCommand,
    CreateDocChangeCommand,
    ValidateCommand,
    ValidatePlanningContextCommand,
    TemporalScanCommand,
    ListMilestonesCommand,
    ListIntentsCommand,
    ListChangesCommand,
    ListDecisionsCommand,
]


# =============================================================================
# CLI Entry Point
# =============================================================================


def build_parser() -> argparse.ArgumentParser:
    """Build parser by iterating over command registry."""
    parser = argparse.ArgumentParser(
        prog="python3 -m skills.planner.cli.plan",
        description="CLI for plan.json manipulation with CAS versioning"
    )
    parser.add_argument("--state-dir", required=True, help="State directory containing plan.json")

    subparsers = parser.add_subparsers(dest="command", required=True)

    for cmd_class in COMMANDS:
        p = subparsers.add_parser(cmd_class.name, help=cmd_class.help)
        cmd_class.add_arguments(p)

    # Batch RPC subcommand
    batch_p = subparsers.add_parser("batch", help="Execute batch of RPC commands")
    batch_p.add_argument("input", nargs="?", help="JSON array of requests (stdin if omitted)")

    # List methods subcommand
    subparsers.add_parser("list-methods", help="List available RPC methods")

    return parser


def cli(args: list[str] = None):
    """Main CLI entrypoint."""
    if not PYDANTIC_AVAILABLE:
        error_exit("pydantic v2 required. Install with: pip install pydantic>=2.0")

    parser = build_parser()
    parsed = parser.parse_args(args)

    set_state_dir(parsed.state_dir)

    # Handle batch command
    if parsed.command == "batch":
        methods = discover_methods(plan_commands)
        ctx = plan_commands.PlanContext(state_dir=Path(parsed.state_dir))

        if hasattr(parsed, 'input') and parsed.input:
            requests = json.loads(parsed.input)
        else:
            requests = json.load(sys.stdin)

        results = batch_dispatch(methods, requests, ctx)
        print(json.dumps(results, indent=2))
        return

    # Handle list-methods command
    if parsed.command == "list-methods":
        methods = discover_methods(plan_commands)
        print(json.dumps(list_methods(methods), indent=2))
        return

    # Find command class by name
    cmd_class = next(c for c in COMMANDS if c.name == parsed.command)

    # Check role permission
    if cmd_class.role:
        role_err = check_role(cmd_class.name)
        if role_err:
            error_exit(role_err)

    cmd_class.run(parsed)


def main():
    cli()


if __name__ == "__main__":
    main()
