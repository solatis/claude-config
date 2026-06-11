<!-- applicable_phases: design_review, diff_review, codebase_review, refactor_design, refactor_code -->

# Structure & Composition

Evaluate whether code is well-structured for comprehension and change.

**The core question**: Can I understand this unit in isolation? Can I change it without understanding its dependents? Structure should reveal intent and isolate concerns.

**What to look for**:

- Functions doing multiple things (requires "and" to describe)
- Deep nesting obscuring control flow
- Implicit state machines hidden in boolean flags
- Hard-coded dependencies making code untestable
- Component definitions scattered across multiple locations
- Error handling that loses information

**The threshold**: Flag when structure obscures intent or when changes would ripple unnecessarily. Length alone is not a smell; unclear responsibility is.

<design-mode>
When evaluating Code Intent (Design Review phase):

- Does the proposed function do one thing or multiple things?
- Does the intent describe clear responsibility boundaries?
- Does the design inject dependencies or hardcode them?
- Is the component's definition complete in one place, or scattered across locations?

Evidence format: Quote the Code Intent description showing structural issue.
</design-mode>

<code-mode>
When evaluating actual code (Diff Review, Codebase Review, Refactor):

- Is the function too long or deeply nested?
- Are boolean flags creating implicit state machines?
- Is error handling preserving context?
- Are component definitions scattered (requirements in one place, validation in another)?

Evidence format: Quote code with file:line showing the issue.
</code-mode>

---

## 1. Function Composition

<principle>
A function should do one thing that can be described in a single sentence. When description requires "and", the function likely needs splitting.
</principle>

Detect: Can I describe this function's purpose in one sentence without using "and"?

<grep-hints>
Structural indicators (starting points, not definitive):
Functions >50 lines, parameter counts >4
</grep-hints>

<violations>
Illustrative patterns (not exhaustive -- similar violations exist):

[high] Responsibility diffusion

- God functions (multiple unrelated responsibilities)
- Long parameter lists (4+ params signals missing concept)
- Any function requiring multiple sentences to describe its purpose

[medium] Structural complexity

- Deep nesting (3+ levels of conditionals)
- Mixed abstraction levels (high-level orchestration mixed with low-level details)

[low] Interface friction

- Boolean parameters that fork behavior (consider splitting into two functions)
  </violations>

<exceptions>
Long functions that do one thing linearly (e.g., state machine, parser). Nesting depth from error handling.
</exceptions>

<threshold>
Flag when function has multiple unrelated responsibilities. Length alone is not a smell.
</threshold>

## 2. Control Flow Smells

<principle>
Control flow should reveal intent, not obscure it. When following execution requires significant mental effort, the structure needs simplification.
</principle>

Detect: Is the control flow harder to follow than necessary? Would a reader need to trace through multiple branches to understand behavior?

<grep-hints>
Pattern indicators (starting points, not definitive):
`elsif.*elsif.*elsif` (Ruby), `else if.*else if` (TypeScript), `switch`, `case`, `? :.*? :`, ternary chains
</grep-hints>

<violations>
Illustrative patterns (not exhaustive -- similar violations exist):

[high] Excessive branching

- Long if/elif chains (5+ branches -> lookup table or strategy pattern)
- Any branching structure that requires tracing to understand

[medium] Obscured flow

- Nested ternaries (2+ levels -> extract to named variables)
- Early-return candidates buried in nested else branches

[low] Hidden complexity

- Conditional assignment cascades
- Implicit else branches hiding edge cases
  </violations>

<exceptions>
Exhaustive pattern matching. State machines with explicit states.
</exceptions>

<threshold>
Flag when control flow obscures intent. Explicit branching for documented cases is acceptable.
</threshold>

## 3. State and Flags

<principle>
Boolean flags that interact create implicit state machines. When understanding state requires tracking multiple flags, make the state machine explicit.
</principle>

Detect: Are boolean flags creating implicit state machines? Do flags interact in ways that require mental tracking?

<grep-hints>
Pattern indicators (starting points, not definitive):
`is_.*=`, `has_.*=`, `_flag`, `_state`, multiple boolean assignments
</grep-hints>

<violations>
Illustrative patterns (not exhaustive -- similar violations exist):

[high] Implicit state machines

- Boolean flag tangles (3+ flags interacting = implicit state machine)
- Any flag interaction requiring mental state tracking

[medium] Order dependencies

- Stateful conditionals depending on mutation order

[low] Defensive complexity

- Defensive null chains (e.g., x and x.y and x.y.z -> optional chaining or null object)
  </violations>

<exceptions>
Single boolean for simple on/off state. Builder pattern flags.
</exceptions>

<threshold>
Flag when flags interact in ways that require mental state tracking. Independent flags are fine.
</threshold>

## 4. Dependency Injection

<principle>
Business logic should be testable without network, disk, or database. Hard-coded dependencies make code untestable and tightly coupled.
</principle>

Detect: Can I test this function in isolation without mocking infrastructure? Are dependencies injected or hard-coded?

<grep-hints>
Pattern indicators (starting points, not definitive):
`Time.now`, `Date.new` (Ruby), `new Date()`, `process.env` (TypeScript), `ENV[` (Ruby), `Net::HTTP`, `Faraday`, `HTTParty` (Ruby), `fetch(`, `axios.` (TypeScript)
</grep-hints>

<violations>
Illustrative patterns (not exhaustive -- similar violations exist):

[high] Untestable coupling

- Hard-coded dependencies (e.g., new Date() inline -> inject clock)
- Global state access (avoid or inject)
- Any business logic that requires infrastructure to test

[medium] Mixed concerns

- Side effects mixed with computation (separate pure logic from effects)
- Concrete class dependencies (depend on interface, not implementation)

[low] Configuration coupling

- Environment coupling (reads env vars directly -> inject config)
- Time-dependent logic (inject clock for testability)
  </violations>

<exceptions>
Entry points that wire dependencies. Test utilities. Scripts meant to run directly.
</exceptions>

<threshold>
Flag when untestable code is in business logic. Infrastructure code at boundaries is expected to have dependencies.
</threshold>

## 5. Definition Locality

<principle>
A component's definition should be complete at a single site. When understanding what a component IS -- its identity, requirements, constraints, and behavior -- demands reading multiple locations, the definition is scattered.
</principle>

Detect: To understand what this component IS, how many locations must I read? If I change what this component requires, how many files must I edit?

<grep-hints>
Structural indicators (starting points, not definitive):
Same requirement checked in 2+ locations, component identity split across files, extraction-with-default patterns (args.get, kwargs.get, getattr with default)
</grep-hints>

<violations>
Illustrative patterns (not exhaustive -- similar violations exist):

[high] Scattered specification

- Same requirement declared in 2+ locations (e.g., parser marks required AND handler checks if missing)
- Component identity split across files without clear ownership
- Definition requiring "mental reassembly" from 3+ sources

[medium] Split declaration/enforcement

- Interface declared at one site, validated at another without shared reference
- Defaults defined separately from schema (e.g., type in schema, default in code)
- Same constraint checked in multiple places
  </violations>

<exceptions>
Dependency injection (injected collaborator's definition lives with collaborator, not here -- that's runtime wiring, not scatter). Composition (A uses B; B's definition is B's concern). Inheritance (intentional decomposition). Plugin architectures (clear ownership boundaries). Registry + reference patterns (define once, reference many times -- this is the fix, not a smell).
</exceptions>

<threshold>
Flag when a component's definition is split across 2+ locations without clear ownership. Key test: who owns this fact? If ownership is unclear or duplicated, it's scatter. Common in LLM-generated code.
</threshold>

## 6. Error Handling

<principle>
Errors should preserve context and reach appropriate handlers. Swallowed or generic catches lose information; errors at wrong levels confuse callers.
</principle>

Detect: What happens if this operation fails? Is error information preserved and routed appropriately?

<grep-hints>
Pattern indicators (starting points, not definitive):
`rescue`, `rescue => e` (Ruby), `catch (`, `catch(` (TypeScript), `throw new Error(`, `raise ` (Ruby)
</grep-hints>

<violations>
Illustrative patterns (not exhaustive -- similar violations exist):

[high] Information loss

- Swallowed exceptions (empty rescue/catch blocks)
- Generic catches (e.g., `rescue StandardError` / `catch (e)` with no handler -> catch specific errors)
- Any error handling that loses diagnostic information

[medium] Wrong abstraction

- Errors at wrong abstraction level (low-level errors leaking to callers)

[low] Missing context

- `raise "failed"` -> `raise OrderError, "order #{id}: #{reason}"` (Ruby) / `throw new Error(\`order ${id}: ${reason}\`)` (TypeScript)
  </violations>

<exceptions>
Generic catch at top-level with logging. Intentionally swallowed expected errors with comment.
</exceptions>

<threshold>
Flag when error handling obscures or loses information. Documented catch-all with logging is acceptable.
</threshold>
