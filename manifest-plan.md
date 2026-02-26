# AI Coding Tool Config Installation Mechanism

## Problem Statement

The config repository currently lives directly in `~/.claude/`. This creates two critical problems:

1. **Bootstrapping paradox**: When developing/fixing skills, a broken skill in the source repo immediately breaks the active coding environment. You cannot use the planner skill to fix the planner skill if both are the same file.

2. **Namespace collision**: `~/.claude/CLAUDE.md` has special meaning to Claude Code -- it's loaded automatically for ALL sessions as global user preferences. This prevents putting project-specific instructions there, conflating "how I want Claude to behave everywhere" with "how this repository works."

The solution: Move the source repository to a separate location and install (copy) distributable files into the target tool's config directory (e.g. `~/.claude/` for Claude Code).

### Multi-Tool Targeting

Claude Code is one intended target. The skills, agents, and conventions in this repo are designed to work across multiple AI coding tools (Gemini, Codex, OpenCode, Ampcode, Pi, etc.). Each tool has its own config directory and context-file conventions:

- Claude Code: `~/.claude/`, context via `CLAUDE.md`
- Other tools: their respective config directories and conventions

The installer uses `--target` to support any destination. Same files, same directory layout for all tools. Each tool loads what it recognizes and ignores the rest.

Tool-specific context files (like `CLAUDE.md` and `README.md`) are development artifacts -- they guide developers working on the source code, not the runtime execution of skills. The installer excludes them because the installation target is production, not a development environment.

`parents[N]` path resolution in the Python skills is purely depth-based -- it navigates by directory count, not by directory name. Installing to `~/.codex/` with identical structure works the same as `~/.claude/`.

**Scope boundary**: The installer copies files. Whether a specific tool can USE the installed skills is outside the installer's scope and may require tool-specific configuration or adaptation layers in the future.

## Why Copying (Not Symlinks)

Symlinks seem attractive but fail this use case:

1. **Path resolution breaks Python imports**: Python's `Path(__file__).resolve()` follows symlinks to the source location. The codebase uses `parents[4]` to navigate from `skills/scripts/skills/lib/conventions.py` up to `.claude/conventions/`. If the file resolves to `~/git/claude-config/...`, the path calculation breaks.

2. **No isolation**: A syntax error in `~/git/claude-config/skills/planner/...` would immediately crash any Claude session trying to use the planner. With copies, the installed version in `~/.claude/` remains stable until explicitly upgraded.

3. **Development workflow**: You want to experiment freely in the source repo, test changes, then "deploy" to production. Symlinks eliminate this staging/production separation.

## Why a Manifest

A simple `cp -r` or `rsync` cannot safely handle:

1. **Orphan cleanup**: If `skills/old-skill/` existed in v1 but is deleted in v2, the installer must remove it from the target. Without tracking what was installed, you cannot know what to delete.

2. **Conflict detection**: If the user manually edited `~/.claude/agents/developer.md`, blindly overwriting loses their changes. The manifest stores hashes to detect modifications.

3. **Clean uninstall**: Removing only managed files while preserving user files (`settings.json`, root `CLAUDE.md`) requires knowing exactly what the installer owns.

## Rejected Alternatives

### GNU Stow / Symlink Farms

Stow creates symlinks from a "stow directory" to a target. Rejected because:
- Symlinks break `Path(__file__).resolve().parents[N]` calculations
- No isolation between dev and production environments
- Cannot use stable skills to fix broken skills

### rsync --delete

Rsync can mirror directories, but:
- `--delete` removes ALL files not in source, including user files like `settings.json`
- No conflict detection (user modifications silently lost)
- Requires careful exclusion rules that are easy to misconfigure

### git worktree

Making `~/.claude/` a git worktree of the source repo:
- Mixes tracked repo files with untracked user data (settings, auth tokens, ephemeral caches)
- Still no isolation -- changes in worktree are immediate
- Complicates the git workflow (detached HEAD states, etc.)

### Archive extraction (tar/zip)

Packaging as an archive and extracting:
- Simple for initial install
- Cannot handle incremental upgrades or orphan cleanup without wiping the directory
- No conflict detection

### Pure shell for manifest operations

JSON manipulation without `jq` is fragile (sed/awk parsing). Set operations for orphan
detection are awkward in shell. Python is already required (skills are Python), so stdlib
is available. Shell is the right tool for bootstrap; Python is the right tool for data
operations.

## Solution: Two-Layer Installer

The installer is split into two layers with a clean responsibility boundary:

- **install.sh** (shell): Bootstrap, prerequisites, repo acquisition, mode detection, target loop
- **install.py** (Python stdlib only): Manifest CRUD, file operations, hashing, conflict detection, orphan cleanup

### install.sh -- Bootstrap Layer

install.sh is the user-facing entry point. It works in two modes:

1. **Piped from curl** (`curl -L <url> | bash`): Clones the source repo, then invokes install.py
2. **Run locally** from inside a cloned repo: Detects it's in the source repo, invokes install.py directly

Responsibilities:
- Validate prerequisites (git, python3 >= 3.9)
- Clone or update source repo to `$CLAUDE_CONFIG_DIR` (default `$HOME/.local/share/claude-config/`)
- Auto-detect install vs upgrade by checking for `.install-manifest.json` in target
- Loop over `--target` arguments, invoke install.py once per target
- Pass through `--dry-run`, `--force`, `--keep-local` flags to install.py

```bash
#!/usr/bin/env bash
set -euo pipefail

# -- Defaults ----------------------------------------------------------------

REPO_URL="${CLAUDE_CONFIG_REPO_URL:-git@github.com:solatis/claude-config.git}"
REPO_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.local/share/claude-config}"
TARGETS=()
PASSTHROUGH_ARGS=()

# -- Argument parsing --------------------------------------------------------

while [[ $# -gt 0 ]]; do
    case "$1" in
        --target)
            TARGETS+=("$2")
            shift 2
            ;;
        --dry-run|--force|--keep-local)
            PASSTHROUGH_ARGS+=("$1")
            shift
            ;;
        *)
            echo "Unknown argument: $1" >&2
            exit 1
            ;;
    esac
done

# Default target if none specified
if [[ ${#TARGETS[@]} -eq 0 ]]; then
    TARGETS=("$HOME/.claude")
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
    # Verify Python version >= 3.9
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

    if [[ -f "$manifest" ]]; then
        command="upgrade"
    else
        command="install"
    fi

    echo "==> $command -> $target"
    python3 "$REPO_DIR/install.py" "$command" \
        --source "$REPO_DIR" \
        --target "$target" \
        "${PASSTHROUGH_ARGS[@]}"
}

# -- Main --------------------------------------------------------------------

check_prereqs
ensure_repo

for target in "${TARGETS[@]}"; do
    run_installer "$target"
done
```

Usage:

```bash
# Fresh install to default (~/.claude/)
curl -L https://raw.github.com/solatis/claude-config/main/install.sh | bash

# Install to specific tool
curl -L ... | bash -s -- --target ~/.codex/

# Multiple targets
curl -L ... | bash -s -- --target ~/.claude/ --target ~/.codex/ --target ~/.gemini/

# Local usage (from cloned repo)
./install.sh
./install.sh --target ~/.codex/ --dry-run

# Local upgrade after pulling new changes
git pull && ./install.sh
```

### install.py -- Manifest Engine

A single-file Python script using only stdlib that:

1. Enumerates source files via `git ls-files --cached`
2. Copies files to target preserving directory structure
3. Writes a manifest tracking installed files with SHA256 hashes
4. On upgrade: diffs manifests, removes orphans, detects conflicts
5. On uninstall: removes only files matching their installed hash

install.py always operates on a single target. Multi-target is handled by install.sh
looping over targets and invoking install.py once per target.

### Manifest Schema

```json
{
  "version": 1,
  "source_commit": "abc123def456...",
  "source_path": "/Users/leon/.local/share/claude-config",
  "installed_at": "2026-01-26T14:30:00Z",
  "files": {
    "skills/planner/SKILL.md": {
      "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "size": 1847
    },
    "agents/developer.md": {
      "sha256": "...",
      "size": 4521
    }
  }
}
```

Location: Per-target at `<target>/.install-manifest.json`. Each target has its own
independent manifest. No cross-target state.

### Command Interface

```
# install.py is invoked by install.sh, but can also be used directly:

# Fresh install (fails if manifest exists)
python3 install.py install --source ~/git/claude-config --target ~/.claude

# Upgrade (diff manifests, handle conflicts)
python3 install.py upgrade --source ~/git/claude-config --target ~/.claude

# Remove all managed files (only if unchanged)
python3 install.py uninstall --target ~/.claude

# Preview without executing
python3 install.py --dry-run install --source . --target ~/.claude

# Override conflict detection
python3 install.py --force upgrade --source . --target ~/.codex
```

### Conflict Handling Policy

When upgrading, for each file:

1. **File unchanged** (`current_hash == manifest_hash`): Safe to overwrite with new version
2. **File modified** (`current_hash != manifest_hash`): User edited it
   - Default: Create backup (`file.md.bak.20260126-143000`), then overwrite
   - With `--keep-local`: Skip this file, continue with others
   - Report all conflicts at end

On uninstall:
- Only delete files where `current_hash == manifest_hash`
- Leave modified files in place, report them

### Exclusions

Files that exist in the source repo but should NOT be installed. Two categories
with different matching semantics:

```python
# Excluded at any path depth (directory or file names).
# These are development artifacts, not runtime dependencies.
ALWAYS_EXCLUSIONS = {
    ".git",
    ".github",
    "CLAUDE.md",           # Dev context for AI coding tools (not needed in prod)
    "README.md",           # Dev documentation (not needed in prod)
}

# Excluded only when they appear at the repo root (depth 1).
ROOT_EXCLUSIONS = {
    "install.py",          # The installer itself
    "install.sh",          # The bootstrap script
    ".gitignore",          # Git config
    "LICENSE",             # Repo license file
    MANIFEST_FILE,         # Prevent circular manifest overwrite
}
```

CLAUDE.md and README.md are development-time context files. They tell
developers (human or AI) how to work on the source code. The installation
target is production -- skills are executed there, not developed. These
files add no runtime value and should not be installed.

Files that the target tool creates but the installer must never touch:

```
settings.json            # User permissions, hooks, API keys
settings.local.json      # Local overrides
projects/                # Session caches
todos/                   # Generated todo artifacts
plans/                   # Generated plan artifacts
debug/                   # Debug output
session-env/             # Session state
telemetry/               # Usage telemetry
statsig/                 # Feature flags
history.jsonl            # Conversation history
```

These are implicitly safe because they're not in `git ls-files --cached`.

### Directory Structure Preservation

The Python scripts use rigid path dependencies via `Path(__file__).resolve().parents[N]`.
Different files use `parents[4]` to reach different ancestor directories depending
on their depth in the tree:

```python
# In skills/scripts/skills/lib/conventions.py (depth 5 from root)
# parents[4] -> <target>/
convention_path = Path(__file__).resolve().parents[4] / "conventions" / name

# In skills/scripts/skills/planner/shared/resources.py (depth 6 from root)
# parents[4] -> <target>/skills/
resource_path = Path(__file__).resolve().parents[4] / "planner" / "resources" / name
```

Both are correct -- each file's `parents[N]` calculation is calibrated to its own
depth. The resolution is purely depth-based, not name-based. What matters is that
the installer preserves relative paths from the repo root, keeping every file at
its original depth:

```
<target>/                            # target root (any path)
  conventions/                       # accessed from conventions.py via parents[4]
  skills/
    planner/
      resources/                     # accessed from resources.py via parents[4]
    scripts/
      skills/
        lib/
          conventions.py             # depth 5
        planner/
          shared/
            resources.py             # depth 6
```

### Crash Safety

Two mechanisms protect against interrupted operations:

**Atomic manifest writes**: The manifest is written to a temporary file, fsynced,
then atomically renamed. A partial write from SIGKILL or power loss cannot corrupt
the manifest.

**Upgrade-in-progress marker**: Before starting an upgrade, install.py writes a
`.upgrade-in-progress` file. On completion it deletes the marker. If the marker
exists at startup, the previous upgrade was interrupted -- install.py warns and
suggests re-running upgrade.

### Dependencies

Skills require Python packages (pydantic, etc.) that are not part of stdlib.
The installer does NOT manage virtual environments or install pip packages.
Dependencies are the user's responsibility.

After installation, install.py checks whether pydantic is importable and prints
a warning if not:

```
Warning: pydantic not found. Skills may fail at runtime.
Install with: pip3 install --user pydantic
```

A DEPENDENCIES.md in the source repo documents required packages and versions.

### Implementation Outline

```python
#!/usr/bin/env python3
"""Config installer - copies from source repo to target tool directory."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

MANIFEST_FILE = ".install-manifest.json"
MANIFEST_VERSION = 1

ALWAYS_EXCLUSIONS = {".git", ".github", "CLAUDE.md", "README.md"}
ROOT_EXCLUSIONS = {"install.py", "install.sh", ".gitignore", "LICENSE", MANIFEST_FILE}


def get_tracked_files(repo_path: Path) -> list[str]:
    """Get list of git-tracked files in repo."""
    result = subprocess.run(
        ["git", "ls-files", "--cached"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True,
    )
    return [f for f in result.stdout.strip().split("\n") if f]


def sha256_file(path: Path) -> str:
    """Compute SHA256 hash of file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def should_exclude(rel_path: str) -> bool:
    """Check if file should be excluded from installation."""
    parts = Path(rel_path).parts
    if len(parts) == 1 and parts[0] in ROOT_EXCLUSIONS:
        return True
    return any(name in parts for name in ALWAYS_EXCLUSIONS)


def load_manifest(target: Path) -> dict | None:
    """Load existing manifest or return None.

    Handles corrupted manifests gracefully: backs up the bad file and
    returns None (treated as fresh install).
    """
    manifest_path = target / MANIFEST_FILE
    if not manifest_path.exists():
        return None
    try:
        return json.loads(manifest_path.read_text())
    except json.JSONDecodeError:
        backup = manifest_path.with_suffix(".json.corrupted")
        shutil.copy2(manifest_path, backup)
        print(f"WARNING: Corrupted manifest backed up to {backup}", file=sys.stderr)
        return None


def save_manifest(target: Path, manifest: dict) -> None:
    """Atomically save manifest to target directory.

    Writes to .tmp, fsyncs, then atomic rename. A crash at any point
    leaves either the old manifest or the new one -- never partial.
    """
    manifest_path = target / MANIFEST_FILE
    tmp_path = target / f"{MANIFEST_FILE}.tmp"
    data = json.dumps(manifest, indent=2, sort_keys=True)
    with open(tmp_path, "w") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    tmp_path.rename(manifest_path)


def install(source: Path, target: Path, dry_run: bool = False) -> None:
    """Fresh install from source to target."""
    existing = load_manifest(target)
    if existing and not dry_run:
        print("ERROR: Manifest exists. Use 'upgrade' instead.", file=sys.stderr)
        sys.exit(1)

    files = get_tracked_files(source)
    manifest = {
        "version": MANIFEST_VERSION,
        "source_commit": get_head_commit(source),
        "source_path": str(source),
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "files": {},
    }

    for rel_path in files:
        if should_exclude(rel_path):
            continue

        src_file = source / rel_path
        dst_file = target / rel_path

        if dry_run:
            print(f"COPY {rel_path}")
        else:
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dst_file)
            manifest["files"][rel_path] = {
                "sha256": sha256_file(dst_file),
                "size": dst_file.stat().st_size,
            }

    if not dry_run:
        save_manifest(target, manifest)
        print(f"Installed {len(manifest['files'])} files to {target}")
        check_dependencies()


def upgrade(source: Path, target: Path, dry_run: bool, force: bool) -> None:
    """Upgrade existing installation."""
    old_manifest = load_manifest(target)
    if not old_manifest:
        print("ERROR: No manifest found. Use 'install' first.", file=sys.stderr)
        sys.exit(1)

    # Crash recovery: check for interrupted previous upgrade
    marker = target / ".upgrade-in-progress"
    if marker.exists() and not force:
        print("WARNING: Previous upgrade was interrupted.", file=sys.stderr)
        print("  Re-running upgrade. Use --force to skip this check.", file=sys.stderr)
        marker.unlink()

    if not dry_run:
        marker.write_text(datetime.now(timezone.utc).isoformat())

    new_files = set(f for f in get_tracked_files(source) if not should_exclude(f))
    old_files = set(old_manifest["files"].keys())

    to_add = new_files - old_files
    to_remove = old_files - new_files
    to_update = new_files & old_files

    conflicts = []
    new_manifest = {
        "version": MANIFEST_VERSION,
        "source_commit": get_head_commit(source),
        "source_path": str(source),
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "files": {},
    }

    # Handle updates (check for conflicts)
    for rel_path in to_update:
        dst_file = target / rel_path
        if dst_file.exists():
            current_hash = sha256_file(dst_file)
            expected_hash = old_manifest["files"][rel_path]["sha256"]
            if current_hash != expected_hash and not force:
                conflicts.append(rel_path)
                timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                backup_path = dst_file.parent / f"{dst_file.name}.bak.{timestamp}"
                if not dry_run:
                    shutil.copy2(dst_file, backup_path)
                print(f"CONFLICT {rel_path} -> backed up to {backup_path.name}")

        if dry_run:
            print(f"UPDATE {rel_path}")
        else:
            src_file = source / rel_path
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dst_file)
            new_manifest["files"][rel_path] = {
                "sha256": sha256_file(dst_file),
                "size": dst_file.stat().st_size,
            }

    # Handle additions
    for rel_path in to_add:
        if dry_run:
            print(f"ADD {rel_path}")
        else:
            src_file = source / rel_path
            dst_file = target / rel_path
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dst_file)
            new_manifest["files"][rel_path] = {
                "sha256": sha256_file(dst_file),
                "size": dst_file.stat().st_size,
            }

    # Handle removals (orphans)
    for rel_path in to_remove:
        dst_file = target / rel_path
        if dst_file.exists():
            current_hash = sha256_file(dst_file)
            expected_hash = old_manifest["files"][rel_path]["sha256"]
            if current_hash == expected_hash or force:
                if dry_run:
                    print(f"REMOVE {rel_path}")
                else:
                    dst_file.unlink()
                    cleanup_empty_dirs(dst_file.parent, target)
            else:
                print(f"SKIP REMOVE {rel_path} (modified)")

    if not dry_run:
        save_manifest(target, new_manifest)
        marker.unlink(missing_ok=True)
        print(f"Upgraded: {len(to_add)} added, {len(to_update)} updated, {len(to_remove)} removed")
        if conflicts:
            print(f"Conflicts: {len(conflicts)} files backed up")


def uninstall(target: Path, dry_run: bool, force: bool) -> None:
    """Remove all managed files."""
    manifest = load_manifest(target)
    if not manifest:
        print("ERROR: No manifest found.", file=sys.stderr)
        sys.exit(1)

    removed = 0
    skipped = 0

    for rel_path, info in manifest["files"].items():
        dst_file = target / rel_path
        if not dst_file.exists():
            continue

        current_hash = sha256_file(dst_file)
        if current_hash == info["sha256"] or force:
            if dry_run:
                print(f"REMOVE {rel_path}")
            else:
                dst_file.unlink()
                cleanup_empty_dirs(dst_file.parent, target)
            removed += 1
        else:
            print(f"SKIP {rel_path} (modified)")
            skipped += 1

    if not dry_run:
        (target / MANIFEST_FILE).unlink(missing_ok=True)
        print(f"Uninstalled: {removed} removed, {skipped} skipped (modified)")


def cleanup_empty_dirs(dir_path: Path, stop_at: Path) -> None:
    """Remove empty directories up to stop_at."""
    while dir_path != stop_at and dir_path.is_dir():
        try:
            dir_path.rmdir()  # Fails if not empty
            dir_path = dir_path.parent
        except OSError:
            break


def get_head_commit(repo: Path) -> str:
    """Get current HEAD commit hash."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def check_dependencies() -> None:
    """Warn if runtime dependencies are missing."""
    try:
        import importlib
        importlib.import_module("pydantic")
    except ImportError:
        print()
        print("WARNING: pydantic not found. Skills may fail at runtime.")
        print("  Install with: pip3 install --user pydantic")


def main():
    parser = argparse.ArgumentParser(description="AI coding tool config installer")
    parser.add_argument("command", choices=["install", "upgrade", "uninstall"])
    parser.add_argument("--dry-run", action="store_true", help="Preview without changes")
    parser.add_argument("--force", action="store_true", help="Override conflict detection")
    parser.add_argument("--keep-local", action="store_true", help="Skip conflicting files")
    parser.add_argument("--source", type=Path, help="Source repo path")
    parser.add_argument("--target", type=Path, default=Path.home() / ".claude",
                        help="Target directory (default: ~/.claude)")
    args = parser.parse_args()

    source = args.source or Path(__file__).parent

    if args.command == "install":
        install(source, args.target, args.dry_run)
    elif args.command == "upgrade":
        upgrade(source, args.target, args.dry_run, args.force)
    elif args.command == "uninstall":
        uninstall(args.target, args.dry_run, args.force)


if __name__ == "__main__":
    main()
```

## Workflow After Implementation

```bash
# Initial setup via curl (one time)
curl -L https://raw.github.com/solatis/claude-config/main/install.sh | bash

# Or clone manually and install
git clone git@github.com:solatis/claude-config.git ~/.local/share/claude-config
cd ~/.local/share/claude-config
./install.sh

# Install to multiple tools
./install.sh --target ~/.claude/ --target ~/.codex/ --target ~/.gemini/

# Development cycle
cd ~/.local/share/claude-config
# ... edit skills, test locally ...
git add -A && git commit -m "Fix planner step 7"
./install.sh                       # auto-detects upgrade

# Upgrade via curl (pulls latest, upgrades)
curl -L https://raw.github.com/solatis/claude-config/main/install.sh | bash

# If something breaks badly
python3 install.py uninstall --target ~/.claude
# Now ~/.claude/ has no skills, safe to debug
```

## Consensus Source

This plan was developed through:

1. Codebase analysis of `~/.claude/` revealing 372 tracked files, `parents[N]` path dependencies at varying depths, and clear separation between distributable and user-specific files.

2. Multi-model consensus (Gemini Pro 3, GPT-5.2, GPT-5.1-Codex) with unanimous agreement on:
   - Manifest-based copying as correct architecture
   - SHA256 hashes mandatory for conflict detection
   - Conservative conflict policy with backups
   - Dry-run mode essential for safety

3. Post-hoc audit (2026-02-08) identified and fixed:
   - Exclusion logic bug: original `should_exclude` matched CLAUDE.md at any depth, incorrectly excluding 43 skill-level context files. Redesigned as two-tier exclusion (ALWAYS_EXCLUSIONS + ROOT_EXCLUSIONS).
   - Missing MANIFEST_FILE from exclusions (circular overwrite risk).
   - Backup path construction: made explicit with `dst_file.parent / name`.
   - Inaccurate parents[4] description: different files resolve to different ancestors depending on depth. Corrected documentation.
   - Multi-tool scope: generalized from Claude Code-only to support Gemini, Codex, Ampcode, Pi as additional targets via `--target`.
   - CLAUDE.md and README.md reclassified as dev-only artifacts, excluded from installation at all depths.

4. Architecture revision (2026-02-08): Restructured from single Python installer to two-layer architecture (install.sh + install.py):
   - install.sh as primary entry point supporting `curl | bash` bootstrap pattern
   - install.sh handles repo acquisition (clone/pull), prerequisite checks, multi-target loop
   - install.py handles all manifest operations (unchanged core logic)
   - Added crash safety: atomic manifest writes (tmp + fsync + rename), upgrade-in-progress marker
   - Added corrupted manifest recovery (backup + treat as fresh install)
   - Added post-install dependency verification (pydantic import check)
   - Added install.sh to ROOT_EXCLUSIONS
   - Confirmed parents[N] is depth-based, not name-based -- multi-tool installs work without modification
   - Per-target manifests: each tool directory maintains independent state
   - No venv management: system Python with documented dependencies

Confidence: 8-9/10 across all models.
