"""Renderer for converting AST to string output.

Simplified renderer handling only the core node types: TextNode, CodeNode, ElementNode.
"""

from typing import Protocol
from skills.lib.workflow.ast.nodes import (
    Node, Document, TextNode, CodeNode, ElementNode, FileContentNode,
    StepHeaderNode, CurrentActionNode, InvokeAfterNode
)


class Renderer(Protocol):
    """Abstract renderer interface."""

    def render_text(self, node: TextNode) -> str: ...
    def render_code(self, node: CodeNode) -> str: ...
    def render_element(self, node: ElementNode) -> str: ...
    def render_file_content(self, node: FileContentNode) -> str: ...
    def render_step_header(self, node: StepHeaderNode) -> str: ...
    def render_current_action(self, node: CurrentActionNode) -> str: ...
    def render_invoke_after(self, node: InvokeAfterNode) -> str: ...


class XMLRenderer:
    """Renders AST nodes to XML format."""

    def render_text(self, node: TextNode) -> str:
        """Render text node as plain string."""
        return node.content

    def render_code(self, node: CodeNode) -> str:
        """Render code node as markdown code block."""
        if node.language:
            return f"```{node.language}\n{node.content}\n```"
        return f"```\n{node.content}\n```"

    def render_element(self, node: ElementNode) -> str:
        """Render generic element with attributes and children."""
        attrs_str = ""
        if node.attrs:
            attrs_str = " " + " ".join(f'{k}="{v}"' for k, v in node.attrs.items())

        if not node.children:
            return f"<{node.tag}{attrs_str} />"

        children_str = "\n".join(self._render_node(child) for child in node.children)
        return f"<{node.tag}{attrs_str}>\n{children_str}\n</{node.tag}>"

    def render_file_content(self, node: FileContentNode) -> str:
        """Render file content node with CDATA wrapping.

        CDATA protects against content containing literal </file> strings
        (e.g., code examples in markdown showing XML parsing).

        Content containing "]]>" would break CDATA, so we escape by splitting
        into multiple CDATA sections: "foo]]>bar" -> "foo]]]]><![CDATA[>bar"
        """
        # Escape "]]>" sequences to prevent premature CDATA termination
        escaped = node.content.replace("]]>", "]]]]><![CDATA[>")
        return f'<file path="{node.path}"><![CDATA[\n{escaped}\n]]></file>'

    def render_step_header(self, node: StepHeaderNode) -> str:
        """Render step header with title as content, metadata as attributes."""
        attrs = {"script": node.script, "step": str(node.step)}
        if node.category:
            attrs["category"] = node.category
        if node.mode:
            attrs["mode"] = node.mode
        if node.total is not None:
            attrs["total"] = str(node.total)

        attrs_str = " " + " ".join(f'{k}="{v}"' for k, v in attrs.items())
        return f"<step_header{attrs_str}>{node.title}</step_header>"

    def render_current_action(self, node: CurrentActionNode) -> str:
        """Render current_action with actions as text children."""
        children_str = "\n".join(action for action in node.actions)
        return f"<current_action>\n{children_str}\n</current_action>"

    def render_invoke_after(self, node: InvokeAfterNode) -> str:
        """Render invoke_after with command or branching structure.

        WHY no validation here: __post_init__ validates at construction time.
        Renderer assumes valid node, focuses solely on XML generation.
        """
        if node.cmd is not None:
            invoke = f'<invoke cmd="cd {node.working_dir} && {node.cmd}" />'
            return f"<invoke_after>\n{invoke}\n</invoke_after>"
        else:
            if_pass_invoke = f'<invoke cmd="cd {node.working_dir} && {node.if_pass}" />'
            if_fail_invoke = f'<invoke cmd="cd {node.working_dir} && {node.if_fail}" />'
            return f"<invoke_after>\n  <if_pass>\n    {if_pass_invoke}\n  </if_pass>\n  <if_fail>\n    {if_fail_invoke}\n  </if_fail>\n</invoke_after>"

    def _render_node(self, node: Node) -> str:
        """Dispatch node to appropriate render method."""
        match node:
            case TextNode():
                return self.render_text(node)
            case CodeNode():
                return self.render_code(node)
            case ElementNode():
                return self.render_element(node)
            case FileContentNode():
                return self.render_file_content(node)
            case StepHeaderNode():
                return self.render_step_header(node)
            case CurrentActionNode():
                return self.render_current_action(node)
            case InvokeAfterNode():
                return self.render_invoke_after(node)


def render(doc: Document, renderer: Renderer) -> str:
    """Render document using provided renderer.

    Args:
        doc: Document to render
        renderer: Renderer implementation (XMLRenderer, etc)

    Returns:
        Rendered string output
    """
    if isinstance(renderer, XMLRenderer):
        parts = [renderer._render_node(child) for child in doc.children]
        return "\n".join(parts)

    raise NotImplementedError(f"Renderer {type(renderer).__name__} not implemented")


def render_step_header(node: StepHeaderNode) -> str:
    """Render StepHeaderNode directly without Document wrapper.

    WHY convenience: Most callers need standalone XML fragments, not full documents.
    """
    return XMLRenderer().render_step_header(node)


def render_current_action(node: CurrentActionNode) -> str:
    """Render CurrentActionNode directly without Document wrapper.

    WHY convenience: Most callers need standalone XML fragments, not full documents.
    """
    return XMLRenderer().render_current_action(node)


def render_invoke_after(node: InvokeAfterNode) -> str:
    """Render InvokeAfterNode directly without Document wrapper.

    WHY convenience: Most callers need standalone XML fragments, not full documents.
    """
    return XMLRenderer().render_invoke_after(node)
