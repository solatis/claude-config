"""AST node types for workflow output representation.

Simplified AST with only the nodes actually used by skills:
- TextNode: Plain text content
- CodeNode: Code blocks with optional language
- ElementNode: Generic XML element (used via W.el())

All specialized nodes (HeaderNode, ActionsNode, etc.) were removed because
skills use W.el("tag_name", ...) pattern exclusively.
"""

from dataclasses import dataclass

from skills.lib.paths import get_skills_working_dir

_SKILLS_DIR = get_skills_working_dir()

__all__ = [
    "TextNode",
    "CodeNode",
    "ElementNode",
    "FileContentNode",
    "StepHeaderNode",
    "CurrentActionNode",
    "InvokeAfterNode",
    "Node",
    "Document",
]


@dataclass(frozen=True)
class TextNode:
    """Plain text content node."""
    content: str


@dataclass(frozen=True)
class CodeNode:
    """Code block with optional language tag."""
    content: str
    language: str | None = None


@dataclass(frozen=True)
class ElementNode:
    """Generic XML element with attributes and children."""
    tag: str
    attrs: dict[str, str]
    children: list['Node']


@dataclass(frozen=True)
class FileContentNode:
    """Embed file content in prompt output.

    For custom mode category selection, the LLM needs to see full category
    definitions to make informed choices. Rather than having the LLM explore
    files (which adds latency and context), we embed content directly.

    Format: <file path="..."><![CDATA[content]]></file>

    Distinct from CodeNode because:
    - CodeNode is for code examples with syntax highlighting hints
    - FileContentNode is for embedding reference material the LLM should read
    """
    # Path relative to workspace root for consistency across invocations
    path: str
    # Raw file content - will be CDATA-wrapped during rendering
    # to prevent XML injection from content containing </file> tags
    content: str


@dataclass(frozen=True)
class StepHeaderNode:
    """Step header for workflow step identification.

    Step headers mark boundaries between workflow steps. The title appears
    as element text content (primary visual information for LLM), while
    script/step are metadata attributes for logging and debugging.

    WHY int step: Type system catches construction errors before XML rendering.
    Renderer converts to string for XML output.

    WHY int total: Consistency with step field. Both are numeric workflow metadata.
    Renderer converts both to string for XML attributes.
    """
    title: str
    script: str
    step: int
    category: str | None = None
    mode: str | None = None
    total: int | None = None


@dataclass(frozen=True)
class CurrentActionNode:
    """Current action block containing LLM instructions.

    Wraps a list of action strings into a current_action element.
    Strings are auto-wrapped in TextNode during rendering, eliminating
    the repetitive [TextNode(a) for a in actions] pattern.

    WHY tuple: Frozen dataclass requires immutable types.
    WHY __init__: Accepts list for convenience, converts to tuple for immutability.
    """
    actions: tuple[str, ...]

    def __init__(self, actions: list[str] | tuple[str, ...]):
        object.__setattr__(self, 'actions', tuple(actions))


@dataclass(frozen=True)
class InvokeAfterNode:
    """Invoke command for workflow step continuation.

    Constructs the <invoke_after> element containing the next step command.
    The working_dir defaults to the skills scripts directory, centralizing
    the path hardcoded in 47+ locations.

    WHY default working_dir: 99% of invocations use the same path; default eliminates
    boilerplate and enables single-point path changes.

    WHY branching: QR gates require different commands for pass/fail outcomes.

    WHY __post_init__ validation: Catches invalid construction immediately instead of
    deferring to render time. Prevents workflow failure from invalid node reaching renderer.
    """
    cmd: str | None = None
    if_pass: str | None = None
    if_fail: str | None = None
    working_dir: str = _SKILLS_DIR

    def __post_init__(self):
        if self.cmd is None and (self.if_pass is None or self.if_fail is None):
            raise ValueError("InvokeAfterNode requires either cmd or both if_pass and if_fail")


# Type union for all AST nodes
# Enables type checking in _render_node match statement
# New node types MUST be added here to be recognized by the renderer
Node = TextNode | CodeNode | ElementNode | FileContentNode | StepHeaderNode | CurrentActionNode | InvokeAfterNode


@dataclass(frozen=True)
class Document:
    """Container for rendered output."""
    children: list[Node]
