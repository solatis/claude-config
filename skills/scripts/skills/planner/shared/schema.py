"""Schema definitions and validation for planner state files.

Authoritative source for: context.json, plan.json, qr-{phase}.json schemas.
Pydantic is optional -- validation degrades gracefully if unavailable.
"""
import sys
import json
from pathlib import Path
from typing import TYPE_CHECKING

# QR item defaults for defensive access when reading malformed data
QA_ITEM_DEFAULTS = {
    "id": "unknown",
    "scope": "*",
    "check": "",
    "status": "TODO",
    "version": 1,
    "finding": None,
    "parent_id": None,
    "group_id": None,
    "severity": "SHOULD",  # Default for backwards compat with existing qr-{phase}.json files
}

# Canonical field names for QR items
QA_ITEM_REQUIRED_FIELDS = frozenset({"id", "scope", "check", "status", "version"})
QA_ITEM_OPTIONAL_FIELDS = frozenset({"finding", "parent_id", "group_id", "severity"})
QA_ITEM_ALL_FIELDS = QA_ITEM_REQUIRED_FIELDS | QA_ITEM_OPTIONAL_FIELDS

# Valid severity values (per conventions/severity.md)
VALID_SEVERITIES = frozenset({"MUST", "SHOULD", "COULD"})

PYDANTIC_AVAILABLE = False

if TYPE_CHECKING:
    from pydantic import BaseModel, Field
    from typing import Literal

try:
    from pydantic import BaseModel, Field, ValidationError
    from typing import Literal
    PYDANTIC_AVAILABLE = True
except ImportError:
    # Graceful degradation: validation functions return empty error lists
    print("warning: pydantic not installed, schema validation disabled", file=sys.stderr)


# =============================================================================
# Context Schema (context.json)
# =============================================================================

if PYDANTIC_AVAILABLE:
    class Context(BaseModel):
        """Context captured in step 2 for sub-agent handover.

        Schema per INTENT.md lines 23-35. All fields are string arrays.
        Empty arrays acceptable; omitting fields is not.
        """
        task_spec: list[str]
        constraints: list[str]
        entry_points: list[str]
        rejected_alternatives: list[str]
        current_understanding: list[str]
        assumptions: list[str]
        invisible_knowledge: list[str]
        reference_docs: list[str]


# =============================================================================
# Plan Schema (plan.json)
# =============================================================================

if PYDANTIC_AVAILABLE:
    class Decision(BaseModel):
        """Architectural or design decision with CAS versioning."""
        id: str  # DL-001 format
        version: int = 1  # CAS optimistic locking: increment on update
        decision: str
        reasoning: str = Field(alias="reasoning_chain")  # premise -> implication -> conclusion

        class Config:
            populate_by_name = True

    class RejectedAlternative(BaseModel):
        """Alternative considered but rejected.

        id required by validate_refs() for error message clarity.
        """
        id: str
        alternative: str
        rejection_reason: str
        decision_ref: str  # DL-XXX cross-reference

    class Risk(BaseModel):
        """Identified risk with mitigation.

        id required by validate_refs() for error message clarity.
        """
        id: str
        risk: str
        mitigation: str
        anchor: str | None = None  # file:L###-L### line anchor
        decision_ref: str | None = None  # Optional DL-XXX cross-reference

    class PlanningContext(BaseModel):
        """Planning context container."""
        decisions: list[Decision] = Field(default_factory=list, alias="decision_log")
        rejected_alternatives: list[RejectedAlternative] = Field(default_factory=list)
        constraints: list[str] = Field(default_factory=list)  # INTENT.md line 67: string[]
        risks: list[Risk] = Field(default_factory=list, alias="known_risks")

        class Config:
            populate_by_name = True

    class InvisibleKnowledge(BaseModel):
        """Knowledge for future LLM sessions."""
        system: str = ""
        invariants: list[str] = Field(default_factory=list)
        tradeoffs: list[str] = Field(default_factory=list)

    class DiagramNode(BaseModel):
        """Node in a diagram graph."""
        id: str
        label: str
        type: str | None = None

    class DiagramEdge(BaseModel):
        """Edge connecting two nodes."""
        source: str
        target: str
        label: str
        protocol: str | None = None

    class DiagramGraph(BaseModel):
        """Architecture diagram as graph IR with optional ASCII render."""
        id: str
        type: Literal["architecture", "state", "sequence", "dataflow"]
        scope: str
        title: str
        nodes: list[DiagramNode] = Field(default_factory=list)
        edges: list[DiagramEdge] = Field(default_factory=list)
        ascii_render: str | None = None

    class CodeIntent(BaseModel):
        """Behavioral description for Developer to implement."""
        id: str  # CI-001 format
        version: int = 1  # CAS optimistic locking: increment on update
        file: str
        function: str | None = None
        behavior: str
        decision_refs: list[str] = Field(default_factory=list)  # DL-XXX cross-references

    class CodeChange(BaseModel):
        """Concrete code change implementing an intent."""
        id: str  # CC-M-001-001 format
        version: int = 1  # CAS optimistic locking: increment on update
        intent_ref: str | None = None  # CI-XXX or null for doc-only changes (READMEs)
        file: str
        diff: str = ""  # Code changes - Developer fills (empty for doc-only)
        # F4: snippet source of truth. When provided, `diff` is tool-computed
        # from these via difflib (the LLM never hand-authors @@ headers).
        old_snippet: str = ""  # Exact current text to replace ("" for insertion)
        new_snippet: str = ""  # Replacement text
        doc_diff: str = ""  # Documentation overlay - TW fills
        comments: str = ""  # WHY comments explaining the change

    class Docstring(BaseModel):
        """Function docstring spec."""
        function: str
        docstring: str

    class FunctionBlock(BaseModel):
        """Function-level explanation block (Tier 2).

        Covers design rationale, architecture context, system interaction
        -- not just algorithms. Convention: documentation.md Tier 2.
        """
        function: str  # function name
        comment: str
        decision_ref: str | None = None
        source: str | None = None  # invisible_knowledge provenance for QR completeness checks

    class InlineComment(BaseModel):
        """Inline WHY comment (Tier 1)."""
        location: str  # function:line format
        comment: str
        decision_ref: str | None = None  # Optional DL-XXX cross-reference
        source: str | None = None

    class Documentation(BaseModel):
        """Documentation enrichment for a milestone.

        DEPRECATED: Use CodeChange.doc_diff instead. This metadata approach
        disconnects documentation from code locations. Kept for backwards
        compatibility with existing plans.
        """
        module_comment: str | None = None
        docstrings: list[Docstring] = Field(default_factory=list)
        function_blocks: list[FunctionBlock] = Field(default_factory=list)
        inline_comments: list[InlineComment] = Field(default_factory=list)

    class ReadmeEntry(BaseModel):
        """Cross-cutting README content for a directory.

        DEPRECATED: Use CodeChange with empty diff and doc_diff for README.
        Kept for backwards compatibility with existing plans.
        """
        path: str  # directory path for README.md
        content: str

    class Milestone(BaseModel):
        """Single implementation milestone."""
        id: str  # M-001 format
        version: int = 1  # CAS optimistic locking: increment on update
        number: int
        name: str
        files: list[str]
        flags: list[str] = Field(default_factory=list)
        requirements: list[str] = Field(default_factory=list)
        acceptance_criteria: list[str] = Field(default_factory=list)
        tests: list[str] = Field(default_factory=list)  # Free-form test descriptions
        code_intents: list[CodeIntent] = Field(default_factory=list)
        code_changes: list[CodeChange] = Field(default_factory=list)
        documentation: Documentation = Field(default_factory=Documentation)
        is_documentation_only: bool = False
        delegated_to: str | None = None  # Agent name for delegation tracking

    class Wave(BaseModel):
        """Execution wave grouping milestones."""
        id: str  # W-001 format
        milestones: list[str]  # M-XXX IDs for parallel execution

    class Overview(BaseModel):
        """Plan overview."""
        problem: str
        approach: str

    class Plan(BaseModel):
        """Root plan.json schema.

        No schema_version field: state files are ephemeral (single planning session).
        Schema versioning adds complexity without benefit for short-lived artifacts.
        """
        plan_id: str = Field(default_factory=lambda: str(__import__('uuid').uuid4()))
        created_at: str = Field(default_factory=lambda: __import__('datetime').datetime.utcnow().isoformat())
        frozen_at: str | None = None  # Timestamp when plan execution began

        overview: Overview
        planning_context: PlanningContext = Field(default_factory=PlanningContext)
        invisible_knowledge: InvisibleKnowledge = Field(default_factory=InvisibleKnowledge)
        milestones: list[Milestone] = Field(default_factory=list)
        waves: list[Wave] = Field(default_factory=list)
        diagram_graphs: list[DiagramGraph] = Field(default_factory=list)
        readme_entries: list[ReadmeEntry] = Field(default_factory=list)

        def get_milestone(self, mid: str) -> Milestone | None:
            for ms in self.milestones:
                if ms.id == mid:
                    return ms
            return None

        def get_intent(self, intent_id: str):
            for ms in self.milestones:
                for ci in ms.code_intents:
                    if ci.id == intent_id:
                        return ms, ci
            return None, None

        def get_decision(self, decision_id: str) -> Decision | None:
            for dl in self.planning_context.decisions:
                if dl.id == decision_id:
                    return dl
            return None

        def get_change(self, change_id: str):
            for ms in self.milestones:
                for cc in ms.code_changes:
                    if cc.id == change_id:
                        return ms, cc
            return None, None

        def validate_diagram_edges(self, diagram_id: str) -> list[str]:
            """Validate edges for a specific diagram."""
            errors = []
            dg = next((d for d in self.diagram_graphs if d.id == diagram_id), None)
            if not dg:
                return [f"diagram {diagram_id} not found"]
            node_ids = {n.id for n in dg.nodes}
            for edge in dg.edges:
                if edge.source not in node_ids:
                    errors.append(f"diagram {dg.id} edge source '{edge.source}' not in nodes")
                if edge.target not in node_ids:
                    errors.append(f"diagram {dg.id} edge target '{edge.target}' not in nodes")
            return errors

        def validate_refs(self) -> list[str]:
            """Validate cross-references between entities.

            Returns error list (empty = valid). Prevents dangling references
            that would break navigation/traceability.
            """
            errors = []
            decision_ids = {dl.id for dl in self.planning_context.decisions}

            for ms in self.milestones:
                intent_ids = {ci.id for ci in ms.code_intents}
                for cc in ms.code_changes:
                    if cc.intent_ref and cc.intent_ref not in intent_ids:
                        errors.append(
                            f"code_change.intent_ref '{cc.intent_ref}' not in "
                            f"milestone {ms.id} code_intents"
                        )
                for ci in ms.code_intents:
                    for dref in ci.decision_refs:
                        if dref not in decision_ids:
                            errors.append(f"{ci.id}.decision_refs '{dref}' not in decisions")
                for ic in ms.documentation.inline_comments:
                    if ic.decision_ref and ic.decision_ref not in decision_ids:
                        errors.append(
                            f"milestone {ms.id} inline_comment decision_ref "
                            f"'{ic.decision_ref}' not in decisions"
                        )
                for fb in ms.documentation.function_blocks:
                    if fb.decision_ref and fb.decision_ref not in decision_ids:
                        errors.append(
                            f"milestone {ms.id} function_block decision_ref "
                            f"'{fb.decision_ref}' not in decisions"
                        )

            for ra in self.planning_context.rejected_alternatives:
                if ra.decision_ref not in decision_ids:
                    errors.append(f"{ra.id}.decision_ref '{ra.decision_ref}' not in decisions")
            for kr in self.planning_context.risks:
                if kr.decision_ref and kr.decision_ref not in decision_ids:
                    errors.append(f"{kr.id}.decision_ref '{kr.decision_ref}' not in decisions")

            for dg in self.diagram_graphs:
                errors.extend(self.validate_diagram_edges(dg.id))
                valid_scopes = {"overview", "invisible_knowledge"}
                if dg.scope in valid_scopes:
                    pass
                elif dg.scope.startswith("milestone:"):
                    mid = dg.scope.split(":", 1)[1]
                    if not self.get_milestone(mid):
                        errors.append(f"diagram {dg.id} scope references unknown milestone '{mid}'")
                else:
                    errors.append(f"diagram {dg.id} has invalid scope '{dg.scope}' (must be 'overview', 'invisible_knowledge', or 'milestone:M-XXX')")

            return errors

        def validate_completeness(self, phase: str) -> list[str]:
            """Phase-specific completeness validation."""
            errors = []
            if phase == "plan-design":
                if not self.overview.problem:
                    errors.append("overview.problem required")
                if not self.milestones:
                    errors.append("at least one milestone required")
                for ms in self.milestones:
                    if not ms.code_intents:
                        errors.append(f"milestone {ms.id} needs at least one code_intent")
            elif phase == "plan-code":
                for ms in self.milestones:
                    intent_ids = {ci.id for ci in ms.code_intents}
                    change_refs = {cc.intent_ref for cc in ms.code_changes}
                    missing = intent_ids - change_refs
                    if missing:
                        errors.append(
                            f"milestone {ms.id} missing code_changes for: "
                            f"{', '.join(sorted(missing))}"
                        )
            elif phase == "plan-docs":
                for ms in self.milestones:
                    for cc in ms.code_changes:
                        # Every code_change with diff should have doc_diff
                        if cc.diff and not cc.doc_diff:
                            errors.append(
                                f"{cc.id}: has code diff but no doc_diff"
                            )
                        # doc_diff must be valid unified diff format if present
                        if cc.doc_diff and not cc.doc_diff.strip().startswith(('---', '@@', 'diff')):
                            errors.append(
                                f"{cc.id}: doc_diff must be valid unified diff format"
                            )
                        # At least one must be non-empty
                        if not cc.diff and not cc.doc_diff:
                            errors.append(
                                f"{cc.id}: must have diff or doc_diff (both empty)"
                            )
            return errors


# =============================================================================
# QR Schema (qr-{phase}.json)
# =============================================================================

if PYDANTIC_AVAILABLE:
    class QRItem(BaseModel):
        """Single QR verification item."""
        id: str
        scope: str
        check: str
        status: str = "TODO"
        version: int = 1
        finding: str | None = None
        parent_id: str | None = None
        group_id: str | None = None
        severity: Literal["MUST", "SHOULD", "COULD"] = "SHOULD"

    class QRFile(BaseModel):
        """qr-{phase}.json file structure."""
        phase: str
        iteration: int = 1
        items: list[QRItem] = Field(default_factory=list)


# =============================================================================
# QR Schema Helpers (moved from shared/qr/schema.py)
# =============================================================================

QA_ITEM_SCHEMA_TEMPLATE = '''{
  "id": "{id_example}",
  "scope": "*" or "file:path:lines",
  "check": "Description of what was checked",
  "status": "TODO",
  "version": 1,
  "finding": null
}'''


def get_qa_state_schema_example(phase: str, id_prefix: str = "qa") -> str:
    """Generate schema example for prompts."""
    return f'''{{
  "phase": "{phase}",
  "items": [
    {QA_ITEM_SCHEMA_TEMPLATE.format(id_example=f"{id_prefix}-001")}
  ]
}}'''


# =============================================================================
# Validation Functions
# =============================================================================

class SchemaValidationError(Exception):
    """Raised when state files fail schema validation."""
    pass


# Schema registry: filename -> (model_class, post_validate_fn or None)
_SCHEMA_REGISTRY = {}

if PYDANTIC_AVAILABLE:
    def _plan_post_validate(plan: Plan) -> list[str]:
        return plan.validate_refs()

    _SCHEMA_REGISTRY = {
        "context.json": (Context, None),
        "plan.json": (Plan, _plan_post_validate),
    }


def validate_planning_context(pc: dict) -> list[str]:
    """Validate a planning_context dict's SHAPE, returning friendly errors (F6).

    The architect emitted planning_context in a richer shape than the schema
    (constraints as dicts not strings; rejected_alternatives missing required
    rejection_reason/decision_ref) -> 10 raw pydantic errors that blocked a
    downstream --step N until hand-coerced. This validator runs on the RAW dict
    (so it works even when a full Plan.model_validate would crash) and returns
    targeted, self-correctable messages instead of a traceback.

    Returns an empty list when the shape is valid.
    """
    errors: list[str] = []
    if not isinstance(pc, dict):
        return ["planning_context must be a JSON object"]

    # constraints: list[str] (INTENT.md line 67). Dicts are the common drift.
    constraints = pc.get("constraints", [])
    if not isinstance(constraints, list):
        errors.append("planning_context.constraints must be a list of strings")
    else:
        for i, c in enumerate(constraints):
            if not isinstance(c, str):
                errors.append(
                    f"planning_context.constraints[{i}] must be a string, got "
                    f"{type(c).__name__} -- flatten it to a plain sentence"
                )

    # rejected_alternatives[*]: each needs rejection_reason + decision_ref.
    rejected = pc.get("rejected_alternatives", [])
    if not isinstance(rejected, list):
        errors.append("planning_context.rejected_alternatives must be a list")
    else:
        for i, ra in enumerate(rejected):
            if not isinstance(ra, dict):
                errors.append(
                    f"planning_context.rejected_alternatives[{i}] must be an object "
                    "with alternative/rejection_reason/decision_ref"
                )
                continue
            for field in ("rejection_reason", "decision_ref"):
                if not ra.get(field):
                    errors.append(
                        f"planning_context.rejected_alternatives[{i}] "
                        f"missing required '{field}'"
                    )

    return errors


def validate_state(state_dir: str) -> None:
    """Validate all state files in state_dir.

    Raises SchemaValidationError on first validation failure.
    Call at start of every planner/executor step and after CLI mutations.
    """
    if not PYDANTIC_AVAILABLE:
        return

    state_path = Path(state_dir)

    for filename, (model, post_validate) in _SCHEMA_REGISTRY.items():
        path = state_path / filename
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text())
            obj = model.model_validate(data)
            if post_validate:
                errors = post_validate(obj)
                if errors:
                    raise SchemaValidationError(f"{filename}: {errors}")
        except SchemaValidationError:
            raise
        except Exception as e:
            raise SchemaValidationError(f"{filename}: {e}")

    for path in state_path.glob("qr-*.json"):
        try:
            data = json.loads(path.read_text())
            QRFile.model_validate(data)
        except Exception as e:
            raise SchemaValidationError(f"{path.name}: {e}")


# =============================================================================
# Exports
# =============================================================================

if PYDANTIC_AVAILABLE:
    __all__ = [
        "PYDANTIC_AVAILABLE",
        "SchemaValidationError",
        "validate_state",
        "validate_planning_context",
        # QR constants
        "QA_ITEM_DEFAULTS", "QA_ITEM_REQUIRED_FIELDS", "QA_ITEM_OPTIONAL_FIELDS",
        "QA_ITEM_ALL_FIELDS", "QA_ITEM_SCHEMA_TEMPLATE", "get_qa_state_schema_example",
        # Models
        "Context", "Plan", "Overview", "Milestone", "CodeIntent", "CodeChange",
        "Decision", "Risk", "RejectedAlternative", "Wave",
        "PlanningContext", "InvisibleKnowledge",
        "Documentation", "Docstring", "FunctionBlock", "InlineComment", "ReadmeEntry",
        "DiagramNode", "DiagramEdge", "DiagramGraph",
        "QRItem", "QRFile",
    ]
else:
    __all__ = [
        "PYDANTIC_AVAILABLE",
        "SchemaValidationError",
        "validate_state",
        "validate_planning_context",
        "QA_ITEM_DEFAULTS", "QA_ITEM_REQUIRED_FIELDS", "QA_ITEM_OPTIONAL_FIELDS",
        "QA_ITEM_ALL_FIELDS", "QA_ITEM_SCHEMA_TEMPLATE", "get_qa_state_schema_example",
    ]
