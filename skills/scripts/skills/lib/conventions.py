"""Convention loading utilities.

Conventions are universal rules used by agents and skills. They live in the
installed config root's conventions/ directory (not skill-specific resources directories).

Available conventions:
- documentation.md: project index file/README.md format specification
- structural.md: Code quality conventions (god object, testing, etc.)
- temporal.md: Comment hygiene (timeless present rule)
- severity.md: MUST/SHOULD/COULD severity definitions
- intent-markers.md: :PERF:/:UNSAFE: marker format
"""
from fnmatch import fnmatch
from pathlib import Path

from skills.lib.io import read_text_or_exit


_REGISTRY_CACHE = None


def get_convention(name: str) -> str:
    """Load convention from centralized store.

    Args:
        name: Convention filename (e.g., "temporal.md", "structural.md")

    Returns:
        Full content of the convention file

    Exits:
        With contextual error message if convention doesn't exist
    """
    # parents[4]: lib -> skills -> scripts -> skills -> config root
    convention_path = Path(__file__).resolve().parents[4] / "conventions" / name
    return read_text_or_exit(convention_path, "loading convention")


def _parse_role_header(content: str) -> tuple[str, dict]:
    """Parse role header line (indent 0).

    Returns:
        (role_name, initial_role_dict)
    """
    role_name = content.split(':')[0].strip()
    return role_name, {}


def _parse_list_item(content: str) -> str:
    """Parse list item (starts with '-').

    Returns:
        Item value with quotes stripped
    """
    return content[1:].strip().strip('"\'')


def _parse_phase_item(content: str) -> tuple[str, list]:
    """Parse phase_specific phase header.

    Returns:
        (phase_name, empty_list)
    """
    phase_name = content.split(':')[0].strip()
    return phase_name, []


def _parse_indent_0_role(content: str, result: dict) -> tuple[str, None, None]:
    """Handle role header (indent 0).

    Returns:
        (current_role, current_key=None, current_phase=None)
    """
    role_name, role_dict = _parse_role_header(content)
    result[role_name] = role_dict
    return role_name, None, None


def _parse_indent_2_keys(content: str, current_role: str, result: dict) -> tuple[str, None]:
    """Handle second-level keys (indent 2).

    Returns:
        (current_key, current_phase=None)
    """
    key = content.split(':')[0].strip()

    if content.endswith('[]'):
        result[current_role][key] = []
    elif key in ('receives',):
        result[current_role][key] = []
    elif key in ('phase_specific', 'mode_specific'):
        result[current_role][key] = {}
    elif key == 'rationale':
        value = content.split(':', 1)[1].strip().strip('"\'')
        result[current_role][key] = value

    return key, None


def _parse_indent_4_items(content: str, current_role: str, current_key: str, result: dict) -> str | None:
    """Handle list items and phase/mode headers (indent 4).

    Returns:
        current_phase (updated if phase/mode header found, else unchanged)
    """
    if current_key == 'receives' and content.startswith('-'):
        value = _parse_list_item(content)
        result[current_role][current_key].append(value)
        return None

    if current_key == 'phase_specific' and ':' in content:
        phase_name, phase_list = _parse_phase_item(content)
        result[current_role][current_key][phase_name] = phase_list
        return phase_name

    if current_key == 'mode_specific' and ':' in content:
        # mode_specific uses same structure as phase_specific
        mode_name, mode_list = _parse_phase_item(content)
        result[current_role][current_key][mode_name] = mode_list
        return mode_name

    return None


def _parse_indent_6_phase_items(content: str, current_role: str, current_key: str, current_phase: str, result: dict) -> None:
    """Handle phase-specific and mode-specific list items (indent 6)."""
    if current_key in ('phase_specific', 'mode_specific') and current_phase and content.startswith('-'):
        value = _parse_list_item(content)
        result[current_role][current_key][current_phase].append(value)


def _validate_parsed_structure(result: dict) -> None:
    """Validate parsed registry structure.

    Args:
        result: Parsed registry dictionary

    Raises:
        ValueError: If structure is invalid
    """
    for role, config in result.items():
        # Each role must have receives or rationale
        if 'receives' not in config and 'rationale' not in config:
            raise ValueError(f"Role '{role}' missing 'receives' or 'rationale'")

        # phase_specific phases must have non-empty lists
        if 'phase_specific' in config:
            for phase, items in config['phase_specific'].items():
                if not isinstance(items, list):
                    raise ValueError(f"Role '{role}' phase_specific.{phase} must be list")

        # mode_specific modes must have non-empty lists
        if 'mode_specific' in config:
            for mode, items in config['mode_specific'].items():
                if not isinstance(items, list):
                    raise ValueError(f"Role '{role}' mode_specific.{mode} must be list")


def _parse_yaml_simple(text: str) -> dict:
    """Simple YAML parser for registry (subset of YAML needed for our structure)."""
    try:
        import yaml
        result = yaml.safe_load(text)
        _validate_parsed_structure(result)
        return result
    except ImportError:
        result = {}
        current_role = None
        current_key = None
        current_phase = None

        for line in text.split('\n'):
            if not line.strip() or line.strip().startswith('#'):
                continue

            indent = len(line) - len(line.lstrip())
            content = line.strip()

            if indent == 0 and ':' in content and not content.startswith('-'):
                current_role, current_key, current_phase = _parse_indent_0_role(content, result)
            elif indent == 2 and current_role and ':' in content:
                current_key, current_phase = _parse_indent_2_keys(content, current_role, result)
            elif indent == 4 and current_role and current_key:
                phase_update = _parse_indent_4_items(content, current_role, current_key, result)
                if phase_update is not None:
                    current_phase = phase_update
            elif indent == 6 and current_role and current_key:
                _parse_indent_6_phase_items(content, current_role, current_key, current_phase, result)

        _validate_parsed_structure(result)
        return result


def get_registry() -> dict:
    """Load role-convention registry (cached)."""
    global _REGISTRY_CACHE
    if _REGISTRY_CACHE is None:
        registry_path = Path(__file__).resolve().parents[4] / "conventions" / "REGISTRY.yaml"
        _REGISTRY_CACHE = _parse_yaml_simple(registry_path.read_text())
    return _REGISTRY_CACHE


def get_conventions_for_role(role: str, phase: str = None, mode: str = None) -> list[str]:
    """Return convention filenames for a role, optionally filtered by phase or mode."""
    registry = get_registry()
    role_config = registry.get(role, {})
    conventions = role_config.get("receives", [])

    if phase and "phase_specific" in role_config:
        phase_conventions = role_config["phase_specific"].get(phase, [])
        if phase_conventions:
            conventions = phase_conventions

    if mode and "mode_specific" in role_config:
        mode_conventions = role_config["mode_specific"].get(mode, [])
        if mode_conventions:
            conventions = mode_conventions

    return conventions


def validate_convention_access(role: str, convention: str) -> bool:
    """Check if role is allowed to access convention."""
    registry = get_registry()
    role_config = registry.get(role, {})
    receives = role_config.get("receives", [])

    # Check receives list (supports wildcards)
    for pattern in receives:
        if fnmatch(convention, pattern):
            return True

    return False
