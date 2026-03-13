# Plan Format

Write your plan using this structure:

```markdown
# [Plan Title]

## Overview

[Problem statement, chosen approach, and key decisions in 1-2 paragraphs]

## Planning Context

This section is consumed VERBATIM by downstream agents (Technical Writer,
Quality Reviewer). Quality matters: vague entries here produce poor annotations
and missed risks.

### Decision Log

| Decision           | Reasoning Chain                                              |
| ------------------ | ------------------------------------------------------------ |
| [What you decided] | [Multi-step reasoning: premise -> implication -> conclusion] |

Each rationale must contain at least 2 reasoning steps. Single-step rationales
are insufficient.

INSUFFICIENT: "Polling over webhooks | Webhooks are unreliable" SUFFICIENT:
"Polling over webhooks | Third-party API has 30% webhook delivery failure in
testing -> unreliable delivery would require fallback polling anyway -> simpler
to use polling as primary mechanism"

INSUFFICIENT: "500ms timeout | Matches upstream latency" SUFFICIENT: "500ms
timeout | Upstream 95th percentile is 450ms -> 500ms covers 95% of requests
without timeout -> remaining 5% should fail fast rather than queue"

Include BOTH architectural decisions AND implementation-level micro-decisions:

- Architectural: "Event sourcing over CRUD | Need audit trail + replay
  capability -> CRUD would require separate audit log -> event sourcing provides
  both natively"
- Implementation: "Mutex over channel | Single-writer case -> channel
  coordination adds complexity without benefit -> mutex is simpler with
  equivalent safety"

Technical Writer sources ALL code comments from this table. If a micro-decision
isn't here, TW cannot document it.

### Rejected Alternatives

| Alternative          | Why Rejected                                                        |
| -------------------- | ------------------------------------------------------------------- |
| [Approach not taken] | [Concrete reason: performance, complexity, doesn't fit constraints] |

Technical Writer uses this to add "why not X" context to code comments.

### Constraints & Assumptions

- [Technical: API limits, language version, existing patterns to follow]
- [Organizational: timeline, team expertise, approval requirements]
- [Dependencies: external services, libraries, data formats]
- [Default conventions applied: cite any `<default-conventions domain="...">`
  used]

### Known Risks

| Risk            | Mitigation                                    | Anchor                                     |
| --------------- | --------------------------------------------- | ------------------------------------------ |
| [Specific risk] | [Concrete mitigation or "Accepted: [reason]"] | [file:L###-L### if claiming code behavior] |

**Anchor requirement**: If mitigation claims existing code behavior ("no change
needed", "already handles X"), cite the file:line + brief excerpt that proves
the claim. Skip anchors for hypothetical risks or external unknowns.

Quality Reviewer excludes these from findings but will challenge unverified
behavioral claims.

## Invisible Knowledge

This section captures knowledge NOT deducible from reading the code alone.
Technical Writer uses this to create README.md files **in the same directory as
the affected code** during post-implementation.

**Placement principle**: Invisible knowledge must be captured CLOSE to
implementation. README.md files go in the package/directory containing the
relevant code, not in a separate documentation directory.

**Self-contained principle**: Code-adjacent documentation must be
self-contained. Do NOT reference external authoritative sources (doc/
directories, wikis, external documentation). If knowledge exists in an
authoritative source, it must be summarized in the code-adjacent README.md.
Duplication is acceptable; maintenance burden is the cost of locality.

**The test**: Would a new team member understand this from reading the source
files? If no, it belongs here.

**Categories** (not exhaustive -- apply the principle):

1. **Architectural decisions**: Component relationships, data flow, module
   boundaries
2. **Business rules**: Domain constraints that shape implementation choices
3. **System invariants**: Properties that must hold but are not enforced by
   types/compiler
4. **Historical context**: Why alternatives were rejected (links to Decision
   Log)
5. **Performance characteristics**: Non-obvious efficiency properties or
   requirements
6. **Tradeoffs**: Costs and benefits of chosen approaches

### Architecture
```

[ASCII diagram showing component relationships]

Example: User Request | v +----------+ +-------+ | Auth |---->| Cache |
+----------+ +-------+ | v +----------+ +------+ | Handler |---->| DB |
+----------+ +------+

```

### Data Flow

```

[How data moves through the system - inputs, transformations, outputs]

Example: HTTP Request --> Validate --> Transform --> Store --> Response | v Log
(async)

````

### Why This Structure

[Reasoning behind module organization that isn't obvious from file names]

- Why these boundaries exist
- What would break if reorganized differently

### Invariants

[Rules that must be maintained but aren't enforced by code]

- Ordering requirements
- State consistency rules
- Implicit contracts between components

### Tradeoffs

[Key decisions with their costs and benefits]

- What was sacrificed for what gain
- Performance vs. readability choices
- Consistency vs. flexibility choices

## Milestones

Milestone numbering starts at 1 within each plan. Use sequential integers (1, 2, 3),
not phase-prefixed numbers (2.1, 3.1) unless explicitly managing multi-phase plans.

### Milestone 1: [Name]

**Files**: [exact paths - e.g., src/auth/handler.py, not "auth files"]

**Flags** (optional):

- `flag-name`: optional focus note
- `another-flag`

| Flag | Consumer | Effect |
|------|----------|--------|
| `error-handling` | QR | Extra RULE 0 scrutiny on error paths |
| `conformance` | QR | Extra RULE 1 scrutiny on project patterns |
| `security` | QR | Focus on auth, injection, data exposure |
| `performance` | QR | Focus on hot paths, allocations, complexity |
| `needs-rationale` | TW | Add extra WHY comments from Decision Log |
| `complex-algorithm` | TW | Add Tier 5 block for non-obvious logic |

Add flags when:

- Multiple valid approaches existed -> `conformance`
- Error paths involve retries, fallbacks, recovery -> `error-handling`
- Code touches auth, user input, external data -> `security`
- Hot path or non-obvious complexity -> `performance`
- Thresholds, timeouts, magic numbers need justification -> `needs-rationale`
- Algorithm strategy not obvious from code -> `complex-algorithm`

**Requirements**:

- [Specific: "Add retry with exponential backoff", not "improve error handling"]

**Acceptance Criteria**:

- [Testable: "Returns 429 after 3 failed attempts" - QR can verify pass/fail]
- [Avoid vague: "Works correctly" or "Handles errors properly"]

**Tests** (milestone not complete until tests pass):

- **Test files**: [exact paths, e.g., tests/test_retry.py]
- **Test type**: [integration | property-based | unit] - see default-conventions
- **Backing**: [user-specified | doc-derived | default-derived]
- **Scenarios**:
  - Normal: [e.g., "successful retry after transient failure"]
  - Edge: [e.g., "max retries exhausted", "zero delay"]
  - Error: [e.g., "non-retryable error returns immediately"]

Skip tests when: user explicitly stated no tests, OR milestone is documentation-only,
OR project docs prohibit tests for this component. State skip reason explicitly.

**Code Intent** (you write this):

Describe WHAT changes are needed. Do NOT include exact code or diffs.
Do NOT read source files -- Developer handles that.

Include:
- Functions/structs to add or modify (names, purposes)
- Behavior to implement
- Key decisions (reference Decision Log entries by name)

Example:
```
**Code Intent**:
- New file `pool.go`: Pool struct with Open(), Close(), Acquire(), Release()
- Modify `config.go`: Add PoolConfig struct after existing Config
- Connection timeout: 500ms (Decision: "95th percentile latency coverage")
```

**Code Changes** (filled by Developer agent):

After plan is written, spawn Developer to convert Code Intent to unified diffs.
Developer reads actual files and produces accurate context lines.
See `conventions/diff-format.md` for diff specification.

```diff
--- a/path/to/file.py
+++ b/path/to/file.py
@@ -123,6 +123,15 @@ def existing_function(ctx):
   # Context lines (unchanged) serve as location anchors
   existing_code()

+  # WHY comment explaining rationale - transcribed verbatim by Developer
+  new_code()

   # More context to anchor the insertion point
   more_existing_code()
```

Documentation-only milestones (ALL files are .md, .rst, .txt, or project index file):
- Code Intent/Changes section states: "Documentation milestone - no code changes."
- Milestone MUST have `Delegated to:` field (typically `@agent-technical-writer`)

### Milestone N: ...

### Milestone [Last]: Documentation

**Delegated to**: @agent-technical-writer (mode: post-implementation)

**Source**: `## Invisible Knowledge` section of this plan

**Files**:

- `path/to/project index file` (index updates -- in same directory as code)
- `path/to/README.md` (if Invisible Knowledge section has content -- in same
  directory as code)

**Requirements**:

Delegate to Technical Writer. For documentation format specification:

<file working-dir="<config-root>" uri="conventions/documentation.md" />

Key deliverables:
- project index file: Pure navigation index (tabular format)
- README.md: Invisible knowledge (if IK section non-empty)

**Acceptance Criteria**:

- project index file is tabular index only (no prose sections)
- README.md exists in each directory with invisible knowledge
- README.md is self-contained (no external references)
- Architecture diagrams in README.md match plan's Invisible Knowledge section

**Source Material**: `## Invisible Knowledge` section of this plan

### Cross-Milestone Integration Tests

When integration tests require components from multiple milestones:

1. Place integration tests in the LAST milestone that provides a required
   component
2. List dependencies explicitly in that milestone's **Tests** section
3. Integration test milestone is not complete until all dependencies are
   implemented

Example:

- M1: Auth handler (property tests for auth logic)
- M2: Database layer (property tests for queries)
- M3: API endpoint (integration tests covering M1 + M2 + M3 with testcontainers)

The integration tests in M3 verify the full flow that end users would exercise,
using real dependencies. This creates fast feedback as soon as all components
exist.

## Milestone Dependencies (if applicable)

```
M1 ---> M2
   \
    --> M3 --> M4
```

Independent milestones can execute in parallel during /plan-execution.
````
