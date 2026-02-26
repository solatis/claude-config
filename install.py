#!/usr/bin/env python3
"""Config installer - copies from source repo to target tool directory."""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

MANIFEST_FILE = ".install-manifest.json"
MANIFEST_VERSION = 1

ALWAYS_EXCLUSIONS = {".git", ".github", "CLAUDE.md", "README.md"}
ROOT_EXCLUSIONS = {"install.py", "install.sh", ".gitignore", "LICENSE", "manifest-plan.md", MANIFEST_FILE}

TOOL_PROFILES = {
    "claude": {
        "CONFIG_DIR": ".claude",
        "SKILLS_DIR": ".claude/skills/scripts",
        "MODEL_STRONG": "opus",
        "MODEL_GENERAL_PURPOSE": "sonnet",
        "MODEL_CHEAP": "haiku",
    },
    "pi": {
        "CONFIG_DIR": ".pi/agent",
        "SKILLS_DIR": ".pi/agent/skills/scripts",
        "MODEL_STRONG": "claude-opus-4-6",
        "MODEL_GENERAL_PURPOSE": "claude-sonnet-4-6",
        "MODEL_CHEAP": "claude-haiku-4-5",
    },
}

TEMPLATE_PATTERN = re.compile(r"\{\{(\w+)\}\}")
TEMPLATE_EXTENSIONS = {".md", ".yaml", ".yml"}


def process_templates(content: str, variables: dict) -> str:
    """Replace {{VAR}} placeholders with tool-specific values.

    Only processes known variables -- unknown {{FOO}} patterns pass through
    unchanged. This prevents corruption of content that happens to contain
    double braces (e.g., Jinja templates in documentation).
    """
    def replace(m):
        key = m.group(1)
        return variables.get(key, m.group(0))
    return TEMPLATE_PATTERN.sub(replace, content)


def copy_file(src: Path, dst: Path, variables: dict) -> None:
    """Copy file, applying template substitution for text files."""
    if src.suffix in TEMPLATE_EXTENSIONS:
        content = src.read_text()
        processed = process_templates(content, variables)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(processed)
        shutil.copystat(src, dst)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


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


def hash_content(src: Path, variables: dict) -> str:
    """Compute SHA256 of file content as it would be installed.

    Applies template substitution for eligible file types, matching
    the transformation that copy_file() performs. This enables dry-run
    to detect whether an upgrade would actually change a file.
    """
    if src.suffix in TEMPLATE_EXTENSIONS:
        content = src.read_text()
        processed = process_templates(content, variables)
        return hashlib.sha256(processed.encode()).hexdigest()
    return sha256_file(src)


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


def install(source: Path, target: Path, dry_run: bool = False, variables: dict = None) -> None:
    """Fresh install from source to target."""
    if variables is None:
        variables = {}
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

    for rel_path in sorted(files):
        if should_exclude(rel_path):
            continue

        src_file = source / rel_path
        dst_file = target / rel_path

        if dry_run:
            print(f"NEW {dst_file}")
        else:
            copy_file(src_file, dst_file, variables)
            manifest["files"][rel_path] = {
                "sha256": sha256_file(dst_file),
                "size": dst_file.stat().st_size,
            }

    if not dry_run:
        save_manifest(target, manifest)
        print(f"Installed {len(manifest['files'])} files to {target}")
        check_dependencies()


def upgrade(source: Path, target: Path, dry_run: bool, force: bool, variables: dict = None) -> None:
    """Upgrade existing installation."""
    if variables is None:
        variables = {}
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
    updated = 0
    new_manifest = {
        "version": MANIFEST_VERSION,
        "source_commit": get_head_commit(source),
        "source_path": str(source),
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "files": {},
    }

    # Handle updates (check for conflicts, skip unchanged)
    for rel_path in sorted(to_update):
        src_file = source / rel_path
        dst_file = target / rel_path

        src_hash = hash_content(src_file, variables)
        old_hash = old_manifest["files"][rel_path]["sha256"]
        changed = src_hash != old_hash

        if not changed:
            if not dry_run:
                new_manifest["files"][rel_path] = old_manifest["files"][rel_path]
            continue

        if dst_file.exists():
            current_hash = sha256_file(dst_file)
            if current_hash != old_hash and not force:
                conflicts.append(rel_path)
                if dry_run:
                    print(f"CONFLICT {dst_file} (would back up)")
                else:
                    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                    backup_path = dst_file.parent / f"{dst_file.name}.bak.{timestamp}"
                    shutil.copy2(dst_file, backup_path)
                    print(f"CONFLICT {dst_file} -> backed up to {backup_path}")

        if dry_run:
            print(f"UPDATE {dst_file}")
        else:
            copy_file(src_file, dst_file, variables)
            new_manifest["files"][rel_path] = {
                "sha256": sha256_file(dst_file),
                "size": dst_file.stat().st_size,
            }
        updated += 1

    # Handle additions
    for rel_path in sorted(to_add):
        src_file = source / rel_path
        dst_file = target / rel_path
        if dry_run:
            print(f"NEW {dst_file}")
        else:
            copy_file(src_file, dst_file, variables)
            new_manifest["files"][rel_path] = {
                "sha256": sha256_file(dst_file),
                "size": dst_file.stat().st_size,
            }

    # Handle removals (orphans)
    for rel_path in sorted(to_remove):
        dst_file = target / rel_path
        if dst_file.exists():
            current_hash = sha256_file(dst_file)
            expected_hash = old_manifest["files"][rel_path]["sha256"]
            if current_hash == expected_hash or force:
                if dry_run:
                    print(f"REMOVE {dst_file}")
                else:
                    dst_file.unlink()
                    cleanup_empty_dirs(dst_file.parent, target)
            else:
                print(f"SKIP REMOVE {rel_path} (modified)")

    total_changes = updated + len(to_add) + len(to_remove)

    if total_changes == 0:
        if not dry_run:
            save_manifest(target, new_manifest)
            marker.unlink(missing_ok=True)
        print("Nothing to do (all files up to date)")
        return

    if not dry_run:
        save_manifest(target, new_manifest)
        marker.unlink(missing_ok=True)
        print(f"Upgraded: {len(to_add)} added, {updated} updated, {len(to_remove)} removed")
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

    for rel_path, info in sorted(manifest["files"].items()):
        dst_file = target / rel_path
        if not dst_file.exists():
            continue

        current_hash = sha256_file(dst_file)
        if current_hash == info["sha256"] or force:
            if dry_run:
                print(f"REMOVE {dst_file}")
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
    parser.add_argument("--force", action="store_true",
                        help="Overwrite locally-modified files without backup; "
                             "remove orphans even if modified")
    parser.add_argument("--source", type=Path, help="Source repo path")
    parser.add_argument("--target", type=Path, required=True,
                        help="Target directory (e.g. ~/.claude, ~/.pi/agent)")
    parser.add_argument("--tool", choices=list(TOOL_PROFILES.keys()), required=True,
                        help="Target tool profile for template substitution")
    args = parser.parse_args()

    args.target = args.target.expanduser().resolve()

    source = args.source or Path(__file__).parent
    variables = TOOL_PROFILES[args.tool]

    if args.command in ("install", "upgrade") and not source.is_dir():
        print(f"ERROR: Source directory not found: {source}", file=sys.stderr)
        sys.exit(1)

    if args.command == "install":
        install(source, args.target, args.dry_run, variables)
    elif args.command == "upgrade":
        upgrade(source, args.target, args.dry_run, args.force, variables)
    elif args.command == "uninstall":
        uninstall(args.target, args.dry_run, args.force)


if __name__ == "__main__":
    main()
