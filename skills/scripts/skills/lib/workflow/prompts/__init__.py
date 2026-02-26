"""Plain-text prompt building blocks for workflows.

Prompts as strings composed via f-strings. No XML, no AST.
"""

from skills.lib.workflow.prompts.subagent import (
    # Building blocks
    dispatch_instruction,
    task_tool_instruction,  # backward compat alias
    sub_agent_invoke,
    parallel_constraint,
    # Dispatch templates
    subagent_dispatch,
    template_dispatch,
    roster_dispatch,
)
# format_step provides step assembly: body content + continuation directive
from skills.lib.workflow.prompts.step import format_step
# format_file_content provides file content embedding with 4-backtick fencing
from skills.lib.workflow.prompts.file import format_file_content

__all__ = [
    # Building blocks
    "dispatch_instruction",
    "task_tool_instruction",  # backward compat alias
    "sub_agent_invoke",
    "parallel_constraint",
    # Dispatch templates
    "subagent_dispatch",
    "template_dispatch",
    "roster_dispatch",
    # Step assembly
    "format_step",
    # File content embedding
    "format_file_content",
]
