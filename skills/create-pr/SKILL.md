---
name: create-pr
description: Invoke IMMEDIATELY when user requests PR creation, opening a pull request, making a PR, submitting changes for review, or pushing and creating a PR. Use for ANY pull request workflow.
---

You are creating a pull request that follows repository conventions.

## Pre-flight Checks (STOP if any fail)

1. Branch is pushed to remote. If not: `git push -u origin <branch>` first
2. Working tree is clean. If uncommitted changes: warn user, ask whether to proceed
3. Not on main/master. If on main: STOP, ask user to create feature branch

## Step 1: Read Template

Read the template file using the Read tool:
1. Try `.github/pull_request_template.md`
2. If not found, try `.github/PULL_REQUEST_TEMPLATE.md`
3. If neither exists, ask: "No PR template found. What sections should the PR include?"

Extract the section headers from the template. You will fill each section in Step 4.

## Step 2: Gather Context

Run these commands and extract key information:
- `git remote get-url origin | sed 's|.*github.com[:/]||; s|\.git$||'` → Repository (use for API calls)
- `git log main..HEAD --oneline` → List of commits (use for description)
- `git diff main --stat` → Files changed (use for scope summary)
- Check for plan files: `*.md` in working directory matching ticket ID

## Step 3: Resolve Ticket Links

For each ticket ID found (PIVOT-XXXXX, PEE-XXXXX), query Notion to get the correct URL.

| Ticket Type | data_source_id |
|-------------|----------------|
| PIVOT-XXXXX | `22b439f9-8a4a-494e-ade6-f9b141528f43` |
| PEE-XXXXX | `e30e85f0-0785-44a7-918f-8072879c1b05` |

Query filter: `{"property": "ID", "unique_id": {"equals": XXXXX}}`

Extract the `url` field from the query result.

**Fallback**: If a ticket is not found in Notion, ask the user for the correct URL.

## Step 4: Create PR Body

For each section header from the template:
- **Description section**: Summarize what changed and why (from commits)
- **Related section**: Link ticket IDs found in branch name or commits

If a plan file exists, embed it:
```
<details>
<summary>Implementation Plan</summary>

[plan content]

</details>
```

## Step 5: Create PR

Use the GitHub API to create the PR (do NOT use `gh pr create` - it may be blocked by hooks):

```bash
gh api repos/{owner}/{repo}/pulls -X POST \
  -f title="[TICKET-ID] Title" \
  -f head="{branch}" \
  -f base="main" \
  -f draft=true \
  -f body="$(cat /tmp/pr-body.md)"
```

Write the PR body to `/tmp/pr-body.md` first, then use the command above.

Default to `draft=true`. Only set `draft=false` if user explicitly requested the PR be ready for review.

## Error Handling

These errors are expected and recoverable:
- **PR already exists**: Update via API: `gh api repos/{owner}/{repo}/pulls/{number} -X PATCH -f body="$(cat /tmp/pr-body.md)"`
- **Branch not pushed**: Run `git push -u origin <branch>`, then retry PR creation
- **Hook blocks command**: If you see "SKILL ENFORCED" error, you used a blocked command (`gh pr create`, `gh pr edit`). Use `gh api` instead.
