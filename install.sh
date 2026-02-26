#!/usr/bin/env bash
set -euo pipefail

# -- Defaults ----------------------------------------------------------------

REPO_URL="${CLAUDE_CONFIG_REPO_URL:-git@github.com:solatis/claude-config.git}"
REPO_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.local/share/claude-config}"
TARGETS=()
PASSTHROUGH_ARGS=()
TOOL=""
UNINSTALL=false

# -- Usage -------------------------------------------------------------------

usage() {
    cat <<'EOF'
Usage: install.sh --tool TOOL [OPTIONS]

Install, upgrade, or uninstall AI coding tool configuration.

Required:
  --tool TOOL       Target tool profile (claude, pi)

Options:
  --target DIR      Target directory (default: derived from --tool)
                    May be specified multiple times for multi-target install
  --uninstall       Remove all managed files from target
  --dry-run         Preview changes without writing
  --force           Overwrite locally-modified files without backup
  --help, -h        Show this help message

Examples:
  install.sh --tool claude                          # Install/upgrade to ~/.claude
  install.sh --tool pi                              # Install/upgrade to ~/.pi/agent
  install.sh --tool claude --target ~/git/repo/.claude  # Project-specific
  install.sh --tool claude --dry-run                # Preview changes
  install.sh --tool claude --uninstall              # Remove managed files
EOF
}

# -- Argument parsing --------------------------------------------------------

while [[ $# -gt 0 ]]; do
    case "$1" in
        --help|-h)
            usage
            exit 0
            ;;
        --target)
            TARGETS+=("$2")
            shift 2
            ;;
        --tool)
            TOOL="$2"
            PASSTHROUGH_ARGS+=("--tool" "$2")
            shift 2
            ;;
        --uninstall)
            UNINSTALL=true
            shift
            ;;
        --dry-run|--force)
            PASSTHROUGH_ARGS+=("$1")
            shift
            ;;
        *)
            echo "Unknown argument: $1" >&2
            echo "Run '$0 --help' for usage." >&2
            exit 1
            ;;
    esac
done

if [[ -z "$TOOL" ]]; then
    echo "ERROR: --tool is required (e.g. --tool claude, --tool pi)" >&2
    exit 1
fi

# -- Tool default target -----------------------------------------------------

tool_default_target() {
    case "$1" in
        claude) echo "$HOME/.claude" ;;
        pi)     echo "$HOME/.pi/agent" ;;
        *)      echo "ERROR: Unknown tool: $1" >&2; exit 1 ;;
    esac
}

# Default target if none specified
if [[ ${#TARGETS[@]} -eq 0 ]]; then
    TARGETS=("$(tool_default_target "$TOOL")")
fi

# -- Prerequisites -----------------------------------------------------------

check_prereqs() {
    if ! command -v git &>/dev/null; then
        echo "ERROR: git is required but not found." >&2
        exit 1
    fi
    if ! command -v python3 &>/dev/null; then
        echo "ERROR: python3 is required but not found." >&2
        exit 1
    fi
    local py_version
    py_version=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    if python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" 2>/dev/null; then
        : # ok
    else
        echo "ERROR: Python 3.9+ required, found $py_version" >&2
        exit 1
    fi
}

# -- Repo acquisition --------------------------------------------------------

ensure_repo() {
    # Detect if we're already inside the source repo
    local script_dir
    if [[ -n "${BASH_SOURCE[0]:-}" ]] && [[ -f "${BASH_SOURCE[0]}" ]]; then
        script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        if [[ -f "$script_dir/install.py" ]]; then
            REPO_DIR="$script_dir"
            return
        fi
    fi

    if [[ -d "$REPO_DIR/.git" ]]; then
        echo "Updating source repo at $REPO_DIR..."
        git -C "$REPO_DIR" fetch origin
        git -C "$REPO_DIR" merge --ff-only origin/main
    elif [[ -d "$REPO_DIR" ]]; then
        echo "ERROR: $REPO_DIR exists but is not a git repository." >&2
        echo "  Remove or rename it, then retry." >&2
        exit 1
    else
        echo "Cloning source repo to $REPO_DIR..."
        mkdir -p "$(dirname "$REPO_DIR")"
        git clone "$REPO_URL" "$REPO_DIR"
    fi
}

# -- Install/upgrade dispatch ------------------------------------------------

run_installer() {
    local target="$1"
    local manifest="$target/.install-manifest.json"
    local command

    if $UNINSTALL; then
        command="uninstall"
    elif [[ -f "$manifest" ]]; then
        command="upgrade"
    else
        command="install"
    fi

    echo "==> $command -> $target"

    local cmd_args=("$command" --target "$target" "${PASSTHROUGH_ARGS[@]}")
    if [[ "$command" != "uninstall" ]]; then
        cmd_args+=(--source "$REPO_DIR")
    fi

    python3 "$REPO_DIR/install.py" "${cmd_args[@]}"
}

# -- Main --------------------------------------------------------------------

check_prereqs
ensure_repo

for target in "${TARGETS[@]}"; do
    run_installer "$target"
done
