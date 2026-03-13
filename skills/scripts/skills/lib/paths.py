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

    Returns path like '.openclaw/skills/scripts', '.pi/agent/skills/scripts',
    or '.claude/skills/scripts' depending on where scripts are installed.

    If scripts are not under HOME (e.g., installed to /opt/), prefer an
    existing known config root under HOME in this order:
    1. .openclaw/skills/scripts
    2. .pi/agent/skills/scripts
    3. .claude/skills/scripts

    If no known root exists, default to '.openclaw/skills/scripts'.
    """
    try:
        return str(_SCRIPTS_DIR.relative_to(Path.home()))
    except ValueError:
        fallback_candidates = (
            ".openclaw/skills/scripts",
            ".pi/agent/skills/scripts",
            ".claude/skills/scripts",
        )
        home = Path.home()
        for candidate in fallback_candidates:
            if (home / candidate).exists():
                return candidate
        return ".openclaw/skills/scripts"
