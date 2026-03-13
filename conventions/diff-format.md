# Unified Diff Format for Plan Code Changes

This document is the authoritative specification for code changes in implementation plans.

## Purpose

Unified diff format encodes both **location** and **content** in a single structure. This eliminates the need for location directives in comments (e.g., "insert at line 42") and provides reliable anchoring even when line numbers drift.

## Anatomy

```diff
--- a/path/to/file.py
+++ b/path/to/file.py
@@ -123,6 +123,15 @@ def existing_function(ctx):
    # Context lines (unchanged) serve as location anchors
    existing_code()

+   # NEW: Comments explain WHY - transcribed verbatim by Developer
+   # Guard against race condition when messages arrive out-of-order
+   new_code()

    # More context to anchor the insertion point
    more_existing_code()
```

## Components

| Component                                  | Authority                 | Purpose                                                    |
| ------------------------------------------ | ------------------------- | ---------------------------------------------------------- |
| File path (`--- a/path/to/file.py`)        | **AUTHORITATIVE**         | Exact target file                                          |
| Line numbers (`@@ -123,6 +123,15 @@`)      | **APPROXIMATE**           | May drift as earlier milestones modify the file            |
| Function context (`@@ ... @@ def func():`) | **SCOPE HINT**            | Function/method containing the change                      |
| Context lines (unchanged)                  | **AUTHORITATIVE ANCHORS** | Developer matches these patterns to locate insertion point |
| `+` lines                                  | **NEW CODE**              | Code to add, including WHY comments                        |
| `-` lines                                  | **REMOVED CODE**          | Code to delete                                             |

## Two-Layer Location Strategy

Code changes use two complementary layers for location:

1. **Prose scope hint** (optional): Natural language describing conceptual location
2. **Diff with context**: Precise insertion point via context line matching

### Layer 1: Prose Scope Hints

For complex changes, add a prose description before the diff block:

````markdown
Add validation after input sanitization in `UserService.validate()`:

```diff
@@ -123,6 +123,15 @@ def validate(self, user):
     sanitized = sanitize(user.input)

+    # Validate format before proceeding
+    if not is_valid_format(sanitized):
+        raise ValidationError("Invalid format")
+
     return process(sanitized)
`` `
```
````

The prose tells Developer **where conceptually** (which method, what operation precedes it). The diff tells Developer **where exactly** (context lines to match).

**When to use prose hints:**

- Changes to large files (>300 lines)
- Multiple changes to the same file in one milestone
- Complex nested structures where function context alone is ambiguous
- When the surrounding code logic matters for understanding placement

**When prose is optional:**

- Small files with obvious structure
- Single change with unique context lines
- Function context in @@ line provides sufficient scope

### Layer 2: Function Context in @@ Line

The `@@` line can include function/method context after the line numbers:

```diff
@@ -123,6 +123,15 @@ def validate(self, user):
```

This follows standard unified diff format (git generates this automatically). It tells Developer which function contains the change, aiding navigation even when line numbers drift.

## Why Context Lines Matter

When a plan has multiple milestones that modify the same file, earlier milestones shift line numbers. The `@@ -123` in Milestone 3 may no longer be accurate after Milestones 1 and 2 execute.

**Context lines solve this**: Developer searches for the unchanged context patterns in the actual file. These patterns are stable anchors that survive line number drift.

Include 2-3 context lines before and after changes for reliable matching.

## Comment Placement

Comments in `+` lines explain **WHY**, not **WHAT**. These comments:

- Are transcribed verbatim by Developer
- Source rationale from Planning Context (Decision Log, Rejected Alternatives)
- Use concrete terms without hidden baselines
- Must pass temporal contamination review (see `conventions/temporal.md`)

**Important**: Comments written during planning often contain temporal contamination -- change-relative language, baseline references, or location directives. @agent-technical-writer reviews and fixes these before @agent-developer transcribes them.

<example type="CORRECT" category="why_comment">
```diff
+   # Polling chosen over webhooks: 30% webhook delivery failures in third-party API
+   # WebSocket rejected to preserve stateless architecture
+   updates = poll_api(interval=30)
```
Explains WHY this approach was chosen.
</example>

<example type="INCORRECT" category="what_comment">
```diff
+   # Poll the API every 30 seconds
+   updates = poll_api(interval=30)
```
Restates WHAT the code does - redundant with the code itself.
</example>

<example type="INCORRECT" category="hidden_baseline">
```diff
+   # Generous timeout for slow networks
+   REQUEST_TIMEOUT = 60
```
"Generous" compared to what? Hidden baseline provides no actionable information.
</example>

<example type="CORRECT" category="concrete_justification">
```diff
+   # 60s accommodates 95th percentile upstream response times
+   REQUEST_TIMEOUT = 60
```
Concrete justification that explains why this specific value.
</example>

## Location Directives: Forbidden

The diff structure handles location. Location directives in comments are redundant and error-prone.

<example type="INCORRECT" category="location_directive">
```python
# Insert this BEFORE the retry loop (line 716)
# Timestamp guard: prevent older data from overwriting newer
get_ctx, get_cancel = context.with_timeout(ctx, 500)
```
Location directive leaked into comment - line numbers become stale.
</example>

<example type="CORRECT" category="location_directive">
```diff
@@ -714,6 +714,10 @@ def put(self, ctx, tags):
    for tag in tags:
        subject = tag.subject

-       # Timestamp guard: prevent older data from overwriting newer
-       # due to network delays, retries, or concurrent writes
-       get_ctx, get_cancel = context.with_timeout(ctx, 500)

        # Retry loop for Put operations
        for attempt in range(max_retries):

```
Context lines (`for tag in tags`, `# Retry loop`) are stable anchors that survive line number drift.
</example>

## When to Use Diff Format

<diff_format_decision>

| Code Characteristic                     | Use Diff? | Boundary Test                            |
| --------------------------------------- | --------- | ---------------------------------------- |
| Conditionals, loops, error handling,    | YES       | Has branching logic                      |
| state machines                          |           |                                          |
| Multiple insertions same file           | YES       | >1 change location                       |
| Deletions or replacements               | YES       | Removing/changing existing code          |
| Pure assignment/return (CRUD, getters)  | NO        | Single statement, no branching           |
| Boilerplate from template               | NO        | Developer can generate from pattern name |

The boundary test: "Does Developer need to see exact placement and context to implement correctly?"

- YES -> diff format
- NO (can implement from description alone) -> prose sufficient

</diff_format_decision>

## Validation Checklist

Before finalizing code changes in a plan:

- [ ] File path is exact (not "auth files" but `src/auth/handler.py`)
- [ ] Context lines exist in target file (validate patterns match actual code)
- [ ] Comments explain WHY, not WHAT
- [ ] No location directives in comments
- [ ] No hidden baselines (test: "[adjective] compared to what?")
- [ ] 2-3 context lines for reliable anchoring
```
