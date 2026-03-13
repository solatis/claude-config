# Default Conventions

These conventions apply when project documentation does not specify otherwise.

## Priority Hierarchy

Higher tiers override lower. Cite backing source when auditing.

| Tier | Source          | Action                           |
| ---- | --------------- | -------------------------------- |
| 1    | user-specified  | Explicit user instruction: apply |
| 2    | doc-derived     | project index file / project docs: apply  |
| 3    | default-derived | This document: apply             |
| 4    | assumption      | No backing: CONFIRM WITH USER    |

## Severity Levels

See `severity.md` for full definitions.

| Level  | Meaning                  |
| ------ | ------------------------ |
| MUST   | Unrecoverable if missed  |
| SHOULD | Maintainability debt     |
| COULD  | Auto-fixable, low impact |

---

## Structural Conventions

<default-conventions domain="god-object">
**God Object**: >15 public methods OR >10 dependencies OR mixed concerns (networking + UI + data)
Severity: SHOULD
</default-conventions>

<default-conventions domain="god-function">
**God Function**: >50 lines OR multiple abstraction levels OR >3 nesting levels
Severity: SHOULD
Exception: Inherently sequential algorithms or state machines
</default-conventions>

<default-conventions domain="duplicate-logic">
**Duplicate Logic**: Copy-pasted blocks, repeated error handling, parallel near-identical functions
Severity: SHOULD
</default-conventions>

<default-conventions domain="dead-code">
**Dead Code**: No callers, impossible branches, unread variables, unused imports
Severity: COULD
</default-conventions>

<default-conventions domain="inconsistent-error-handling">
**Inconsistent Error Handling**: Mixed exceptions/error codes, inconsistent types, swallowed errors
Severity: SHOULD
Exception: Project specifies different handling per error category
</default-conventions>

---

## File Organization Conventions

<default-conventions domain="test-organization">
**Test Organization**: Extend existing test files; create new only when:
- Distinct module boundary OR >500 lines OR different fixtures required
Severity: SHOULD (for unnecessary fragmentation)
</default-conventions>

<default-conventions domain="file-creation">
**File Creation**: Prefer extending existing files; create new only when:
- Clear module boundary OR >300-500 lines OR distinct responsibility
Severity: COULD
</default-conventions>

---

## Testing Conventions

<default-conventions domain="testing">
**Principle**: Test behavior, not implementation. Fast feedback.

**Test Type Hierarchy** (preference order):

1. **Integration tests** (highest value)
   - Test end-user verifiable behavior
   - Use real systems/dependencies (e.g., testcontainers)
   - Verify component interaction at boundaries
   - This is where the real value lies

2. **Property-based / generative tests** (preferred)
   - Cover wide input space with invariant assertions
   - Catch edge cases humans miss
   - Use for functions with clear input/output contracts

3. **Unit tests** (use sparingly)
   - Only for highly complex or critical logic
   - Risk: maintenance liability, brittleness to refactoring
   - Prefer integration tests that cover same behavior

**Test Placement**: Tests are part of implementation milestones, not separate
milestones. A milestone is not complete until its tests pass. This creates fast
feedback during development.

**DO**:

- Integration tests with real dependencies (testcontainers, etc.)
- Property-based tests for invariant-rich functions
- Parameterized fixtures over duplicate test bodies
- Test behavior observable by end users

**DON'T**:

- Test external library/dependency behavior (out of scope)
- Unit test simple code (maintenance liability exceeds value)
- Mock owned dependencies (use real implementations)
- Test implementation details that may change
- One-test-per-variant when parametrization applies

Severity: SHOULD (violations), COULD (missed opportunities)
</default-conventions>

---

## Modernization Conventions

<default-conventions domain="version-constraints">
**Version Constraint Violation**: Features unavailable in project's documented target version
Requires: Documented target version
Severity: SHOULD
</default-conventions>

<default-conventions domain="modernization">
**Modernization Opportunity**: Legacy APIs, verbose patterns, manual stdlib reimplementations
Severity: COULD
Exception: Project requires legacy pattern
</default-conventions>

---

## Testing Strategy Defaults

<default-conventions domain="testing-strategy">
**Default Test Type Preferences** (apply when project docs silent):

| Type        | Default Strategy            | Rationale                 |
| ----------- | --------------------------- | ------------------------- |
| Unit        | Property-based (quickcheck) | Few tests, many variables |
| Integration | Behavior-focused, real deps | End-user verifiable       |
| E2E         | Generated datasets          | Deterministic replay      |

These are Tier 3 defaults. User confirmation (Tier 1) overrides.

Severity: TESTING_STRATEGY_VIOLATION (SHOULD) if contradicted without override.
</default-conventions>
