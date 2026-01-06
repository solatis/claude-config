# create-pr Skill

## Overview

Automates GitHub PR creation with proper Notion ticket linking. Solves the problem of broken or missing ticket links by querying Notion directly rather than guessing URLs.

## Architecture

The skill follows a 5-step sequential workflow:

1. **Read Template** - Load PR template from `.github/`
2. **Gather Context** - Collect repo identity, commits, file changes
3. **Resolve Ticket Links** - Query Notion for correct URLs
4. **Create PR Body** - Assemble content with embedded plans
5. **Create PR** - Submit via gh CLI (draft by default)

Steps 2 and 3 perform context gathering before any content generation, preventing hallucination of repo names or ticket URLs.

## Design Decisions

### Local Git for Repository Identity

**Decision**: Use `git remote get-url origin | sed` instead of `gh repo view`

**Rationale**:
- 65x faster (8ms vs 518ms) - verified via decision-critic analysis
- Works offline - no network dependency for context gathering
- Equally reliable - sed pattern handles SSH, HTTPS, and bare URL formats

**Alternative considered**: `gh repo view --json nameWithOwner` - rejected due to unnecessary network latency and offline failure mode.

### Notion API for Ticket Links

**Decision**: Query Notion databases directly rather than constructing URLs

**Rationale**:
- Notion URLs contain UUIDs, not predictable patterns
- PIVOT and PEE tickets live in separate Notion databases
- Prevents hallucination of incorrect URLs (e.g., Atlassian links)

### Draft PR Default

**Decision**: Always create PRs as drafts unless explicitly requested otherwise

**Rationale**: Prevents premature merges; reviewers see "Draft" status and wait for author signal.

## Invariants

### Notion Database IDs

These IDs must be kept in sync with the actual Notion workspace:

| Ticket Type | data_source_id |
|-------------|----------------|
| PIVOT-XXXXX | `22b439f9-8a4a-494e-ade6-f9b141528f43` |
| PEE-XXXXX | `e30e85f0-0785-44a7-918f-8072879c1b05` |

### URL Parsing Pattern

The sed pattern `'s|.*github.com[:/]||; s|\.git$||'` handles:
- SSH: `git@github.com:owner/repo.git` → `owner/repo`
- HTTPS: `https://github.com/owner/repo.git` → `owner/repo`
- HTTPS (no .git): `https://github.com/owner/repo` → `owner/repo`

If GitHub changes URL formats, this pattern may need updating.
