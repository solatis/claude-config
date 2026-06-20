"""Resource management for planner scripts.

Handles loading of resource files and path resolution.
"""

from pathlib import Path

import json

from skills.lib.io import read_text_or_exit


"""State directory argument configuration.

WHY: The state_dir requirement was split between CLI declaration
(said "optional") and runtime validation (enforced "required").
The actual contract: required for all steps except step 1 (init).

This docstring documents the contract. Runtime validation references
this documentation rather than reimplementing the logic.
"""

# Contract: state_dir is REQUIRED for steps 2+ (init creates it)
# Step 1: Creates state_dir (not required as input)
# Steps 2+: Requires state_dir (passed from step 1)
# QR retry mode: Detected via qr-{phase}.json file inspection

# WHY STATE_DIR_ARG_REQUIRED instead of CONTEXT_FILE_ARG_REQUIRED:
# Convention over configuration. If state_dir is known, all other paths are deterministic.
# This matches the pattern: component that READS a file owns its location convention.
# Single source of truth for path derivation prevents drift across 3 sub-agent scripts.
STATE_DIR_ARG_REQUIRED = (
    ['--state-dir'],
    {'type': str, 'required': True, 'help': 'Path to state directory (REQUIRED)'}
)


def validate_state_dir_requirement(step: int, state_dir: str | None) -> None:
    """Validate state_dir based on step.

    Raises ValueError if state_dir is required but missing.

    WHY step 1 doesn't require state_dir:
    - Step 1 (init) CREATES the state directory
    - Requiring it as input would be circular dependency
    - User invokes: /plan -> step 1 creates ~/.claude/plans/xyz/ -> passes to step 2

    WHY steps 2+ require state_dir:
    - All workflow state persists in this directory (qa_state.json, plan.md, etc.)
    - Without it, steps can't read previous work or write outputs
    - Orchestrator passes state_dir between steps via invoke_after

    WHAT BREAKS if validation changes:
    - Remove step > 1 check -> Step 1 fails spuriously (no state_dir exists yet)
    - Change to warning -> Steps silently fail later with cryptic IOErrors
    """
    if step > 1 and not state_dir:
        raise ValueError(
            f"--state-dir required for step {step}. "
            "Step 1 creates the state directory; subsequent steps require it."
        )

def get_context_path(state_dir: str) -> Path:
    """Derive context.json path from state directory.

    WHY this function: Centralizes path derivation convention. If context.json location
    changes (e.g., moves to state_dir/inputs/context.json), only this function needs updating.
    Sub-agents call this instead of manually constructing Path(state_dir) / "context.json".
    """
    return Path(state_dir) / "context.json"


def default_state_root() -> Path:
    """Persistent root for planner state directories (never /tmp).

    The planner is deployed at <project>/.claude/skills/scripts/...; state
    belongs at <project>/.claude/planner-state/ -- persistent across session
    restarts and git-ignored. Walks up from this file to the nearest `.claude`
    ancestor; falls back to <cwd>/.claude/planner-state when none exists
    (standalone dev checkout).

    WHY persistent (not tempfile.mkdtemp in /tmp): a session-limit restart
    wipes /tmp, destroying an in-progress plan one step before the final
    write. This is F1 in PLANNER-HARNESS-FIX-ROADMAP.md -- it cost an entire
    completed plan on the first real run.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        if parent.name == ".claude" and parent.is_dir():
            return parent / "planner-state"
    return Path.cwd() / ".claude" / "planner-state"


def create_state_dir(explicit: str | None) -> str:
    """Resolve the state directory for step 1 (init).

    If `explicit` is given (--state-dir), honor it verbatim (creating it if
    needed) so a killed run can be resumed against the SAME directory with
    zero loss. Otherwise mint a fresh persistent directory under
    default_state_root().

    WHY step 1 honors --state-dir (it previously self-generated /tmp and
    ignored the flag): resumability. The orchestrator -- or a human after a
    restart -- can re-run step 1 against an existing dir to recover state
    instead of starting over. F1 in PLANNER-HARNESS-FIX-ROADMAP.md.
    """
    import tempfile

    if explicit:
        path = Path(explicit).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        return str(path)
    root = default_state_root()
    root.mkdir(parents=True, exist_ok=True)
    return tempfile.mkdtemp(prefix="planner-", dir=str(root))

# WHY explicit __all__ update: resources.py uses __all__ (lines 23-32) to enforce
# public API contract. STATE_DIR_ARG_REQUIRED and get_context_path must be listed
# because sub-agent scripts import them directly. Implicit exports would work but
# explicit __all__ makes interface contract clear -- only listed symbols are public.
__all__ = [
    "get_resource",
    "get_mode_script_path",
    "get_exhaustiveness_prompt",
    "get_qa_schema",
    "load_context_block",
    "STATE_DIR_ARG_REQUIRED",
    "get_context_path",
    "default_state_root",
    "create_state_dir",
    "render_context_file",
    "PlannerResourceProvider",
    "validate_state_dir_requirement",
]


# =============================================================================
# Resource Provider Implementation
# =============================================================================


class PlannerResourceProvider:
    """ResourceProvider implementation for planner workflows.

    Provides access to conventions and step guidance.
    """

    def get_resource(self, name: str) -> str:
        """Retrieve resource content from conventions directory.

        Implements ResourceProvider protocol for planner workflows.
        Maps resource name to file in CONVENTIONS_DIR.
        """
        resource_path = Path(__file__).resolve().parents[4] / "planner" / "resources" / name
        try:
            return read_text_or_exit(resource_path, "loading planner resource")
        except SystemExit:
            raise FileNotFoundError(f"Resource not found: {name}")

    def get_step_guidance(self, **kwargs) -> dict:
        """Get step-specific guidance (placeholder for forward compatibility).

        Returns empty dict until per-step guidance requirements emerge.
        Decision Log (get_step_guidance placeholder) explains deferral rationale.
        """
        return {}


# =============================================================================
# Resource Loading
# =============================================================================


def get_resource(name: str) -> str:
    """Read resource file from planner resources directory.

    Resources are authoritative sources for specifications that agents need.
    Scripts inject these at runtime so agents don't need embedded copies.

    Args:
        name: Resource filename (e.g., "plan-format.md")

    Returns:
        Full content of the resource file

    Exits:
        With contextual error message if resource doesn't exist
    """
    # shared -> planner -> skills -> scripts -> skills -> planner/resources
    resource_path = Path(__file__).resolve().parents[4] / "planner" / "resources" / name
    return read_text_or_exit(resource_path, "loading planner resource")


def get_mode_script_path(script_name: str) -> str:
    """Get module path for -m invocation.

    Mode scripts provide step-based workflows for sub-agents.
    Scripts are organized by agent: qr/, dev/, tw/

    Args:
        script_name: Script path relative to planner/ (e.g., "qr/plan-docs.py")

    Returns:
        Module path for python3 -m (e.g., "skills.planner.qr.plan_docs")
    """
    # Convert path to module: "qr/plan-docs.py" -> "qr.plan_docs"
    module = script_name.replace("/", ".").replace("-", "_").removesuffix(".py")
    return f"skills.planner.{module}"


def get_exhaustiveness_prompt() -> list[str]:
    """Return exhaustiveness verification prompt for QR steps.

    Research shows models satisfice (stop after finding "enough" issues)
    unless explicitly prompted to find more. This prompt counters that
    tendency by forcing adversarial self-examination.

    Returns:
        List of prompt lines for exhaustiveness verification
    """
    return [
        "<exhaustiveness_check>",
        "STOP. Before reporting your findings, perform adversarial self-examination:",
        "",
        "1. What categories of issues have you NOT yet checked?",
        "2. What assumptions are you making that could hide problems?",
        "3. Re-read each milestone -- what could go wrong that you missed?",
        "4. What would a hostile reviewer find that you overlooked?",
        "",
        "List any additional issues discovered. Only report PASS if this",
        "second examination finds nothing new.",
        "</exhaustiveness_check>",
    ]


def get_qa_schema() -> str:
    """Return QA state schema documentation.

    QA state tracks verification tasks across decomposition iterations.
    Schema defines structure for qa.yaml state file.

    Returns:
        Full content of qa-schema.md resource
    """
    return get_resource("qa-schema.md")


def load_context_block(context_file: str | None) -> list[str]:
    """Load planning context from JSON file and return as action lines.

    Returns list[str] instead of structured type because sub-agent consumes
    context as prompt text (action lines), not as data structure for branching.
    Simpler contract: helpers produce action blocks, workflow engine assembles.

    Silently swallows errors (graceful fallback rationale): missing context.json
    means orchestrator skipped step 2 or user invoked sub-agent standalone for
    testing. Sub-agent should function without context (degraded mode) rather
    than crash. Empty context block = no additional context, proceed with task.

    Args:
        context_file: Path to context.json, or None

    Returns:
        List of action lines with context wrapped in XML, or empty list
    """
    if not context_file:
        return []
    try:
        context = json.loads(Path(context_file).read_text())
        # Context prepended to actions (not separate block) to ensure LLM reads
        # context BEFORE task instructions. Prompt order = attention priority.
        # XML tags allow sub-agent to distinguish context from instructions.
        return [
            "<planning_context>",
            # indent=2 balances human readability (debuggability) with token
            # efficiency. Single-line JSON would save ~50 tokens but makes
            # step-through debugging painful. Indent=4 wastes tokens for
            # marginal readability gain. indent=2 is the Goldilocks zone.
            json.dumps(context, indent=2),
            "</planning_context>",
            "",
        ]
    except (FileNotFoundError, json.JSONDecodeError):
        return []  # Graceful fallback


def render_context_file(context_file: str) -> str:
    """Load and format context.json for sub-agent consumption.

    WHY logical name: LLM sees "context.json" (semantic) not
    "/tmp/planner_xyz/context.json" (implementation detail).
    """
    from skills.lib.workflow.prompts import format_file_content

    try:
        content = Path(context_file).read_text()
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Context file not found: {context_file}. "
            "Orchestrator must create context.json before sub-agent dispatch."
        )
    return format_file_content("context.json", content)


