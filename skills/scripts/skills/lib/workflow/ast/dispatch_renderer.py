"""Renderer for dispatch node types.

Separate from ast/renderer.py because:
1. Substitution scope: Template variable substitution ($var) is dispatch-specific.
   Generic ElementNode rendering should never perform substitution.
2. Expansion semantics: Dispatch rendering EXPANDS N nodes from 1 template.
   Generic rendering operates 1:1 (one node -> one output).
3. Future separation: Dispatch nodes may gain additional rendering concerns
   (model selection, parallel constraints) that don't belong in core AST.
"""

import re
from string import Template

from skills.lib.workflow.ast.dispatch import (
    SubagentDispatchNode,
    TemplateDispatchNode,
    RosterDispatchNode,
)


def _extract_template_vars(s: str) -> list[str]:
    """Extract $var names from template string."""
    return [m.group(1) for m in re.finditer(r'\$(\w+)', s)]


def _expand_template_targets(template: str, command: str, targets: tuple[dict[str, str], ...]) -> list[dict[str, str]]:
    """Expand template+command for each target with substituted values.

    Substitution happens here, not in render_template_dispatch, so
    render functions only assemble XML from pre-expanded data.

    Args:
        template: Prompt template with $var placeholders
        command: Command template with $var placeholders
        targets: Variable bindings per target

    Returns:
        List of dicts with "prompt" and "command" keys, values substituted

    Raises:
        ValueError: If template contains $var not present in target dict
    """
    result = []
    for i, t in enumerate(targets):
        try:
            prompt = Template(template).substitute(t)
            cmd = Template(command).substitute(t)
        except KeyError as e:
            required = set(_extract_template_vars(template) + _extract_template_vars(command))
            provided = set(t.keys())
            raise ValueError(
                f"Template variable {e} missing in target {i}. "
                f"Required: {sorted(required)}. Provided: {sorted(provided)}"
            ) from e
        result.append({"prompt": prompt, "command": cmd})
    return result


def _build_execution_constraint(count: int) -> str:
    """Build MANDATORY_PARALLEL execution constraint XML."""
    lines = [
        '  <execution_constraint type="MANDATORY_PARALLEL">',
        f"    You MUST dispatch ALL {count} agents in ONE assistant message.",
        "    Your message must contain exactly N Task tool calls, issued together.",
        "",
        "    CORRECT (single message, multiple tools):",
        "      [You send ONE message containing Task call 1, Task call 2, ... Task call N]",
        "",
        "    WRONG (sequential):",
        "      [You send message with Task call 1]",
        "      [You wait for result]",
        "      [You send message with Task call 2]",
        "",
        "    FORBIDDEN: Waiting for any agent before dispatching the next.",
        "  </execution_constraint>",
    ]
    return "\n".join(lines)


def _build_model_selection(model: str | None) -> str:
    """Build model selection guidance XML.

    Always emits explicit guidance, even when model is None. This prevents
    LLM pattern-matching errors where model selection from a previous step
    (e.g., "use HAIKU for Explore agents") incorrectly propagates to
    subsequent steps that have no explicit model requirement.

    Silent omission (returning "") leaves the LLM to infer from prior context.
    Explicit "use default" provides a counter-signal that breaks the
    pattern-matching chain.
    """
    if model is None:
        lines = [
            "  <model_selection>",
            "    Use DEFAULT model (omit model parameter from Task tool).",
            "    Do NOT carry forward model selections from previous steps.",
            "  </model_selection>",
        ]
        return "\n".join(lines)
    lines = [
        "  <model_selection>",
        f"    Use {model.upper()} for all agents.",
        "  </model_selection>",
    ]
    return "\n".join(lines)


def render_subagent_dispatch(node: SubagentDispatchNode) -> str:
    """Render single agent dispatch as XML.

    Args:
        node: SubagentDispatchNode with agent details

    Returns:
        XML string for single agent dispatch

    Raises:
        ValueError: If command is empty
    """
    agent_type = node.agent_type or "general-purpose"

    if not node.command.strip():
        raise ValueError(
            "SubagentDispatchNode.command cannot be empty. "
            "All agents must start with a prompt injection command (invoke)."
        )

    lines = [f'<subagent_dispatch agent="{agent_type}" mode="script">']

    # Always emit explicit model guidance to prevent LLM pattern-matching
    # from prior steps. See _build_model_selection() docstring.
    if node.model:
        lines.append(f'  <model>{node.model}</model>')
    else:
        lines.append('  <model>DEFAULT (omit model parameter from Task tool)</model>')

    if node.prompt:
        lines.append("  <prompt>")
        for line in node.prompt.split("\n"):
            lines.append(f"    {line}" if line else "")
        lines.append("  </prompt>")

    # Wrap invoke in directive to signal immediate execution
    lines.append('  <directive action="IMMEDIATELY invoke">')
    lines.append(f'    <invoke cmd="cd .claude/skills/scripts && {node.command}" />')
    lines.append('  </directive>')

    lines.append("</subagent_dispatch>")

    return "\n".join(lines)


def render_template_dispatch(node: TemplateDispatchNode) -> str:
    """Render template dispatch with SIMD pattern.

    Orchestrates expansion -> assembly pipeline.
    All targets are expanded at render time; LLM sees final prompts.

    Args:
        node: TemplateDispatchNode with template and targets

    Returns:
        XML string with parallel_dispatch structure

    Raises:
        ValueError: If node.targets is empty (cannot dispatch zero agents)
    """
    if not node.targets:
        raise ValueError(
            f"TemplateDispatchNode.targets cannot be empty. "
            f"Agent type: {node.agent_type}"
        )

    expanded = _expand_template_targets(node.template, node.command, node.targets)
    count = len(expanded)

    lines = [f'<parallel_dispatch agent="{node.agent_type}" count="{count}">']

    if node.instruction:
        lines.append("  <instruction>")
        lines.append(f"    {node.instruction}")
        lines.append("  </instruction>")
        lines.append("")

    lines.append(_build_execution_constraint(count))
    lines.append("")
    lines.append(_build_model_selection(node.model))
    lines.append("")

    lines.append("  <agents>")
    for i, e in enumerate(expanded, 1):
        lines.append(f'    <agent index="{i}">')

        if e["prompt"]:
            lines.append("      <prompt>")
            for prompt_line in e["prompt"].split("\n"):
                lines.append(f"        {prompt_line}" if prompt_line else "")
            lines.append("      </prompt>")

        lines.append(f'      <invoke cmd="cd .claude/skills/scripts && {e["command"]}" />')
        lines.append("    </agent>")
    lines.append("  </agents>")

    lines.append("</parallel_dispatch>")

    return "\n".join(lines)


def render_roster_dispatch(node: RosterDispatchNode) -> str:
    """Render roster dispatch with MIMD pattern.

    Each agent receives shared_context + unique prompt.
    Command is fixed for all agents.

    Args:
        node: RosterDispatchNode with shared context and unique prompts

    Returns:
        XML string with parallel_dispatch structure

    Raises:
        ValueError: If node.agents is empty (cannot dispatch zero agents)
    """
    if not node.agents:
        raise ValueError(
            f"RosterDispatchNode.agents cannot be empty. "
            f"Agent type: {node.agent_type}"
        )

    count = len(node.agents)

    lines = [f'<parallel_dispatch agent="{node.agent_type}" count="{count}">']

    if node.instruction:
        lines.append("  <instruction>")
        lines.append(f"    {node.instruction}")
        lines.append("  </instruction>")
        lines.append("")

    lines.append(_build_execution_constraint(count))
    lines.append("")
    lines.append(_build_model_selection(node.model))
    lines.append("")

    if node.shared_context:
        lines.append("  <shared_context>")
        for ctx_line in node.shared_context.split("\n"):
            lines.append(f"    {ctx_line}" if ctx_line else "")
        lines.append("  </shared_context>")
        lines.append("")

    lines.append("  <agents>")
    for i, agent_prompt in enumerate(node.agents, 1):
        lines.append(f'    <agent index="{i}">')
        lines.append("      <task>")
        for task_line in agent_prompt.split("\n"):
            lines.append(f"        {task_line}" if task_line else "")
        lines.append("      </task>")
        lines.append(f'      <invoke cmd="cd .claude/skills/scripts && {node.command}" />')
        lines.append("    </agent>")
    lines.append("  </agents>")

    lines.append("</parallel_dispatch>")

    return "\n".join(lines)


__all__ = [
    "render_subagent_dispatch",
    "render_template_dispatch",
    "render_roster_dispatch",
]
