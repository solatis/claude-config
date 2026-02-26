"""Tool-agnostic path resolution.

All path computation derives from __file__ position in the directory tree.
This avoids environment variables, config files, and hardcoded tool names.
The installer preserves relative directory structure, so depth-based
navigation works regardless of installation root name.
"""
from pathlib import Path

# parents[2]: lib/ -> skills/ -> scripts/
_SCRIPTS_DIR = Path(__file__).resolve().parents[2]


def get_scripts_dir() -> Path:
    """Return absolute path to the skills/scripts/ directory.

    Use for sys.path manipulation and absolute path construction.
    For invoke directive working-dir attributes, use get_skills_working_dir().
    """
    return _SCRIPTS_DIR


def get_skills_working_dir() -> str:
    """Compute working-dir for invoke directives (relative to HOME).

    Returns path like '.claude/skills/scripts' or '.pi/agent/skills/scripts'
    depending on where the scripts are installed.

    Falls back to '.claude/skills/scripts' if the scripts directory is not
    under HOME (e.g., installed to /opt/). This preserves backward
    compatibility for non-standard installations.
    """
    try:
        return str(_SCRIPTS_DIR.relative_to(Path.home()))
    except ValueError:
        return ".claude/skills/scripts"
