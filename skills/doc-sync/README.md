# Doc Sync

The index-file/README.md hierarchy is central to context hygiene (AGENTS.md in
Pi, CLAUDE.md in Claude Code). The index files are pure navigation tables with
"What" and "When to read" columns that help LLMs (and humans) find relevant
files without loading everything. README.md files capture invisible knowledge:
architecture decisions, design tradeoffs, and invariants that are not apparent
from reading code.

The doc-sync skill audits and synchronizes this hierarchy across a repository.

## How It Works

The skill operates in five phases:

1. **Discovery** -- Maps all directories, identifies missing or outdated
   index files (AGENTS.md/CLAUDE.md)
2. **Audit** -- Checks for drift (files added/removed but not indexed),
   misplaced content (architecture docs in index files instead of README.md)
3. **Migration** -- Moves architectural content from index files to README.md
4. **Update** -- Creates/updates indexes with proper tabular format
5. **Verification** -- Confirms complete coverage and correct structure

## When to Use

Use this skill for:

- **Bootstrapping** -- Adopting this workflow on an existing repository
- **After bulk changes** -- Major refactors, directory restructuring
- **Periodic audits** -- Checking for documentation drift
- **Onboarding** -- Before starting work on an unfamiliar codebase

If you use the planning workflow consistently, the technical writer agent
maintains documentation as part of execution. As such, doc-sync is primarily for
bootstrapping or recovery -- not routine use.

## Example Usage

```
Use your doc-sync skill to synchronize documentation across this repository
```

For targeted updates:

```
Use your doc-sync skill to update documentation in src/validators/
```
