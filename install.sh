#!/usr/bin/env bash
set -euo pipefail

# -- Defaults ----------------------------------------------------------------

REPO_URL="${CLAUDE_CONFIG_REPO_URL:-git@github.com:solatis/claude-config.git}"
REPO_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.local/share/claude-config}"
TARGETS=()
PASSTHROUGH_ARGS=()
TOOL=""
UNINSTALL=false
VERBOSE=false

# -- Usage -------------------------------------------------------------------

usage() {
    cat <<'EOF'
Usage: install.sh --tool TOOL [OPTIONS]

Install, upgrade, or uninstall AI coding tool configuration.

Required:
  --tool TOOL       Target tool profile (claude, pi, openclaw)

Options:
  --target DIR      Target directory (default: derived from --tool)
                    May be specified multiple times for multi-target install
  --uninstall       Remove all managed files from target
  --dry-run         Preview changes without writing
  --verbose, -v     Print per-file operations in addition to summary
  --force           Overwrite locally-modified files without backup
  --help, -h        Show this help message

Examples:
  install.sh --tool claude                          # Install/upgrade to ~/.claude
  install.sh --tool pi                              # Install/upgrade to ~/.pi/agent
  install.sh --tool openclaw                        # Install/upgrade to discovered OpenClaw root
  install.sh --tool openclaw --target ~/.openclaw  # Explicit OpenClaw root
  install.sh --tool claude --target ~/git/repo/.claude  # Project-specific
  install.sh --tool claude --dry-run                # Preview changes
  install.sh --tool pi --verbose                    # Show all file operations
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
        --verbose|-v)
            PASSTHROUGH_ARGS+=("$1")
            VERBOSE=true
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
    echo "ERROR: --tool is required (e.g. --tool claude, --tool pi, --tool openclaw)" >&2
    exit 1
fi

# -- Tool default target -----------------------------------------------------

OPENCLAW_DISCOVERED_TARGETS=()

normalize_path() {
    local raw="$1"
    python3 - "$raw" <<'PY'
import os
import pathlib
import sys

raw = sys.argv[1].strip()
if not raw:
    raise SystemExit(1)

print(pathlib.Path(os.path.expanduser(raw)).resolve())
PY
}

append_openclaw_candidate() {
    local raw="$1"
    [[ -n "$raw" ]] || return

    local normalized
    normalized="$(normalize_path "$raw" 2>/dev/null)" || return

    local existing
    for existing in "${OPENCLAW_DISCOVERED_TARGETS[@]}"; do
        if [[ "$existing" == "$normalized" ]]; then
            return
        fi
    done

    OPENCLAW_DISCOVERED_TARGETS+=("$normalized")
}

is_openclaw_state_root() {
    local dir="$1"
    [[ -f "$dir/openclaw.json" || -d "$dir/skills" || -d "$dir/agents" || -d "$dir/workspace" ]]
}

collect_openclaw_state_root_candidates() {
    OPENCLAW_DISCOVERED_TARGETS=()

    if [[ -n "${OPENCLAW_STATE_DIR:-}" ]]; then
        append_openclaw_candidate "$OPENCLAW_STATE_DIR"
    fi

    if [[ -n "${OPENCLAW_CONFIG_PATH:-}" ]]; then
        append_openclaw_candidate "$(dirname "$OPENCLAW_CONFIG_PATH")"
    fi

    local default_root="$HOME/.openclaw"
    if [[ -d "$default_root" ]] && is_openclaw_state_root "$default_root"; then
        append_openclaw_candidate "$default_root"
    fi

    local previous_nullglob
    previous_nullglob=$(shopt -p nullglob || true)
    shopt -s nullglob

    local root
    for root in "$HOME"/.openclaw-*; do
        [[ -d "$root" ]] || continue
        if is_openclaw_state_root "$root"; then
            append_openclaw_candidate "$root"
        fi
    done

    eval "$previous_nullglob"
}

resolve_openclaw_default_target() {
    collect_openclaw_state_root_candidates

    local candidate_count=${#OPENCLAW_DISCOVERED_TARGETS[@]}
    if [[ "$candidate_count" -eq 0 ]]; then
        echo "$HOME/.openclaw"
        return
    fi

    if [[ "$candidate_count" -eq 1 ]]; then
        echo "${OPENCLAW_DISCOVERED_TARGETS[0]}"
        return
    fi

    echo "ERROR: Multiple OpenClaw roots discovered from implicit sources:" >&2
    local candidate
    for candidate in "${OPENCLAW_DISCOVERED_TARGETS[@]}"; do
        echo "  - $candidate" >&2
    done
    echo "Explicit target required when discovery is ambiguous." >&2
    echo "Run: $0 --tool openclaw --target ~/.openclaw" >&2
    exit 1
}

tool_default_target() {
    case "$1" in
        claude)   echo "$HOME/.claude" ;;
        pi)       echo "$HOME/.pi/agent" ;;
        openclaw) resolve_openclaw_default_target ;;
        *)        echo "ERROR: Unknown tool: $1" >&2; exit 1 ;;
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
    if $VERBOSE; then
        if [[ -f "$manifest" ]]; then
            echo "    found previous manifest file: $manifest"
        else
            echo "    no manifest file found at: $manifest"
        fi
    fi

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
