<!-- applicable_phases: diff_review, codebase_review, refactor_code -->

# Patterns & Idioms

Evaluate whether code uses idiomatic patterns for its language.

**The core question**: Is this idiomatic? Modern languages provide features to simplify common patterns. When code uses outdated patterns, verbose anti-patterns, or unnecessarily complex expressions, it adds cognitive load without benefit.

**What to look for**:

- Complex boolean expressions requiring mental evaluation
- Verbose conditional patterns with simpler equivalents
- Outdated iteration/callback patterns
- Commented code blocks and unreachable branches (within files)
- Missing language features that would simplify code

**The threshold**: Flag mechanical anti-patterns and expression-level complexity that obscures intent. Well-commented complex logic is acceptable; unnecessarily complex logic is not. Only flag outdated patterns when a clearly better modern idiom exists in the project's language version.

<design-mode>
Not applicable -- this group requires actual code to evaluate.
</design-mode>

<code-mode>
When evaluating actual code (Diff Review, Codebase Review, Refactor):

- Are boolean expressions readable at a glance?
- Do conditionals use simpler equivalent forms?
- Are modern language features being utilized?
- Is commented code cluttering the file?

Evidence format: Quote code with file:line showing the issue.
</code-mode>

---

## 1. Boolean Expression Complexity

<principle>
A boolean expression should be readable at a glance. If it requires mental evaluation to understand, it needs simplification or naming.
</principle>

Detect: Can I understand this boolean expression without tracing through it mentally?

<grep-hints>
Pattern indicators (starting points, not definitive):
`and.*and`, `or.*or`, `&&.*&&`, `||.*||`, `not.*not`, `!.*!`
</grep-hints>

<violations>
Illustrative patterns (not exhaustive -- similar violations exist):

[medium] Cognitive overload

- Multi-clause expressions (3+ AND/OR terms -> extract named predicate)
- Negated compound conditions (e.g., not (a and b) -> clearer positive form)
- Any expression requiring paper/mental tracing to evaluate

[low] Ambiguity

- Mixed AND/OR without parentheses clarifying precedence
- Double/triple negatives (e.g., if not disabled, if not is_invalid)
  </violations>

<exceptions>
Complex conditions with clear structure and comments explaining the logic.
</exceptions>

<threshold>
Flag when expression requires mental evaluation to understand. Well-commented complex conditions are acceptable.
</threshold>

## 2. Conditional Anti-Patterns

<principle>
Conditions should express intent directly. When a simpler form exists that preserves meaning, the complex form is an anti-pattern.
</principle>

Detect: Is there a simpler way to express this condition that preserves the same meaning?

<grep-hints>
Pattern indicators (starting points, not definitive):
`if.*return true.*else.*return false`, `rescue; end` / empty `catch` block, `&&` side effects
</grep-hints>

<violations>
Illustrative patterns (not exhaustive -- similar violations exist):

[medium] Verbose patterns

- `if cond; return true; else; return false; end` (just return cond)
- Exception-based control flow (rescue/catch as if/else)
- Any condition with a simpler equivalent form

[low] Subtle complexity

- Short-circuit side effects (e.g., `cond && do_thing()`)
- Yoda conditions without clear benefit (e.g., `if 5 == x`)
  </violations>

<exceptions>
Exception handling for actual exceptional conditions. Short-circuit for lazy evaluation.
</exceptions>

<threshold>
Flag mechanical anti-patterns only. Intent-preserving variations are style preferences.
</threshold>

## 3. Modern Idioms

<principle>
Modern language features exist to simplify common patterns. When older patterns persist unnecessarily, they add cognitive load without benefit.
</principle>

Detect: Is there a newer language feature that would simplify this code? Is the project's language version being underutilized?

<grep-hints>
Pattern indicators (starting points, not definitive):
`.each_with_index`, old-style `for` loops (Ruby), `+ ` string concat (Ruby/TypeScript), `sprintf`/`%` formatting (Ruby), `new Promise(` callback patterns (TypeScript), `nil` checks (Ruby), `null`/`undefined` checks (TypeScript)
</grep-hints>

<violations>
Illustrative patterns (not exhaustive -- similar violations exist):

[medium] Outdated patterns

- Old iteration patterns (e.g., manual index loops -> `.each`, `.map`, `.each_with_index`)
- Deprecated API usage
- Any pattern with a simpler modern equivalent

[low] Missing features

- Missing language features (e.g., no destructuring, no pattern matching)
- Legacy patterns (e.g., callbacks -> async/await, Promises -> async/await)
- Outdated idioms (e.g., string concatenation -> `"#{interpolation}"` / template literals)
- Manual nil/null checks (-> `&.` safe navigation (Ruby), optional chaining `?.` / `??` (TypeScript))
  </violations>

<exceptions>
Intentional use of older patterns for compatibility. Performance-critical code avoiding allocations.
</exceptions>

<threshold>
Flag when modern idiom is clearly better AND available in the project's language version. Do not flag style preferences.
</threshold>

## 4. Readability

<principle>
Code should be understandable in isolation. When understanding requires external lookup or tribal knowledge, the code needs clarification.
</principle>

Detect: Can I understand this code without reading other files or asking someone? Is intent clear from the code itself?

<grep-hints>
Pattern indicators (starting points, not definitive):
Boolean literals in function calls, magic numbers, unexplained constants
</grep-hints>

<violations>
Illustrative patterns (not exhaustive -- similar violations exist):

[high] Obscured intent

- Boolean trap (e.g., fn(True, False) -> fn(enabled=True, debug=False))
- Any call where argument meaning requires looking up the function signature

[medium] Magic values

- Magic numbers/strings (e.g., 42 -> MAX_RETRIES = 42)
- Positional args where named params would clarify intent

[low] Dense expressions

- Dense expressions (e.g., nested ternaries -> named intermediate variables)
- Missing WHY comments on non-obvious decisions
- Implicit ordering dependencies between calls (document or make explicit)
  </violations>

<exceptions>
Well-known constants (0, 1, -1, 100). Boolean in obviously-named function (e.g., setEnabled(true)).
</exceptions>

<threshold>
Flag when meaning requires external lookup. Self-evident code needs no comments.
</threshold>

## 5. Zombie Code (File Scope)

<principle>
Dead code is noise that misleads readers. Code that cannot execute or is never called should be removed, not left to confuse future maintainers.
</principle>

Detect: If I deleted this, would any test fail or behavior change?

<grep-hints>
Pattern indicators (starting points, not definitive):
Commented blocks, `=begin`/`=end` blocks (Ruby), unreachable branches, unused variables
</grep-hints>

<violations>
Illustrative patterns (not exhaustive -- similar violations exist):

[high] Dead code blocks

- Commented-out code blocks (>5 lines of code, not documentation)
- Unreachable branches (e.g., else after unconditional return, dead switch cases)
- Any code that cannot execute

[medium] Unused declarations

- Unused local variables or parameters

[low] Orphaned functions

- Functions defined but never called within file
  </violations>

<exceptions>
Commented code with explanation (debugging aid). Unused params required by interface contract. Public API entry points. Plugin interfaces.
</exceptions>

<threshold>
Flag when code is demonstrably unreachable/unused AND is not a public API entry point, plugin interface, or documented debugging aid.
</threshold>
